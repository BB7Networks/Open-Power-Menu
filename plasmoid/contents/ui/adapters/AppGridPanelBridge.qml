// SPDX-License-Identifier: MIT
// AppGrid Center 1.9.x's special Wayland overlay behavior lives here.
// Keep the Start widget and the default Plasma adapter unaware of its window.
import QtQuick
import QtQuick.Window
import org.kde.plasma.core as PlasmaCore
import "AppGridLauncher.js" as AppGridLauncher
import "AppGridPanelGeometry.js" as PanelGeometry

Item {
    id: bridge
    visible: false
    width: 0
    height: 0

    // Dependencies supplied by the launcher-agnostic host.
    property var selectedLauncherPlan: null
    property bool active: false   // original panel button is hidden
    property var panelWindow: null
    property int panelLocation: -1
    property real compactButtonHeight: 40
    signal launcherOpened()

    property var passThroughWindow: null
    property var passThroughApplet: null
    property string passThroughSignature: ""
    property int passThroughAttempts: 0

    function restoreAppGridPassThrough() {
        const owner = passThroughApplet;
        const win = passThroughWindow;
        passThroughWindow = null;
        passThroughApplet = null;
        passThroughSignature = "";
        if (!owner || !win) return;
        try {
            if (typeof owner.setInputRect === "function") {
                // AppGrid's documented 0x0 rect restores full-window input.
                owner.setInputRect(win, 0, 0, 0, 0);
                console.info("Open Power Menu: restored AppGrid full-window input");
            }
        } catch (e) {
            console.warn("Open Power Menu: could not restore AppGrid input mask:", String(e));
        }
    }

    function applyAppGridPassThrough() {
        const plan = selectedLauncherPlan;
        if (!active || !AppGridLauncher.supportsPanelPassThrough(plan)) return false;
        const item = plan.item;
        // While dragging, AppGrid owns its input mask to allow external drops.
        if (item.isDragInFlight === true) return false;
        const win = item.gridWindow;
        if (!win || win.visible !== true || !panelWindow) return false;
        // Do not modify a layer surface on a different output.
        try {
            const sourceScreen = panelWindow.screen ? String(panelWindow.screen.name || "") : "";
            const targetScreen = win.screen ? String(win.screen.name || "") : "";
            if (sourceScreen.length && targetScreen.length && sourceScreen !== targetScreen)
                return false;
        } catch (e) { return false; }
        const edge = panelLocation === PlasmaCore.Types.BottomEdge ? "bottom" :
                     panelLocation === PlasmaCore.Types.TopEdge ? "top" :
                     panelLocation === PlasmaCore.Types.LeftEdge ? "left" :
                     panelLocation === PlasmaCore.Types.RightEdge ? "right" : "";
        if (!edge) return false;
        const axisLength = (edge === "bottom" || edge === "top") ? win.height : win.width;
        const measured = (edge === "bottom" || edge === "top") ? panelWindow.height : panelWindow.width;
        const thickness = Number.isFinite(measured) && measured >= 16 &&
                measured <= axisLength * 0.22 ? measured :
                Math.max(28, Math.min(96, compactButtonHeight || 40));
        const rect = PanelGeometry.inputRect(win.width, win.height,
                                             edge, thickness, win.panelRect);
        if (!rect) return false;
        const signature = [plan.applet.id, win.width, win.height, edge,
                           rect.x, rect.y, rect.w, rect.h].join(":");
        if (passThroughApplet === plan.applet && passThroughWindow === win &&
                passThroughSignature === signature) return true;
        if (passThroughWindow && passThroughWindow !== win)
            restoreAppGridPassThrough();
        try {
            plan.applet.setInputRect(win, rect.x, rect.y, rect.w, rect.h);
            passThroughApplet = plan.applet;
            passThroughWindow = win;
            passThroughSignature = signature;
            console.info("Open Power Menu: AppGrid panel input pass-through applied:",
                         edge, "strip=" + rect.cut + "px", "applet=" + plan.applet.id);
            return true;
        } catch (e) {
            console.warn("Open Power Menu: AppGrid input pass-through unavailable:", String(e));
            return false;
        }
    }

    function reset() {
        appGridPassThroughRetry.stop();
        restoreAppGridPassThrough();
        passThroughAttempts = 0;
    }

    function schedule() {
        if (!active || !AppGridLauncher.supportsPanelPassThrough(selectedLauncherPlan)) return;
        passThroughAttempts = 0;
        appGridPassThroughRetry.restart();
    }

    // Ownership changes and disabling the optional integration always
    // restore AppGrid's full input surface, even without a gridOpen signal.
    onActiveChanged: {
        if (!active) reset();
        else schedule();
    }
    onSelectedLauncherPlanChanged: {
        if (passThroughApplet && (!selectedLauncherPlan ||
                selectedLauncherPlan.applet !== passThroughApplet)) reset();
        schedule();
    }
    onPanelLocationChanged: {
        passThroughSignature = "";
        schedule();
    }
    onPanelWindowChanged: {
        passThroughSignature = "";
        schedule();
    }

    Timer {
        id: appGridPassThroughRetry
        interval: 80
        repeat: true
        onTriggered: {
            if (!bridge.active || !AppGridLauncher.supportsPanelPassThrough(bridge.selectedLauncherPlan)) {
                stop();
                return;
            }
            if (bridge.applyAppGridPassThrough()) {
                stop();
                return;
            }
            if (++bridge.passThroughAttempts >= 20) {
                stop();
                console.warn("Open Power Menu: panel input pass-through was not installed; " +
                             "AppGrid may intercept right-clicks");
            }
        }
    }

    Connections {
        target: bridge.selectedLauncherPlan && bridge.selectedLauncherPlan.item
                ? bridge.selectedLauncherPlan.item.gridWindow : null
        ignoreUnknownSignals: true
        function onVisibleChanged() {
            const item = bridge.selectedLauncherPlan ? bridge.selectedLauncherPlan.item : null;
            const win = item ? item.gridWindow : null;
            if (win && win.visible && item.gridOpen === true) bridge.schedule();
            else if (!win || !win.visible) bridge.restoreAppGridPassThrough();
        }
        function onWidthChanged() {
            bridge.passThroughSignature = "";
            bridge.schedule();
        }
        function onHeightChanged() {
            bridge.passThroughSignature = "";
            bridge.schedule();
        }
    }

    Connections {
        target: bridge.selectedLauncherPlan ? bridge.selectedLauncherPlan.item : null
        ignoreUnknownSignals: true
        function onGridOpenChanged() {
            const plan = bridge.selectedLauncherPlan;
            if (!plan || !AppGridLauncher.matches(plan.applet)) return;
            console.info("Open Power Menu: observed AppGrid gridOpen change:",
                         AppGridLauncher.describeState(plan.item, plan.applet));
            if (plan.item && plan.item.gridOpen === true) bridge.schedule();
            else bridge.reset();
            bridge.launcherOpened();
        }
        function onIsDragInFlightChanged() {
            const plan = bridge.selectedLauncherPlan;
            if (!plan || !AppGridLauncher.matches(plan.applet) || !plan.item) return;
            const item = plan.item;
            if (item.isDragInFlight === true) {
                appGridPassThroughRetry.stop();
                bridge.passThroughSignature = "";
            } else if (item.gridOpen === true) {
                bridge.passThroughSignature = "";
                // AppGrid finishes restoring its own drag mask first.
                Qt.callLater(() => bridge.schedule());
            }
        }
    }

    Component.onDestruction: reset()
}
