// SPDX-License-Identifier: MIT
.pragma library
function iconSize(preset, fontHeight) {
    return Math.round((preset === 'small' ? 14 : preset === 'large' ? 24 : 18) * Math.max(1, fontHeight / 18));
}
function rowHeight(density, fontHeight, icon) {
    return Math.max(density === 'compact' ? 28 : density === 'comfortable' ? 42 : 34,
                    Math.max(fontHeight, icon) + (density === 'compact' ? 6 : density === 'comfortable' ? 16 : 10));
}
function menuWidth(preset, standard, fontHeight, available) {
    const preferred = (preset === 'narrow' ? standard * .82 : preset === 'wide' ? standard * 1.35 : standard) * Math.max(1, fontHeight / 18);
    return Math.min(preferred, available > 0 ? Math.max(1, available - 16) : preferred);
}

// All dimensions are Qt logical pixels; never multiply these by screen DPR.
function menuHeight(mode, custom, natural, available, padding) {
    const desired = mode === "custom" ? custom : natural;
    const limit = available > 0 ? Math.max(1, available - padding - 8) : desired;
    return Math.max(1, Math.min(Math.ceil(desired), Math.floor(limit)));
}
function workArea(screen, available) {
    if (available.width > 0 && available.height > 0)
        return {x: screen.x + available.x, y: screen.y + available.y,
                width: available.width, height: available.height};
    return screen;
}
function hasHints(entries) {
    return (entries || []).some(entry => !!entry.access_hint);
}
