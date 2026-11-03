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

function chooseIcon(applet, mode, custom, fallback) {
    return Plasma.chooseIcon(applet, mode, custom, fallback);
}

function describeState(item, applet) {
    return kind(applet) === "appgrid-center"
        ? AppGrid.describeState(item, applet) : Plasma.describeState(item, applet);
}

// Keep verbose diagnostics limited to the unusual adapter that needs them.
function trace(label, item, applet) {
    if (kind(applet) !== "appgrid-center") return;
    console.info("Open Power Menu: " + label + ":", describeState(item, applet));
}

function traceDismissal(result, item, applet) {
    if (kind(applet) !== "appgrid-center") return;
    console.info("Open Power Menu: launcher dismissal:", result.mode,
                 "forcedHidden=" + String(result.forceHidden === true),
                 describeState(item, applet));
}

function requestAsyncClose(applet, send, isCurrent, done) {
    if (kind(applet) === "appgrid-center")
        return AppGrid.requestStandaloneHide(send, isCurrent, done);
    done(false, "Selected launcher has no asynchronous close adapter");
}
