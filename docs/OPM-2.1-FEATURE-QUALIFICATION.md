# OPM 2.1 resumed feature qualification — November 8, 2026

Starting commit: `4d672c2cc5f0eb51ac469e9fba5094556316e1fa`.
Continue `feature/native-architecture-v1.1` and draft
[PR #10](https://github.com/BB7Networks/Open-Power-Menu/pull/10).
Final implementation: `462a351a2642b5faf5f22e67691bb065241bdcfc`.
The final report commit is documentation only on top of that implementation. Stable remains
1.0.1, development 2.1.0-dev, next public release 2.1.0. Physical acceptance is
**Not run**; this report does not qualify a release candidate.

## Repository and baseline

The initial workspace was a clean stable checkout at `3405848` on local `work`.
Fetching the existing development branch recovered exactly `4d672c2`; no newer
remote changes, local edits or untracked source were discarded. PR #10 was open
and draft. Both baseline workflows were independently checked through GitHub:
[PR 42501949225](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42501949225)
and [push 42501946325](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42501946325)
completed successfully, with all eight jobs passing in each. The resolved older
Manjaro mirror timeout was not treated as an application defect.

The first correction checkpoint `4d0ec86` passed all eight jobs in
[PR 42524169511](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42524169511)
and [push 42524165643](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42524165643),
the latter after one unchanged-source Manjaro retry. The subsequent real-asset
visual review found and corrected the Aero contrast issue; those intermediate
artifacts are superseded.

The Aero correction at `69409d7` also passed all eight jobs in both workflows;
the push Manjaro job passed after one unchanged-source retry. A final narrow-window
keyboard check then demonstrated and corrected the hidden-focus issue below.

Final implementation workflows: [PR 42527140249](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42527140249)
and [push 42527135563](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42527135563).
**All eight jobs passed in both workflows**, with one unchanged-source Manjaro
retry in the push workflow (attempt 2). PR artifacts identify merge checkout
`8f6cb93712cf2f402d4faef5892c297c90f1f53e`.
Fetching that merge and comparing its complete tree with branch `462a351`
produced no differences. The baseline PR artifacts instead identify `7237ebd…`;
merge checkout IDs and branch implementation IDs must not be confused.

Each correction checkpoint had an initial push Manjaro build-step failure, followed
by a successful unchanged-source retry. Raw failed-job logs are blocked. The user
provided the `69409d7` failure excerpt: `pacman -Syu ...` exited 1 during dependency
installation, before application compilation or tests. That excerpt does not show
the underlying package/download error; other failures are not assigned that cause
without their logs. The earlier `cdeb2c0` mirror timeout remains a separate event.
No workflow or expected test result was changed to silence these failures.

## Demonstrated corrections

- Under Breeze, Native standalone menus painted Small/Standard/Large icons all
  at 16 logical pixels. A rendered-pixel regression caught this even though the
  configured metrics differed. The local menu stylesheet now also sizes the icon
  subcontrol for nonstandard presets. Native/Aero, Fusion/Breeze and hidden-icon
  checks pass; QApplication's style remains unchanged.
- Actual Breeze SVG screenshots also exposed flat light-theme icons disappearing
  against Aero. A local icon engine now brightens only flat dark monochrome artwork
  on Aero, preserving alpha/DPI, colored and multitone images and Native appearance.
  Regression checks cover those distinctions and the explicit Aero theme override.
- Keyboard Tab navigation in a 620x480 General page could focus and change
  preferences below the viewport without scrolling. The General page now reveals
  its focused control, independently of tabs and popup contents. The regression
  asserts the entire focused control is inside the viewport; actual screenshots
  confirm the new settings are visible. The complete dialog workflow also passes
  at 620x480.
- A fresh profile's import preview promised to preserve a nonexistent active file.
  It now explicitly says there is no previous file to back up. Existing-file
  imports still create protected recovery copies, including retention zero.
- Failed exports could leave an earlier success message visible. Failure now clears
  that status; import selection also clears stale portability success feedback.
  Existing-file refusal is exercised through the file picker and storage layer.

No storage transaction, authorization, inhibitor, checksum, plugin or ABI guard
was relaxed. No Python runtime dependency was introduced.

## Current local evidence

Disposable Debian 13 x86-64, Qt 6.8.2 (`qt6-base-dev 6.8.2+dfsg-9+deb13u2`),
KF6 Service 6.13.0-1 / Config 6.13.0-2, GCC 14.2, software rendering. Tests use
private profiles/buses; runtime and GUI test containers have networking disabled.

| Check | Current result |
| --- | --- |
| Portable/legacy/widget, pinned PySide6 6.10.2 | 466 passed, 8 existing skips, 18 subtests |
| Complete native CTest | 8/8 targets passed |
| Actual editor GUI target within CTest | 7 Qt Test cases passed, zero skipped |
| Backend-only differential/private D-Bus | 12 passed |
| Actual released 1.0.1 installation/upgrade/rollback | 9 passed |
| Standalone X11/Fusion, first correction checkpoint | 41 passed, 1 existing focus-seat skip |
| Standalone X11/Breeze, final implementation | 42 passed, 1 existing focus-seat skip |
| Standalone Weston, final implementation | 42 passed, 1 existing focus-seat skip |
| Standalone virtual KWin, final implementation | 43 passed |
| KWin, two outputs, scale 1.25, final implementation | 43 passed |
| Actual Breeze SVG icons, 640x720 / 144 font DPI / scale 1.25 | 108 combinations rendered; geometry/visibility/style assertions and representative visual review passed |
| Real Kirigami widget-row/flyout icon painting, Native/Aero | 2 passed; narrow-screen/144-DPI/125% matrix 4 passed |
| Complete Debian package and independent runtime image | Build and installation/activation/editor/reinstall/removal/rollback smoke passed |

The final CTest, 466-test portable suite and rebuilt Python-free runtime smoke
were rerun after the focus correction. The Breeze/Wayland menu matrix and three
fresh dialog processes ran after the Aero correction; menu code was unchanged
by the later editor-only correction. Twelve backend contracts and nine local
installer scenarios ran at the first correction checkpoint; those sources were
unchanged. Final CI reran their relevant workflows and all three distribution
upgrade/runtime gates on `462a351`.

The focused QML checks are included in the Python total. The new rendered-icon
cases are included in the standalone totals, not additional tests. X11/Weston
lack the KWin input-seat behavior required by the existing cross-process activation
case; KWin runs it successfully. These are functional checks, not performance
measurements or physical desktop certification.

### Actual editor and dialogs

The real Kirigami editor is exercised at 620x480 using Tab/End/Up/Space for the
new preferences with complete control visibility assertions, then Save,
destruction/recreation, all three tabs, persisted
selection checks, accessibility names and icon visibility enable/disable behavior.

The real Qt Quick fallback file dialogs receive mouse/keyboard input: cancel
Export; create a new export; choose the existing filename and confirm the file
picker's overwrite question; observe OPM's safe refusal and unchanged bytes;
select local Import; inspect unresolved-command warnings; cancel the preview;
preview again; mutate the source and click Apply; verify conflict and unchanged
active configuration; preview again and apply successfully; select and restore
the protected pre-import copy through the backup browser and confirmation button.
Malformed input and dirty-draft disabling are also checked. No imported command
executes. Desktop portal/KDE-native chooser variants still require physical testing.

The offscreen plugin did not reliably deliver input to the native preview popup.
CTest now prefers `xvfb-run` when available. Debian and pacman build images include
Xvfb/authentication **test** tools, and PKGBUILD records them as `checkdepends`;
independent runtime images and application dependencies are unchanged. Without
Xvfb, the offscreen fallback explicitly skips the new file-dialog interaction case
and cannot qualify it. The retained passing local CTest used X11 and skipped no
editor cases. No CI failure was hidden by changing an expected result.

A later repeated GUI run exposed a synthetic-pointer race: native popup grabs
could consult the cursor left over a closed picker. The test now moves the actual
virtual pointer before clicking and waits for the Apply signal. This corrects test
input delivery without bypassing any dialog operation. Three fresh private-bus/X11
processes subsequently passed the full dialog workflow with zero skips.

An initial dependency-notice test correctly refused directories created with the
container's inherited `umask 0000`. The final local run uses `umask 077`; no secure
filesystem checks were weakened. The Kirigami platform-plugin warning for Fusion
is retained; the actual QML editor loads and its interaction checks pass.

### Menus and hover

An additional 108-combination scratch matrix uses actual installed Breeze SVG
icons across Native/Aero, all densities/widths/sizes and visible/hidden icons on
a 640x720, 144-font-DPI, 125% virtual display. Geometry and application-style
assertions pass; representative screenshots were inspected. The review image
initially lacked Debian's separate Qt SVG plugins. Installing that desktop-theme
support in the disposable image enabled the actual assets; no new C++/runtime
link dependency was introduced. The minimal runtime image checks PNG-capable
operation, not SVG theme artwork.

Real painted pixels verify increasing icon sizes and complete hiding in Native
and Aero; screenshots were visually inspected. Existing density/width tests cover
all presets, long labels, hints, enlarged fonts and screen bounds. Hover coverage
now includes 300 ms alongside system/immediate/100/600 ms. Keyboard override,
cancellation and lifecycle tests are retained.

Both frontends intentionally keep the existing child visible while a sibling's
hover delay runs, replacing it when the delay completes. Keeping a usable path
into the old child avoids unnecessary disappearance. The shipped-QML test covers
return-to-child cancellation, sibling replacement and parent selection restoration.
Its offscreen Plasma-window stub needs an explicit cross-window Leave event;
that is an input-fixture limitation, not physical compositor evidence. Mirroring,
nested configuration propagation, fast/held access-key filtering and pending-timer
destruction remain covered by the existing suites. Additional scratch checks paint the shipped row/flyout QML with real Kirigami icons
(instead of the icon stub), including hiding, all sizes, Native/Aero and a 640x720
virtual screen at 144 font DPI and 125% scale. These passed and screenshots were
inspected. Their Plasma window primitives are still stubbed. Actual Plasma popup placement,
root widget integration, remote desktop and physical mixed-DPI remain separate gates.

### Import safety and compatibility

Additional native regressions cover the 4 MiB boundary, excessive JSON extension
and menu nesting, symlinked parents for import/export, fresh installation without
an active file, legacy JSON without a schema-version field, unknown metadata,
source inode replacement with identical bytes, and successful re-preview after
failure. Existing tests retain malformed/unsupported schema, dirty drafts,
stale source/active revisions, non-execution, local-path warnings, no-follow source
files, exclusive export and protected restore with retention zero.

Source review confirms bounded reads (including growth during a read), component
by component no-follow parent traversal, atomic exclusive export publication and
source revision checks both before and immediately before the locked atomic import
publication. A same-user process writing after the final check is outside a promise
of filesystem-wide locking of arbitrary input files; import applies the validated
preview bytes, never newly read unvalidated commands. No copying shortcut replaced
the existing storage engine.

## Runtime and distributions

The independent Debian runtime image contains neither Python/PySide6 nor compiler
or CMake. Its actual native installer/activation/editor/menu/reinstall/removal and
rollback smoke passed. The installer was rebuilt with `OPM_INSTALL_TEST_HOOKS=OFF`;
the runtime smoke sets fault variables and verifies they cannot inject a failure.
Python/PySide6 in the toolchain are compatibility/GUI test tools. Released 1.0.1
still needs its original runtime for rollback. No system package was removed.

Local Arch/Manjaro packages were not built: these use the separate GitHub CI
jobs. Final PR CI passed Debian, Arch and Manjaro packaging, installed runtime
and released 1.0.1 upgrade/rollback gates. The push attempt/retry result is
recorded above. These distribution gates do not certify a physical Plasma session.
Do not substitute the locally built Debian archive for a Manjaro package.

Final local Debian archive SHA-256:
`fad824b9e46a9fdd993bbbe6060cce6436eca167b67a48641eedbb798ea1dfe4`.
Actual bytes and the checked checksum are retained under
`/workspace/opm-artifacts/local-debian-462a351/`. This is the local Debian payload,
not the Manjaro candidate. The earlier Debian payload is retained separately.

## Artifact availability and handoff

Use [Manjaro artifact 13635987400](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42527140249/artifacts/13635987400),
`opm-2.1-dev-Manjaro-8f6cb93712cf2f402d4faef5892c297c90f1f53e`.
GitHub reports outer ZIP SHA-256
`3aaac6cf3c80e28afe20ccf514644cc804efe4971e26871ffcf29f7c95463fd2`.
The corresponding [Arch artifact 13635827823](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42527140249/artifacts/13635827823)
reports ZIP SHA-256
`c0abdb729a23c3a13d0759a0c96ff00f6d496bb7b11e13a7834e1fe49ff8f64b`.
Both expire November 15, 2026 and include the packages, native bundle, widget and
inventories per the successful CI collection step. These hashes are remote
metadata, **not independently verified downloads**.

Final Manjaro and Arch downloads were refused after redirect to
`productionresultssa30.blob.core.windows.net`; zero bytes of either archive were
retrieved. An earlier failed push-job log was refused at
`productionresultssa9.blob.core.windows.net`; zero log bytes were retrieved.
An official, unapplied environment-settings draft preserves the original custom
hosts and proposes only the five observed Azure storage hosts (`productionresultssa2`,
`productionresultssa9`, `productionresultssa13`, `productionresultssa17`,
`productionresultssa30`, all under
`blob.core.windows.net`). The configuration tool requires review, save and
publication; saving the draft alone does not change runtime access. No alternative
network path was used. Package checksums and the exact current Manjaro Qt/KF6/
Plasma/glibc inventories remain **blocked**, not inferred from historical data.
Metadata is retained under `/workspace/opm-artifacts/final-candidate-metadata.json`.

Baseline [Manjaro artifact 13625672800](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42501949225/artifacts/13625672800)
and [Arch artifact 13625961943](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42501949225/artifacts/13625961943)
were unexpired and scheduled for November 15, 2026. Their GitHub metadata is
retained locally, but both actual archive downloads were refused after redirect
to `productionresultssa17.blob.core.windows.net`. That destination is outside the
applied policy. No bypass or unrelated download service was used.

Archive metadata or GitHub's reported ZIP digest does not establish that package
bytes, internal checksums or inventories were downloaded and independently verified.
Current package hashes and exact rolling-distribution inventories must be read from
the downloaded candidate's `PACKAGE.sha256`, bundle checksum, `SOURCE-COMMIT`,
`os-release`, `packages.txt` and `runtime-packages.txt`. See the added controlled
candidate procedure in [physical acceptance](OPM-2.1-PHYSICAL-ACCEPTANCE.md).

## Remaining gates

Verify the exact final candidate's downloaded bytes and inventories before
installation. The parallel push retry does not replace that
artifact identity.
Then the user performs the existing physical Manjaro Wayland-first, X11-second
procedure: backup/upgrade/recovery, harmless editor/menu/access-key/appearance and
launcher tests, monitor/scaling and remote-desktop checks, then rollback. All
physical rows remain **Not run**. Sleep/Hibernate, authorization/inhibitors and
logout/restart/shutdown require separate explicit permission and supervision.
No live desktop installation, Plasma restart, panel/shortcut change, power action,
merge, release, tag or Store publication was performed.

Local reproduction logs/screenshots are under ignored `work/qualification/`.
The full build is `work/review-build` in `opm-review:complete`; run
`umask 077; dbus-run-session -- ctest --test-dir work/review-build --output-on-failure`.
The runtime smoke image is `opm-review:runtime`. Test logs distinguish discarded
setup/harness attempts from the retained passing `ctest-package-focus.log`,
`display-aero-final.log`, `dialog-repeat-final.log`, `theme-matrix-aero.log` and
`runtime-focus.log`. The final narrow-editor screenshot is
`work/qualification/screenshots/editor-general-narrow-0.png`. Earlier checkpoint evidence is in `pytest-final.log`,
`contract.log` and `packaging.log`.
