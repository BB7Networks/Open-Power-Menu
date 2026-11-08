// SPDX-License-Identifier: MIT
import QtQuick
QtObject {
    id: hover
    property int delay: -1
    property bool enabled: true
    property bool hovered: false
    signal openRequested()
    property Timer timer: Timer {
        interval: Math.max(0, hover.delay)
        onTriggered: if (hover.enabled && hover.hovered) hover.openRequested()
    }
    function cancel() { timer.stop(); }
    function request() {
        timer.stop();
        if (!enabled || !hovered) return;
        // The widget's existing default is immediate; standalone uses its style.
        if (delay <= 0) openRequested();
        else timer.start();
    }
    onHoveredChanged: { if (hovered) request(); else cancel(); }
    onEnabledChanged: { if (enabled && hovered) request(); else cancel(); }
    onDelayChanged: { if (hovered) request(); }
}
