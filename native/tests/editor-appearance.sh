#!/bin/sh
# Real QML/Breeze screenshots and layout assertions in a private X11 profile.
set -eu
binary=$1
output=$2
profile=$(mktemp -d)
trap 'rm -rf "$profile"' EXIT
for scheme in BreezeLight BreezeDark; do
    for scale in 1 1.5 2; do
        destination="$output/$scheme-$scale"
        config="$profile/$scheme-$scale"
        mkdir -p "$config" "$destination"
        dbus-run-session -- xvfb-run -a -s '-screen 0 3840x2400x24' env \
            OPM_TEST_COLOR_SCHEME="$scheme" XDG_CONFIG_HOME="$config" XDG_CACHE_HOME="$config/cache" \
            QT_QPA_PLATFORM=xcb QT_QPA_PLATFORMTHEME=kde QT_QUICK_CONTROLS_STYLE=org.kde.desktop \
            QT_QUICK_BACKEND=software QT_SCALE_FACTOR="$scale" \
            OPM_QUALIFICATION_SCREENSHOTS="$destination" \
            "$binary" powerConfirmationGeometry > "$destination/test.log" 2>&1 || { cat "$destination/test.log"; exit 1; }
    done
done
