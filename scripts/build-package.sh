#!/bin/sh
# Rebuild source and stage only an explicit public payload allowlist.
set -eu
export LC_ALL=C
export COPYFILE_DISABLE=1
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
cd "$repo_root"
./scripts/build.sh
version=$(/bin/cat VERSION)
/bin/mkdir -p dist
package_work=$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/sp420-package.XXXXXX")
trap '/bin/rm -rf "$package_work"' EXIT HUP INT TERM
payload="$package_work/root/Library/Printers/SP420Native"
/bin/mkdir -p "$payload" "$package_work/scripts"
/bin/cp -X build/rastertosp420 "$payload/rastertosp420"
/bin/cp -X ppd/idprt-sp420-native.ppd "$payload/idprt-sp420-native.ppd"
/bin/cp -X LICENSE "$payload/LICENSE"
/bin/cp -X scripts/uninstall.sh "$payload/uninstall.sh"
/bin/cp -X scripts/preinstall scripts/postinstall "$package_work/scripts/"
/bin/chmod 755 "$payload/rastertosp420" "$payload/uninstall.sh" "$package_work/scripts/"*
/bin/chmod 644 "$payload/idprt-sp420-native.ppd" "$payload/LICENSE"
# New files can acquire local provenance attributes even after cp -X.
# Clear all attributes on this private, task-created staging tree.
/usr/bin/xattr -cr "$package_work"
/usr/bin/pkgbuild --root "$package_work/root" --ownership recommended \
  --scripts "$package_work/scripts" \
  --identifier org.kollinnapier.idprt-sp420-macos-native-driver \
  --version "$version" "dist/idprt-sp420-macos-native-driver-$version.pkg"
python3 ./scripts/clean-package.py "dist/idprt-sp420-macos-native-driver-$version.pkg"
(cd dist && /usr/bin/shasum -a 256 "idprt-sp420-macos-native-driver-$version.pkg" > SHA256SUMS.txt)
