> Historical document, retained from the approved Phase 1 source. Versions,
> commands and status claims describe that earlier work. Use the [current documentation](../../README.md) for native 2.1 guidance.

# X11 dismissal/ghosting candidate

The original X11 popup-collapse correction is **physically verified by the
user** on Manjaro. The X11-only `Qt.Tool` flyout flag and its native
`WM_TRANSIENT_FOR` relationship are preserved without changes in this follow-up.
PR #10 remains draft; the source baseline is `5b13848` plus the complete
18-file popup candidate. No installation, panel, shortcut, or compositor setting
on the user's workstation was changed.

## Outcome and limits

The supplied recording confirms the residual Desktop row at about 12.8 seconds,
cleared by 13.6 seconds. It does not establish window ownership or map state.
The user reports Plasma and KWin **6.7.5**. This environment has Plasma/KWin
**6.3.6**, libplasma 6.3.5, Qt 6.8.2, and Mesa llvmpipe on Xvfb.

The persistent text remnant has **not been reproduced here**. Consequently,
there is no evidence-backed ghosting correction in this candidate. It extends
the default-off diagnostics and provides a native X11 observer to distinguish
these cases on the physical machine. No speculative animation disable, repaint
request, synthetic pointer workaround, forced window destruction, or focus
loop was introduced.

A separate, reproducible **Meta+X dismissal defect** was found and corrected on
X11: Plasma's activation callback can run after OPM's handler. In the baseline
trace, `openMenu.toggleOff` sets expanded=false, then an external expanded=true
arrives four milliseconds later with `powerIsOpen=false` and
`requestedMenu=none`. The root window is mapped again. This is a real mapped
window, not evidence for the Escape ghost shown in the recording.

The correction defers only the X11 `activated()` handler to the next event-loop
turn using `Qt.callLater`, after Plasma's synchronous signal handlers finish.
There is no timed delay or repeated activation. A regression tests both signal
connection orders; Wayland retains the existing immediate handler. The real
private-session test sends Meta+X through kglobalacceld rather than calling a
QML method to simulate the shortcut.

## Measured dismissal lifecycle

The first virtual run had compositing active but did not load slide/blur. That
run was insufficient for the visual question. Subsequent runs explicitly loaded
slidingpopups, blur and contrast **in disposable test profiles only**, with
`KWIN_EFFECTS_FORCE_ANIMATIONS=1`. Tests also used Breeze Dark and 2x scaling.

For Escape and outside clicks, and Meta+X after the ordering correction:

- X11 `UnmapNotify` is observed; the previously mapped applet/utility windows
  report `IsUnMapped` after dismissal. Keeping an unmapped QWindow for reuse is
  normal and does not indicate a leaked visible window.
- The root popup's Qt item stays parented to Plasma's popup content item. It does
  not move into the panel's QQuickWindow. Its Item.visible can remain true while
  its owning window is hidden; that alone is not a rendering leak.
- Root/flyout QWindow visibility becomes false; expanded becomes false. The
  existing external-collapse synchronization may follow native hiding by 100 ms
  in this Plasma version; OPM does not add another delay.
- Pre-started, windowless screen capture did not show persistent menu text in
  the panel. A later panel hover can change its tint slightly. Pixel differences
  are recorded as measurements, **not treated as a universal ghost-free
  assertion** or proof of physical acceptance.

These observations rule out a mapped-window or panel-reparenting leak in the
local tested Escape/outside-click paths. They cannot rule those out on the
physical 6.7.5 session. Stale compositor/blur content remains a hypothesis for
the recorded ghost, not an established root cause.

## Physical capture without changing focus

Use a candidate already loaded through your normal user-approved test install.
These steps only enable diagnostics; they do not install code or restart Plasma.
The native observer also works with the preceding complete candidate, although
its QML log lacks the new item-parent/frame fields.

1. Start both captures **before** reproducing:

   ```sh
   journalctl --user -f -o cat | rg --line-buffered 'OPM_POPUP_TRACE' > opm-dismissal-qml.log
   ```

   In another terminal, from the source checkout:

   ```sh
   python3 tools/trace-x11-popup.py --seconds 60 > opm-dismissal-x11.jsonl
   ```

   This needs `xdotool`, `xprop`, `xwininfo`, `xev`, and `stdbuf`. It reads native
   window IDs, type/parent/slide properties, geometry, stacking and map states;
   its xev processes subscribe only to structure/expose events. It creates no
   visible window, grabs no input, and requests neither focus nor repaint.
   Event timestamps are receipt times, not exact compositor presentation times.

2. Enable the existing default-off gate:

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

   Expect `trace-enabled`. Reproduce root-only Desktop hover then Escape with
   the pointer stationary; separately try outside click and Meta+X. Repeat after
   visiting a flyout without clicking an action. Keep the existing screen
   recording running. Note the order of attempts and when you intentionally
   move onto the panel to clear a remnant.

3. Repeat step 2 with `false` and stop the journal capture. Return the two logs,
   recording and Plasma theme name. No power action needs to be selected.

Interpretation: if the recorded pixels persist after the corresponding native
window's `UnmapNotify`/`IsUnMapped`, and the QML item remains in the hidden popup
rather than the panel, the evidence points to retained composited content. If a
window remains mapped, its ID/type/geometry identifies that separate lifecycle
path. The extra frameSwapped callbacks and Qt item/window identities help
correlate rendering with those native events. The QML logger deliberately does
not call `winId()`, which can create a native window as a side effect.

## Repeating the automated checks

The editor Docker recipe includes the new dismissal matrix. With its dependencies:

```sh
python3 native/tests/plasma_popup.py --dismissal --output /tmp/opm-dismissal-new
python3 native/tests/plasma_popup.py --dismissal --scale 2 --output /tmp/opm-dismissal-2x-new
python3 native/tests/plasma_popup.py --dismissal --diagnostics-off --output /tmp/opm-dismissal-off-new
python3 native/tests/plasma_popup.py --output /tmp/opm-collapse-new
python3 native/tests/plasma_startup.py --only wayland-ready --single-start --output /tmp/opm-wayland-new
```

All output paths must be new. Each session uses a fresh X display, private bus
and XDG profile, a read-only backend, and a normal active xterm behind OPM. The
matrix covers root-only and flyout dismissals by Escape, outside click and real
Meta+X, with the original launcher visible/hidden. Native events, lifecycle JSON,
compositor information and screenshots are retained. A single shell starts per
profile; none is restarted. Capturing screenshots creates no visible UI.

## Complete changed-file inventory relative to 5b13848

This self-contained candidate includes the physically verified collapse patch.
It is for a fresh checkout at that base; it is not an incremental patch to apply
over an already-patched tree. Use `git apply --check` before application.

| File | Purpose |
| --- | --- |
| `plasmoid/contents/ui/main.qml` | Attributed closes; item/parent/window/frame observations; X11 activation-order correction |
| `plasmoid/contents/ui/PopupTrace.qml` (new) | Default-off diagnostic snapshots, including object/animation/item state |
| `plasmoid/contents/ui/SideFlyout.qml` | Preserved verified X11 Qt.Tool correction and original trace hooks |
| `plasmoid/contents/ui/PointerDismissal.qml` | Preserved dismissal observation signals |
| `plasmoid/contents/config/main.xml` | Preserved default-off diagnostic setting |
| `native/tests/plasma_popup.py` (new) | Crossing fixture and private dismissal/scale/shortcut setup |
| `native/tests/plasma_dismissal.py` (new) | Six dismissal scenarios, native map/event checks, passive screenshots and pixel measurements |
| `native/tests/plasma_startup.py` | Preserved single-start option for Wayland validation |
| `native/tests/editor.Dockerfile` | Fixture dependencies and CI invocation |
| `tools/trace-x11-popup.py` (new) | User-led, read-only native X11 capture |
| `tests/test_popup_trace.py` (new) | Preserved trace attribution/default-off checks |
| `tests/test_x11_popup_probe.py` (new) | Read-only native state/geometry parsing |
| `tests/test_native_shortcut.py` | Shortcut handler fixtures and both Plasma signal orders |
| `tests/test_appgrid_lifecycle.py` | Preserved attributed-setter fixture adaptation |
| `tests/test_inmenu_js.py` | Preserved attributed-setter fixture adaptation |
| `tests/test_menu_exclusivity_icon.py` | Preserved attributed-setter fixture adaptation |
| `tests/test_popup_startup.py` | Preserved attributed-setter fixture adaptation |
| `tests/test_v0413_adapters.py` | Preserved named-callback fixture adaptation |
| `tests/test_v0416_popup_handoff.py` | Preserved attributed-setter fixture adaptation |
| `tests/test_v048_target_activation.py` | Preserved attributed-setter fixture adaptation |
| `docs/X11-POPUP-DIAGNOSTICS.md` (new) | Earlier collapse findings with physical acceptance update |
| `docs/X11-GHOSTING-INVESTIGATION.md` (new) | This investigation, limitations, inventory and capture procedure |

## Regression results for this candidate

- Full Python/QML suite: **502 passed, 8 skipped, 18 subtests passed**.
- Dismissal matrix: **24 scenarios passed** across six dismissal combinations,
  visible/hidden original launcher, and two runs (2x traced / 1x untraced).
  Additional 1x traced checks validate close attribution directly.
- Native state: root and any opened flyout were unmapped after each dismissal.
  Traced Escape/Meta+X closes are attributed to OPM; outside click to external
  Plasma handling. The untraced runs emitted no product trace records.
- Existing application-behind-widget crossing regression: **passed** for both
  launcher visibility states. The verified SideFlyout.qml is byte-for-byte
  unchanged from the complete collapse candidate.
- Real Plasma Wayland startup/reopening with one shell start: **passed**.
- `git diff --check`: passed. The self-contained patch is forward-applied and
  checked against a clean checkout of base `5b13848` before delivery.

Observed panel tint differences at 2x were at most 5–6 channel levels, without
visible retained text in the inspected frames; the 1x untraced comparisons were
identical. These are measurements on this fixture, not a physical acceptance
claim. The main release risk remains the unresolved 6.7.5 ghost and the version,
GPU, theme and compositor differences. The Meta+X correction is X11-scoped and
covered for both signal orders, but still requires physical acceptance there.
