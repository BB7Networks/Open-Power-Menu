.pragma library

// Presentation-only hierarchy. Executable definitions stay in the backend.
function references(entries) {
    return entries.map(entry => entry.kind === "submenu"
        ? {id: entry.id, items: references(entry.items)} : {id: entry.id});
}
function start(response) {
    return {token: response.token, entries: response.entries,
        original: JSON.stringify(references(response.entries)), parentId: "", selectedId: "", views: {}};
}
// UI-only memory belongs to the applet's draft, never to the saved references.
function rememberView(draft, parentId, view) {
    if (!draft.views) draft.views = {};
    draft.views[parentId || ""] = view;
}
function view(draft, parentId) {
    return draft && draft.views ? draft.views[parentId || ""] : null;
}
function selection(draft, parentId, fallback) {
    const saved = view(draft, parentId);
    const items = children(draft.entries, parentId) || [];
    return saved && items.some(entry => entry.id === saved.selectedId) ? saved.selectedId
        : items.some(entry => entry.id === fallback) ? fallback : items.length ? items[0].id : "";
}
function dirty(draft) {
    return !!draft && JSON.stringify(references(draft.entries)) !== draft.original;
}
function find(entries, id, parentId, depth) {
    for (let index = 0; index < entries.length; index++) {
        const entry = entries[index];
        if (entry.id === id) return {entry: entry, container: entries, index: index, parentId: parentId || "", depth: depth || 0};
        if (entry.kind === "submenu") {
            const found = find(entry.items, id, entry.id, (depth || 0) + 1);
            if (found) return found;
        }
    }
    return null;
}
function children(entries, id) {
    if (!id) return entries;
    const found = find(entries, id);
    return found && found.entry.kind === "submenu" ? found.entry.items : null;
}
function valid(entries, depth) {
    if ((depth || 0) > 8 || entries.length > 200) return false;
    return entries.every(entry => entry.kind !== "submenu" || valid(entry.items, (depth || 0) + 1));
}
function height(entry) {
    return entry.kind === "submenu" ? 1 + entry.items.reduce((maximum, child) => Math.max(maximum, height(child)), 0) : 0;
}
function canEnter(draft, id, parentId) {
    const source = find(draft.entries, id);
    return !!source && !!children(draft.entries, parentId) && parentId !== id
        && !(source.entry.kind === "submenu" && find(source.entry.items, parentId));
}
function moveError(draft, id, parentId, beforeId) {
    const source = find(draft.entries, id);
    const destination = children(draft.entries, parentId);
    if (!source || !destination)
        return "Choose an existing entry and destination.";
    if (parentId === id || (source.entry.kind === "submenu" && find(source.entry.items, parentId)))
        return "A submenu cannot move into itself or one of its children.";
    if (beforeId && !destination.some(entry => entry.id === beforeId))
        return "Choose a position inside the destination menu.";
    const parent = parentId ? find(draft.entries, parentId) : null;
    if ((parent ? parent.depth + 1 : 0) + height(source.entry) > 8
            || destination.length + (destination === source.container ? 0 : 1) > 200)
        return "Keep at most eight submenu levels and 200 entries per menu.";
    return "";
}
function move(draft, id, parentId, beforeId) {
    const error = moveError(draft, id, parentId, beforeId);
    if (error) throw new Error(error);
    const entries = JSON.parse(JSON.stringify(draft.entries));
    const source = find(entries, id);
    const destination = children(entries, parentId);
    if (beforeId === id && source.container === destination) return draft;
    source.container.splice(source.index, 1);
    const index = beforeId ? destination.findIndex(entry => entry.id === beforeId) : destination.length;
    destination.splice(index, 0, source.entry);
    if (!valid(entries, 0))
        throw new Error("Keep at most eight submenu levels and 200 entries per menu.");
    return Object.assign({}, draft, {entries: entries, parentId: parentId || "", selectedId: id});
}
function select(draft, parentId, id) {
    return Object.assign({}, draft, {parentId: parentId || "", selectedId: id || ""});
}
function nextIndex(entries, current, direction, editing) {
    if (!entries.length) return -1;
    let index = current;
    if (index < 0) index = direction > 0 ? -1 : 0;
    for (let count = 0; count < entries.length; count++) {
        index = (index + direction + entries.length) % entries.length;
        if (editing || (entries[index].kind !== "separator" && entries[index].enabled !== false)) return index;
    }
    return -1;
}
