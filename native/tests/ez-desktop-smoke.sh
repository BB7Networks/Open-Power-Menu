#!/bin/sh
# Called only inside a private dbus-run-session and Xvfb or virtual KWin seat.
set -eu
ez=$1
platform=$2
output=$3
case "$platform" in xcb|wayland) :;; *) exit 2;; esac
if [ "${4:-}" != inside ]; then
    profile=$(mktemp -d)
    trap 'rm -rf "$profile"' EXIT
    export XDG_DATA_HOME="$profile/data" XDG_CONFIG_HOME="$profile/config"
    export XDG_BIN_HOME="$profile/bin" XDG_CACHE_HOME="$profile/cache"
    if [ "$platform" = xcb ]; then
        export XDG_RUNTIME_DIR="$profile/runtime"
        mkdir -m 700 "$XDG_RUNTIME_DIR"
    fi
    dbus-run-session -- sh "$0" "$ez" "$platform" "$output" inside
    exit $?
fi
export QT_QPA_PLATFORM="$platform" QT_QUICK_BACKEND=software
mkdir -p "$output"
bash "$ez/install.sh" --yes
"$XDG_BIN_HOME/open-power-menu" --check
"$XDG_BIN_HOME/open-power-menu" --edit --smoke-test --screenshot "$output/installed-editor-$platform.png"
# These are read-only activation/version checks, never menu selection/dispatch.
"$XDG_BIN_HOME/open-power-menu" --version > "$output/installed-version-$platform"
"$XDG_BIN_HOME/open-power-menu" --widget-menu-json > "$output/installed-menu-$platform.json"
bash "$ez/install.sh" --uninstall --yes
test ! -e "$XDG_DATA_HOME/open-power-menu"
printf '%s\n' passed > "$output/ez-desktop-$platform"
