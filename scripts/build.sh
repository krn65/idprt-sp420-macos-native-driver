#!/bin/sh
# Build as the ordinary user. Administrator privileges belong only to Installer.
set -eu
export LC_ALL=C
if [ "$(/usr/bin/id -u)" -eq 0 ]; then
  echo "Build without sudo; only installation needs administrator authorization." >&2
  exit 1
fi
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
cd "$repo_root"
version=$(/bin/cat VERSION)
printf '%s\n' "$version" | /usr/bin/grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || exit 1
/bin/mkdir -p build
output=build/rastertosp420
if [ "${1:-}" = --sanitize ]; then
  output=build/rastertosp420-sanitize
  set -- -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer
elif [ "$#" -eq 0 ]; then
  set -- -O2 -g0
else
  echo "Usage: scripts/build.sh [--sanitize]" >&2
  exit 1
fi
/usr/bin/xcrun clang -std=c11 -Wall -Wextra -Wpedantic -Werror \
  -Wno-deprecated-declarations -arch arm64 -mmacosx-version-min=14.0 \
  -fstack-protector-strong -D_FORTIFY_SOURCE=2 \
  "-ffile-prefix-map=$repo_root=." "-fdebug-prefix-map=$repo_root=." \
  "-DDRIVER_VERSION=\"$version\"" "$@" \
  -o "$output" src/rastertosp420.c -lcups
/usr/bin/codesign --force --sign - --timestamp=none \
  --identifier org.kollinnapier.idprt-sp420-native-filter "$output"
/usr/bin/codesign --verify "$output"
/usr/bin/file "$output"
