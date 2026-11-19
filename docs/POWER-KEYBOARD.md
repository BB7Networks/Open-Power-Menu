# Immediate power actions and keyboard candidate

Historical report for the 51-file candidate. Its held-key blocker and timestamp
workaround are superseded by [held-key stabilization](HELD-KEY-STABILIZATION.md).
The later report records the physical-input guard. RC2's three-mode preference
and migration supersede the checkbox described here; see
[power and distribution compatibility](POWER-DISTRIBUTION-RC2.md).

This continues the **local 34-file session-reliability candidate**, based on
`5b1384832c19d3d1d9a5dbadf8421f6e9b612811`, on
`feature/native-architecture-v1.1`. The complete patch includes that baseline.
The verified X11 `Qt.Tool`/`WM_TRANSIENT_FOR` fix, Meta+X ordering correction,
Configure session resolver, diagnostics and installer/rollback work are retained.
Taskbar text ghosting remains deferred. This is a candidate, not a release:
the X11 held-key stress failure described below is a release blocker.

## Dispatch and configuration

The native default is `confirm_power_actions: false`. Configure → General →
**Power Actions** exposes **Confirm power actions**, with the requested text:

> When enabled, show KDE's confirmation screen before shutting down, restarting,
> or signing out. When disabled, begin the selected action immediately.

The native model captures these operations in the existing protected selection,
including the confirmation mode. It no longer resolves these three built-ins to
external command-line D-Bus utilities. Existing revision checks, one-use menu
identities, asynchronous result handling and duplicate prevention remain in use.
Changing the preference invalidates an earlier selection even when its custom
title is identical. Closing the menu has no backend cancellation operation.

All calls use the **session bus**, with no arguments and a void result:

| Action | Preference off: service/interface `org.kde.Shutdown`, path `/Shutdown` | Preference on: service/interface `org.kde.LogoutPrompt`, path `/LogoutPrompt` |
| --- | --- | --- |
| Shutdown | `logoutAndShutdown` | `promptShutDown` |
| Restart | `logoutAndReboot` | `promptReboot` |
| Sign out | `logout` | `promptLogout` |

These exact signatures and the cleanup path were checked in KDE Plasma 6 source:

- [Shutdown interface](https://github.com/KDE/plasma-workspace/blob/Plasma/6.3/startkde/plasma-shutdown/org.kde.Shutdown.xml)
- [LogoutPrompt interface](https://github.com/KDE/plasma-workspace/blob/Plasma/6.3/ksmserver/org.kde.LogoutPrompt.xml)
- [Shutdown implementation](https://github.com/KDE/plasma-workspace/blob/Plasma/6.3/startkde/plasma-shutdown/shutdown.cpp)
- [KWorkspace session management](https://github.com/KDE/plasma-workspace/blob/Plasma/6.3/libkworkspace/sessionmanagement.cpp)
- [KWorkspace backend](https://github.com/KDE/plasma-workspace/blob/Plasma/6.3/libkworkspace/sessionmanagementbackend.cpp)

The inspected `Plasma/6.3` source tree was
`63e4bad2fe4bfc2b8c42f6347f61d2418cc7143c`; copies accompany the evidence.
KWorkspace's explicit Skip/ForcePrompt routes use these same endpoints. OPM does
not read or change KDE's `confirmLogout` preference. `Shutdown::startLogout()`
requests KSMServer session cleanup asynchronously, including application prompts;
it does not mean unsaved work is forcibly discarded. A successful D-Bus reply
means KDE accepted the request, **not** that shutdown or logout finished.

Discovery reads the bus daemon's `ListNames`/`ListActivatableNames` and logind's
`CanPowerOff`/`CanReboot`. It disables auto-start on discovery messages and never
probes or activates plasma-shutdown or the logout greeter to test availability.
Execution checks KDE's two logout authorization keys with `KAuthorized`, and
rechecks the relevant read-only logind capability before one final KDE request.
There is no force option, systemctl operation, direct logind session termination,
or fallback around KDE. Sleep/Hibernate retain their separate PowerDevil,
inhibitor, logind WithFlags and asynchronous authorization path. Lock is unchanged.

Known D-Bus failures produce an error. Missing, malformed, disconnected or timed
out final replies are treated as uncertain: the power manager prohibits another
request for its lifetime and never retries automatically. An accepted operation
is not canceled by a subsequent menu refresh, closure or configuration change.

Complete editor/package builds now explicitly require KConfigCore. Backend-only
or standalone development builds can still compile without it, but session-ending
actions are disabled because KDE policy cannot be checked. Complete bundles
already needed KConfig for the editor. The test runtime images include the new
backend dependency. Installer transactions, ownership checks and rollback are
unchanged.

## Migration and compatibility

- Old files missing the setting use `false` in memory; reading does not rewrite
  the file. Saving uses the existing atomic storage and backup mechanism.
- Non-boolean values, including strings, numbers and null, are rejected.
- Save/reopen, integration, editor state and import/export include the setting.
  Unknown metadata, custom layouts, commands and access keys survive unchanged.
- Normal built-in titles lose `...` for immediate mode and regain it in confirmed
  mode. Custom titles keep their punctuation. Explicit labels equal to the stock
  title, with or without its ellipsis, are treated as ordinary built-in labels.
  No menu entries are rewritten just to change their displayed title.
- The existing **layout** reset preserves General preferences, including this one.
  Unchecking the checkbox restores its default. No new whole-configuration reset
  is introduced. Backups and imported older files retain their existing semantics.
- Shared legacy Python resources are unchanged, preserving the 1.0.1 rollback
  behavior. Native/legacy differential tests exclude the three intentionally
  different built-ins; exact native routes have dedicated tests instead.
- Production shortcut registration and existing assignments are unchanged. Only
  the disposable X11 test profile is assigned Meta+X by its harness.

## Keyboard findings and corrections

The earlier local widget fails the isolated rapid `U, U` case: the submenu opens,
but no mock final action arrives. With an application active behind OPM, the next
key can reach the root QWindow before X11 transfers focus to the flyout. The
root previously interpreted it using root entries again. It now passes the event
to the visible keyboard submenu's existing handler, recursively for deeper levels.
Leaf access keys use the current entry directly instead of waiting for a row
delegate to appear. Keys, custom assignments, collision handling and dispatch
still come from the existing configurable menu model.

The reverse handoff also occurred: a second Escape reached the already-hidden
flyout after Escape/Left had returned to its parent. A flyout closed specifically
by keyboard return can pass that queued event back to the parent handler. A
closed root rejects events. No extra activation request, focus loop or production
delay is added; existing user-initiated focus transfer is retained.

Modified keys and editable fields are excluded. Escape, Enter and access-key
auto-repeat are ignored; Up/Down can repeat. Qt's ordinary fallback mnemonics
and repeated Enter are also blocked in the standalone menu. Real Plasma tests
found that Alt+U could invoke the header tool button's automatic “Unlock menu
layout” mnemonic before `Keys.onPressed`; shortcut-override handling now reserves
modified input during menu navigation, while preserving editable controls and
layout editing.

The same tests exposed a presentation bug after the five-second capability cache
expired. The QML D-Bus plugin returned `{value:true}` for the pending boolean;
the strict scalar comparison missed it, leaving “Checking…” rows disabled.
The existing bounded refresh now recognizes both scalar and wrapped booleans.
This changes presentation readiness only, never power execution.

### Held-key release blocker

The isolated Qt 6.8.2/Xvfb stress test sometimes labels server-generated repeat
**release and press** events `isAutoRepeat=false`. Holding U after opening the
power submenu then produces one unintended **mock** shutdown request. Other runs
classify the repeats correctly and pass. No duplicate final request was observed,
but the unintended first request is unacceptable for release.

The failing trace includes a repeated release/press at the same logged millisecond
after several correctly marked repeats. Qt's XCB keyboard implementation detects
core repeats by looking ahead for a matching timestamp/keycode in its event queue;
QML's KeyEvent does not expose that native timestamp. The evidence does not prove
this also happens on Manjaro's Qt stack or identify a safe OPM-only correction.
The candidate deliberately does not guess with a debounce delay, disable system
repeat, or change window focus. **Do not promote this candidate until this gate is
resolved.** The stronger held-key test remains enabled in the Docker test recipe
and can fail the build. Ordinary matrix coverage can be run separately to retain
results when the stress test fails.

## Automated verification

Tests use Debian 13, Qt 6.8.2 and Plasma/KWin 6.3.6 in a disposable container,
not the physical Manjaro Plasma/KWin 6.7.5 workstation. No real shutdown, restart,
logout, suspend, hibernate or lock was executed. All policy/final calls in the
power harness are private or injected; the harness points both bus addresses to
its private bus and replaces Lock with a recording script. It starts the mocks
before the production backend and never forwards requests to host services.

- Native CTest: 11/11 suites passed. New session-power suite: 23 QTest results,
  including all three actions × both OPM modes × both KDE-global settings,
  exact service/path/interface/method/no-argument assertions, one-use selection,
  stale preference, custom labels, editor round-trip and backups, Kiosk denial,
  permission denial, failures, malformed reply, timeout and late reply handling.
- Standalone suite passed again after adding modified/repeated-key coverage.
- Python suite: 517 passed, 8 skipped, 18 subtests passed. The final targeted QML run passed
  64 tests after the keyboard guards and return routing.
- Private native/legacy contracts: 15 passed. Disposable native packaging and
  rollback: 10 passed, including the actual 1.0.1 installer and failure recovery.
- Real Plasma X11 crossing tests passed with the launcher visible/hidden and
  standalone comparison. Root/flyout dismissal tests passed for Escape, outside
  click and real Meta+X in both launcher states. Startup tests passed all eight
  X11/Wayland combinations of slow menu, slow preferences, warm startup and left
  panel placement.
- `plasma_keyboard.py` uses the production backend and exact recorded power calls.
  X11 uses real KGlobalAccel Meta+X and XTest input with a harmless application
  behind OPM; Wayland uses the applet activation signal and QtTest window events.
  This is not a claim of end-to-end Wayland compositor shortcut injection.
  All four ordinary matrix seats passed. The matrix covers all six U sequences in both confirmation modes,
  toggle-off, Escape, arrows/Enter, custom/disabled keys and modified input, with
  both launcher visibility states. Results are retained per seat in JSON.
- The final `--held-repeat` run failed: its ordinary cases recorded 14 expected
  requests, then holding U produced a 15th, unintended mock `promptShutDown`
  request when a repeat was marked fresh. The test failed during its popup-state
  assertion as that asynchronous request was being dispatched. Earlier stress
  runs failed directly at the no-additional-request assertion.
  Recognized auto-repeat, editable-field exclusion, nested return routing and
  ambiguous access-key collisions also have deterministic QML regressions.

XTest needs distinct millisecond timestamps for a genuine release/repress of U.
The harness uses a two-millisecond transport interval between those input events,
without waiting for a flyout frame or focus change between submenu and action.
Before Meta+X it waits for the background application to acquire actual X input
focus and for Plasma to observe the old popup/parent becoming inactive; EWMH
active-window acknowledgement alone was too early. These are fixture
conditions, not production sleeps or focus changes.

Reproduce in a disposable environment with the dependencies in
`native/tests/editor.Dockerfile` (including test-only `qml6-module-qttest`):

```sh
umask 022
cmake -S . -B /tmp/opm-power-build -G Ninja -DOPM_BUILD_PACKAGE=ON -DOPM_INSTALL_TEST_HOOKS=ON
cmake --build /tmp/opm-power-build --parallel 2
QT_QUICK_CONTROLS_STYLE=Basic ctest --test-dir /tmp/opm-power-build --output-on-failure
python3 native/tests/plasma_keyboard.py --output /tmp/opm-keyboard-results \
  --backend /tmp/opm-power-build/native/open-power-menu-native
python3 native/tests/plasma_keyboard.py --platform xcb --held-repeat \
  --output /tmp/opm-held-key-results --backend /tmp/opm-power-build/native/open-power-menu-native
```

The harness refuses existing output case directories. `--widget-source` accepts
another checkout for before/after widget comparison with the same mock-backed
native backend. Test copies contain input/trace hooks; the installed widget does
not import QtTest or run those fixture timers. Existing product diagnostics stay
default off and observation-only.

## Physical acceptance and remaining release gates

1. Resolve the held-key failure with repeatable evidence and a passing stress test.
   Use mock actions, never genuine session-ending actions, for repeat/focus stress.
2. After an explicitly authorized installation, validate on Manjaro Plasma/KWin
   6.7.5, recording its Qt version. Test X11 with Brave, Dolphin and Konsole active,
   and Wayland, with the original launcher visible and hidden. Test automatic
   pointer dismissal both disabled and enabled; preserve all existing settings.
3. Test real Meta+X open/close; U then U/R/I/S/H/L; rapid successive distinct presses;
   holding U, Enter, Escape and arrows; modified keys; nested Escape/Left and root
   Escape; editable fields; unavailable entries; custom, disabled and ambiguous
   access keys. Use an isolated mock-backed test profile for activation tests.
4. Verify Configure save/reopen/import/export, checkbox default and label ellipses,
   stale selection refusal, custom titles/layouts, backup history and unchanged
   global shortcuts. Repeat the prior session-reliability login matrix and popup
   crossing/dismissal checks. Wayland global shortcut/focus behavior still needs
   physical acceptance; virtual window-event tests do not substitute for it.
5. Actual machine Shutdown/Restart/Sign out and Sleep/Hibernate acceptance requires
   separate explicit authorization, saved work and controlled sessions. Check both
   OPM settings against opposite KDE global settings, app cleanup and cancellation,
   and the difference between request acceptance and completed session shutdown.
6. Validate a distribution-matched complete native package, installation and 1.0.1
   rollback on an authorized disposable target before release. Deferred taskbar
   ghosting is not claimed fixed by this work.

No commit, push, merge, tag, PR change, publication, release, session restart or
modification of the active Manjaro installation is part of this delivery.

## Patch delivery and complete inventory

Use **one** patch for its matching baseline:

- `opm-2.1-power-keyboard-incremental.patch`: latest local 34-file session candidate.
- `opm-2.1-power-keyboard-complete.patch`: clean `5b13848`.

Both are generated using `git diff --binary`, with relevant new files included
using `git add -N`. Application and file-byte comparisons are verified in separate
clean checkouts. Logs, build outputs and unrelated untracked files are excluded.
The delivery includes a machine-readable inventory with per-file hashes.

This step changes 24 files (including this report):

- `docs/POWER-KEYBOARD.md` (new)
- `native/CMakeLists.txt`
- `native/README.md`
- `native/editor_session.cpp`
- `native/model.cpp`
- `native/model.hpp`
- `native/power.cpp`
- `native/power.hpp`
- `native/qml/Main.qml`
- `native/standalone.cpp`
- `native/tests/contract.py`
- `native/tests/editor.Dockerfile`
- `native/tests/editor_gui_test.cpp`
- `native/tests/plasma_keyboard.py` (new)
- `native/tests/runtime.Dockerfile`
- `native/tests/session_power_test.cpp` (new)
- `native/tests/standalone.Dockerfile`
- `native/tests/standalone_test.cpp`
- `plasmoid/contents/ui/AccessKeys.js`
- `plasmoid/contents/ui/SideFlyout.qml`
- `plasmoid/contents/ui/main.qml`
- `tests/test_inmenu_js.py`
- `tests/test_popup_startup.py`
- `tests/test_qt_flyout.py`

The complete patch also preserves these 27 files from the local baseline,
for **51 files total**:

- `docs/SESSION-RELIABILITY.md`
- `docs/X11-GHOSTING-INVESTIGATION.md`
- `docs/X11-POPUP-DIAGNOSTICS.md`
- `native/editor_launch.cpp`
- `native/editor_launch.hpp`
- `native/editor_main.cpp`
- `native/main.cpp`
- `native/service.cpp`
- `native/service.hpp`
- `native/tests/editor_launch.py`
- `native/tests/editor_launch_probe.cpp`
- `native/tests/launch_probe.cpp`
- `native/tests/plasma_dismissal.py`
- `native/tests/plasma_popup.py`
- `native/tests/plasma_startup.py`
- `plasmoid/contents/config/main.xml`
- `plasmoid/contents/ui/PointerDismissal.qml`
- `plasmoid/contents/ui/PopupTrace.qml`
- `tests/test_appgrid_lifecycle.py`
- `tests/test_menu_exclusivity_icon.py`
- `tests/test_native_shortcut.py`
- `tests/test_popup_trace.py`
- `tests/test_v0413_adapters.py`
- `tests/test_v0416_popup_handoff.py`
- `tests/test_v048_target_activation.py`
- `tests/test_x11_popup_probe.py`
- `tools/trace-x11-popup.py`
