#!/usr/bin/env python3
"""Offline tests. No printer, network, root access, or Python packages required."""
from __future__ import annotations

import os
import hashlib
from pathlib import Path
import re
import runpy
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SANITIZE = "--sanitize" in sys.argv
if SANITIZE:
    sys.argv.remove("--sanitize")


def command(args, **kwargs):
    return subprocess.run(args, capture_output=True, timeout=30, **kwargs)


def decode_job(data):
    """Parse output by declared bitmap lengths, never by scanning binary pixels."""
    if not data.startswith(bytes(512) + b"\r\n"):
        raise AssertionError("missing vendor initialization preamble")
    pos = 514
    pages = []
    while pos < len(data):
        start = pos
        match = re.search(rb"BITMAP 0,0,(\d+),(\d+),1,", data[pos:])
        if not match:
            raise AssertionError("missing mode-1 bitmap")
        pos += match.end()
        width, height = map(int, match.groups())
        payload = data[pos:pos + width * height]
        if len(payload) != width * height:
            raise AssertionError("short bitmap")
        pos += len(payload)
        tail = re.match(rb"\r\nPRINT 1,(\d+)\r\n", data[pos:])
        if not tail:
            raise AssertionError("missing page print command")
        pos += tail.end()
        pages.append({"width_bytes": width, "height": height,
                      "pixels": payload, "copies": int(tail[1]),
                      "commands": data[start:start + match.start()]})
    return pages


def pdf_fixture(pages=2):
    """Create a tiny synthetic PDF using only the standard library."""
    objects = [b"", b""]
    kids = []
    for page in range(pages):
        page_id = len(objects) + 1
        content_id = page_id + 1
        font_id = 3 + pages * 2
        kids.append(f"{page_id} 0 R")
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 283.4646 425.1969] "
                        f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
                        f"/Contents {content_id} 0 R >>").encode())
        stream = f"BT /F1 18 Tf 30 370 Td (SYNTHETIC TEST PAGE {page + 1}) Tj ET\n".encode()
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"endstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {pages} >>".encode()
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend((f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                 f"startxref\n{xref}\n%%EOF\n").encode())
    return bytes(data)


class NativeDriverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="sp420-tests-")
        cls.work = Path(cls.workspace.name)
        cls.env = os.environ.copy()
        cls.env["PPD"] = str(ROOT / "ppd/idprt-sp420-native.ppd")
        cls.env["TMPDIR"] = str(cls.work)
        cls.env["ASAN_OPTIONS"] = "detect_leaks=0:abort_on_error=1"
        cls.env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
        cls.binary = cls.work / "rastertosp420"
        cls.fixture = cls.work / "fixture-writer"
        cls.units = cls.work / "test-render"
        flags = ["-Wall", "-Wextra", "-Werror", "-Wno-deprecated-declarations"]
        flags += (["-O1", "-g", "-fno-omit-frame-pointer", "-fsanitize=address,undefined"]
                  if SANITIZE else ["-O2"])
        for source, target in [(ROOT / "src/rastertosp420.c", cls.binary),
                               (ROOT / "tests/fixture_writer.c", cls.fixture),
                               (ROOT / "tests/test_render.c", cls.units)]:
            result = command(["xcrun", "clang", *flags, str(source), "-lcups", "-o", str(target)])
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors="replace"))

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def fixture_data(self, mode="W8"):
        path = self.work / "fixture.ras"
        result = command([str(self.fixture), mode, str(path)], env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        return path.read_bytes()

    def run_filter(self, data, options="", copies="1", extra_env=None):
        env = self.env.copy()
        if extra_env:
            env.update(extra_env)
        result = command([str(self.binary), "1", "synthetic-user", "synthetic-title", copies, options],
                         input=data, env=env)
        self.assertNotIn(b"AddressSanitizer", result.stderr)
        self.assertNotIn(b"runtime error:", result.stderr)
        return result

    def valid(self, mode="W8", **kwargs):
        result = self.run_filter(self.fixture_data(mode), **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        return decode_job(result.stdout)

    def rejected(self, data, **kwargs):
        result = self.run_filter(data, **kwargs)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"", "failed jobs must not emit printer commands")

    def test_private_renderer_units(self):
        result = command([str(self.units)], env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn(b"unit assertions passed", result.stdout)

    def test_exact_golden_bitmap_and_padding(self):
        pages = self.valid()
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["pixels"], b"\xaa\xaf\x55\x57")
        self.assertEqual((pages[0]["width_bytes"], pages[0]["height"]), (2, 2))

    def test_supported_color_spaces_are_equivalent(self):
        golden = self.valid()[0]["pixels"]
        for mode in ["K8", "W1bit", "K1bit", "rgb"]:
            with self.subTest(mode=mode):
                self.assertEqual(self.valid(mode)[0]["pixels"], golden)

    def test_vendor_default_commands(self):
        page = self.valid()[0]
        self.assertEqual(page["commands"], b"SIZE 101.6 mm, 152.4 mm\r\n"
                         b"SET TEAR ON\r\nSET CUTTER OFF\r\nSET PEEL OFF\r\nCLS\r\n")
        self.assertEqual(page["copies"], 1)

    def test_metadata_is_not_in_wire_output(self):
        result = self.run_filter(self.fixture_data())
        self.assertNotIn(b"synthetic-user", result.stdout)
        self.assertNotIn(b"synthetic-title", result.stdout)

    def test_header_copies_are_not_multiplied(self):
        self.assertEqual(self.valid("copies", copies="3")[0]["copies"], 3)

    def test_zero_header_copies_uses_argument(self):
        self.assertEqual(self.valid("copies-zero", copies="2")[0]["copies"], 2)

    def test_multiple_pages_preserve_order(self):
        pages = self.valid("multipage")
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0]["pixels"], b"\xaa\xaf\x55\x57")
        self.assertEqual(pages[1]["pixels"], b"\x55\x57\xaa\xaf")

    def test_software_rotation(self):
        self.assertEqual(self.valid(options="Rotate=180")[0]["pixels"], b"\x55\x57\xaa\xaf")

    def test_explicit_supported_controls(self):
        page = self.valid(options="Darkness=9 PrintSpeed=3 MediaTracking=Gap GapHeight=3")[0]
        self.assertIn(b"DENSITY 9\r\n", page["commands"])
        self.assertIn(b"SPEED 3\r\n", page["commands"])
        self.assertIn(b"GAP 3 mm, 0 mm\r\n", page["commands"])

    def test_halftone_modes_keep_binary_extremes(self):
        golden = self.valid()[0]["pixels"]
        for mode in ["Ordered", "Diffusion"]:
            with self.subTest(mode=mode):
                self.assertEqual(self.valid(options="Halftone=" + mode)[0]["pixels"], golden)

    def test_reject_bad_raster_formats_and_bounds(self):
        for mode in ["bad-format", "wide", "tall", "bad-resolution", "bad-order",
                     "large-media", "copies-excess"]:
            with self.subTest(mode=mode):
                self.rejected(self.fixture_data(mode))

    def test_reject_truncated_pixel_stream(self):
        self.rejected(self.fixture_data("truncated-pixels"))

    def test_reject_partial_second_header(self):
        self.rejected(self.fixture_data() + b"incomplete second raster header")

    def test_reject_empty_and_invalid_stream(self):
        for data in [b"", b"not a raster stream", b"RaS2"]:
            with self.subTest(length=len(data)):
                self.rejected(data)

    def test_reject_truncations_without_partial_output(self):
        data = self.fixture_data()
        for end in [1, 3, 8, 100, len(data) - 13, len(data) - 1]:
            with self.subTest(end=end):
                self.rejected(data[:end])

    def test_reject_invalid_copy_argument(self):
        for copies in ["0", "-1", "1000", "abc", "1\nPRINT 1,9", "9" * 80]:
            with self.subTest(copies=copies):
                self.rejected(self.fixture_data(), copies=copies)

    def test_missing_ppd_uses_safe_defaults(self):
        pages = self.valid(extra_env={"PPD": str(self.work / "absent.ppd")})
        self.assertEqual(pages[0]["pixels"], b"\xaa\xaf\x55\x57")

    @unittest.skipUnless(Path("/usr/sbin/cupsfilter").exists(), "native macOS cupsfilter unavailable")
    def test_coregraphics_copy_collation_integration(self):
        pdf = self.work / "synthetic.pdf"
        pdf.write_bytes(pdf_fixture())
        for collate, counts in [("True", [1, 1, 1, 1]), ("False", [2, 2])]:
            with self.subTest(collate=collate):
                raster = command(["/usr/sbin/cupsfilter", "-p", self.env["PPD"],
                                  "-i", "application/pdf", "-m", "application/vnd.cups-raster",
                                  "-n", "2", "-o", "PageSize=w283h425", "-o", "Collate=" + collate,
                                  str(pdf)], env=self.env)
                self.assertEqual(raster.returncode, 0, raster.stderr.decode(errors="replace"))
                result = self.run_filter(raster.stdout, copies="2")
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                pages = decode_job(result.stdout)
                self.assertEqual([p["copies"] for p in pages], counts)
                for page in pages:
                    self.assertIn(b"SIZE 100.0 mm, 150.0 mm\r\n", page["commands"])
                    self.assertGreater(sum(byte != 255 for byte in page["pixels"]), 100)


class PackagingContractTests(unittest.TestCase):
    """Build and inspect a package without ever executing its install scripts."""

    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="sp420-package-tests-")
        cls.addClassCleanup(cls.workspace.cleanup)
        cls.work = Path(cls.workspace.name)
        # A generated marker catches build-directory leaks without encoding a
        # maintainer's account name or other personal information in this suite.
        cls.source = cls.work / ("PRIVATE_SOURCE_MARKER_" + os.urandom(8).hex())
        cls.source.mkdir()
        for name in ["src", "ppd", "scripts"]:
            shutil.copytree(ROOT / name, cls.source / name)
        for name in ["LICENSE", "VERSION"]:
            shutil.copy2(ROOT / name, cls.source / name)
        cls.version = (cls.source / "VERSION").read_text().strip()
        result = command(["/bin/sh", "scripts/build-package.sh"], cwd=cls.source)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        cls.package = cls.source / "dist" / f"idprt-sp420-macos-native-driver-{cls.version}.pkg"
        cls.expanded = cls.work / "expanded"
        result = command(["/usr/sbin/pkgutil", "--expand-full", str(cls.package),
                          str(cls.expanded)])
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        cls.raw = cls.work / "raw"
        cls.raw.mkdir()
        for name in ["Payload", "Scripts"]:
            result = command(["/usr/bin/tar", "-xOf", str(cls.package), name])
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors="replace"))
            (cls.raw / name).write_bytes(result.stdout)
        cls.payload = cls.expanded / "Payload"
        cls.expected_files = {
            "Library/Printers/SP420Native/rastertosp420": 0o755,
            "Library/Printers/SP420Native/idprt-sp420-native.ppd": 0o644,
            "Library/Printers/SP420Native/LICENSE": 0o644,
            "Library/Printers/SP420Native/uninstall.sh": 0o755,
        }
        cls.expected_dirs = {".", "Library", "Library/Printers", "Library/Printers/SP420Native"}

    def test_payload_is_an_explicit_allowlist_without_links(self):
        files, dirs = set(), {"."}
        for path in self.payload.rglob("*"):
            self.assertFalse(path.is_symlink(), str(path.relative_to(self.payload)))
            relative = path.relative_to(self.payload).as_posix()
            mode = path.stat().st_mode
            if stat.S_ISREG(mode):
                files.add(relative)
                self.assertEqual(stat.S_IMODE(mode), self.expected_files.get(relative))
            elif stat.S_ISDIR(mode):
                dirs.add(relative)
                self.assertEqual(stat.S_IMODE(mode), 0o755)
            else:
                self.fail("package contains a special filesystem object")
        self.assertEqual(files, set(self.expected_files))
        self.assertEqual(dirs, self.expected_dirs)
        # Full expansion merges AppleDouble resource entries into xattrs. Check
        # the actual archive names too, so hidden metadata cannot evade this
        # allowlist merely because pkgutil presents a cleaned filesystem view.
        for archive, expected in [("Payload", self.expected_dirs | set(self.expected_files)),
                                  ("Scripts", {"preinstall", "postinstall"})]:
            result = command(["/usr/bin/tar", "-tf", str(self.raw / archive)])
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            names = {name.removeprefix("./").rstrip("/") or "."
                     for name in result.stdout.decode().splitlines()}
            if archive == "Scripts":
                names.discard(".")
            self.assertEqual(names, expected)

    def test_bom_records_only_root_owned_expected_paths(self):
        result = command(["/usr/bin/lsbom", "-p", "fmug", str(self.expanded / "Bom")])
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        entries = {}
        for line in result.stdout.decode().splitlines():
            name, mode, uid, gid = line.split("\t")
            name = name.removeprefix("./")
            self.assertEqual(uid, "0", "package ownership must be root, not the build account")
            self.assertEqual(gid, "0", "package group ownership must be wheel")
            entries[name] = int(mode, 8)
        self.assertEqual(set(entries), self.expected_dirs | set(self.expected_files))
        for name, mode in entries.items():
            expected = self.expected_files.get(name, 0o755)
            self.assertEqual(stat.S_IMODE(mode), expected)
            self.assertFalse(mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX))

    def test_package_metadata_and_scripts_are_expected(self):
        info = ET.parse(self.expanded / "PackageInfo").getroot()
        self.assertEqual(info.attrib["identifier"], "org.kollinnapier.idprt-sp420-macos-native-driver")
        self.assertEqual(info.attrib["version"], self.version)
        # pkgbuild omits the attribute for its default root destination.
        self.assertEqual(info.attrib.get("install-location", "/"), "/")
        self.assertEqual(info.attrib["auth"], "root")
        self.assertEqual(info.attrib["relocatable"], "false")
        self.assertEqual(int(info.find("payload").attrib["numberOfFiles"]),
                         len(self.expected_dirs) + len(self.expected_files))
        scripts = self.expanded / "Scripts"
        self.assertEqual({p.name for p in scripts.iterdir()}, {"preinstall", "postinstall"})
        for name in ["preinstall", "postinstall"]:
            path = scripts / name
            self.assertFalse(path.is_symlink())
            self.assertEqual(path.read_bytes(), (ROOT / "scripts" / name).read_bytes())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755)
        self.assertEqual((self.payload / "Library/Printers/SP420Native/LICENSE").read_bytes(),
                         (ROOT / "LICENSE").read_bytes())

    def test_release_bytes_have_no_absolute_source_or_home_paths(self):
        forbidden = [b"/Users/", bytes(str(self.source), "utf-8"), self.source.name.encode()]
        toc = self.work / "package-toc.xml"
        result = command(["/usr/bin/xar", "--dump-toc=" + str(toc), "-f", str(self.package)])
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        metadata = ET.parse(toc).getroot()
        for tag in ["user", "group", "uid", "gid", "ea"]:
            self.assertEqual(metadata.findall(".//" + tag), [], "unexpected build-account metadata")
        # Inspect expanded contents as well as the compressed archive: searching
        # the archive alone cannot detect private strings inside its payload.
        for path in [self.package, toc, *self.expanded.rglob("*")]:
            if path.is_file() and not path.is_symlink():
                data = path.read_bytes()
                for marker in forbidden:
                    self.assertNotIn(marker, data, path.relative_to(self.work).as_posix())

    def test_release_binary_is_native_and_adhoc_signature_valid(self):
        binary = self.payload / "Library/Printers/SP420Native/rastertosp420"
        result = command(["/usr/bin/lipo", "-archs", str(binary)])
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(result.stdout.strip(), b"arm64")
        result = command(["/usr/bin/codesign", "--verify", "--strict", str(binary)])
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_published_checksum_matches_package(self):
        checksum = self.package.parent / "SHA256SUMS.txt"
        self.assertEqual(checksum.read_text(),
                         hashlib.sha256(self.package.read_bytes()).hexdigest() + "  " +
                         self.package.name + "\n")

    def test_shell_script_syntax(self):
        for path in sorted((ROOT / "scripts").iterdir()):
            if path.is_file() and path.read_bytes().startswith(b"#!/bin/sh"):
                with self.subTest(script=path.name):
                    result = command(["/bin/sh", "-n", str(path)])
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_postinstall_uri_validation_without_system_side_effects(self):
        source = (ROOT / "scripts/postinstall").read_text()
        # Extract only the self-contained predicate. Never source or execute the
        # installer, which contains privileged CUPS configuration commands.
        match = re.search(r"^valid_uri\(\) \{\n.*?^\}\n", source, re.M | re.S)
        self.assertIsNotNone(match, "keep the URI predicate independently testable")
        predicate = match.group(0) + '\nvalid_uri "$1"\n'
        valid = ["usb://iDPRT/SP420", "usb://iDPRT/SP420?serial=SYNTHETIC-TEST"]
        invalid = ["", "usb://iDPRT/SP420Other", "usb://Other/SP420", "ipp://iDPRT/SP420",
                   "usb://iDPRT/SP420?x=bad value", "usb://iDPRT/SP420?x=bad\nvalue",
                   "usb://iDPRT/SP420?x=bad\tvalue", "usb://iDPRT/SP420?x=bad\rvalue",
                   "usb://iDPRT/SP420?x=" + "x" * 2048]
        for uri in valid + invalid:
            with self.subTest(uri=uri[:60]):
                result = command(["/bin/sh", "-c", predicate, "uri-test", uri],
                                 env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
                self.assertEqual(result.returncode == 0, uri in valid)

    def test_package_cleaner_preserves_all_file_bytes_on_repeat(self):
        package = self.work / "repeat-clean.pkg"
        shutil.copyfile(self.package, package)
        result = command([sys.executable, str(ROOT / "scripts/clean-package.py"), str(package)])
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        output = self.work / "repeat-clean"
        result = command(["/usr/sbin/pkgutil", "--expand-full", str(package), str(output)])
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        for relative in [*("Payload/" + name for name in self.expected_files),
                         "Scripts/preinstall", "Scripts/postinstall"]:
            self.assertEqual((output / relative).read_bytes(),
                             (self.expanded / relative).read_bytes(), relative)

    def test_package_cleaner_refuses_signed_or_unknown_status_without_mutation(self):
        helper = runpy.run_path(str(ROOT / "scripts/clean-package.py"))
        package = self.work / "signature-refusal.pkg"
        original = self.package.read_bytes()
        package.write_bytes(original)
        for code, output in [(0, b"Status: signed by a certificate\n"),
                             (1, b"Status: invalid signature\n"), (1, b"unrecognized input\n"),
                             (0, b"Status: no signature\n")]:
            with self.subTest(status=output):
                response = subprocess.CompletedProcess([], code, output, b"")
                with mock.patch.dict(helper["clean_package"].__globals__,
                                     {"run": mock.Mock(return_value=response)}) as globals_:
                    with self.assertRaises(ValueError):
                        helper["clean_package"](package)
                    self.assertEqual(globals_["run"].call_count, 1)
                self.assertEqual(package.read_bytes(), original)

    def test_package_cleaner_path_policy(self):
        helper = runpy.run_path(str(ROOT / "scripts/clean-package.py"))
        predicate = helper["is_appledouble"]
        self.assertTrue(predicate("./Library/._metadata"))
        self.assertFalse(predicate("./Library/ordinary-file"))
        for path in ["/Library/absolute", "../outside", "Library/../../outside"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                predicate(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
