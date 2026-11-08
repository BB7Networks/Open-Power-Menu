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
