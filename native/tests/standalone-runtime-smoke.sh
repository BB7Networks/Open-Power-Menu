#!/bin/sh
set -eu
! command -v python3
! command -v g++
! command -v cmake
profile=$(mktemp -d)
trap 'rm -rf "$profile"' EXIT
export XDG_CONFIG_HOME="$profile/config" XDG_DATA_HOME="$profile/data" XDG_CACHE_HOME="$profile/cache"
export XDG_RUNTIME_DIR="$profile/runtime"
mkdir -m 700 "$XDG_RUNTIME_DIR"
unset DISPLAY WAYLAND_DISPLAY
open-power-menu-standalone --version
open-power-menu-standalone --default-config > "$profile/defaults.json"
open-power-menu-standalone --list > "$profile/list.json"
open-power-menu-standalone --check > "$profile/check.json"
cmp "$profile/list.json" "$profile/check.json"
test ! -e "$XDG_CONFIG_HOME/open-power-menu/menu.json"
# The minimal image deliberately lacks normal desktop applications. Use a
# harmless available command so this checks a real visible menu, not an empty one.
printf '%s\n' '{"menu":[{"label":"Runtime fixture","command":["/bin/true"]}]}' > "$profile/menu.json"
# Diagnostic samples prove exposure; timeout deliberately closes the test process.
set +e
QT_QPA_PLATFORM=offscreen timeout 3 open-power-menu-standalone --config "$profile/menu.json" --diagnose-launch > "$profile/trace"
result=$?
set -e
test "$result" -eq 124
grep '"event":"show-requested"' "$profile/trace"
grep '"exposed":true' "$profile/trace"
test ! -e "$XDG_CONFIG_HOME/open-power-menu/menu.json"
# The dynamic loader names a missing dependency before C++ can run.
widgets=$(find /usr/lib -name 'libQt6Widgets.so.6' -print -quit)
mv "$widgets" "$widgets.absent"
trap '[ ! -e "$widgets.absent" ] || mv "$widgets.absent" "$widgets"; rm -rf "$profile"' EXIT
if open-power-menu-standalone --version 2> "$profile/missing-library"; then exit 1; fi
grep 'libQt6Widgets.so.6' "$profile/missing-library"
mv "$widgets.absent" "$widgets"
