// SPDX-License-Identifier: MIT
// Temporary opt-in observation for the X11 popup-collapse investigation.
// No timers, input handlers, focus requests or window/property writes.
import QtQml

QtObject {
    id: trace
    property bool enabled: false
    property var snapshot: null
    property int sequence: 0
    property int requestSequence: 0
    property var currentRequest: null
    // A signal also lets the regression fixture inspect the exact JSON logged.
    signal recorded(string json)

    function windowState(window) {
        if (!window) return null;
        return {object: String(window), visible: window.visible, visibility: window.visibility,
            active: window.active, flags: window.flags,
            // winId() can create a native surface. Never call it from QML
            // diagnostics; correlate this object/geometry with the X11 probe.
            animated: typeof window.animated === "boolean" ? window.animated : null,
            geometry: [window.x, window.y, window.width, window.height],
            transientParent: window.transientParent ? {
                visible: window.transientParent.visible, active: window.transientParent.active,
                geometry: [window.transientParent.x, window.transientParent.y,
                    window.transientParent.width, window.transientParent.height]} : null};
    }
    function itemState(item) {
        if (!item) return null;
        return {object: String(item), visible: item.visible, opacity: item.opacity,
            clip: item.clip, geometry: [item.x, item.y, item.width, item.height],
            parent: item.parent ? String(item.parent) : null};
    }
    function record(callback, details = null) {
        if (!enabled) return;
        let state;
        try { state = snapshot ? snapshot() : null; }
        catch (error) { state = {inspectionError: String(error)}; }
        const json = JSON.stringify({time: new Date().toISOString(), time_ms: Date.now(),
            sequence: ++sequence, callback: callback, request: currentRequest,
            details: details, state: state});
        console.info("OPM_POPUP_TRACE", json);
        recorded(json);
    }
    function setExpanded(target, value, callback) {
        if (!enabled) { target.expanded = value; return; }
        const previous = currentRequest;
        currentRequest = {id: ++requestSequence, callback: callback, value: value};
        record("opm-expanded-request");
        try { target.expanded = value; }
        finally {
            record("opm-expanded-return");
            currentRequest = previous;
        }
    }
    function expandedChanged() {
        // Attribution is scoped to the synchronous setter, not the most recent
        // request: a no-op OPM close must not label a later Plasma collapse.
        record("root.expandedChanged", {origin: currentRequest ? "opm" : "external-to-opm"});
    }
    onEnabledChanged: record("trace-enabled")
}
