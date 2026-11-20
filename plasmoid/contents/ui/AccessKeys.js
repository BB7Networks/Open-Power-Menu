// Local menu access keys; the native model owns assignments and collision validation.
// Physical press/release admission belongs to the shared native InputGuard,
// before QML delivery. This per-row lookup must never rearm keys on focus change.
.pragma library
function index(entries, text, modifiers, repeat) {
    if (repeat || modifiers !== 0) return -1;
    const key = String(text).toUpperCase();
    if (!/^[A-Z0-9]$/.test(key)) return -1;
    let match = -1;
    for (let i = 0; i < entries.length; ++i) {
        if (entries[i].access_key !== key) continue;
        if (match !== -1) return -1;
        match = i;
    }
    return match >= 0 && entries[match].enabled !== false && entries[match].kind !== "separator" ? match : -1;
}
function editable(item) {
    return !!item && typeof item.text === "string" && typeof item.cursorPosition === "number";
}
