.pragma library

// Only the center AppGrid plugin needs this adapter. AppGrid Panel and every
// other launcher use the generic Plasma adapter automatically.
const PLUGIN_ID = "dev.xarbit.appgrid";

function matches(applet) {
    try { return !!applet && String(applet.pluginName || "") === PLUGIN_ID; }
    catch (e) { return false; }
}

// AppGrid Center 1.9.x embeds a GridWindow in its QML applet; a later variant
// uses a standalone D-Bus server. Never confuse the two closing mechanisms.
function hasLegacyWindow(item) {
    if (!item) return false;
    try {
        return typeof item.gridOpen === "boolean" ||
               (item.gridWindow && typeof item.gridWindow.visible === "boolean");
    } catch (e) { return false; }
}

function originalIsOpen(item) {
    if (!item) return false;
    try {
        if (typeof item.gridOpen === "boolean") return item.gridOpen;
        if (item.gridWindow && typeof item.gridWindow.visible === "boolean")
            return item.gridWindow.visible;
        return item.expanded === true;
    } catch (e) { return false; }
}

function originalIsVisiblyOpen(item) {
    if (!item) return false;
    try {
        if (item.gridWindow && typeof item.gridWindow.visible === "boolean" &&
                item.gridWindow.visible) return true;
        return originalIsOpen(item);
    } catch (e) { return originalIsOpen(item); }
}

// AppGrid 1.9.x can be logically closed while an exit animation is still
// painted. Only touch the window owned by the explicitly selected AppGrid item.
function hideOwnedAppGridWindow(item) {
    try {
        if (!item || !item.gridWindow ||
                typeof item.gridWindow.visible !== "boolean" ||
                item.gridWindow.visible !== true) return false;
        item.gridWindow.visible = false;
        return item.gridWindow.visible === false;
    } catch (e) { return false; }
}

function closeOriginal(item, applet, hideStandalone) {
    if (!matches(applet)) return {ok:false, mode:"not-appgrid"};
    if (hasLegacyWindow(item)) {
        try {
            const open = item.gridOpen === true ||
                (typeof item.gridOpen !== "boolean" && item.gridWindow && item.gridWindow.visible === true);
            if (!open) {
                // This is in-process AppGrid: don't probe a nonexistent daemon.
                if (typeof item.closeWindow === "function") {
                    try { item.closeWindow(); } catch (e) {}
                }
                const forceHidden = hideOwnedAppGridWindow(item);
                return {ok:true, mode:"appgrid-local-closed", forceHidden:forceHidden};
            }
            let direct = false;
            if (typeof item.closeWindow === "function") {
                try { item.closeWindow(); direct = true; } catch (e) { direct = false; }
            }
            if (item.gridOpen === true) {
                // The activation signal toggles AppGrid; use only when known OPEN.
                if (applet && typeof applet.activated === "function") {
                    try {
                        applet.activated();
                        return {ok:true, mode:"appgrid-activation-fallback"};
                    } catch (e) {}
                }
                return {ok:false, mode:"appgrid-close-failed"};
            }
            if (direct) {
                const forceHidden = hideOwnedAppGridWindow(item);
                return {ok:true, mode:"appgrid-native-close", forceHidden:forceHidden};
            }
            return {ok:false, mode:"appgrid-unavailable-close"};
        } catch (e) { return {ok:false, mode:"appgrid-close-exception"}; }
    }
    // Newer standalone AppGrid: Hide is idempotent; never use Toggle.
    if (typeof hideStandalone === "function") {
        hideStandalone();
        return {ok:true, mode:"appgrid-daemon-hide"};
    }
    return {ok:false, mode:"appgrid-daemon-unavailable"};
}

function supportsPanelPassThrough(plan) {
    try {
        return !!(plan && matches(plan.applet) && plan.item &&
            plan.item.gridOpen === true &&
            typeof plan.applet.setInputRect === "function");
    } catch (e) { return false; }
}

// A zero-by-zero mask restores AppGrid's full-screen input region.
// This is delegated to its QML adapter, not the generic launcher core.
function describeState(item, applet) {
    let state = "plugin=" + (applet ? String(applet.pluginName || "unknown") : "none");
    try {
        state += " gridOpen=" + (item ? String(item.gridOpen) : "no-item");
        state += " closeWindow=" + (item ? typeof item.closeWindow : "no-item");
        state += " gridWindowVisible=" + (item && item.gridWindow ? String(item.gridWindow.visible) : "unavailable");
        state += " expanded=" + (item ? String(item.expanded) : "no-item");
        state += " activated=" + (applet ? typeof applet.activated : "no-applet");
    } catch (e) { state += " inspection-error=" + String(e); }
    return state;
}

// Never auto-activate a dormant D-Bus service merely to CLOSE a launcher.
// send(service, path, iface, method, args, callback) is the generic host's
// existing async D-Bus transport; isCurrent guards stale click replies.
function requestStandaloneHide(send, isCurrent, done) {
    send("org.freedesktop.DBus", "/org/freedesktop/DBus",
         "org.freedesktop.DBus", "NameHasOwner", [PLUGIN_ID], (ownerOk, ownerValue) => {
        if (!isCurrent()) return;
        if (!ownerOk) {
            done(false, "Could not check whether AppGrid's standalone daemon is running");
            return;
        }
        const owned = ownerValue === true || String(ownerValue).toLowerCase() === "true";
        console.info("Open Power Menu: AppGrid standalone bus owner:", owned);
        if (!owned) {
            done(true, "not-running");
            return;
        }
        send(PLUGIN_ID, "/Standalone", "dev.xarbit.appgrid.Standalone", "Hide", [], (ok, value) => {
            if (!isCurrent()) return;
            console.info("Open Power Menu: AppGrid standalone Hide:", ok ? "acknowledged" : "failed");
            done(!!ok, ok ? "hidden" : "AppGrid standalone Hide failed; Power Menu stayed closed");
        });
    });
}
