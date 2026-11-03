.pragma library

// Default adapter: use only Plasma's published applet contract. No plugin IDs,
// custom window state, process control, or assumptions about a third party.
function closeExpanded(item) {
    if (!item) return false;
    try {
        if (typeof item.expanded !== "boolean") return false;
        if (item.expanded) item.expanded = false;
        return item.expanded === false;
    } catch (e) { return false; }
}

function originalIsOpen(item) {
    if (!item) return false;
    try { return item.expanded === true; } catch (e) { return false; }
}

function originalIsVisiblyOpen(item) { return originalIsOpen(item); }

function closeOriginal(item) {
    const ok = closeExpanded(item);
    return {ok:ok, mode:ok ? "plasma-expanded" : "unsupported-launcher"};
}

function activate(applet) {
    if (!applet || typeof applet.activated !== "function") return false;
    applet.activated();
    return true;
}

function describeState(item, applet) {
    let state = "plugin=" + (applet ? String(applet.pluginName || "unknown") : "none");
    try {
        state += " expanded=" + (item ? String(item.expanded) : "no-item");
        state += " activated=" + (applet ? typeof applet.activated : "no-applet");
    } catch (e) { state += " inspection-error=" + String(e); }
    return state;
}

function chooseIcon(applet, mode, custom, fallback) {
    const defaultIcon = fallback || "start-here-kde";
    if (mode === "custom") return custom || defaultIcon;
    if (applet) {
        try {
            const icon = applet.icon;
            // Plasma may expose a theme-name string or a QIcon object.
            if (typeof icon === "string" && icon.trim()) return icon;
            if (icon !== null && typeof icon === "object") return icon;
        } catch (e) {}
    }
    return defaultIcon;
}
