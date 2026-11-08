#!/bin/sh
set -eu
# Manjaro's base image needs Python for pacman-mirrors. Keep that unrelated
# runtime; separately require PySide6 absence. Debian/Arch prove strict absence.
case "${OPM_TEST_RUNTIME_PYTHON:-absent}" in
    absent) absent_tools='python3 python g++ cmake';;
    distro)
        python -c 'import importlib.util; assert importlib.util.find_spec("PySide6") is None'
        absent_tools='g++ cmake';;
    *) echo 'Unknown runtime test profile' >&2; exit 1;;
esac
for tool in $absent_tools; do
    if command -v "$tool" >/dev/null; then
        echo "Unexpected runtime tool: $tool" >&2
        exit 1
    fi
done
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
bundle=${OPM_TEST_BUNDLE:-/opt/opm-bundle}
installer="$bundle/app/bin/open-power-menu-install"
# Packaged executables must have crash-injection hooks compiled out.
export OPM_INSTALL_CRASH_AFTER=0 OPM_INSTALL_FAIL_AFTER=0
if [ -n "${OPM_TEST_SETUP:-}" ]; then
    "$OPM_TEST_SETUP"
else
    sh "$bundle/install.sh"
fi
unset OPM_INSTALL_CRASH_AFTER OPM_INSTALL_FAIL_AFTER
"$XDG_BIN_HOME/open-power-menu" --version
"$XDG_BIN_HOME/open-power-menu" --check
"$XDG_BIN_HOME/open-power-menu" --edit --smoke-test
"$XDG_BIN_HOME/open-power-menu" --widget-menu-json
test ! -e "$XDG_CONFIG_HOME/open-power-menu/menu.json"
"$installer" --install "$bundle"
"$XDG_BIN_HOME/open-power-menu" --uninstall
test ! -e "$XDG_DATA_HOME/open-power-menu"
test ! -e "$XDG_BIN_HOME/open-power-menu"
"$installer" --rollback
"$XDG_BIN_HOME/open-power-menu" --check
"$installer" --uninstall
