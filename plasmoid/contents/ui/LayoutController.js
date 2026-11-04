.pragma library
.import "LayoutDraft.js" as Draft

function call(root, method, args, done) {
    root.send("org.openpowermenu.Service", "/OpenPowerMenu", "org.openpowermenu.Service", method, args, done);
}
function response(ok, value) {
    if (!ok) return {ok: false, message: "Backend unavailable. Your draft is retained. Run open-power-menu --check; install the complete package with bash install.sh if needed."};
    try { return JSON.parse(String(value)); }
    catch (e) { return {ok: false, message: "Could not read the backend response. Your draft is retained."}; }
}
function begin(root) {
    if (root.layoutBusy || root.layoutDraft) return;
    const epoch = ++root.layoutEpoch;
    root.menuFetchEpoch++;
    root.fetching = false;
    root.commandError = "";
    root.layoutBusy = true;
    root.layoutStatus = "Loading the complete layout…";
    root.layoutExpired = false;
    call(root, "BeginLayoutEdit", [], (ok, value) => {
        if (epoch !== root.layoutEpoch) return;
        root.layoutBusy = false;
        const result = response(ok, value);
        if (!result.ok) { root.layoutStatus = result.message; root.menuStatus = result.message; return; }
        try {
            root.layoutDraft = Draft.start(result);
            root.layoutStatus = "All entries are shown. Commands stay inactive while editing.";
        } catch (e) {
            root.layoutStatus = "Could not load this layout. Update the complete installation and try again.";
            root.menuStatus = root.layoutStatus;
        }
    });
}
function cancel(root) {
    if (root.layoutBusy) return; // Do not race a save already being committed.
    const token = root.layoutDraft ? root.layoutDraft.token : "";
    ++root.layoutEpoch;
    root.layoutDraft = null;
    root.layoutExpired = false;
    root.layoutStatus = "";
    if (token) call(root, "CancelLayoutEdit", [token], () => {});
    root.fetchMenu();
}
function toggle(root) {
    if (root.layoutBusy) return;
    if (!root.layoutDraft) { begin(root); return; }
    if (!Draft.dirty(root.layoutDraft)) { cancel(root); return; }
    root.layoutStatus = "Choose Save layout or Cancel to finish editing. Your changes are still here.";
}
function save(root) {
    if (!root.layoutDraft || root.layoutBusy || root.layoutExpired) return;
    const epoch = root.layoutEpoch;
    root.layoutBusy = true;
    root.layoutStatus = "Saving layout…";
    call(root, "SaveLayoutEdit", [root.layoutDraft.token, JSON.stringify(Draft.references(root.layoutDraft.entries))], (ok, value) => {
        if (epoch !== root.layoutEpoch) return;
        root.layoutBusy = false;
        const result = response(ok, value);
        if (!result.ok) {
            root.layoutStatus = result.message;
            root.layoutExpired = result.code === "expired";
            return;
        }
        ++root.layoutEpoch;
        root.layoutDraft = null;
        root.layoutStatus = "";
        root.layoutExpired = false;
        root.fetchMenu();
    });
}
function keep(root) {
    if (!root.layoutDraft || root.layoutBusy || root.layoutExpired) return;
    const epoch = root.layoutEpoch;
    call(root, "KeepLayoutEdit", [root.layoutDraft.token], (ok, value) => {
        if (epoch !== root.layoutEpoch || !root.layoutDraft) return;
        const result = response(ok, value);
        if (!result.ok) {
            root.layoutStatus = result.message;
            root.layoutExpired = result.code === "expired";
        }
    });
}
