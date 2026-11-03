.pragma library

// AppGrid 1.9.x's full-screen overlay intercepts the pointer over Plasma's
// panel. Use its existing Q_INVOKABLE setInputRect(QWindow*, x, y, w, h) to
// exclude only the panel edge while keeping the center grid interactive.
// Pure geometry helper: Qt/Wayland calls remain in the widget's main.qml.
function inputRect(width, height, edge, thickness, launcherPanel) {
    if (!Number.isFinite(width) || !Number.isFinite(height) ||
            width < 320 || height < 320 || !Number.isFinite(thickness) ||
            thickness < 16) return null;
    width = Math.floor(width);
    height = Math.floor(height);
    const axis = edge === "left" || edge === "right" ? width : height;
    const cut = Math.ceil(thickness + 8);
    // Refuse an unexpectedly thick panel (e.g. a bad window geometry result).
    if (cut > Math.min(160, axis * 0.22)) return null;
    let r = null;
    if (edge === "bottom") r = {x:0, y:0, w:width, h:height-cut, cut:cut};
    else if (edge === "top") r = {x:0, y:cut, w:width, h:height-cut, cut:cut};
    else if (edge === "left") r = {x:cut, y:0, w:width-cut, h:height, cut:cut};
    else if (edge === "right") r = {x:0, y:0, w:width-cut, h:height, cut:cut};
    if (!r || r.w < 250 || r.h < 250) return null;

    // Never make an actual portion of AppGrid's interactive grid unreachable.
    // AppGrid 1.9.6 exports the content's `panelRect` in its GridWindow.
    const p = launcherPanel;
    if (p && [p.x,p.y,p.w,p.h].every(Number.isFinite) && p.w > 0 && p.h > 0) {
        if (p.x < r.x || p.y < r.y || p.x + p.w > r.x+r.w || p.y+p.h > r.y+r.h)
            return null;
    }
    return r;
}
