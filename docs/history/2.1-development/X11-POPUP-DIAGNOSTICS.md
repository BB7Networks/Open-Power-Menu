> Historical document, retained from the approved Phase 1 source. Versions,
> commands and status claims describe that earlier work. Use the [current documentation](../../README.md) for native 2.1 guidance.

# X11 widget popup collapse: investigation and capture

Base: PR #10 / `feature/native-architecture-v1.1`, `5b1384832c19d3d1d9a5dbadf8421f6e9b612811`.
The PR remains draft. The user has now physically verified the collapse fix on
Manjaro X11. A separate dismissal ghost is investigated in
[X11-GHOSTING-INVESTIGATION.md](X11-GHOSTING-INVESTIGATION.md). The original local
reproduction described here uses xterm on a private Xvfb/KWin seat.

## Evidence and correction

Test system: Debian 13, Qt 6.8.2, libplasma 6.3.5, KWin/plasma-workspace 6.3.6.
The new fixture starts a normal xterm window and verifies that it is active
before opening the widget. It supplies a read-only backend that refuses all
commands and power actions, and seeds a private panel with Kickoff and OPM.
It never attaches to the user's display, bus or panel, and never restarts a shell.

With diagnostics only, the original code failed when returning from the flyout
onto Run. Ordinary enabled/disabled rows, separators and Search/Run had stayed
open before entering the flyout. At the unexpected hide:

- No OPM `expanded=false` request occurred; `root.expandedChanged` reported
  `external-to-opm` after the native window became invisible.
- `autoClose=false`, the dismissal timer was not pending, and Kickoff was closed.
- The pointer was at `[176,695]`, inside the unchanged content rectangle
  `[12,523,328,227]`; the native popup remained `[8,519,336,235]` until hidden.
- The flyout's Qt `transientParent` referred to the applet, but `xprop` showed no
  `WM_TRANSIENT_FOR`. Its native type was NORMAL/OVERRIDE with input focus false.
- Assigning the transient parent earlier did not repair the native property or
  the collapse. That experimental change was discarded.

Qt's XCB backend publishes `WM_TRANSIENT_FOR` only for transient window types;
plain Window is excluded. Plasma's `PopupPlasmaWindow` already sets the Qt parent
while positioning. The correction adds **`Qt.Tool` only on X11** to the existing
flyout flags. It applies to nested flyouts through the same component. The
native property then points to the applet popup, and the reproduced traversal
stays open. Existing mouse/keyboard focus flags and Wayland flags are retained.
No focus loop, new delay, dismissal override, or geometry workaround was added.

Relevant upstream implementation:

- [Qt 6.8.2 QXcbWindow::isTransient / updateWmTransientFor](https://github.com/qt/qtbase/blob/v6.8.2/src/plugins/platforms/xcb/qxcbwindow.cpp)
- [Plasma 6.3.5 PopupPlasmaWindow::updatePosition](https://github.com/KDE/libplasma/blob/v6.3.5/src/plasmaquick/popupplasmawindow.cpp)
- [Plasma 6.3.5 AppletPopup::focusOutEvent](https://github.com/KDE/libplasma/blob/v6.3.5/src/plasmaquick/appletpopup.cpp)

The standalone uses X11 QMenu handling. On the same private seat, its enabled
and disabled rows, separators, Search/Run and submenu traversal stayed open,
including outside hover, until an intentional outside click.

## Physical log capture (already-loaded candidate widget)

The temporary `popupDiagnostics` widget setting defaults to false. These
commands toggle logging in the loaded candidate; they do **not** reload QML
code. Installing files alone does not prove plasmashell is running the candidate.

1. Start capture in Konsole:

   ```sh
   journalctl --user -f -o cat | rg --line-buffered 'OPM_POPUP_TRACE' | tee opm-popup.log
   ```

2. In a second terminal enable the gate for OPM widgets:

   ```sh
   qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '
   panels().forEach(p => p.widgets().forEach(w => {
       if (w.type === "org.openpowermenu.start") {
           w.currentConfigGroup = ["General"];
           w.writeConfig("popupDiagnostics", true);
           w.reloadConfig();
       }
   }));'
   ```

   Expect `trace-enabled`. If absent, check that the candidate QML is loaded and
   the session journal receives plasmashell output; do not treat missing logs as
   evidence of no collapse.

3. Disable automatic pointer dismissal in OPM. With Brave active, open the
   widget, traverse enabled/disabled rows, separators, Search/Run, into a flyout
   and back. Do not click an action. Finally click outside intentionally. Repeat
   with the original launcher visible/hidden and with Dolphin/Konsole active.
   Record which app and visibility setting correspond to each attempt. Compare
   the native standalone using `open-power-menu-standalone --diagnose-launch`.

4. Repeat step 2 with `false`, then stop capture with Ctrl+C.

`OPM_POPUP_TRACE` contains UTC timestamps, sequence numbers, callback names,
OPM request IDs, expanded state, window visibility/activation/flags/transient
parent, global content/window geometry, pointer/hover/dismissal state, and
original launcher state. It does not log command arguments or menu text.
`opm-expanded-request` identifies every explicit OPM close, including no-ops.
A changed signal outside the synchronous setter is labelled `external-to-opm`;
this label does not pretend to identify a particular Plasma C++ caller.
The trace uses signal observation only: no focus requests, input grabs, polling,
window writes or timers. The test fixture separately samples read-only geometry.

## Repeating the automated checks

`native/tests/editor.Dockerfile` now includes the X11 fixture in CI with logging
both enabled and disabled. In an environment with its build dependencies:

```sh
python3 native/tests/plasma_popup.py --output /tmp/opm-popup-new
python3 native/tests/plasma_popup.py --output /tmp/opm-popup-untraced-new --diagnostics-off
# Optional native comparison in the same seat:
python3 native/tests/plasma_popup.py --output /tmp/opm-popup-native-new \
  --standalone /absolute/path/to/open-power-menu-standalone
python3 native/tests/plasma_startup.py --only wayland-ready --single-start \
  --output /tmp/opm-wayland-new
```

Each output directory must be new. Logs retain window properties, cursor/active
window samples and traces. The X11 assertions cover three reopenings, enabled
and disabled rows, separators, Search/Run, flyout crossings, outside hover/click,
keyboard flyout return/Escape, both launcher visibility states, and disabled
automatic dismissal. Backend requests must remain read-only.

## Validation results for this candidate

- Python/QML suite: **500 passed, 8 skipped, 18 subtests passed**. Skips retain
  the suite's existing optional/baseline requirements.
- Native CTest: **6/6 targets passed** (including native standalone).
- Native standalone on private KWin Wayland: **50 passed**.
- Real Plasma Wayland startup/reopening: **passed**, one shell start.
- Real Plasma X11: **all four cases passed** (launcher visible/hidden × trace
  on/off), including keyboard return and intentionally distinct OPM/external
  close attribution. Automatic pointer dismissal was disabled throughout.
- Native standalone/X11 with active xterm: **passed** for both private profiles.
- `git diff --check`: passed.

The baseline failed twice at flyout return; an earlier-parent-assignment
experiment also failed. The one-line X11 window-type correction passed. This
supports that correction for the reproduced path, since physically verified by
the user. The later dismissal ghost remains a separate investigation. Direct
crossings without a preceding flyout did not collapse in this environment.

Changed production files: `plasmoid/contents/ui/SideFlyout.qml` (X11 correction
and trace hooks), `main.qml` (attributed setters and snapshots), `PopupTrace.qml`
(new gated observer), `PointerDismissal.qml` (observation signals), and
`plasmoid/contents/config/main.xml` (default-off gate).

Coverage/infrastructure: `native/tests/plasma_popup.py`,
`native/tests/editor.Dockerfile`, `native/tests/plasma_startup.py`,
`tests/test_popup_trace.py`. Existing JS handler fixtures were adapted to the
attributed setter in `test_appgrid_lifecycle.py`, `test_inmenu_js.py`,
`test_menu_exclusivity_icon.py`, `test_native_shortcut.py`, `test_popup_startup.py`,
`test_v0413_adapters.py`, `test_v0416_popup_handoff.py`, and
`test_v048_target_activation.py`. This document contains the findings and
physical capture procedure.
