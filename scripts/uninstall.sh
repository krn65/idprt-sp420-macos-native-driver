#!/bin/sh
# Delete only this driver's fixed paths; never follow a redirected directory.
set -eu
export LC_ALL=C
if [ "$(/usr/bin/id -u)" -ne 0 ]; then
  echo "Run: sudo /bin/sh /Library/Printers/SP420Native/uninstall.sh" >&2
  exit 1
fi
for path in /Library /Library/Printers /Library/Printers/SP420Native; do
  [ ! -L "$path" ] && [ -d "$path" ] || exit 1
  [ "$(/usr/bin/stat -f %u "$path")" -eq 0 ] || exit 1
  mode=$(/usr/bin/stat -f %Lp "$path")
  [ "$((0$mode & 0022))" -eq 0 ] || exit 1
done
jobs=$(/usr/bin/lpstat -o iDPRT_SP420_Native 2>/dev/null || true)
[ -z "$jobs" ] || { echo "Finish or cancel native SP420 jobs before uninstalling." >&2; exit 1; }
if /usr/bin/lpstat -p iDPRT_SP420_Native >/dev/null 2>&1; then
  /usr/sbin/lpadmin -x iDPRT_SP420_Native
fi
/bin/rm -f /Library/Printers/SP420Native/rastertosp420 \
  /Library/Printers/SP420Native/idprt-sp420-native.ppd \
  /Library/Printers/SP420Native/SP420-Native.ppd \
  /Library/Printers/SP420Native/LICENSE \
  /Library/Printers/SP420Native/uninstall.sh
/bin/rmdir /Library/Printers/SP420Native 2>/dev/null || true
/usr/sbin/pkgutil --forget org.kollinnapier.idprt-sp420-macos-native-driver >/dev/null 2>&1 || true
/usr/sbin/pkgutil --forget org.local.sp420.native >/dev/null 2>&1 || true
