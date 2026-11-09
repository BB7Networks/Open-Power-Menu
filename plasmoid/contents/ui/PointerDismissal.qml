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
    // Opening/repositioning can synthesize a brief Enter/Leave pair. Discard
    // that history until geometry has been quiet for 150ms. The user's normal
    // leave interval is unchanged and begins only after a stable visit.
    property int transitionDelay: 150
    property point lastPointer: Qt.point(NaN, NaN)
    readonly property bool settling: transition.running
    readonly property bool pending: deadline.running
    signal dismissed()

    function update() {
        if (!enabled || !menuOpen || settling || pointerInside || protectedInteraction || keyboardMode || !entered)
            deadline.stop();
        else if (!deadline.running)
            deadline.start();
    }
    function geometryChanged() {
        deadline.stop();
        entered = false;
        if (menuOpen) transition.restart();
    }
    function keyboardUsed() { keyboardMode = true; update(); }
    function observePointer(x, y) {
        // Global coordinates avoid interpreting layout movement beneath a
        // stationary cursor as mouse input after keyboard navigation.
        if (x !== undefined && y !== undefined) {
            const moved = Number.isFinite(lastPointer.x) && (x !== lastPointer.x || y !== lastPointer.y);
            lastPointer = Qt.point(x, y);
            if (!moved || settling) return;
        }
        pointerMoved();
    }
    function pointerMoved() { keyboardMode = false; update(); }
    onDelayChanged: { deadline.stop(); update(); }
    onEnabledChanged: update()
    onProtectedInteractionChanged: update()
    onPointerInsideChanged: {
        if (pointerInside && menuOpen && !settling) entered = true;
        update();
    }
    onMenuOpenChanged: {
        deadline.stop();
        transition.stop();
        entered = false;
        keyboardMode = false;
        lastPointer = Qt.point(NaN, NaN);
        if (menuOpen) transition.start();
    }
    property Timer transition: Timer {
        interval: policy.transitionDelay
        repeat: false
        onTriggered: { policy.entered = policy.menuOpen && policy.pointerInside; policy.update(); }
    }
    property Timer deadline: Timer {
        interval: policy.delay
        repeat: false
        onTriggered: {
            if (policy.enabled && policy.menuOpen && !policy.settling && !policy.pointerInside &&
                    !policy.protectedInteraction && !policy.keyboardMode && policy.entered)
                policy.dismissed();
        }
    }
}
