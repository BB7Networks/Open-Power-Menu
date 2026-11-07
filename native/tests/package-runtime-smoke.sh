#!/bin/sh
set -eu
! command -v python3
! command -v python
! command -v g++
! command -v cmake
if [ "${1:-}" != inside ]; then
    profile=$(mktemp -d)
    trap 'rm -rf "$profile"' EXIT
    export XDG_DATA_HOME="$profile/data" XDG_CONFIG_HOME="$profile/config"
    export XDG_BIN_HOME="$profile/bin" XDG_CACHE_HOME="$profile/cache" XDG_RUNTIME_DIR="$profile/runtime"
    mkdir -m 700 "$XDG_RUNTIME_DIR"
    dbus-run-session -- sh "$0" inside
    exit $?
fi
export QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software
installer=/opt/opm-bundle/app/bin/open-power-menu-install
sh /opt/opm-bundle/install.sh
"$XDG_BIN_HOME/open-power-menu" --version
"$XDG_BIN_HOME/open-power-menu" --check
"$XDG_BIN_HOME/open-power-menu" --edit --smoke-test
"$XDG_BIN_HOME/open-power-menu" --widget-menu-json
test ! -e "$XDG_CONFIG_HOME/open-power-menu/menu.json"
"$installer" --install /opt/opm-bundle
"$XDG_BIN_HOME/open-power-menu" --uninstall
test ! -e "$XDG_DATA_HOME/open-power-menu"
test ! -e "$XDG_BIN_HOME/open-power-menu"
"$installer" --rollback
"$XDG_BIN_HOME/open-power-menu" --check
"$installer" --uninstall
