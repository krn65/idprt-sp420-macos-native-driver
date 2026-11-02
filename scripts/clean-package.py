#!/usr/bin/env python3
"""Remove AppleDouble metadata from this unsigned component package before signing.

macOS can attach protected provenance xattrs even after `xattr -cr`. pkgbuild
turns those into AppleDouble entries. Use Apple's documented archive/BOM tools
to remove those entries; never install a package or execute its scripts.
"""
# SPDX-License-Identifier: MIT
from pathlib import Path, PurePosixPath
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def run(args, *, check=True, cwd=None):
    env = os.environ.copy()
    env.update(LC_ALL="C", COPYFILE_DISABLE="1")
    result = subprocess.run(args, capture_output=True, env=env, timeout=60, cwd=cwd)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result


def require_unsigned(package):
    result = run(["/usr/sbin/pkgutil", "--check-signature", str(package)], check=False)
    # Fail closed for signed, damaged, unrecognized, or unverifiable inputs.
    # Unsigned component packages are explicitly reported this way by pkgutil.
    statuses = [line.strip() for line in result.stdout.decode(errors="replace").splitlines()
                if line.strip().startswith("Status:")]
    if result.returncode != 1 or statuses != ["Status: no signature"]:
        raise ValueError("Only an explicitly unsigned package may be cleaned; clean before signing.")


def is_appledouble(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe path in package archive or BOM.")
    return any(part.startswith("._") for part in path.parts)


def clean_archive(archive, output):
    listing = run(["/usr/bin/tar", "-tf", str(archive)]).stdout.decode().splitlines()
    for name in listing:
        is_appledouble(name)  # Validate paths before passing an archive to tar.
    run(["/usr/bin/tar", "--disable-copyfile", "--no-xattrs", "--format", "cpio",
         "--exclude", "._*", "-czf", str(output), "@" + str(archive)])
    cleaned = run(["/usr/bin/tar", "-tf", str(output)]).stdout.decode().splitlines()
    if any(is_appledouble(name) for name in cleaned):
        raise ValueError("AppleDouble metadata remains in the cleaned archive.")
    output.replace(archive)


def clean_package(package):
    package = Path(package).absolute()
    if package.is_symlink() or not package.is_file():
        raise ValueError("Expected a regular unsigned component package.")
    require_unsigned(package)  # Must precede extraction, mutation, and replacement.
    with tempfile.TemporaryDirectory(prefix="sp420-clean-", dir=package.parent) as temp:
        work = Path(temp)
        expanded = work / "expanded"
        expanded.mkdir()
        members = {"Bom", "PackageInfo", "Payload", "Scripts"}
        names = run(["/usr/bin/tar", "-tf", str(package)]).stdout.decode().splitlines()
        if set(names) != members or len(names) != len(members):
            raise ValueError("Expected this driver's four-member component package.")
        # pkgutil expands Scripts automatically; extract bytes with libarchive
        # instead so its compressed archive can be cleaned without re-extraction.
        for name in members:
            data = run(["/usr/bin/tar", "-xOf", str(package), name]).stdout
            (expanded / name).write_bytes(data)
        info_path = expanded / "PackageInfo"
        info = ET.parse(info_path)
        payload_info = info.getroot().find("payload")
        if info.getroot().tag != "pkg-info" or payload_info is None:
            raise ValueError("Expected a single component package with a payload.")
        for name in ("Payload", "Scripts"):
            archive = expanded / name
            if archive.is_file():
                clean_archive(archive, work / (name + ".clean"))
        lines = run(["/usr/bin/lsbom", str(expanded / "Bom")]).stdout.decode().splitlines()
        retained = []
        for line in lines:
            if not is_appledouble(line.split("\t", 1)[0]):
                retained.append(line)
        listing = work / "bom-list.txt"
        listing.write_text("\n".join(retained) + "\n")
        run(["/usr/bin/mkbom", "-i", str(listing), str(expanded / "Bom")])
        payload_info.set("numberOfFiles", str(len(retained)))
        info.write(info_path, encoding="utf-8", xml_declaration=True)
        rebuilt = work / "clean.pkg"
        # pkgutil --flatten archives Scripts again and reintroduces protected
        # xattrs. Apple's xar distribution mode wraps the four clean byte streams
        # without filesystem ownership, timestamps, or extended attributes.
        run(["/usr/bin/xar", "--distribution", "--compression", "none", "-cf", str(rebuilt),
             "Bom", "PackageInfo", "Payload", "Scripts"], cwd=expanded)
        rebuilt.chmod(package.stat().st_mode & 0o777)
        rebuilt.replace(package)  # Same filesystem: original survives any earlier failure.


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: scripts/clean-package.py UNSIGNED_COMPONENT.pkg")
    try:
        clean_package(sys.argv[1])
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        sys.exit(str(error))
