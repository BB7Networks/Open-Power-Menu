#!/bin/sh
# Private, offline sessions. Required platform selection comes from the
# explicitly validated distribution profile, never compositor auto-detection.
set -eu
source=/src/work/pacman-source/src/Open-Power-Menu
build=/src/work/pacman-source/src/build
evidence=/tmp/desktop-qualification
mkdir "$evidence"
profile=${OPM_SESSION_PROFILE:?}
export OPM_TEST_INPUT_MODULE="$build/native/nativeinput"
case "$profile" in
  manjaro-wayland) platforms=wayland;;
  plasma67-x11) platforms='xcb wayland';;
  *) exit 2;;
esac
cp /src/work/pacman-source/artifacts/session-coverage.json "$evidence/"
for platform in $platforms; do
    python "$source/native/tests/plasma_keyboard.py" --platform "$platform" --held-repeat \
        --backend "$build/native/open-power-menu-native" --output "$evidence/keyboard-tests"
    python "$source/native/tests/plasma_greeter.py" --platform "$platform" \
        --backend "$build/native/open-power-menu-native" --output "$evidence/greeter-$platform"
    python "$source/native/tests/plasma_startup.py" --platform "$platform" --output "$evidence/startup-tests"
done
if [ "$profile" = plasma67-x11 ]; then
    python "$source/native/tests/plasma_popup.py" --output "$evidence/popup-tests"
    python "$source/native/tests/plasma_popup.py" --diagnostics-off --output "$evidence/popup-untraced-tests"
    python "$source/native/tests/plasma_popup.py" --dismissal --output "$evidence/dismissal-tests"
fi
printf 'passed\n' > "$evidence/desktop-tests-result"
