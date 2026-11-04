.pragma library

// Presentation-only hierarchy. Executable definitions stay in the backend.
function references(entries) {
    return entries.map(entry => entry.kind === "submenu"
        ? {id: entry.id, items: references(entry.items)} : {id: entry.id});
}
function start(response) {
    return {token: response.token, entries: response.entries,
        original: JSON.stringify(references(response.entries)), parentId: "", selectedId: ""};
}
function dirty(draft) {
    return !!draft && JSON.stringify(references(draft.entries)) !== draft.original;
}
function find(entries, id, parentId) {
    for (let index = 0; index < entries.length; index++) {
        const entry = entries[index];
        if (entry.id === id) return {entry: entry, container: entries, index: index, parentId: parentId || ""};
        if (entry.kind === "submenu") {
            const found = find(entry.items, id, entry.id);
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
function move(draft, id, parentId, beforeId) {
    const entries = JSON.parse(JSON.stringify(draft.entries));
    const source = find(entries, id);
    const destination = children(entries, parentId);
    if (!source || !destination)
        throw new Error("Choose an existing entry and destination.");
    if (parentId === id || (source.entry.kind === "submenu" && find(source.entry.items, parentId)))
        throw new Error("A submenu cannot move into itself or one of its children.");
    if (beforeId === id && source.container === destination) return draft;
    if (beforeId && !destination.some(entry => entry.id === beforeId))
        throw new Error("Choose a position inside the destination menu.");
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
