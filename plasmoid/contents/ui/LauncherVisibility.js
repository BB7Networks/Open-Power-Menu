.pragma library

// Launcher-independent, opt-in runtime visibility using Plasma's HiddenStatus.
// Plasma's panel AppletContainer and LayoutManager already react to this status:
// the container and applet item are removed from the visible layout while the
// underlying applet remains registered. No direct writes to item geometry,
// opacity, appletsrc, or launcher's visible/enabled/expanded properties.
// KDE upstream: plasma-desktop/containments/panel/AppletContainer.qml
// KDE upstream: plasma-desktop/containments/panel/LayoutManager.js

var KNOWN_LAUNCHER_IDS = [
    "org.kde.plasma.kickoff", "org.kde.plasma.kicker", "org.kde.plasma.kickerdash",
    "dev.xarbit.appgrid", "dev.xarbit.appgrid.panel"
];

function idOf(applet) {
    return applet ? Number(applet.id) : -1;
}

function isLauncherCandidate(applet) {
    if (!applet) return false;
    var plugin = String(applet.pluginName || "").toLowerCase();
    var title = String(applet.title || "").toLowerCase();
    if (KNOWN_LAUNCHER_IDS.indexOf(plugin) !== -1) return true;
    var words = (plugin.replace(/[._-]/g, " ") + " " + title).toLowerCase();
    var markers = ["appgrid", "kickoff", "kicker", "application launcher",
                   "application dashboard", "start menu", "startmenu",
                   "launcher widget", "launcher menu", "application menu", "launcher"];
    for (var i = 0; i < markers.length; i++) {
        if (words.indexOf(markers[i]) !== -1) return true;
    }
    return false;
}

function findOriginal(applets, selfId, requestedId) {
    if (!applets) throw new Error("Plasma containment applets are not accessible");
    var matches = [];
    for (var i = 0; i < applets.length; ++i) {
        var candidate = applets[i];
        if (!candidate || idOf(candidate) === Number(selfId)) continue;
        if (requestedId > 0 ? idOf(candidate) === requestedId : isLauncherCandidate(candidate))
            matches.push(candidate);
    }
    if (matches.length !== 1) {
        if (requestedId > 0)
            throw new Error("Selected widget #" + requestedId + " not found on this panel");
        throw new Error("Cannot auto-select a unique launcher on this panel; select its widget ID in Configure");
    }
    return matches[0];
}

function isOurContainment(node, ourApplet, selfId, containmentId, root) {
    if (!node || typeof node.itemFor !== "function") return false;
    try {
        var ownItem = node.itemFor(ourApplet);
        if (!ownItem) return false;
        if (ownItem === root) return true;
        // Some Plasma versions expose a wrapper item rather than the exact
        // QML root object. Match both containment and the applet instance.
        var owner = node.plasmoid;
        var instance = ownItem.plasmoid;
        return owner && instance && Number(owner.id) === Number(containmentId)
            && Number(instance.id) === Number(selfId);
    } catch (e) {
        return false;
    }
}

function findContainmentItem(root, ourApplet, selfId, containmentId) {
    var node = root;
    for (var depth = 0; node && depth < 24; ++depth) {
        if (isOurContainment(node, ourApplet, selfId, containmentId, root)) return node;
        node = node.parent;
    }
    // In Plasma 6 a plasmoid's QML root frequently has no parent. Its panel
    // ContainmentItem is still in the same QQuickWindow visual scene graph.
    var win = null;
    try { win = root.Window.window; } catch (e) {}
    if (!win) try { win = root.window; } catch (e) {}
    if (!win || !win.contentItem)
        throw new Error("Panel scene is unavailable (run on the actual panel, not plasmawindowed)");
    var queue = [win.contentItem];
    var examined = 0;
    for (var head = 0; head < queue.length && examined < 2500; ++head) {
        node = queue[head];
        examined++;
        if (isOurContainment(node, ourApplet, selfId, containmentId, root))
            return node;
        var children = node && node.children;
        if (children && children.length) {
            for (var j = 0; j < children.length; j++) queue.push(children[j]);
        }
    }
    throw new Error("Could not find the panel ContainmentItem in Plasma's QML scene");
}

function findPanelContainer(appletItem, containment) {
    // KDE panel's LayoutManager.addApplet() inserts the PlasmoidItem into its
    // AppletContainer (a Loader with isAppletContainer=true).
    // Verify that this is genuinely the panel's layout-managed wrapper.
    var candidate = appletItem ? appletItem.parent : null;
    for (var depth = 0; candidate && candidate !== containment && depth < 5; depth++) {
        if (candidate.isAppletContainer === true && candidate.applet === appletItem)
            return candidate;
        candidate = candidate.parent;
    }
    throw new Error("Selected applet has no KDE panel container; it remains visible");
}

function prepare(root, applets, ourApplet, selfId, containmentId, selectedId) {
    var requestedId = Number(selectedId || 0);
    if (!Number.isInteger(requestedId) || requestedId < 0)
        throw new Error("Invalid launcher widget ID");
    var selected = findOriginal(applets, selfId, requestedId);
    var containment = findContainmentItem(root, ourApplet, selfId, containmentId);
    var item = containment.itemFor(selected);
    if (!item)
        throw new Error("Selected launcher has no active Plasma item");
    var container = findPanelContainer(item, containment);
    if (typeof selected.status !== "number")
        throw new Error("Selected launcher does not expose Plasma's status property");
    return {applet: selected, item: item, container: container, panel: containment};
}

// The QML Binding in main.qml requests PlasmaCore.Types.HiddenStatus (=6).
// Panel main.qml and AppletContainer.qml derive item/container visibility
// from applet.status, so no fake 1px slot or compactRepresentation is needed.
function didHide(plan, expectedStatus) {
    if (!plan || !plan.applet || !plan.item || !plan.container) return false;
    if (plan.applet.status !== expectedStatus) return false;
    // Plasma deliberately shows otherwise hidden applets while configuring
    // panels. That is not a hide failure; returning from edit mode hides it.
    try {
        var panel = plan.applet.containment;
        if (panel && panel.corona && panel.corona.editMode) return true;
        if (panel && panel.userConfiguring) return true;
    } catch (e) {}
    return plan.item.visible === false && plan.container.visible === false;
}
