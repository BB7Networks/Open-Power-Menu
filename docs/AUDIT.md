# v0.4.15 status-flash follow-up

The user confirmed v0.4.14 fixed the persistent duplicate, leaving a brief
single-frame flash on left-click in KDE's Application Launcher. The 0.4.14
repair handler explicitly queued its `Binding` reassert via `Qt.callLater`.
This release moves it into the same signal turn with a reentrancy guard and
reduces redundant scene traversals during the five-second settings poll.
The exact live flicker mechanism is not proven without frame/status logs.
No AppGrid adapter, visibility helper, editor or panel settings are changed.

# v0.4.14 — Generic mask stability follow-up

The v0.4.13 launcher-agnostic adapter structure is intact. One shared
visibility policy could destabilize native Plasma launchers: every five-second
refresh called `didHide()`, and if the panel widget was temporarily reported
visible during an expanded-popup transition, it called `releaseMask()` and
reinstalled the mask. That can expose the old icon until the next status/
layout evaluation. v0.4.14 keeps the same-applet Binding alive and adds a
bounded `statusChanged` reassertion. Because it is a runtime-only status
Binding, it does not write the user's saved panel or widget preferences.

**Confirmed:** static code path and automated mocks. **Not yet confirmed:**
that this resolves the user's intermittent duplicate Kickoff button on a live
Plasma 6 Wayland panel. If it persists, capture the new
`restored hidden launcher status` diagnostics and inspect the selected
applet ID, status and panel edit state.

---

# v0.4.13 follow-up — adapter extraction

This executes the narrow refactor recommended at the end of the v0.4.12 audit:
AppGrid's QML layer-surface input code, in-process close logic, and optional
standalone D-Bus interaction have dedicated modules. Other launchers always use
the default Plasma adapter. The old `LauncherInteraction.js` and
`LauncherPassThrough.js` were replaced by those modules; they are no longer
imported by the widget. The visual menu, general/layout editor, backend, and
status binding are unchanged.

**Risk:** This reorganizes QML signal handlers and module imports, so portable
Node tests passing does not prove live Wayland behavior. Keep v0.4.11 as the
known-good release; test left/right menu switching, Meta activation, close,
AppGrid drag-and-drop, and recovery at the physical console before calling
v0.4.13 field verified.

---

# Open Power Menu v0.4.11 → v0.4.12 code audit

**Scope:** Examine accumulated launcher integration code after releases
0.4.2–0.4.11. Prioritize preserving the user-confirmed v0.4.11 desktop behavior.
This is a source and automated-test audit, **not** an end-to-end Plasma GUI test.

## Outcome at a glance

| Area | Classification | Decision in v0.4.12 |
|---|---|---|
| Plasma applet discovery + same-panel validation | Core | Keep |
| Plasma `HiddenStatus` via reversible `Binding` | Core, proven | Keep **unchanged** |
| Selected applet `activated()` + standard `expanded=false` | Core | Keep **unchanged** |
| Live launcher icon inheritance + custom icon | Core, proven | Keep **unchanged** |
| AppGrid 1.9.x Wayland panel-edge input pass-through | AppGrid-specific, proven | Keep **unchanged** |
| AppGrid 1.9.x `closeWindow()` and owned window hide | AppGrid-specific | Keep |
| AppGrid 1.9.x probing absent standalone D-Bus daemon | Redundant for this variant | **Remove** the call |
| Newer standalone AppGrid `NameHasOwner` → `Hide` | Optional adapter | Keep only for build without legacy QML window |
| Earlier 1px slot, layout-hint, opacity masking | Superseded in v0.4.4 | Already absent from v0.4.11; nothing to delete |
| Older `appgrid-already-closing` early return | Superseded | Already absent from v0.4.11 |
| Close handoff epoch, polling and follow-up timer | Defensive runtime behavior | Retain pending live regression coverage |
| Verbose switch diagnostic messages | Nonessential diagnostic trace | Retain temporarily; can make opt-in later |
| Power menu hover and side-flyout anchor logic | Existing, proven | Keep **unchanged** |

## What was genuinely necessary?

Three things unlocked the unified button:

1. **Hide the original launcher at the Plasma layer, not with fake size
   hints.** `LauncherVisibility.js` verifies a launcher on the same panel and
   `main.qml` applies `PlasmaCore.Types.HiddenStatus` using Qt's reversible
   `Binding`. Plasma's panel layout honors this status. It keeps the applet,
   menu, shortcuts, and saved configuration alive.
2. **Delegate left-click to the exact selected applet.** The original Plasma
   launcher still owns its UI and menu. Icon adoption reads its existing icon;
   there is no copied favorites list or launcher reimplementation.
3. **Handle AppGrid 1.9.6's full-screen Wayland overlay.** This version has
   its own layer-surface window and intercepts input over the panel. The
   working adapter narrows that window's input region only while it is open;
   it checks panel/monitor geometry, avoids overlapping the interactive grid,
   and restores the region on close/disable/destruction and after drags. This
   was confirmed to solve the user's right-click issue in v0.4.11.

## What the troubleshooting added unnecessarily

- **v0.4.2–0.4.3 masking experiments** (transparent icons, squeezing width,
  size hints, traversal assumptions) didn't work. Their implementation was
  replaced rather than retained in v0.4.11. Only the correct containment
  lookup remains.
- **v0.4.6–0.4.10 repeatedly changed close routines** even though the overlay
  was preventing the click from reaching the button in the first place. Some
  defensive close polling remains active, but the decisive problem was input
  delivery, not an absent close method or D-Bus daemon.
- **v0.4.9 probed `dev.xarbit.appgrid` on the session bus when AppGrid 1.9.6
  reported `gridOpen=false`.** The user verified that service did not exist
  on their installation. v0.4.12 removes that probe from the legacy in-process
  code path, preserving the optional standalone compatibility path.
- **Diagnostic traces** of before/after window state were crucial during
  debugging but are not functionally necessary. They remain for incident
  recovery; they can be gated by a debug preference in a later maintenance
  release without touching launcher behavior.

These observations do **not** prove every timer or fallback can be safely
removed. The tests model timing and error paths, but only live Wayland
regression testing can establish if the handoff guards are redundant.

## Launcher-agnostic design boundary

The common contract is simple: discover an existing same-panel Plasma applet,
optionally hide its panel representation, read its icon, send its native
activation signal, and close a **standard** expanded popup. All of that is
independent of AppGrid.

The plugin-specific exception is AppGrid Center's special window/pointer input
behavior. It is guarded by plugin ID and only enabled when the original button
is hidden. Other full-screen or standalone third-party launchers may require
similar separate adapters. We should not broaden the AppGrid pointer mask to
unknown windows or use process killing/KWin hacks as a generic fallback.

**Recommended next refactor (separate release):** move AppGrid's input-region
lifecycle and optional daemon integration out of `main.qml` into a dedicated
adapter, with runtime capability checks and a neutral interface. Do that only
after taking a live baseline and testing standard launchers (Kickoff/Kicker),
AppGrid Center 1.9.6, multiple screens, panel edges, and the emergency unhide
path. The existing, proven code is not rewritten as part of this UI-only
maintenance release.

## Verification in v0.4.12

- Automated Python tests, Node-based QML JavaScript harnesses, and configuration
  preservation checks run locally in the build environment.
- Byte-for-byte comparison against v0.4.11 confirms `main.qml`,
  `LauncherVisibility.js`, `LauncherPassThrough.js`, `SideFlyout.qml`, and
  `configGeneral.qml` are unchanged.
- Only `LauncherInteraction.js` has the narrow, one-branch legacy D-Bus probe
  reduction in the widget runtime. The original behavior for newer AppGrid
  standalone mode is covered by separate tests.
- The graphical editor is source-validated; PySide6 is not installed in the
  packaging environment, so a live visual check on Manjaro is still required.


### 0.4.16 follow-up

The 0.4.15 `immediate launcher hide repair` diagnostic remained silent while a
brief Kickoff flash was observed. That log only fires after a successful repair;
it is not a general visibility trace. A separate right-click-to-left-click race
was observed where Kickoff opens and then closes. We added a bounded native
popup focus settling delay only for that switch, rather than changing the
AppGrid adapter or adding another hide mechanism. The status/item/container
observability added for the icon flash is read-only; any further visual mask
change should wait for the runtime trace.
