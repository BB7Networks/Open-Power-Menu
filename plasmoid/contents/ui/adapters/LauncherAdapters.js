.pragma library
.import "PlasmaLauncher.js" as Plasma
.import "AppGridLauncher.js" as AppGrid

// The public contract used by the Start button. Generic Plasma is the default;
// only explicitly recognized nonstandard launchers get specialized handling.
function kind(applet) {
    return AppGrid.matches(applet) ? "appgrid-center" : "plasma";
}

function closeOriginal(item, applet, hideStandalone) {
    return kind(applet) === "appgrid-center"
        ? AppGrid.closeOriginal(item, applet, hideStandalone)
        : Plasma.closeOriginal(item, applet);
}

function originalIsOpen(item, applet) {
    return kind(applet) === "appgrid-center"
        ? AppGrid.originalIsOpen(item) : Plasma.originalIsOpen(item);
}

function originalIsVisiblyOpen(item, applet) {
    return kind(applet) === "appgrid-center"
        ? AppGrid.originalIsVisiblyOpen(item) : Plasma.originalIsVisiblyOpen(item);
}

function activate(applet) { return Plasma.activate(applet); }

function deferSignalClose(applet) { return kind(applet) === "appgrid-center"; }

function chooseIcon(applet, mode, custom, fallback) {
    return Plasma.chooseIcon(applet, mode, custom, fallback);
}

function describeState(item, applet) {
    return kind(applet) === "appgrid-center"
        ? AppGrid.describeState(item, applet) : Plasma.describeState(item, applet);
}

// Keep verbose diagnostics limited to the unusual adapter that needs them.
function trace(label, item, applet, context) {
    AppGrid.trace(label, item, applet, context);
}

function traceRequest(root, label, callbackEpoch) {
    const plan = root.selectedLauncherPlan;
    if (!plan || kind(plan.applet) !== "appgrid-center") return;
    trace(label, plan.item, plan.applet, {
        epoch: root.menuSwitchEpoch, callbackEpoch: callbackEpoch,
        requested: root.requestedMenu, powerOpen: root.expanded,
        pendingLauncher: root.pendingLauncherEpoch, pendingPower: root.pendingPowerEpoch,
        awaitingClose: root.awaitingAsyncClose, maskActive: root.maskActive,
        hideRequested: root.hideOriginalLauncherRequested, draft: !!root.layoutDraft
    });
}

function traceDismissal(result, item, applet) {
    if (kind(applet) !== "appgrid-center") return;
    trace("dismissal", item, applet, {mode:result.mode, forcedHidden:result.forceHidden === true});
}

function requestAsyncClose(applet, send, isCurrent, done) {
    if (kind(applet) === "appgrid-center")
        return AppGrid.requestStandaloneHide(send, isCurrent, done);
    done(false, "Selected launcher has no asynchronous close adapter");
}
