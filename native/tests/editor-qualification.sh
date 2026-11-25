#!/bin/sh
# Run inside the disposable compiled image, with networking disabled. Record
# versions/source before tests so a failure still leaves collectible evidence.
set -eu
umask 022
cd /src
evidence=/tmp/qualification
mkdir "$evidence"
cp /etc/os-release "$evidence/os-release"
dpkg-query -W > "$evidence/packages.txt"
date -u
dpkg-query -W plasma-workspace kwin-x11 kwin-wayland libqt6core6t64 libkf6coreaddons6 | sed 's/^/OPM_RUNTIME_VERSION /'
printf '%s\n' "$OPM_SOURCE_COMMIT" > "$evidence/SOURCE-COMMIT"
finish() {
    result=$?
    trap - EXIT
    for path in /tmp/native-tests.xml /tmp/applications.json /tmp/dropdown-screenshots /tmp/plasma-*; do
        if [ -e "$path" ]; then cp -r "$path" "$evidence/"; fi
    done
    printf '%s\n' "$result" > "$evidence/test-exit-status"
    exit "$result"
}
trap finish EXIT
QT_QUICK_CONTROLS_STYLE=Basic ctest --test-dir /tmp/build --output-on-failure --output-junit /tmp/native-tests.xml
QT_QUICK_CONTROLS_STYLE=org.kde.desktop ctest --test-dir /tmp/build -R native-editor-gui --output-on-failure
sh native/tests/editor-appearance.sh /tmp/build/native/native-editor-gui-tests /tmp/dropdown-screenshots
dbus-run-session -- xvfb-run -a env QT_QPA_PLATFORM=xcb /tmp/build/native/native-standalone-tests
dbus-run-session -- env OPM_WAYLAND_COMPOSITOR=kwin sh native/tests/standalone-wayland.sh /tmp/build/native/native-standalone-tests
XDG_CURRENT_DESKTOP=KDE QT_QPA_PLATFORM=offscreen python3 native/tests/application_resolution.py --probe /tmp/build/native/native-application-probe --live-audit /tmp/applications.json
python3 native/tests/plasma_greeter.py --backend /tmp/build/native/open-power-menu-native --output /tmp/plasma-greeter
python3 native/tests/plasma_greeter.py --platform wayland --backend /tmp/build/native/open-power-menu-native --output /tmp/plasma-greeter-wayland
python3 native/tests/plasma_startup.py --output /tmp/plasma-startup
python3 native/tests/plasma_popup.py --output /tmp/plasma-popup
python3 native/tests/plasma_popup.py --output /tmp/plasma-popup-untraced --diagnostics-off
python3 native/tests/plasma_popup.py --dismissal --output /tmp/plasma-dismissal
python3 native/tests/plasma_keyboard.py --held-repeat --output /tmp/plasma-keyboard --backend /tmp/build/native/open-power-menu-native
