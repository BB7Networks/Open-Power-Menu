#!/bin/sh
# Disposable image only: exercise native GUI startup with no Python installed.
set -eu
if command -v python3 || command -v python || command -v g++; then
    echo 'This runtime smoke image must not contain Python or a compiler' >&2
    exit 1
fi
task_profile=$(mktemp -d)
trap 'rm -rf "$task_profile"' EXIT
export XDG_CONFIG_HOME="$task_profile/config" XDG_DATA_HOME="$task_profile/data"
export XDG_CACHE_HOME="$task_profile/cache" XDG_RUNTIME_DIR="$task_profile/runtime"
export XDG_CURRENT_DESKTOP=KDE XDG_MENU_PREFIX=opm-test-
export QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software
mkdir -p "$XDG_CONFIG_HOME/menus" "$XDG_DATA_HOME/applications" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR" "$XDG_CONFIG_HOME"
cat > "$XDG_CONFIG_HOME/menus/opm-test-applications.menu" <<'MENU'
<!DOCTYPE Menu PUBLIC "-//freedesktop//DTD Menu 1.0//EN" "http://www.freedesktop.org/standards/menu-spec/1.0/menu.dtd">
<Menu><Name>Applications</Name><DefaultAppDirs/><Include><All/></Include></Menu>
MENU
cat > "$XDG_DATA_HOME/applications/opm-native-smoke.desktop" <<'APP'
[Desktop Entry]
Type=Application
Name=Native smoke fixture
Exec=/bin/true
Icon=system-run
Categories=Utility;
APP
open-power-menu-native --version
open-power-menu-editor --version
dbus-run-session -- open-power-menu-editor --smoke-test
test ! -e "$XDG_CONFIG_HOME/open-power-menu/menu.json"
