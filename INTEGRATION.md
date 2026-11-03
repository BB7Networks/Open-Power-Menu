# Native launcher flicker refinement — v0.4.15

On a normal Plasma application launcher (such as Kickoff), activation can
change the applet status independently of Open Power Menu. v0.4.14 guarded
the status but used `Qt.callLater`, which can permit one render turn between
Plasma showing the original icon and our hide repair. The new generic repair
changes the reversible `Binding.value` dependency synchronously inside the
applet's `statusChanged` signal. There are no `Item.visible`, size-hint,
opacity, or applet-layout writes. The original binding/value remains
restorable when the user disables the hide preference or removes OPM.

The five-second editor settings poll now checks the panel's applet list and
reuses the same selected object, avoiding unnecessary `itemFor`/scene graph
lookup while the popup is being created. A real target change or lost item
continues to use the existing restore-and-resolve path.

This is an informed fix, not yet confirmed live; mock tests cannot
establish one-frame compositor timing. AppGrid's full-screen overlay adapter
is unchanged.

# Generic Plasma native launcher hide guard — v0.4.14

`main.qml` owns the reversible `Binding` for the selected applet's status.
After the initial hide verifies, polling the editor preference no longer
releases that Binding when the selected applet is unchanged. A native
`statusChanged` handler requests deferred re-evaluation of the same Binding,
which is invalidated on disable/selection changes and bounded to avoid
infinite loops. This is generic and does not affect the AppGrid adapter or
Wayland pointer mask. The first hide still uses `LauncherVisibility.didHide()`
to verify the panel actually hides the widget, with the existing safe fallback.

---

# Current integration (v0.4.13)

As of 0.4.13, `main.qml` orchestrates launcher activation, mutually exclusive
menu handoffs, user interface, and a **generic, reversible** Plasma `HiddenStatus`
binding. The adapter registry selects the default Plasma behavior unless the
chosen applet is explicitly `dev.xarbit.appgrid` Center. The AppGrid-specific
window closing, standalone owner check / Hide, and Wayland input region now
live in `plasmoid/contents/ui/adapters/`.

The project **already supported generic launcher selection** before this
release. 0.4.13 is not a new launcher manager; it is a code separation only.
See [ADAPTERS.md](ADAPTERS.md) for the module contract and safe extension path.

---

# v0.4.11 — Why right-click was not reaching the widget

The actual live trace: `launcher after left-click ... gridOpen=true ...
windowVisible=true`, then AppGrid's `gridOpenChanged` to false, but **no**
`launcher before right-click`. The user's right click is caught by AppGrid's
full-screen Wayland overlay (which paints a dim background and includes a
full-window MouseArea), not the panel Start button.

Upstream source (tag v1.9.6):
- `package/contents/ui/views/GridWindow.qml`: window width and height match the
  whole screen; outside clicks are handled by a full-window MouseArea.
- `src/appgridplugin.h` / `.cpp`: Q_INVOKABLE `setInputRect(QWindow*, ...)`
  wraps `QWindow::setMask(QRegion)`; on Wayland it changes wl_surface pointer
  input regions. A zero rectangle restores full input, used by AppGrid itself
  after drag-and-drop.

In this release, OPM applies a single rectangular region to the running
**selected AppGrid instance's owned** GridWindow. This is not a hardcoded
screen region: it derives from the live window dimensions, Plasma panel edge,
and panel thickness, checks for screen mismatch, and refuses to mask any part
of AppGrid's visible centered grid. The region excludes the strip occupied
by the panel, making the panel mouse-reachable while AppGrid remains visible.
It is applied only when AppGrid is open and its original button is already
hidden using the existing opt-in HiddenStatus integration. It is reset when
closing or disabling, and never overrides AppGrid's drag-and-drop input mask.

The adapted window remains owned by AppGrid. No source files, appletsrc,
config, daemon, icon or launcher state are modified. Wayland compositor
behavior still requires verification on the user's desktop.

---

# v0.4.10: AppGrid 1.9.6 close/trace update

The installed `plasma6-applets-appgrid 1.9.6-1` is a compiled QML applet.
Its window is created in-process from `package/variants/center/main.qml`;
it stores the actual `GridWindow` in the root object's `gridWindow` property.
`closeWindow()` changes `gridOpen` to false immediately but `GridWindow.closeGrid()`
can defer hiding the QML window until its close animation finishes.
On an explicit request to switch to Power Menu, this version calls the native
closeWindow first and, if that same owned window is still visible, sets
`gridWindow.visible=false`. No applet config or files are touched.

We also log pre-action state for both buttons, because v0.4.9 logged only the
post-close state and could not establish the before-state. If `gridOpen=false`
and `gridWindow.visible=false` already before right-click, there may be a
second/untracked launcher window; do not guess or attempt to close an unknown
window by process name or PID.

# Plasma launcher integration: HiddenStatus and exclusive popups (experimental, v0.4.7)

## Why v0.4.3 could not hide widget 59

On the reported Manjaro Plasma panel, the selection is correct: panel 2, AppGrid widget 59, `hide_original_launcher=true`. The old implementation required `compactRepresentationItem` and writable `Layout` hints. The supplied errors demonstrate that this assumption fails for AppGrid. The opacity/one-pixel mask is **removed** in v0.4.4.

## Actual upstream Plasma panel behavior

KDE's panel already has a native hide mechanism, `PlasmaCore.Types.HiddenStatus` (enum value 6).

- `plasma-desktop/containments/panel/LayoutManager.js`, `addApplet()`: binds the applet item's `visible` property to its applet's status. Hidden applets remain accessible through the panel configuration interface.
- `plasma-desktop/containments/panel/AppletContainer.qml`: binds the *layout container's* `visible` to the same `status`; QtQuick.Layouts ignores invisible containers. This prevents both a visible icon and a blank panel slot.
- `plasma-workspace/shell/shellcorona.cpp`, `ShellCorona::activateLauncherMenu()`: selects applets that provide `org.kde.plasma.launchermenu` and emits `activated()`. It does not exclude applets whose `status` is `HiddenStatus`.
- `api.kde.org/plasma-types.html`: documents `HiddenStatus`.

Source URLs (the Plasma 6 code reviewed for this release):

- https://github.com/KDE/plasma-desktop/blob/master/containments/panel/LayoutManager.js
- https://github.com/KDE/plasma-desktop/blob/master/containments/panel/AppletContainer.qml
- https://github.com/KDE/plasma-workspace/blob/master/shell/shellcorona.cpp
- https://api.kde.org/plasma-types.html
- https://doc.qt.io/qt-6/qml-qtqml-binding.html

## How the hiding mechanism operates (retained from v0.4.4)

The editor retains the checkbox and launcher-appId selection from v0.4.3. The existing `menu.json` is not migrated or overwritten by the installer.

On a running **standard Plasma panel** (not `plasmawindowed`), the Open Power Menu widget finds its own `ContainmentItem` and locates the chosen applet **only within that panel**. It verifies that the applet has a KDE panel `AppletContainer` before applying a single QML `Binding` to the applet's `status` property, setting it to `HiddenStatus`. The *hiding binding* does not manipulate `visible`, `opacity`, `enabled`, `expanded`, icon geometry, or saved Plasma settings. In v0.4.5, when right-click explicitly requests the Power User menu, the popup-coordination logic independently sets the selected launcher's **runtime `AppletQuickItem.expanded`** to `false` to close its open popup. No stored settings are changed. Qt's `Binding.RestoreBindingOrValue` is used so disabling the option restores the applet's original status or binding rather than overwriting its original QML logic.

After 350ms the widget checks that the applet is hidden *and* its panel container is invisible (except while the panel is in edit mode, where Plasma intentionally displays hidden applets). A failure releases the Binding and shows a diagnostic in the widget tooltip and journal. The menu editor and backend remain independent of any particular launcher; no AppGrid-specific patches are made.

## Risks / limitations

- Plasma's standard panel implements HiddenStatus, but a third-party panel containment may not. Unsupported panels are left unchanged with an error.
- KDE's global `activateLauncherMenu` still emits the launcher's `activated()` signal, but **the launched window's native popup anchor may change when the original panel slot collapses**. Test left-click, Meta and positioning before relying on this setup. AppGrid has both centered and panel-popup variants; test whichever you use.
- A launcher may choose to change its own status while opening its popup. If that overrides the temporary status binding, the panel may briefly show its button. The widget checks the state periodically and may restore the original button if the hidden state doesn't hold.
- In panel edit mode, Plasma deliberately shows hidden applets so they can be moved or configured. This is an intentional recovery feature.
- No live Manjaro Plasma/Wayland session is available in the packaging environment; tests exercise the QML adapter model, validation, installer and rollback, not live visual behavior.

## Recovery

From a terminal (does not require the UI or a restart):

```bash
~/.local/bin/open-power-menu --show-launcher-button
```

The widget checks configuration about every 5 seconds and releases the Binding. You can also uncheck the hide option in the Configure editor. To verify the launcher ID, run `open-power-menu --launcher-diagnostics`. Never delete your existing launcher or manually edit `plasma-org.kde.plasma.desktop-appletsrc` to apply this feature. Do not restart Plasma in a RustDesk-only session.

The other journal message `Plasma::Applet.action is not a function` is not present in v0.4.3/v0.4.4 QML and may come from an earlier loaded revision in the same boot journal; the more recent line-numbered failure messages about layout hints are the directly relevant ones.

## Popup switching and icon resolution (v0.4.5)

KDE exposes `AppletQuickItem.expanded` as a writable, notifying boolean property (`plasma-framework/src/plasmaquick/appletquickitem.h` and `.cpp`). The panel resolves the selected launcher item from the same validated containment used for hiding. On right-click, Open Power Menu sets that item's `expanded=false` if it is open, then expands its own popup. A delayed follow-up protects against a pending D-Bus activation finishing immediately after right-click. On left-click, Open Power Menu immediately closes its own popup and side flyouts, and calls Plasma's `activateLauncherMenu` on the next event-loop turn. A generation counter cancels an unsent left activation if the user right-clicks first. If a launcher expands by Meta or a separate shortcut while the Power menu is open, the widget observes `expandedChanged` and dismisses the Power menu (except during a brief outstanding right-click guard).

Icon mode is read from the same `menu.json` as the editor and delivered through `GetIntegration`. In `launcher` mode, the button uses the selected applet's `icon` property as a theme name or QIcon value, falling back to the widget's own configured icon if absent. In `custom` mode, it uses the user-specified theme icon or local file. The original launcher's icon, configuration and applet status are not modified by icon selection. This works across third-party launchers **that expose standard Plasma icon/expanded properties**.

Plasma source checked:

- https://github.com/KDE/plasma-framework/blob/master/src/plasmaquick/appletquickitem.h
- https://github.com/KDE/plasma-framework/blob/master/src/plasmaquick/appletquickitem.cpp

### Known limits

- Third-party launchers that render their own independent windows rather than a standard Plasma full representation may not close when `expanded` is reset. There is intentionally no generic "close all windows" or process-kill fallback.
- If Plasma cannot read the source launcher's icon, use Custom icon from the editor; its saved icon/favorites are not touched.
- Actual rapid-click handling, popup stacking, and icon rendering must be validated in the live Plasma session. Mocked QML tests cannot validate the entire compositor/window-manager interaction.

## AppGrid window lifecycle (v0.4.6 fix)

AppGrid Center releases 1.9.x, including tag v1.9.6, run their centered window inside the Plasma applet root as `gridWindow`. `gridOpen` reports whether that window is open and the root's `closeWindow()` requests an animated close. The separate `PlasmoidItem.expanded` remains false by design (`activationTogglesExpanded: false`). v0.4.5 therefore couldn't close the actual window on right-click.

`LauncherInteraction.closeOriginal()` first checks for the supported root-QML capability (`gridOpen` boolean and `closeWindow()` function). It calls `closeWindow()` only when open. For the newer AppGrid standalone architecture, whose center applet no longer owns the window, it invokes the idempotent session-D-Bus `Hide()` method exposed by the standalone daemon at service `dev.xarbit.appgrid`, path `/Standalone`, interface `dev.xarbit.appgrid.Standalone`. Non-AppGrid launchers continue to close through the normal Plasma `expanded` API. This is **runtime only**; no changes to the selected launcher's appletsrc, icon, favorites, or process lifecycle.

For AppGrid 1.9.x, Open Power Menu listens to `gridOpenChanged` in addition to `expandedChanged`. An AppGrid window opened by Meta while Power Menu is visible closes the Power menu, except for a brief latest-right-click guard that dismisses a delayed prior left activation. Some animations may overlap very briefly even after the close is requested; actual timing still requires live Plasma testing.

Primary upstream source:
- AppGrid v1.9.6: https://github.com/xarbit/plasma6-applet-appgrid/blob/v1.9.6/package/variants/center/main.qml
- AppGrid standalone D-Bus schema: https://github.com/xarbit/plasma6-applet-appgrid/blob/main/src/dbus/dev.xarbit.appgrid.Standalone.xml
- AppGrid 2.x QML window (main development branch): https://github.com/xarbit/plasma6-applet-appgrid/blob/main/package/standalone/main.qml

## v0.4.7: coordinated right-click handoff

The earlier v0.4.6 code invoked an AppGrid close method and synchronously set `root.expanded=true` for Power Menu. Legacy AppGrid `GridWindow.closeGrid()` may set the logical `gridOpen=false` before the window's QML close animation completes. In that interval both menus appeared simultaneously. The direct AppGrid QML method can also be inaccessible from a different plasmoid's QML context; the old helper did not report its actual failed path.

The Open Power Menu QML now tracks `menuSwitchEpoch`, `pendingPowerEpoch`, and a 40ms polling timer. Right-click chooses the launcher-specific, idempotent close operation. For old AppGrid it waits for `gridWindow.visible=false`, and for newer daemon-based AppGrid it waits for the D-Bus `Hide` reply. Standard Plasma launchers are dismissed using `expanded=false`. Only after the selected close operation has completed does it set `root.expanded=true` and display Power Menu. All async callbacks check their original epoch before modifying pending state. Left-click or a second right-click cancels an outstanding Power handoff. A failed/missing close or 2-second nonclosing window is reported in the widget tooltip and `journalctl`; the widget **does not** open Power User Menu on top of a known-open original launcher.

AppGrid Center v1.9.x fallback: If QML `closeWindow()` is not available or fails, signal `Plasma::Applet.activated()` **only after** reading `gridOpen === true` from that exact selected launcher item; never emit it for an unknown, closed or standalone window. This is a narrowly gated compatibility fallback, not a generic toggle to close arbitrary launchers.

The new behavior has source-extracted QML JavaScript tests for animation overlap, failing native close, fallback safety, rapid click cancellation, D-Bus callbacks that arrive after a newer click, and timeout. There is no headless Qt/Plasma compositor in the test environment, so it remains a candidate for live validation rather than a confirmed fix for this workstation.

## v0.4.8: eliminate split launcher targets

KDE Plasma's `ShellCorona::activateLauncherMenu()` searches all containments
and emits `activated()` on the first applet advertising the launcher capability.
It does not promise to activate the specific widget selected in Open Power Menu.
Previously, the right-click code worked against `selectedLauncherPlan.applet` but
left-click used this global search; the two could legitimately refer to different
instances. The v0.4.7 logs showed the selected AppGrid's own `gridOpen=false` and
`gridWindow.visible=false`, so more animation polling could not solve that.

Left-click now calls the selected applet's `activated()` directly (a public
Plasma signal), with the same epoch cancellation. The selected instance is
resolved through the existing validated panel lookup. The global D-Bus method
is retained only as a compatibility fallback when no launcher ID has been
explicitly configured, and is never used to switch to a different applet when
an explicitly configured launcher is missing. This preserves the original
launcher code and its window positioning, because the signal handler is the
same one Plasma uses. Tests validate matching left/right targets, failure
fallbacks, and stale-click cancellation. Live validation is still required.


## v0.4.9: AppGrid standalone detection when legacy state is false

A real v0.4.8 trace showed `gridOpen=false`, `gridWindow.visible=false`,
`expanded=false` for the selected widget while the user reported the visible
AppGrid did not close. The `appgrid-already-closing` early return prevented any
attempt to close AppGrid's standalone window; it had incorrectly assumed that
one applet's legacy QML state was authoritative for all windows.

v0.4.9 tries the local `closeWindow()` method idempotently in that branch and
then probes the session bus `org.freedesktop.DBus.NameHasOwner` for service
`dev.xarbit.appgrid`. Only a **running** daemon receives the non-toggling
`Hide` call on path `/Standalone`, interface
`dev.xarbit.appgrid.Standalone`. Both async callbacks check the click epoch,
and the handoff timer waits until the probes finish. It does not call Toggle,
kill AppGrid, edit another widget, auto-start a daemon, or use KWin scripting.

In the live session, `AppGrid standalone bus owner: true` and
`AppGrid standalone Hide: acknowledged` are the decisive diagnostic messages.
If the owner is false and the visible window remains open, the remaining
problem is elsewhere; this implementation does not claim to close an unknown
or unrelated window. KDE and AppGrid APIs may differ across releases.

Source: https://github.com/xarbit/plasma6-applet-appgrid/blob/main/src/dbus/dev.xarbit.appgrid.Standalone.xml


### 0.4.16 — Power popup to native launcher focus handoff

The generic Plasma adapter is still the default and emits the selected
`Plasma::Applet::activated()` signal; it is not a Kickoff-specific toggle.
The host's `activateLauncher()` now distinguishes a visible Power Menu from
a closed one. For a visible Power Menu, the host closes the popup first and
schedules the existing selected-instance activation via an epoch-protected
140 ms `launcherActivationSettle` Timer. A newer right-click cancels the timer.
If `originalIsOpen()` is already true when it fires, the host skips a redundant
toggle. This leaves AppGrid's adapter and full-screen input bridge untouched.

For cosmetic Kickoff flicker, the host logs `launcher visibility:` on native
`statusChanged`, `expandedChanged` and unexpected panel item/container exposure.
It never writes those visible properties; KDE's own `HiddenStatus` bindings
remain authoritative. When the status is constantly HiddenStatus and both
visible properties false, do not introduce a new forced-visibility mask based
solely on a perceived compositor flash.
