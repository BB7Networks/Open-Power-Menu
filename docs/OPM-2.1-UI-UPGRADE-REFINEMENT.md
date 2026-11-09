# OPM 2.1 UI and upgrade refinement

Baseline: 88db27b, existing development branch and draft PR #10. The user reports
physical Manjaro Plasma 6.7.5 / Qt 6.11.2 / KF6 6.30.0 observations. Earlier
runtime stabilization remains in place; neither desktop nor power actions are
authorized by this pass.

## Intended design

- Auto-fit is the default. Natural main-menu height follows rendered content,
  header, editing controls, status and padding; main and nested menus are limited
  by the source monitor's available work area rather than fixed pixel caps.
- General offers explicit Auto-fit/Custom height and Reset to automatic. The
  stored custom height is in logical pixels and is independent of density,
  font/monitor changes and temporary geometry constraints. Width presets remain.
  Popup geometry events never write preferences. No unverified drag handle or
  compositor resize gesture is treated as user intent.
- Every row at a menu level reserves the same font-aware hint column when that
  level has hints. Glyphs are centered; labels elide; hints-off reclaims the space.
- Pointer dismissal distinguishes opening/geometry transitions from real exits.
  A brief settling period clears synthetic entry/leave history, without changing
  the selected 500/1200/5000 ms delay after an established genuine exit. Root and
  child windows share one timer; keyboard/editing and closed state stop it.
- Compare installed widget content hashes during committed install/rollback and
  recovery. Explain that installed QML differs from the running frontend; offer
  deferral with logout/login guidance in terminal output and an optional passive
  desktop notification. No shell restart, widget recreation or panel rewrite.
- Current frontends inspect the backend's method contract before activation, so
  a rollback to the released Run API can be used without retrying an uncertain
  request. Existing native Run and request-specific APIs remain intact.
- Saved ordinary preferences continue to refresh on opening and through the
  existing five-second integration poll, without restarting desktop components.

## API research and limits

KDE libplasma PlasmoidItem exposes screenGeometry and availableScreenRect. Its
implementation returns the available rectangle in screen-relative coordinates;
add the screen origin before placing flyouts on negative/non-primary outputs.
Inspected upstream files: src/plasmaquick/plasmoid/plasmoiditem.h and .cpp.

KDE plasma-workspace shell/scripting/applet.cpp::reloadConfig restores KConfig
and emits configChanged; it does not recreate the QML component or clear the
shared QML engine's component cache. It is not a verified widget-code reload.
No supported in-place code reload preserving applet identity was established
for both supported sessions. A shell restart is also not physically validated
here, and remote-session safety cannot be established from this cloud process.
Only the safe defer/logout-login choice will be offered. No reload success will
be claimed. This is deliberate capability handling, not a failed reload attempt.

Physical Plasma resizing/placement and the exact 500 ms premature-close cause
need confirmation on the user's desktop. Controlled tests will distinguish
reproduced synthetic hover sequences from observations not reproducible here.
Breeze TextArea and AT-SPI warnings remain separate nonblocking compatibility
observations unless a functional defect is reproduced. No system style files or
global Qt style settings will be changed.

## Implemented behavior and confirmed causes

The main 590px and flyout 540px ceilings caused scrolling before the monitor was
full. They are removed. Main natural height includes header margins, divider,
rendered rows/separators, editor navigation/instructions/actions, status and
backend setup. Long status/setup content gets a separate bounded scroll area
only when the complete content does not fit. Flyout height includes theme padding
inside its work-area constraint. Both use logical pixels, with a small edge
clearance; DPR is not multiplied a second time. Nested menus inherit live
preferences and work area, and re-anchor after size/position changes without
resetting keyboard selection.

Qt.application.font is a constant QML property, so its existing metric bindings
did not follow live font changes. Text and metrics now follow the notifying
Kirigami.Theme.defaultFont. The rendered regression changes that font after the
menu is already open and checks both row and hint-column growth.

Plasma's AppletPopup can restore popupHeight/popupWidth and then ignore preferred
size updates (`m_sizeExplicitlySetFromConfig`). OPM now supplies equal minimum,
preferred and maximum bounds for its computed size, so cached geometry cannot
silently override Auto-fit or an explicit Custom preference. This does not edit
Plasma configuration. Plasma still owns popup placement and may impose additional
compositor/platform limits; actual panel placement requires physical acceptance.

General → Widget menu height offers Auto-fit (default) and Custom. Custom stores
`menu_height_mode: "custom"` and `menu_custom_height` (integer 120–10000 logical
pixels; initial remembered value 600). The height describes the widget content
area; theme padding is additional and included in the screen constraint. A runtime minimum leaves room for controls and at least one row, including
layout editing; it does not change the saved number. Density,
icon/font changes and monitor constraints never write that preference. Reset to
automatic switches mode and keeps the remembered number for a later explicit
Custom choice. Narrow/Automatic/Wide width choices remain. Older profiles receive
Auto-fit defaults; personal/unknown fields survive. Both keys participate in
portable JSON export/import and transactional Save/undo.

Custom height is for the Plasma main widget. Nested flyouts and the native
standalone QMenu remain content-sized with their existing scroll/keyboard access.
Plasma internally has a window resize handler, but no verified cross-session
intent signal was established that distinguishes manual drag from compositor
geometry. OPM therefore offers explicit controls, not drag-to-Custom. Equal bounds
also avoid accidentally adopting restored or compositor-constrained dimensions.

Previously each hint's implicit glyph width determined its column, so I/M/W and
other letters had different centers. A font-measured fixed-width column now
centers each hint. Every row at a level reserves it when that level has hints,
including rows without an assigned key. Disabling hints removes the column and
its layout spacing. The name still elides before the hint; submenu gutters remain
stable with icons on/off. Input access-key matching is unchanged.

The previous dismissal policy treated any initial Enter as a genuine visit. A
controlled reproduction of a brief opening Enter/Leave pair closed the baseline
20/20 times at 505–506ms despite no stable visit. The updated QML policy closed
0/20 times for the identical sequence. This establishes a vulnerable event
sequence, not the exact event trace on the user's workstation. Opening, model
replacement and geometry changes discard hover history until geometry has been
quiet for 150ms. A stable visit followed by an exit starts the selected full
500/1200/5000ms interval. Root and descendants share the leave timer. Re-entry,
keyboard input, editing, closed state and reopen reset remain protected. Global
pointer coordinates prevent layout movement under a stationary pointer from
canceling keyboard protection. Native QMenu follows the same settling rule.

## Upgrade activation and compatibility

The installer compares the transaction's old/new widget digests after durable
commit, including rollback and completed recovery. Changed widget files produce
terminal instructions and a passive best-effort notification; identical widget
reinstallation does not. Missing notification support does not undo installation.
The supported choice is **Later / I'll sign out and back in myself**. No reload,
restart, logout, widget deletion or panel rewrite is attempted. Consequently there
is no successful-reload claim and no destructive reload failure path to recover.

A normal later logout/login is necessary to guarantee new QML is loaded. Installing
backend/files cannot replace already instantiated components. Settings Save is
different: an active current frontend refreshes on next opening and through its
five-second integration poll, with no desktop or backend restart.

The service retains `Run(string) -> bool` for the released frontend and retains
protected presentation keys, asynchronous authorization and request-specific
`StartRun`/`RunResult`. This frontend introspects before dispatch, selecting the
new API or released Run API after rollback. It never falls back after an uncertain
execution response. Cached 88db27b-era QML cannot acquire this compatibility code
in memory; if it is rolled back directly to 1.0.1, logout/login remains necessary
before commands work. Missing legacy Python/PySide6 still blocks that rollback
before replacement. No legacy snapshot is patched and no runtime package removed.

## Focused validation and evidence boundaries

Focused tests cover native defaults/validation, height persistence through Save,
density changes, Reset, reopening and portable import/export; real editor keyboard
controls; JavaScript work-area/height behavior and live preference transport;
rendered Qt Quick flyout dimensions, last-row scrolling, hint centers, blank keys,
hints-off space, nested live preferences; opening/geometry hover noise and
stationary-pointer keyboard protection; and upgrade/rollback notices with multiple
widget entries and unchanged shortcut/panel bytes. Failed or unsupported backend
protocol probes dispatch nothing; ambiguous activations are never retried.

Local full suite: 488 portable/widget tests plus 18 subtests, with eight existing
optional-environment skips. Private backend contracts: 15 passed. Installer
transactions: 10 passed, including the actual 1.0.1 installer and rollback.
All eight native CTest suites passed, including editor/recovery and actual
QMenu input. The sealed bundle also passed install, activation, editor startup,
reinstall, uninstall and rollback in the Python/compiler-free runtime image. CI must qualify the exact final source in its existing eight jobs;
the current PR description records run IDs and the selected artifact.

The production main-menu body is also rendered under a controlled applet fixture,
including custom/automatic height, editing, long errors and last-row keyboard
reachability. Rendered Qt Quick checks exercise normal/large fonts, Native/Aero, icons on/off,
all density choices, negative-origin work areas and overflow reachability. Eight
hint screenshots and JSON measurements record I/M/W/P/O/U/E/V plus an unassigned
row; all hint centers match within each menu. A separate Qt 6.8.2/Kirigami run
passes 12 focused cases with real Kirigami rather than the test icon stub. These
use a test Plasma window primitive and are not real plasmashell placement tests.

Each controlled display run repeats **21 complete opening/transition cycles**,
seven at each configured interval. It includes opening hover noise, late re-entry,
root/child transitions, resize while outside, keyboard followed by pointer input,
reopen and corner anchors. Delivered Qt input events and virtual compositor windows
are stronger than geometry arithmetic but do not represent physical mouse motion
across an actual panel. There were no unexpected closes in the following runs:

| Environment | 500ms measured | 1200ms measured | 5000ms measured | Full suite |
|---|---:|---:|---:|---|
| Xvfb X11 | 505ms | 1201–1203ms | 5001–5008ms | 46 passed, 1 focus-seat skip |
| Weston Wayland | 504–505ms | 1201–1203ms | 5000–5009ms | 46 passed, 1 focus-seat skip |
| KWin Wayland | 504–506ms | 1200–1204ms | 5001–5008ms | 47 passed |
| KWin, two outputs at 125% | 505–506ms | 1201–1203ms | 5000–5010ms | 47 passed |
| KWin, two outputs at 150% | 505–509ms | 1201–1204ms | 5000–5006ms | 47 passed |

The skipped cross-process focus test needs KWin's virtual input seat and passes
there. Measurements come from QMenu's aboutToHide signal, not the test polling
interval. The separate original/new QML opening comparison uses 20 repetitions.
Heterogeneous monitor scales and real panel struts still require physical testing;
two outputs at one fractional scale are not claimed as mixed physical displays.

## Focused physical acceptance for the next candidate

No physical procedure below has been executed by the agent. Stable remains 1.0.1;
PR #10 remains draft. No real power operation is part of acceptance.

1. Verify the candidate's SOURCE-COMMIT and PACKAGE.sha256 against the artifact
   recorded in PR #10. Back up the existing profile. Upgrade as the desktop user;
   confirm the activation notice, choose Later, and verify old frontend/backend
   operation. At a convenient user-chosen time, sign out/in and check new controls.
2. With the full personal menu, test Auto-fit at all three densities and icon sizes,
   icons on/off, Native/Aero, normal/large fonts, and long names/status text. All
   entries should fit without scrolling when work area permits; otherwise reach
   the last entry with wheel and keyboard. Repeat in layout editing and submenus.
3. Set Custom to a deliberately small height, Save, reopen, then change density.
   Verify the number persists. Move to a smaller screen and back; the number must
   survive clamping. Reset to automatic and check that density again changes size.
4. Check I/M/W/P/O/U/E/V, blank keys, disabled hints, nested menus and arrow gutters.
   Preserve Meta+X, local letters, nested U sequences, arrows, Enter and Escape;
   use only harmless commands, never a real power action.
5. At 500/1200/5000ms, repeat fast/slow launcher entry, late re-entry, parent/child
   crossings, async discovery, resize/reposition, keyboard then mouse and reopen.
   Record any early close with the actual event sequence and approximate timing.
6. Repeat with top/bottom/left/right panels, edges, non-primary and negative-origin
   outputs, heterogeneous 100/125/150% monitors, AppGrid, and both X11 and Wayland.
   Keep the daily X11/remote-access environment intact; do not restart its shell.
7. Save ordinary preferences and verify next-open or at-most-five-second changes
   without restarting anything. Roll back and re-upgrade, checking activation
   notices, layout, launcher association, shortcut ownership and saved preferences.
   A previously cached frontend may need the documented later logout/login.

Breeze 6.7.5 TextArea and AT-SPI warnings remain nonblocking observations unless a
functional editor defect is reproduced. No system Breeze files or global style
settings were changed. Safe widget-only reload and shell restart have not been
validated on a physical KDE desktop and are not offered.
