// SPDX-License-Identifier: MIT
// Plasma 6.7-compatible right-click Start adapter: no launcher patches.
import QtQuick
import QtQuick.Layouts
import QtQml
import QtQuick.Window
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PC3
import org.kde.plasma.workspace.dbus as DBus
import "LauncherVisibility.js" as LauncherVisibility
import "LayoutDraft.js" as LayoutDraft
import "LayoutController.js" as LayoutController
import "adapters" as AdapterUi
import "adapters/LauncherAdapters.js" as LauncherAdapters

PlasmoidItem {
    id: root
    Plasmoid.icon: root.effectiveButtonIcon
    preferredRepresentation: compactRepresentation
    activationTogglesExpanded: false
    Plasmoid.hasConfigurationInterface: true
    toolTipMainText: "Open Power Menu Start Button"
    toolTipSubText: launcherSwitchError.length ? launcherSwitchError
                    : launcherMaskError.length ? "Original launcher remains visible: " + launcherMaskError
                    : commandError.length ? commandError
                    : layoutDraft ? "Layout draft retained · Right-click to continue editing"
                    : maskActive ? "Original launcher hidden by Plasma (experimental) · Left click opens it"
                    : "Left click: launcher · Right click: Power User menu"

    // KDE's native widget shortcut expands PlasmoidItem before QML receives
    // activated(). Route the event through the guarded OPM popup handoff.
    Connections {
        target: Plasmoid
        function onActivated() { root.activatePowerShortcut(); }
    }

    property var menuEntries: []
    property var visibleEntries: []
    property string menuStatus: "Loading system shortcuts..."
    property bool fetching: false
    property int menuFetchEpoch: 0
    property string menuAppearance: "native"
    property string commandError: ""
    property bool launchPending: false
    // Temporary state belongs to the applet, so closing its popup keeps the draft.
    property var layoutDraft: null
    readonly property bool layoutEditing: layoutDraft !== null
    property bool layoutBusy: false
    property bool layoutExpired: false
    property int layoutEpoch: 0
    property string layoutStatus: ""

    Timer {
        interval: 60000
        repeat: true
        running: root.layoutEditing
        onTriggered: LayoutController.keep(root)
    }

    // Both launcher visibility and the Start icon are shared editor settings.
    // A missing/unsupported original icon falls back to the widget's saved
    // icon, without mutating the underlying launcher's configuration.
    property string buttonIconMode: "launcher" // "launcher" or "custom"
    property string customButtonIcon: ""
    property var selectedLauncherPlan: null
    readonly property var selectedLauncherItem: selectedLauncherPlan ? selectedLauncherPlan.item : null
    readonly property var effectiveButtonIcon: LauncherAdapters.chooseIcon(
        selectedLauncherPlan ? selectedLauncherPlan.applet : null,
        buttonIconMode, customButtonIcon,
        Plasmoid.configuration.buttonIcon || "start-here-manjaro")

    // Last requested menu wins. Defer launcher activation one event-loop turn
    // so the Power User popup and its side flyouts are closed first.
    property int menuSwitchEpoch: 0
    property string requestedMenu: "none"
    // Tracks an OPM-opened popup, not Plasma's eager shortcut expansion.
    property bool powerIsOpen: false
    // A popup's expanded=false is not the same as its native dialog having
    // finished losing focus. Wait briefly only when switching from a visible
    // Power Menu to a Plasma launcher, or the old popup can close the new one.
    property int pendingLauncherEpoch: -1

    Timer {
        id: launcherActivationSettle
        interval: 140
        repeat: false
        onTriggered: {
            const epoch = root.pendingLauncherEpoch;
            LauncherAdapters.traceRequest(root, "activation-settle", epoch);
            root.pendingLauncherEpoch = -1;
            if (epoch !== root.menuSwitchEpoch || root.requestedMenu !== "launcher" || root.expanded)
                return;
            const plan = root.selectedLauncherPlan;
            // External Meta/shortcut activation may have won during the wait.
            // Don't issue a second toggle and close a launcher that's open.
            if (LauncherAdapters.originalIsOpen(root.selectedLauncherItem,
                    plan ? plan.applet : null)) {
                console.info("Open Power Menu: launcher already open after popup settled; avoiding second toggle");
                return;
            }
            console.info("Open Power Menu: activating launcher after Power Menu popup settled");
            root.activateSelectedLauncher(epoch);
        }
    }

    // A switch to Power Menu isn't complete until the other menu has closed.
    // The selected adapter may close asynchronously or animate its window.
    // Only open Power Menu when the adapter confirms it is no longer visible.
    property int pendingPowerEpoch: -1
    property int launcherClosePollCount: 0
    property bool awaitingAsyncClose: false
    property string launcherSwitchError: ""

    // A launcher-specific adapter handles AppGrid's unusual full-screen Wayland
    // input surface. All other launchers bypass this bridge entirely.
    AdapterUi.AppGridPanelBridge {
        id: appGridPanelBridge
        selectedLauncherPlan: root.selectedLauncherPlan
        active: root.maskActive && root.hideOriginalLauncherRequested
        panelWindow: root.Window.window
        panelLocation: Plasmoid.location
        compactButtonHeight: button.height
        onLauncherOpened: root.onOriginalLauncherOpened()
    }

    function closeLauncherPopup() {
        if (!selectedLauncherPlan) {
            try {
                const panel = Plasmoid.containment;
                selectedLauncherPlan = LauncherVisibility.prepare(root,
                    panel ? panel.applets : [], Plasmoid, Plasmoid.id,
                    panel ? panel.id : -1, launcherAppletId);
            } catch (e) {
                // A standalone Power Menu works even without a launcher target.
                console.warn("Open Power Menu: original launcher unavailable for dismissal:", String(e));
                return {ok:true, mode:"no-target"};
            }
        }
        const plan = selectedLauncherPlan;
        const requestEpoch = root.menuSwitchEpoch;
        LauncherAdapters.trace("launcher before right-click", plan.item, plan.applet);
        const result = LauncherAdapters.closeOriginal(plan.item, plan.applet, () => {
            // Only a specialized adapter can request an asynchronous close.
            // The callback is never invoked by the generic Plasma adapter.
            root.awaitingAsyncClose = true;
            LauncherAdapters.requestAsyncClose(plan.applet,
                (...args) => root.send(...args),
                () => requestEpoch === root.menuSwitchEpoch,
                (ok, reason) => {
                    if (requestEpoch !== root.menuSwitchEpoch) return;
                    root.awaitingAsyncClose = false;
                    if (!ok) {
                        root.launcherSwitchError = String(reason);
                        console.warn("Open Power Menu:", root.launcherSwitchError);
                        launcherClosePoll.stop();
                    }
                });
        });
        LauncherAdapters.traceDismissal(result, plan.item, plan.applet);
        return result;
    }

    function finishOpeningPower(epoch) {
        LauncherAdapters.traceRequest(root, "power-close-confirmed", epoch);
        if (epoch !== menuSwitchEpoch || requestedMenu !== "power") return;
        launcherClosePoll.stop();
        pendingPowerEpoch = -1;
        awaitingAsyncClose = false;
        launcherSwitchError = "";
        powerIsOpen = true;
        expanded = true;
        fetchMenu();
        launcherCloseFollowup.restart();
    }

    Timer {
        id: launcherClosePoll
        interval: 40
        repeat: true
        onTriggered: {
            if (root.requestedMenu !== "power" || root.pendingPowerEpoch !== root.menuSwitchEpoch) {
                stop();
                return;
            }
            root.launcherClosePollCount++;
            if (root.launcherSwitchError.length) {
                stop();
                return;
            }
            const item = root.selectedLauncherItem;
            const plan = root.selectedLauncherPlan;
            const stillVisible = LauncherAdapters.originalIsVisiblyOpen(item, plan ? plan.applet : null);
            if (!root.awaitingAsyncClose && !stillVisible) {
                root.finishOpeningPower(root.pendingPowerEpoch);
                return;
            }
            // A custom launcher's close may animate. Retry once, but never
            // blindly toggle an unknown window.
            if (root.launcherClosePollCount === 15 && !root.awaitingAsyncClose) {
                root.closeLauncherPopup();
            }
            if (root.launcherClosePollCount >= 50) {
                stop();
                root.pendingPowerEpoch = -1;
                root.launcherSwitchError = "Original launcher did not close; Power Menu was not opened";
                console.warn("Open Power Menu:", root.launcherSwitchError,
                             LauncherAdapters.describeState(item, plan ? plan.applet : null));
            }
        }
    }

    // Guard against a late launch activation just after a right-click.
    // Outside this guard, a later Meta activation takes precedence instead.
    Timer {
        id: launcherCloseFollowup
        interval: 350
        repeat: false
        onTriggered: {
            LauncherAdapters.traceRequest(root, "close-followup", root.menuSwitchEpoch);
            if (root.expanded && root.requestedMenu === "power")
                root.closeLauncherPopup();
        }
    }
    function onOriginalLauncherOpened() {
        LauncherAdapters.traceRequest(root, "launcher-state-signal", root.menuSwitchEpoch);
        if (!root.expanded || !LauncherAdapters.originalIsOpen(
                root.selectedLauncherItem,
                root.selectedLauncherPlan ? root.selectedLauncherPlan.applet : null))
            return;
        if (root.requestedMenu === "power" && launcherCloseFollowup.running) {
            if (!LauncherAdapters.deferSignalClose(root.selectedLauncherPlan ? root.selectedLauncherPlan.applet : null)) {
                root.closeLauncherPopup();
                return;
            }
            // gridOpen changes before AppGrid's openWindow finishes showing its
            // window. Do not reenter closeWindow halfway through that call.
            const epoch = root.menuSwitchEpoch;
            Qt.callLater(() => {
                LauncherAdapters.traceRequest(root, "late-open-close-callback", epoch);
                if (epoch === root.menuSwitchEpoch && root.requestedMenu === "power" && root.expanded)
                    root.closeLauncherPopup();
            });
        } else {
            root.menuSwitchEpoch += 1;
            root.requestedMenu = "launcher";
            root.expanded = false; // Original launcher/Meta takes precedence.
        }
    }
    Connections {
        target: root
        function onExpandedChanged() { LauncherAdapters.traceRequest(root, "power-expanded", root.menuSwitchEpoch); }
        function onMaskActiveChanged() { LauncherAdapters.traceRequest(root, "mask-active", root.menuSwitchEpoch); }
    }
    Connections {
        target: root.selectedLauncherItem
        ignoreUnknownSignals: true
        // Standard Plasma launchers expose their popup through expanded.
        // Nonstandard lifecycle signals are owned by their adapters.
        function onExpandedChanged() {
            root.logLauncherVisibility("original launcher expanded changed");
            root.onOriginalLauncherOpened();
        }
    }

    // Plasma's own panel code honors the HiddenStatus of any applet.
    // A reversible Binding is used on the chosen existing applet's *status*.
    // No size-hint, opacity, visible, enabled or layout overrides are made.
    // Qt restores the original value/binding when the preference is disabled.
    property var maskedLauncher: null
    property bool maskActive: false
    property int launcherAppletId: 0
    property bool hideOriginalLauncherRequested: false
    property string launcherMaskError: ""
    property var maskPlan: null

    // Observation only. The native panel owns both visibility bindings; we do
    // not write Item.visible or AppletContainer.visible. If KDE's launcher
    // flashes without a status repair, this distinguishes container exposure
    // from a visual/representation repaint without changing working behavior.
    function logLauncherVisibility(reason) {
        const plan = maskPlan;
        if (!maskActive || !plan || plan.applet !== maskedLauncher) return;
        try {
            console.info("Open Power Menu: launcher visibility:", reason,
                         "status=" + String(plan.applet.status),
                         "hidden=" + String(plan.applet.status === PlasmaCore.Types.HiddenStatus),
                         "containerVisible=" + String(plan.container ? plan.container.visible : "unavailable"),
                         "itemVisible=" + String(plan.item ? plan.item.visible : "unavailable"),
                         "launcherExpanded=" + String(plan.item ? plan.item.expanded : "unavailable"));
        } catch (e) {
            console.warn("Open Power Menu: launcher visibility inspection failed:", String(e));
        }
    }
    Connections {
        target: root.maskPlan ? root.maskPlan.container : null
        ignoreUnknownSignals: true
        function onVisibleChanged() {
            if (root.maskActive && root.maskPlan && root.maskPlan.container && root.maskPlan.container.visible)
                root.logLauncherVisibility("original panel container became visible");
        }
    }
    Connections {
        target: root.maskPlan ? root.maskPlan.item : null
        ignoreUnknownSignals: true
        function onVisibleChanged() {
            if (root.maskActive && root.maskPlan && root.maskPlan.item && root.maskPlan.item.visible)
                root.logLauncherVisibility("original applet item became visible");
        }
    }

    // A launcher can overwrite its status during activation. A Binding alone
    // will not necessarily win that write: refresh its revision synchronously
    // on statusChanged, before the panel has a chance to paint a second icon.
    // The guarded, reversible Binding still owns the actual status write.
    property int launcherMaskRevision: 0
    property bool launcherMaskRepairInProgress: false
    property bool launcherMaskRepairScheduled: false
    property int launcherMaskRepairAttempts: 0
    property int launcherMaskIdentity: 0

    function hiddenStatusForRevision(_revision) {
        return PlasmaCore.Types.HiddenStatus;
    }

    Binding {
        id: launcherStatusBinding
        target: root.maskedLauncher
        property: "status"
        value: root.hiddenStatusForRevision(root.launcherMaskRevision)
        when: root.maskActive && root.maskedLauncher !== null
        restoreMode: Binding.RestoreBindingOrValue
    }

    Timer {
        id: maskRepairBudget
        interval: 2500
        repeat: false
        onTriggered: root.launcherMaskRepairAttempts = 0
    }

    // The native panel reacts to status changes itself. Never override the
    // panel's Item.visible, the launcher's expanded state, or its layout slot.
    // Repair immediately during statusChanged, not one event-loop turn later:
    // Qt.callLater can leave the original button visible for a rendered frame.
    // Guard against nested statusChanged caused by re-evaluating our Binding.
    function repairLauncherMask() {
        if (!maskActive || !hideOriginalLauncherRequested || !maskedLauncher ||
                maskedLauncher.status === PlasmaCore.Types.HiddenStatus ||
                launcherMaskRepairInProgress)
            return;
        const target = maskedLauncher;
        const identity = launcherMaskIdentity;
        // Bound retries are a safety valve for incompatible/custom launchers.
        // Twenty transitions within 2.5 seconds indicates a binding fight,
        // not ordinary user clicking, and restores the original launcher.
        if (launcherMaskRepairAttempts >= 20) {
            releaseMask();
            launcherMaskError = "Launcher repeatedly overrides its hidden status; original button restored";
            console.warn("Open Power Menu:", launcherMaskError);
            return;
        }
        launcherMaskRepairAttempts += 1;
        maskRepairBudget.restart();
        launcherMaskRepairInProgress = true;
        try {
            launcherMaskRevision += 1;
        } finally {
            launcherMaskRepairInProgress = false;
        }
        // Report repairs so live logs can distinguish status flicker from a
        // popup or panel drawing issue without enabling verbose logging.
        if (target.status === PlasmaCore.Types.HiddenStatus)
            console.info("Open Power Menu: immediate launcher hide repair", String(target.pluginName || "unknown"));
        // Usually the Binding has already restored HiddenStatus by this point.
        // On runtimes deferring evaluation, try again later without reentrancy.
        if (target.status !== PlasmaCore.Types.HiddenStatus && !launcherMaskRepairScheduled) {
            launcherMaskRepairScheduled = true;
            Qt.callLater(() => {
                root.launcherMaskRepairScheduled = false;
                if (root.maskActive && root.hideOriginalLauncherRequested &&
                        root.launcherMaskIdentity === identity && root.maskedLauncher === target)
                    root.repairLauncherMask();
            });
        }
    }

    Connections {
        target: root.maskedLauncher
        ignoreUnknownSignals: true
        function onStatusChanged() {
            root.logLauncherVisibility("original launcher status changed");
            root.repairLauncherMask();
        }
    }

    function releaseMask() {
        // Keeping the target until after Binding.when turns false ensures
        // original bindings are restored, not replaced with raw JS writes.
        appGridPanelBridge.reset();
        maskActive = false;
        launcherMaskIdentity += 1;
        launcherMaskRepairInProgress = false;
        launcherMaskRepairScheduled = false;
        launcherMaskRepairAttempts = 0;
        maskRepairBudget.stop();
        maskVerification.stop();
        // Never write a status or toggle expanded/visible directly.
    }

    Timer {
        id: maskVerification
        interval: 350
        repeat: false
        onTriggered: {
            if (!root.maskActive) return;
            if (LauncherVisibility.didHide(root.maskPlan, PlasmaCore.Types.HiddenStatus)) {
                root.launcherMaskError = "";
            } else {
                root.releaseMask();
                const reason = "Plasma did not hide the launcher container; restored previous status";
                root.launcherMaskError = reason;
                console.warn("Open Power Menu: " + reason);
            }
        }
    }

    function fetchIntegration() {
        send("org.openpowermenu.Service", "/OpenPowerMenu", "org.openpowermenu.Service",
             "GetIntegration", [], (ok, value) => {
                 if (!ok) return; // A temporary D-Bus outage should not change panel state.
                 try {
                     const cfg = JSON.parse(String(value));
                     const desired = cfg.hide_original_launcher === true;
                     const selected = Number(cfg.launcher_applet_id || 0);
                     if (!Number.isInteger(selected) || selected < 0) return;
                     if (launcherAppletId !== selected) {
                         releaseMask();
                         launcherAppletId = selected;
                     }
                     hideOriginalLauncherRequested = desired;
                     buttonIconMode = cfg.button_icon_mode === "custom" ? "custom" : "launcher";
                     customButtonIcon = String(cfg.button_icon || "");
                     menuAppearance = cfg.appearance === "aero" ? "aero" : "native";
                     synchronizeLauncherVisibility();
                 } catch (e) {
                     console.warn("Open Power Menu: invalid integration configuration", e);
                 }
             });
    }

    function synchronizeLauncherVisibility() {
        // Keep a reference to the selected panel launcher even when hiding is
        // disabled: its icon and expanded state are needed for the button.
        if (!hideOriginalLauncherRequested) {
            releaseMask();
            launcherMaskError = "";
        }
        // The editor's five-second preference poll must not repeatedly find
        // the panel wrapper while a native popup is being created/destroyed.
        // The cached target is valid when Plasma still reports that *exact*
        // selected applet in the same containment. This also rechecks that
        // automatic selection remains unique when no ID was configured.
        if (hideOriginalLauncherRequested && maskActive && maskedLauncher &&
                selectedLauncherPlan && selectedLauncherPlan.applet === maskedLauncher) {
            try {
                const panel = Plasmoid.containment;
                const current = LauncherVisibility.findOriginal(
                    panel ? panel.applets : [], Plasmoid.id, launcherAppletId);
                if (current === maskedLauncher) {
                    repairLauncherMask();
                    return;
                }
            } catch (e) {
                // Applet selection changed or was removed; let normal fallback
                // verify and safely release a stale target.
            }
        }
        try {
            const panel = Plasmoid.containment;
            const planned = LauncherVisibility.prepare(root, panel ? panel.applets : [],
                           Plasmoid, Plasmoid.id, panel ? panel.id : -1, launcherAppletId);
            selectedLauncherPlan = planned;
            if (!hideOriginalLauncherRequested) return;

            if (maskActive) {
                if (maskedLauncher === planned.applet) {
                    // Refresh the item/container references without toggling
                    // the status Binding. A normal popup transition must not
                    // briefly restore the original panel icon.
                    maskPlan = planned;
                    repairLauncherMask();
                    return;
                }
                releaseMask();
            }
            // Qt must restore the old target's original status/binding before
            // we assign the Binding to a different selected widget.
            if (maskedLauncher && maskedLauncher !== planned.applet) {
                maskedLauncher = null;
                maskPlan = null;
                Qt.callLater(() => root.synchronizeLauncherVisibility());
                return;
            }
            maskPlan = planned;
            maskedLauncher = planned.applet;
            maskActive = true;
            launcherMaskError = "";
            maskVerification.restart();
        } catch (e) {
            selectedLauncherPlan = null;
            if (!hideOriginalLauncherRequested) return;
            releaseMask();
            const message = String(e);
            if (message !== launcherMaskError)
                console.warn("Open Power Menu: launcher remains visible (safe fallback):", message);
            launcherMaskError = message;
        }
    }

    // The editor is a separate Qt process. Poll its shared preference rather
    // than caching a state that could leave a launcher inaccessible. Clicking
    // Refresh or opening the menu also re-reads it without any delay.
    Timer {
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.fetchIntegration()
    }
    Component.onDestruction: {
        releaseMask();
    }

    function send(serviceName, path, iface, methodName, args, onDone) {
        const reply = DBus.SessionBus.asyncCall({
            service: serviceName, path: path, iface: iface, member: methodName, arguments: args
        });
        reply.finished.connect(() => {
            const bad = reply.isError;
            const value = reply.value;
            if (onDone) onDone(!bad, value);
            reply.destroy();
        });
    }

    // Make left/right actions target the *same* launcher. Plasma's global
    // activateLauncherMenu chooses the first matching launcher after sorting
    // all panels/outputs. That can be a different instance from the widget
    // deliberately selected in Configure (and therefore from the instance
    // right-click tries to close). Emitting activated() is the same action the
    // Plasma shell uses, but on our exact selected applet.
    function activateSelectedLauncher(epoch) {
        LauncherAdapters.traceRequest(root, "activation-callback", epoch);
        if (epoch !== root.menuSwitchEpoch || root.requestedMenu !== "launcher")
            return;
        let plan = root.selectedLauncherPlan;
        if (!plan || !plan.applet || (root.launcherAppletId > 0 &&
                Number(plan.applet.id) !== root.launcherAppletId)) {
            try {
                const panel = Plasmoid.containment;
                plan = LauncherVisibility.prepare(root, panel ? panel.applets : [],
                            Plasmoid, Plasmoid.id, panel ? panel.id : -1,
                            root.launcherAppletId);
                root.selectedLauncherPlan = plan;
            } catch (e) {
                plan = null;
                console.warn("Open Power Menu: cannot resolve selected launcher for activation:", String(e));
            }
        }
        if (plan && plan.applet && typeof plan.applet.activated === "function") {
            try {
                LauncherAdapters.trace("launcher before left-click", plan.item, plan.applet);
                LauncherAdapters.activate(plan.applet);
                console.info("Open Power Menu: activated selected launcher widget",
                             Number(plan.applet.id), String(plan.applet.pluginName || ""));
                LauncherAdapters.trace("launcher after left-click", plan.item, plan.applet);
                return;
            } catch (e) {
                console.warn("Open Power Menu: selected launcher activation failed:", String(e));
            }
        }
        // Never accidentally activate some OTHER launcher when Configure
        // explicitly names a widget which is missing/not activatable.
        if (root.launcherAppletId > 0) {
            root.launcherSwitchError = "Selected launcher cannot be activated; check widget ID in Configure";
            return;
        }
        // Portable fallback for unconfigured users: preserve Plasma's normal
        // launcher activation semantics until a specific launcher is chosen.
        root.send("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell",
                  "activateLauncherMenu", [], (ok, value) => {
                      if (!ok) console.warn("Open Power Menu: Plasma launcher activation failed");
                  });
    }

    function activateLauncher() {
        // Opening a second native popup while our first popup is still losing
        // focus can trigger KDE's hide-on-deactivate on the new launcher.
        // Normal left-click stays immediate; only a visible Power Menu incurs
        // a short settling interval before we emit the selected applet signal.
        const wasPowerPopupOpen = expanded === true;
        const epoch = ++menuSwitchEpoch;
        requestedMenu = "launcher";
        LauncherAdapters.traceRequest(root, "left-request", epoch);
        launcherClosePoll.stop();
        pendingPowerEpoch = -1;
        awaitingAsyncClose = false;
        launcherSwitchError = "";
        launcherCloseFollowup.stop();
        expanded = false; // Also closes any visible side flyout.
        if (wasPowerPopupOpen) {
            pendingLauncherEpoch = epoch;
            launcherActivationSettle.restart();
        } else {
            Qt.callLater(() => root.activateSelectedLauncher(epoch));
        }
    }
    function fetchMenu() {
        if (layoutEditing || layoutBusy) return;
        const epoch = ++menuFetchEpoch;
        fetching = true;
        menuStatus = "Loading system shortcuts...";
        send("org.openpowermenu.Service", "/OpenPowerMenu", "org.openpowermenu.Service",
             "GetMenu", [], (ok, value) => {
                 if (epoch !== menuFetchEpoch || layoutEditing || layoutBusy) return;
                 fetching = false;
                 if (!ok) {
                     menuStatus = "Backend unavailable. Run open-power-menu --check. Install the complete package with bash install.sh if needed.";
                     menuEntries = [];
                 } else {
                     try {
                         menuEntries = JSON.parse(String(value));
                         menuStatus = menuEntries.length ? "" : "No available commands";
                         if (menuEntries.length === 1 && menuEntries[0].key === "" && menuEntries[0].enabled === false)
                             menuStatus = "Configuration could not be loaded. Open Configure to recover it.";
                     } catch (e) {
                         menuStatus = "Could not read menu configuration";
                         menuEntries = [];
                     }
                 }
                 rebuild();
             });
    }
    // The main menu always has only top-level rows. Submenus are real side
    // popups, not extra rows inserted below the selected parent.
    function rebuild() {
        visibleEntries = menuEntries;
    }
    function activatePowerShortcut() {
        // Plasma's PlasmoidItem first calls setExpanded(true) for activated().
        // The state below distinguishes a genuine OPM popup or pending handoff
        // from that eager expansion. Never launch a second standalone window.
        if (powerIsOpen || (requestedMenu === "power" && launcherClosePoll.running)) {
            root.openMenu(); // Toggle off an existing/pending power popup.
            return;
        }
        expanded = false; // Undo the eager expand before our handoff begins.
        root.openMenu();
    }

    function openMenu() {
        fetchIntegration();
        const alreadyOpen = expanded || (launcherClosePoll.running && requestedMenu === "power");
        const epoch = ++menuSwitchEpoch; // Cancel an unsent left-click activation.
        launcherActivationSettle.stop(); // Cancel pending Power -> Launcher switch.
        pendingLauncherEpoch = -1;
        requestedMenu = alreadyOpen ? "none" : "power";
        LauncherAdapters.traceRequest(root, "right-request", epoch);
        launcherClosePoll.stop();
        launcherCloseFollowup.stop();
        pendingPowerEpoch = -1;
        awaitingAsyncClose = false;
        launcherSwitchError = "";
        if (alreadyOpen) {
            expanded = false;
            return;
        }
        const result = closeLauncherPopup();
        if (!result.ok) {
            launcherSwitchError = "Cannot dismiss original launcher (" + result.mode + ")";
            console.warn("Open Power Menu:", launcherSwitchError);
            return;
        }
        pendingPowerEpoch = epoch;
        launcherClosePollCount = 0;
        // Wait for adapter close/acknowledgment before opening Power Menu.
        launcherClosePoll.start();
    }
    function openEditor() {
        // Close the panel popup so the separate Qt editor is visible.
        expanded = false;
        send("org.openpowermenu.Service", "/OpenPowerMenu", "org.openpowermenu.Service",
             "Edit", [], (ok, value) => {
                 if (!ok || value === false) {
                     menuStatus = "Could not start menu editor. Run open-power-menu --edit in Konsole.";
                     commandError = menuStatus;
                     console.warn("Open Power Menu: editor unavailable; service may need restarting");
                 }
             });
    }

    function launchItem(key) {
        if (layoutEditing || layoutBusy || launchPending) return;
        const epoch = menuSwitchEpoch;
        launchPending = true;
        commandError = "";
        send("org.openpowermenu.Service", "/OpenPowerMenu", "org.openpowermenu.Service",
             "Run", [key], (ok, value) => {
                 launchPending = false;
                 if (epoch !== menuSwitchEpoch) return;
                 if (!ok || value === false) {
                     commandError = ok ? "Could not start this item. It may be unavailable; refresh or check it in Configure."
                                       : "Backend unavailable. Run open-power-menu --check and try again.";
                 } else {
                     expanded = false;
                 }
             });
    }

    compactRepresentation: Item {
        id: button
        Layout.minimumWidth: height
        Layout.minimumHeight: Kirigami.Units.iconSizes.small
        Layout.preferredWidth: Math.max(height, Kirigami.Units.iconSizes.medium)
        activeFocusOnTab: true
        Accessible.name: "Start menu and Power User menu"
        Accessible.role: Accessible.Button

        Kirigami.Icon {
            anchors.centerIn: parent
            width: Math.min(parent.width, parent.height)
            height: width
            source: Plasmoid.icon
            active: hit.containsMouse
        }
        MouseArea {
            id: hit
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onPressed: mouse => {
                if (mouse.button === Qt.RightButton) {
                    console.info("Open Power Menu: right-click received by Start button");
                    root.openMenu();
                    mouse.accepted = true;
                }
            }
            onClicked: mouse => {
                if (mouse.button === Qt.LeftButton) {
                    if (Plasmoid.configuration.leftAction === "power") root.openMenu();
                    else root.activateLauncher();
                }
            }
        }
        Keys.onPressed: event => {
            if (event.key === Qt.Key_Menu || (event.key === Qt.Key_F10 && (event.modifiers & Qt.ShiftModifier))) {
                root.openMenu();
                event.accepted = true;
            } else if (event.key === Qt.Key_Enter || event.key === Qt.Key_Return || event.key === Qt.Key_Space) {
                if (Plasmoid.configuration.leftAction === "power") root.openMenu();
                else root.activateLauncher();
                event.accepted = true;
            }
        }
    }

    fullRepresentation: Item {
        id: popup
        focus: true
        property int activeIndex: -1
        Rectangle {
            anchors.fill: parent
            color: root.menuAppearance === "aero" ? "#27313D" : "transparent"
            z: -1
        }

        // Flyouts derive their anchor from the hovered ROW, with a separate
        // one-pixel proxy for bottom-edge vertical alignment. Screen geometry
        // is read from the visible row before the flyout becomes visible.
        property string activeFlyoutKey: ""

        function showFlyout(entry, sourceRow) {
            if (root.layoutEditing || root.layoutBusy) return;
            if (entry.kind !== "submenu") return;
            if (flyout.visible && activeFlyoutKey === entry.key
                    && flyout.visualParent === flyoutAnchor) return;
            flyout.visible = false;
            flyout.entries = entry.items || [];
            flyout.screenRect = sourceRow.menuScreen;
            // Plasma side popups center vertically on visualParent. A slim
            // proxy lets the flyout's BOTTOM meet the parent row's bottom.
            flyout.positionAtRow(sourceRow, flyoutAnchor, sourceRow.menuScreen);
            flyout.visualParent = flyoutAnchor;
            flyout.popupDirection = flyout.chooseSide(flyoutAnchor);
            activeFlyoutKey = entry.key;
            flyout.visible = true;
        }

        // Invisible position-only anchor. Keep it outside the ScrollView
        // so the parent row's clipping cannot affect the popup geometry.
        Item {
            id: flyoutAnchor
            width: 1
            height: 1
        }

        SideFlyout {
            id: flyout
            appearance: root.menuAppearance
            onReturnToParent: {
                if (!root.expanded) return;
                if (popup.Window.window) popup.Window.window.requestActivate();
                popup.forceActiveFocus();
            }
            onTriggered: key => {
                flyout.visible = false;
                root.launchItem(key);
            }
            onVisibleChanged: {
                if (!visible) popup.activeFlyoutKey = "";
            }
        }
        Connections {
            target: root
            function onExpandedChanged() {
                if (!root.expanded) {
                    root.powerIsOpen = false;
                    flyout.visible = false;
                    layoutEditor.cancelDrag();
                } else {
                    popup.activeIndex = -1;
                    Qt.callLater(() => {
                        if (!root.expanded) return;
                        if (root.layoutEditing) layoutEditor.forceActiveFocus();
                        else popup.forceActiveFocus();
                    });
                }
            }
            function onLayoutEditingChanged() {
                flyout.visible = false;
                Qt.callLater(() => {
                    if (!root.expanded) return;
                    if (root.layoutEditing) layoutEditor.forceActiveFocus();
                    else popup.forceActiveFocus();
                });
            }
        }

        // Fit the popup to the rows actually displayed. The old fixed 590px
        // preferred height left an empty area below the list when fewer
        // commands were available; moving footer buttons did not fix that.
        // Only scroll when the list is taller than the available screen area.
        readonly property real naturalHeight: {
            // Header margins are 5px each; keep a small inset allowance
            // so the final row is never obscured by theme/rounding effects.
            return menuHeader.implicitHeight + 10
                + Math.max(1, menuDivider.implicitHeight)
                + (root.layoutEditing ? layoutEditor.implicitHeight : menuColumn.implicitHeight)
                + (menuStatusLabel.visible ? menuStatusLabel.implicitHeight : 0)
                + 4;
        }
        readonly property real heightCap: Math.min(590,
            Screen.desktopAvailableHeight > 140
                ? Screen.desktopAvailableHeight - 48 : 590)

        // A submenu edit flyout lives beside its parent inside ONE Plasma popup.
        // Clamp the expanded width to the active desktop's available area.
        Layout.preferredWidth: root.layoutEditing && layoutEditor.flyoutVisible
            ? Math.max(328, Math.min(650, Screen.desktopAvailableWidth - 32)) : 328
        Layout.preferredHeight: Math.max(76, Math.min(heightCap, naturalHeight))
        Layout.minimumWidth: 285
        Layout.minimumHeight: 76

        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            RowLayout {
                id: menuHeader
                Layout.fillWidth: true
                Layout.leftMargin: 12
                Layout.rightMargin: 7
                Layout.topMargin: 5
                Layout.bottomMargin: 5
                spacing: 3
                PC3.Label {
                    Layout.fillWidth: true
                    font.bold: true
                    text: "Power User Menu"
                    color: root.menuAppearance === "aero" ? "#eff3f8" : Kirigami.Theme.textColor
                }
                PC3.ToolButton {
                    id: lockButton
                    icon.name: root.layoutEditing ? "object-unlocked" : "object-locked"
                    icon.color: root.menuAppearance === "aero" ? "#eff3f8" : Kirigami.Theme.textColor
                    text: root.layoutEditing ? "Finish editing layout" : "Unlock menu layout to rearrange items"
                    display: QQC2.AbstractButton.IconOnly
                    Layout.preferredWidth: 29
                    Layout.preferredHeight: 29
                    enabled: !root.layoutBusy && !root.launchPending
                    Accessible.name: text
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.text: text
                    onClicked: LayoutController.toggle(root)
                }
                PC3.ToolButton {
                    id: refreshButton
                    icon.color: root.menuAppearance === "aero" ? "#eff3f8" : Kirigami.Theme.textColor
                    icon.name: "view-refresh"
                    text: "Refresh menu"
                    display: QQC2.AbstractButton.IconOnly
                    Layout.preferredWidth: 29
                    Layout.preferredHeight: 29
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.text: "Refresh menu entries"
                    enabled: !root.layoutEditing && !root.layoutBusy
                    onClicked: { root.commandError = ""; root.fetchMenu(); root.fetchIntegration(); }
                }
                PC3.ToolButton {
                    id: configureButton
                    icon.color: root.menuAppearance === "aero" ? "#eff3f8" : Kirigami.Theme.textColor
                    icon.name: "configure"
                    text: "Configure menu"
                    display: QQC2.AbstractButton.IconOnly
                    Layout.preferredWidth: 29
                    Layout.preferredHeight: 29
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.text: "Add, remove and reorder menu entries"
                    enabled: !root.layoutEditing && !root.layoutBusy
                    onClicked: root.openEditor()
                }
            }
            Kirigami.Separator {
                id: menuDivider
                Layout.fillWidth: true
            }
            LayoutEditor {
                id: layoutEditor
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 6
                Layout.rightMargin: 6
                visible: root.layoutEditing
                draft: root.layoutDraft
                busy: root.layoutBusy
                expired: root.layoutExpired
                palette.window: root.menuAppearance === "aero" ? "#27313D" : Kirigami.Theme.backgroundColor
                palette.base: palette.window
                palette.text: root.menuAppearance === "aero" ? "#eff3f8" : Kirigami.Theme.textColor
                palette.windowText: palette.text
                palette.buttonText: palette.text
                palette.button: root.menuAppearance === "aero" ? "#344659" : Kirigami.Theme.backgroundColor
                palette.highlight: Kirigami.Theme.highlightColor
                palette.highlightedText: Kirigami.Theme.highlightedTextColor
                onEdited: value => root.layoutDraft = value
                onFailed: message => root.layoutStatus = message
                onSaveRequested: LayoutController.save(root)
                onCancelRequested: LayoutController.cancel(root)
                onCloseRequested: root.expanded = false
            }
            QQC2.ScrollView {
                id: menuScroll
                visible: !root.layoutEditing
                enabled: !root.layoutBusy && !root.launchPending
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth
                contentHeight: menuColumn.implicitHeight
                Column {
                    id: menuColumn
                    width: menuScroll.availableWidth
                    spacing: 0
                    Repeater {
                        id: normalRows
                        model: root.visibleEntries
                        delegate: Item {
                            id: menuRow
                            required property var modelData
                            required property int index
                            property var entry: modelData
                            // Screen attached to a visible row in the main Plasma popup.
                            // virtualX/Y also cover non-primary monitors.
                            readonly property rect menuScreen: Qt.rect(
                                Screen.virtualX, Screen.virtualY,
                                Screen.width, Screen.height)
                            width: menuColumn.width
                            height: entry.kind === "separator" ? 13 : 34
                            Kirigami.Separator {
                                anchors.centerIn: parent
                                width: parent.width - 24
                                visible: menuRow.entry.kind === "separator"
                            }
                            Rectangle {
                                anchors.fill: parent
                                anchors.leftMargin: 4
                                anchors.rightMargin: 4
                                radius: 3
                                visible: menuRow.entry.kind !== "separator" && (rowMouse.containsMouse || rowMouse.pressed || popup.activeIndex === menuRow.index)
                                color: Kirigami.Theme.highlightColor
                                opacity: 0.30
                            }
                            RowLayout {
                                visible: menuRow.entry.kind !== "separator"
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 9
                                Kirigami.Icon {
                                    source: menuRow.entry.icon || "application-x-executable"
                                    color: root.menuAppearance === "aero" ? "#eff3f8" : Kirigami.Theme.textColor
                                    Layout.preferredHeight: 18
                                    Layout.preferredWidth: 18
                                    visible: menuRow.entry.kind !== "separator"
                                    opacity: menuRow.entry.enabled === false ? 0.4 : 1
                                }
                                PC3.Label {
                                    Layout.fillWidth: true
                                    text: menuRow.entry.title || ""
                                    color: root.menuAppearance === "aero" ? "#eff3f8" : Kirigami.Theme.textColor
                                    elide: Text.ElideRight
                                    opacity: menuRow.entry.enabled === false ? 0.5 : 1
                                }
                                Kirigami.Icon {
                                    Layout.preferredWidth: 14
                                    Layout.preferredHeight: 14
                                    source: "go-next-symbolic"
                                    color: root.menuAppearance === "aero" ? "#eff3f8" : Kirigami.Theme.textColor
                                    visible: menuRow.entry.kind === "submenu"
                                }
                            }
                            MouseArea {
                                id: rowMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                enabled: menuRow.entry.kind !== "separator" && menuRow.entry.enabled !== false
                                // Prefer right-hand flyouts regardless of
                                // panel edge. Plasma flips left if necessary.
                                onEntered: {
                                    popup.activeIndex = menuRow.index;
                                    if (menuRow.entry.kind === "submenu") {
                                        popup.showFlyout(menuRow.entry, menuRow);
                                    } else {
                                        flyout.visible = false;
                                    }
                                }
                                onClicked: {
                                    if (menuRow.entry.kind === "submenu") {
                                        popup.showFlyout(menuRow.entry, menuRow);
                                    } else {
                                        flyout.visible = false;
                                        root.launchItem(menuRow.entry.key);
                                    }
                                }
                            }
                            Accessible.role: Accessible.MenuItem
                            Accessible.name: menuRow.entry.title || "Separator"
                            Accessible.focused: popup.activeIndex === menuRow.index
                            Accessible.onPressAction: {
                                if (menuRow.entry.enabled === false || menuRow.entry.kind === "separator") return;
                                if (menuRow.entry.kind === "submenu") popup.showFlyout(menuRow.entry, menuRow);
                                else root.launchItem(menuRow.entry.key);
                            }
                        }
                    }
                }
            }
            PC3.Label {
                id: menuStatusLabel
                visible: text.length > 0
                Layout.fillWidth: true
                Layout.leftMargin: 12
                Layout.rightMargin: 12
                text: root.layoutEditing || root.layoutBusy ? root.layoutStatus : root.commandError || root.menuStatus
                color: root.menuAppearance === "aero" ? "#eff3f8" : Kirigami.Theme.textColor
                wrapMode: Text.WordWrap
                opacity: 0.75
            }
        }
        Keys.onPressed: event => {
            if (root.layoutEditing || root.layoutBusy || root.launchPending) return;
            if (event.key === Qt.Key_Up || event.key === Qt.Key_Down) {
                flyout.visible = false;
                activeIndex = LayoutDraft.nextIndex(root.visibleEntries, activeIndex, event.key === Qt.Key_Up ? -1 : 1, false);
                const row = normalRows.itemAt(activeIndex);
                const viewport = menuScroll.contentItem;
                if (row && viewport && typeof viewport.contentY === "number") {
                    if (row.y < viewport.contentY) viewport.contentY = row.y;
                    else if (row.y + row.height > viewport.contentY + menuScroll.availableHeight)
                        viewport.contentY = row.y + row.height - menuScroll.availableHeight;
                }
                event.accepted = true;
            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Right) {
                const row = normalRows.itemAt(activeIndex);
                if (!row || row.entry.enabled === false || row.entry.kind === "separator") return;
                if (row.entry.kind === "submenu") { showFlyout(row.entry, row); flyout.focusFirst(); }
                else if (event.key !== Qt.Key_Right) root.launchItem(row.entry.key);
                event.accepted = true;
            }
        }
        Keys.onEscapePressed: root.expanded = false
    }
}
