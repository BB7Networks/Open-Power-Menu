# v0.4.15 generic launcher stability note

The shared Plasma adapter and its public contract are unchanged. The runtime
in `main.qml` now restores the selected applet's `HiddenStatus` binding
synchronously and avoids redundant panel wrapper discovery while the
selection remains stable. This applies equally to Kickoff, Kicker, and
third-party Plasma applets; AppGrid remains an isolated special case.

# Launcher adapters — v0.4.14

## Why this exists

Open Power Menu was already built to use **any compatible Plasma launcher**.
It selects an existing applet on its own panel and delegates activation,
icon retrieval, and reversible button hiding to Plasma. The accumulated
AppGrid 1.9.6 workarounds were exceptional and belonged in a separate adapter.

## Source map

```text
plasmoid/contents/ui/
  main.qml                    One Start button, two menus, race coordination,
                              reversible native HiddenStatus Binding
  LauncherVisibility.js       Same-panel selection and safe hide checks
  SideFlyout.qml              Power User Menu submenus
  adapters/
    LauncherAdapters.js       Plugin dispatcher; Plasma is the default
    PlasmaLauncher.js         Standard activated(), expanded and icon
    AppGridLauncher.js        AppGrid Center 1.9.x close + optional daemon Hide
    AppGridPanelBridge.qml    AppGrid Center gridOpen/window/drag signals,
                              Wayland pointer mask lifecycle
    AppGridPanelGeometry.js   Tested safe panel-edge rectangle calculations
```

## Public adapter contract

The host calls `LauncherAdapters` to:

| Operation | Generic Plasma | AppGrid Center extension |
|---|---|---|
| `activate(applet)` | Send selected `activated()` | Same native activation |
| `chooseIcon(...)` | Read applet icon, fallback/custom | Same behavior |
| `closeOriginal(...)` | Writable `expanded=false` | Local `closeWindow()` / owned window hide, or a guarded D-Bus `Hide` |
| `originalIsOpen(...)` | `expanded` state | In-process `gridOpen` where exposed |
| `originalIsVisiblyOpen(...)` | `expanded` state | Owned `gridWindow.visible` including animations |
| `describeState(...)` | Generic diagnostics | Additional GridWindow diagnostics |

The optional `requestAsyncClose(...)` delegates to an adapter-specific
non-toggling close operation. The default Plasma adapter never uses it.

Hiding/unhiding is deliberately handled at the **Plasma layer**, not by a
launcher adapter. This keeps applet `status` restoration and panel verification
identical across launchers. **v0.4.14** additionally protects the reversible
`HiddenStatus` binding against transient status changes and does not tear it
down just because a same-applet popup's representation is changing.

`AppGridPanelBridge` adds a tightly scoped runtime input-region feature for
the legacy *center* variant. The normal Plasma adapter never changes a
third-party QWindow or calls AppGrid methods.

## Adding future adapters

1. Prefer the default Plasma adapter. No new module should be needed for
   a normal launcher with `expanded`, `icon`, and `activated()`.
2. Only if a launcher has a nonstandard window, add a plugin-ID-specific JS
   adapter with defensive capability checks.
3. Wire the registry dispatcher for that exact ID; unknown launchers still
   fall back to generic Plasma.
4. Use a separate QML bridge only for window/event/input integrations that
   genuinely need Qt signal connections. Reset any runtime state on opt-out,
   selection changes and component destruction.
5. Never toggle an unknown window to close it, kill processes, edit the
   original launcher, or change saved Plasma panel configuration.
6. Add portable regression tests and a **live** acceptance matrix for
   every panel edge, monitor choice, drag, keyboard Meta, and emergency unhide.

## Acceptance boundaries

Automated tests cannot emulate a live Plasma 6 Wayland compositor or prove
click delivery. The user confirmed full switching on v0.4.11 with AppGrid
1.9.6. v0.4.13 changes module wiring and must be tested locally before
replacing that established baseline.
