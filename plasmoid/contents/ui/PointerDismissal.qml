// SPDX-License-Identifier: MIT
// One leave timer for the root popup and all of its native flyout windows.
import QtQuick
QtObject {
    id: policy
    property bool enabled: false
    property bool menuOpen: false
    property bool pointerInside: false
    property bool protectedInteraction: false
    property bool keyboardMode: false
    property bool entered: false
    property int delay: 1200
    readonly property bool pending: deadline.running
    signal dismissed()

    function update() {
        if (!enabled || !menuOpen || pointerInside || protectedInteraction || keyboardMode || !entered)
            deadline.stop();
        else if (!deadline.running)
            deadline.start();
    }
    function keyboardUsed() { keyboardMode = true; update(); }
    function pointerMoved() { keyboardMode = false; update(); }
    onDelayChanged: { deadline.stop(); update(); }
    onEnabledChanged: update()
    onProtectedInteractionChanged: update()
    onPointerInsideChanged: {
        if (pointerInside && menuOpen) entered = true;
        update();
    }
    onMenuOpenChanged: {
        deadline.stop();
        entered = menuOpen && pointerInside;
        keyboardMode = false;
    }
    property Timer deadline: Timer {
        interval: policy.delay
        repeat: false
        onTriggered: {
            if (policy.enabled && policy.menuOpen && !policy.pointerInside &&
                    !policy.protectedInteraction && !policy.keyboardMode && policy.entered)
                policy.dismissed();
        }
    }
}
