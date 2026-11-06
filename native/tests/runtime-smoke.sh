#!/bin/sh
# Run only in the disposable runtime image; Python must actually be absent.
set -eu
if command -v python3 || command -v python; then
    echo 'This smoke check requires an image without Python' >&2
    exit 1
fi
task_config=$(mktemp -d)
trap 'rm -rf "$task_config"' EXIT
export XDG_CONFIG_HOME="$task_config"
task_binary=${1:-/usr/local/bin/open-power-menu-native}
"$task_binary" --version
"$task_binary" --check
dbus-run-session -- sh -eu -c '
    "$1" --service &
    backend=$!
    trap '\''kill "$backend" 2>/dev/null || true; wait "$backend" 2>/dev/null || true'\'' EXIT
    attempts=0
    until "$1" --call Ping; do
        kill -0 "$backend"
        attempts=$((attempts + 1))
        test "$attempts" -lt 50
        sleep 0.1
    done
    "$1" --call GetMenu
    "$1" --call GetIntegration
' sh "$task_binary"
