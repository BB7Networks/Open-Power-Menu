# Held-key stabilization evidence and mock acceptance

The original 64-file patch continued the **51-file power/keyboard candidate**, preserving its
contents before making these changes. Base: `5b1384832c19d3d1d9a5dbadf8421f6e9b612811`,
branch `feature/native-architecture-v1.1`. That patch delivery performed no commit,
push, release, PR change or workstation installation. The release candidate now
incorporates that complete patch; see [RC1 release notes](../RELEASE-NOTES-v2.1.0-rc1.md)
for artifact provenance and current qualification. The results below describe the
original held-key qualification, and the mock acceptance procedure still applies.
PR #10 remains draft. X11 taskbar text ghosting is still deferred.

## Cause and correction

Qt's XCB core-key repeat detection looks ahead for a matching release/press
pair in its event queue. During a real X11 key hold, Qt sometimes delivered a
synthetic release and the following repeat as `isAutoRepeat=false`. The old
per-event check then accepted U again in the newly opened native flyout. Focus
transfer changed the receiving window; it did not prove another physical press.
Conversely, two genuine, same-millisecond presses can be marked as repeat.
Neither a cooldown nor trusting the Qt repeat flag resolves both cases.

A simultaneous XI2/Qt probe on the private X server observed one raw physical
press and release during a hold, while Qt received multiple core release/press
pairs. Two deliberate zero-delay presses produced two raw pairs. The regression
trace also demonstrates both mismatches: repeated U events marked fresh are
rejected, and genuine presses marked repeat are admitted. Earlier captured X11
stress evidence contains seven rejected fresh-flag U events and two admitted
repeat-flag physical presses. No real power action occurred.

The correction is a small shared native input guard:

- On X11, a separate XCB connection subscribes to XInput2 raw key events. A
  bounded ledger grants one admission per physical press, matched to Qt's native
  scan code and server timestamp. Core Qt releases never rearm it. Device-held
  state survives focus changes, popup dismissal and reopening. Initial keymap
  snapshots and hierarchy changes quarantine uncertain held keys.
- A read-only X server ordering barrier drains the separate connection before
  admission. There is no timing threshold. Queued genuine presses survive their
  releases, including multiple press/release pairs with the same timestamp.
  Missing evidence, unsupported XI2, connection failure and queue overflow lose
  permission rather than manufacture a new press.
- One private QML plugin filters only OPM's registered popup/flyout QWindows.
  It does not filter the shared panel. The standalone menu uses the same guard.
  Internal standalone Right/Return routing happens only after an admitted press.
  Root/flyout events share state, so changing the receiving window does not rearm
  a key. Up/Down navigation can repeat; selection, Escape, Left and Right require
  separate physical presses. Editable controls retain normal typing/repeat.
- On Wayland, one shared held-key set uses the compositor's Qt release events;
  repeated releases are ignored and false-flag duplicate presses are rejected.
  Focus/menu changes do not clear it. A release outside OPM's windows cannot be
  observed on Wayland: that key remains quarantined until an observed non-repeat
  release. One release/press in OPM restores it; no timer guesses that it is up.
- The existing default-off popup diagnostics report admission/rejection, Qt's
  repeat flag, target window and focus item. Raw global key events and text are
  not logged. There are no XKB setting changes, global repeat changes, input
  grabs, added focus requests or focus loops in production.

The existing X11 `Qt.Tool` / `WM_TRANSIENT_FOR` correction is unchanged. The
existing deferred Meta+X toggle now also runs at the end of the activation signal
on Wayland: the private KWin test observed Plasma eagerly expanding after OPM's
intentional close callback. This uses `Qt.callLater`, without a timed cooldown.
Session resolution, Configure, confirmation settings, KDE-native dispatch,
configuration migration and protected selection identities remain intact.

## Packaging

`nativeinput/libopminputplugin.so` and its `qmldir` are included inside the widget
bundle. The installer validates the staged plugin before cutover; missing or
corrupt helpers leave the previous installation intact. A source-only QML copy
without the helper fails closed for keyboard navigation and activation. Build
the matching helper on the target distribution; this patch is not a portable
binary. Debian GUI builds add `libxcb-xinput-dev`, runtime `libxcb-xinput0`;
Manjaro supplies these through `libxcb`.

## Regression results and limits

Tests ran in an isolated Debian 13 lab with Qt 6.8.2 and Plasma/KWin 6.3.6.
Physical Manjaro Plasma/KWin 6.7.5 acceptance is still pending. All power policy
and final operations used injected/private mocks. Both bus addresses were
redirected to the private fixture; Lock used a recording executable. No real
shutdown, restart, logout, suspend, hibernate or lock was executed.

| Check | Result |
| --- | --- |
| Native CTest, including editor/session/power/model/recovery/input | 12/12 suites pass |
| Physical-input ledger | 27 QTest results pass; both Qt repeat flags, same timestamp, unknown state, overflow, shared release |
| Full keyboard stress matrix | All four seats pass: X11 visible/hidden, Wayland visible/hidden; no unintended requests |
| Session power actions | 23 QTest results pass, including immediate/confirmed routes, policy, stale selections and ambiguous replies |
| Standalone on real private X11 input | 51 pass, 1 platform-specific skip |
| Standalone on virtual KWin Wayland | 52 pass |
| Python/QML/JavaScript regressions | 518 pass, 8 skips, 18 subtests pass |
| Private backend/legacy contracts | 15 pass |
| Disposable installation/upgrade/rollback | 11 pass, including missing/corrupt helper preflight and actual 1.0.1 rollback |
| X11 row crossing, disabled rows, separators, Search/Run, flyouts, standalone comparison | Pass with original launcher visible/hidden and automatic pointer dismissal off |
| Root and flyout dismissal | Escape, outside click and real Meta+X pass in both launcher states |
| Startup and configuration readiness | All eight X11/Wayland cases pass |
| Manual Xephyr fixture startup/cleanup | Pass, zero requests without input |

A fresh build from the applied complete patch also passed all 12 native suites
and all 11 packaging tests. Crash/rollback tests require the documented
`-DOPM_INSTALL_TEST_HOOKS=ON`: an initial run without it failed four tests that
expected deliberate crashes. The correctly configured rerun passed; hooks were
then disabled again. This required no source correction.

The keyboard matrix covers immediate/confirmed U/U, U/R, U/I, U/S, U/H, U/L,
modifier exclusion, custom/disabled assignments, Enter/arrows/Escape, repeated
activation, and both launcher states. Held-U must record **zero** requests until
release and deliberate repress. Held R/I/S/H/L selects once; keeping the key down
through dismissal/reopening cannot select again. A deliberate release/repress
then selects exactly once more. Held Escape returns one level only. X11 also
tests a key held before opening, input/focus in another application, genuine
server repeats, and zero-delay U/U. Synthetic native tests vary `isAutoRepeat`
independently of physical evidence.

Final expected mock totals were 27 per X11 seat and 25 per Wayland seat. These
include the ordinary action matrix and deliberate re-presses, not actions caused
by holding a key. Each seat's `stress.json` records the cases; `requests.jsonl`
records the exact final methods. The formerly failing one-second X11 U hold now
leaves the count unchanged and the submenu open, followed by exactly one request
after release/repress.

Wayland integration uses virtual KWin, the applet activation signal and QtTest
window input. It does not claim compositor-level global shortcut injection or
physical Wayland keyboard acceptance. Synthetic input is confined to mapped OPM
windows: QtTest falls back to the panel for hidden windows, which can invoke
KRunner. The X11 tests exercise closed-window input using real XTest. Test
readiness waits for previous mock dispatch completion and actual X11 input
focus, not merely Qt's grouped active-window state. These are fixture checks,
not production delays or activation requests.

## Reproduce without installing

Use a disposable lab with the dependencies in `native/tests/editor.Dockerfile`,
plus the package-build dependencies in `native/tests/packaging.Dockerfile` when
testing installation. Commands below build only inside the checkout:

```sh
umask 022
cmake -S . -B build/held-key -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DOPM_BUILD_EDITOR=ON -DOPM_BUILD_STANDALONE=ON
cmake --build build/held-key --parallel 2
ctest --test-dir build/held-key --output-on-failure
python3 native/tests/plasma_keyboard.py \
  --backend "$PWD/build/held-key/native/open-power-menu-native" \
  --output /tmp/opm-held-key-new --held-repeat
```

Use a new output directory each time. The harness creates private profiles,
displays and D-Bus services, copies the plugin into its disposable widget and
records `requests.jsonl`, `results.json`, `stress.json` and `plasma.log` per seat.
It does not install into the user's Plasma profile.

## Physical acceptance with private mocks

Use a disposable VM first. For a nested test on the target X11 stack, install
only the test/build dependencies if needed and build as above. Also require
Xephyr (`xserver-xephyr` on Debian, `xorg-server-xephyr` on Manjaro), QtTest's QML
module, PySide6 QtCore/QtGui/QtDBus, `xdotool`, `qdbus6`, and `kglobalacceld`.
Do not run the OPM installer or replace/restart the workstation panel.

```sh
python3 native/tests/plasma_keyboard.py \
  --backend "$PWD/build/held-key/native/open-power-menu-native" \
  --output /tmp/opm-physical-visible-new --platform xcb --manual-seconds 300
# Repeat separately with --hidden and a different output directory.
```

Wait for `SAFE_MANUAL_READY` in the case's `session.log`. The nested window is
titled **OPM PRIVATE MOCKS - no real power actions**. Click inside it and use
Xephyr's Ctrl+Shift keyboard grab before Meta+X; otherwise the host's shortcut
could receive the key. If capture is uncertain, use the disposable VM. Only
operate the OPM widget inside this nested test desktop. The fixture has
confirmation disabled and no automatic power selections.

Watch the case's `requests.jsonl` from a separate terminal (`tail -F` handles a
file that does not yet exist). Perform these steps with the harmless application
active behind OPM:

1. Meta+X, hold U for several seconds: submenu opens once; request count stays
   unchanged. Release U and press U again: exactly one `logoutAndShutdown` record.
2. Reopen, type U/U rapidly: exactly one new record, with no required pause.
3. Hold U through Meta+X dismissal/reopening and application focus changes:
   no new selection until a release and deliberate press. Release in a different
   OPM window and repeat; the shared ledger must accept the next press once.
4. Open the power flyout, hold R/I/S/H/L in separate trials: one record per
   physical press. Keep it held while reopening and entering the submenu: no
   second record. Release and press again: exactly one more.
5. Check Escape, Left, Right, Enter, Up/Down, outside clicks and repeated Meta+X.
   Repeat with the launcher hidden. The automated matrix separately covers
   custom/disabled assignments and both confirmation modes.

The seat exits after the requested duration and terminates its private
processes. Save the logs and counts. An unintended request, missing helper or
unexplained admission remains a release blocker. These mock-only checks do not
authorize or require testing a real power operation.

## Patch delivery

`opm-2.1-held-key-incremental.patch` applies to the exact latest 51-file candidate.
`opm-2.1-held-key-complete.patch` applies to clean `5b13848`. Apply one appropriate
patch, not both. New files are included using `git add -N` and `git diff --binary`;
logs, downloaded packages and build outputs are excluded. Both patches were
applied in separate clean verification checkouts: all 64 required files exist
with identical source hashes and executable modes, including the new helper,
QML loader, diagnostics, settings and tests.

## Complete changed-file inventory

64 files differ from clean `5b13848`; 29 change in this increment.
The remaining 35 files are carried forward byte-for-byte from the 51-file candidate.

### Changed in this increment

- `.github/workflows/tests.yml`
- `docs/HELD-KEY-STABILIZATION.md`
- `docs/POWER-KEYBOARD.md`
- `native/CMakeLists.txt`
- `native/README.md`
- `native/input.qmldir`
- `native/input_plugin.cpp`
- `native/packaging/bundle.cmake.in`
- `native/packaging/installer.cpp`
- `native/physical_keys.cpp`
- `native/physical_keys.hpp`
- `native/standalone.cpp`
- `native/standalone.hpp`
- `native/tests/editor.Dockerfile`
- `native/tests/packaging.Dockerfile`
- `native/tests/packaging.py`
- `native/tests/physical_keys_test.cpp`
- `native/tests/plasma_keyboard.py`
- `native/tests/plasma_popup.py`
- `native/tests/plasma_startup.py`
- `native/tests/standalone.Dockerfile`
- `native/tests/standalone_test.cpp`
- `plasmoid/contents/ui/AccessKeys.js`
- `plasmoid/contents/ui/NativeInput.qml`
- `plasmoid/contents/ui/SideFlyout.qml`
- `plasmoid/contents/ui/main.qml`
- `tests/test_inmenu_js.py`
- `tests/test_native_shortcut.py`
- `tests/test_qt_flyout.py`

### Carried forward unchanged

- `docs/SESSION-RELIABILITY.md`
- `docs/X11-GHOSTING-INVESTIGATION.md`
- `docs/X11-POPUP-DIAGNOSTICS.md`
- `native/editor_launch.cpp`
- `native/editor_launch.hpp`
- `native/editor_main.cpp`
- `native/editor_session.cpp`
- `native/main.cpp`
- `native/model.cpp`
- `native/model.hpp`
- `native/power.cpp`
- `native/power.hpp`
- `native/qml/Main.qml`
- `native/service.cpp`
- `native/service.hpp`
- `native/tests/contract.py`
- `native/tests/editor_gui_test.cpp`
- `native/tests/editor_launch.py`
- `native/tests/editor_launch_probe.cpp`
- `native/tests/launch_probe.cpp`
- `native/tests/plasma_dismissal.py`
- `native/tests/runtime.Dockerfile`
- `native/tests/session_power_test.cpp`
- `plasmoid/contents/config/main.xml`
- `plasmoid/contents/ui/PointerDismissal.qml`
- `plasmoid/contents/ui/PopupTrace.qml`
- `tests/test_appgrid_lifecycle.py`
- `tests/test_menu_exclusivity_icon.py`
- `tests/test_popup_startup.py`
- `tests/test_popup_trace.py`
- `tests/test_v0413_adapters.py`
- `tests/test_v0416_popup_handoff.py`
- `tests/test_v048_target_activation.py`
- `tests/test_x11_popup_probe.py`
- `tools/trace-x11-popup.py`
