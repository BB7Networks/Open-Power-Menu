#!/bin/sh
# Headless Weston is deliberately private; never connect to the desktop session.
set -eu
runtime=$(mktemp -d /tmp/opm-wayland.XXXXXX)
chmod 700 "$runtime"
export XDG_RUNTIME_DIR="$runtime" WAYLAND_DISPLAY=opm-test-wayland
export XDG_CONFIG_HOME="$runtime/config" XDG_DATA_HOME="$runtime/data" XDG_CACHE_HOME="$runtime/cache"
if [ "${OPM_WAYLAND_COMPOSITOR:-weston}" = kwin ]; then
    printf '%s\n' 'standalone-wayland fixture' > "$runtime/.opm-private-seat"
    export OPM_TEST_PRIVATE_WAYLAND_SOCKET="$runtime/$WAYLAND_DISPLAY"
    export OPM_TEST_WAYLAND_INPUT="$(cd "$(dirname "$0")" && pwd)/private_wayland_input.py"
    mkdir "$runtime/bin"
    # Avoid optional file capabilities unsupported by unprivileged containers.
    # Keep the basename: KWin's private QPA plugin verifies it.
    cp "$(command -v kwin_wayland)" "$runtime/bin/kwin_wayland"
    # This private compositor alone permits the fixture's input client. No
    # workstation compositor, keyboard setting or runtime configuration changes.
    KWIN_WAYLAND_NO_PERMISSION_CHECKS=1 KWIN_COMPOSE="${OPM_TEST_KWIN_COMPOSE:-Q}" QT_QUICK_BACKEND=software "$runtime/bin/kwin_wayland" \
        --virtual --width 1600 --height 1000 --scale "${OPM_SCALE:-1}" \
        --output-count "${OPM_OUTPUT_COUNT:-1}" --no-lockscreen --no-global-shortcuts \
        --socket "$WAYLAND_DISPLAY" > "$runtime/weston.log" 2>&1 &
else
    weston --backend=headless-backend.so --socket="$WAYLAND_DISPLAY" --idle-time=0 \
        --width=1600 --height=1000 --scale=1 > "$runtime/weston.log" 2>&1 &
fi
compositor=$!
trap 'kill "$compositor" 2>/dev/null || true; wait "$compositor" 2>/dev/null || true; rm -rf "$runtime"' EXIT
for attempt in $(seq 1 100); do
    test ! -S "$runtime/$WAYLAND_DISPLAY" || break
    kill -0 "$compositor" || { cat "$runtime/weston.log"; exit 1; }
    sleep .05
done
test -S "$runtime/$WAYLAND_DISPLAY" || { cat "$runtime/weston.log"; exit 1; }
if [ "${OPM_WAYLAND_COMPOSITOR:-weston}" = kwin ]; then
    python3 "$(dirname "$0")/private_compositor.py" --pid "$compositor" || { cat "$runtime/weston.log"; exit 1; }
fi
QT_QPA_PLATFORM=wayland "$@"
if [ "${OPM_WAYLAND_COMPOSITOR:-weston}" = kwin ]; then
    python3 "$(dirname "$0")/private_compositor.py" --pid "$compositor" || { cat "$runtime/weston.log"; exit 1; }
fi
