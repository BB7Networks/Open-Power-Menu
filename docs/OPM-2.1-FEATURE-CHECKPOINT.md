# OPM 2.1 feature checkpoint — November 8, 2026

## Resumed qualification

Resumed from exact `4d672c2cc5f0eb51ac469e9fba5094556316e1fa` on the existing
development branch; PR #10 remains draft. Both checkpoint workflows passed all
eight jobs. Current corrections and verification are recorded in
[feature qualification](OPM-2.1-FEATURE-QUALIFICATION.md). Physical Plasma and
supervised power acceptance remain unperformed.

The following is the retained original checkpoint, not current CI status.

## Original feature checkpoint

Paused at the user's request before full qualification. Start: `cdeb2c0ee425fc85ca2f090291fc757d2d241b44`.
Continue `feature/native-architecture-v1.1` and draft [PR #10](https://github.com/BB7Networks/Open-Power-Menu/pull/10).
The checkpoint commit is the commit introducing this document. Stable remains 1.0.1;
development remains 2.1.0-dev. This is **not completion of the feature handoff**.

## Existing versus added

Existing: shared access keys and nested presets, optional hints/master toggle,
independent binding reset, 500–5000 ms pointer dismissal (1200 ms default, disabled
by default), native power policy, hierarchical editor and reversible installer.
Their implementations were retained. No new global shortcut or power dispatch path.

Added in this checkpoint:

- Shared `submenu_hover_delay_ms` (`-1` default, `0` immediate, 100–600 ms/100 steps),
  `menu_density` (`standard`), `menu_width` (`auto`) and `menu_icon_size` (`standard`).
- Widget-owned cancellable hover timers and shared font-aware row/icon/width metrics;
  propagation through nested flyouts. Standalone per-menu Qt proxy styles, native
  hover timing and bounded preferred widths; Aero spacing respects density.
- General-tab controls; Backups-tab local JSON file pickers and import preview.
- Portable draft export excludes launcher/button/retention preferences and never
  overwrites an existing file. Private, atomic exclusive publication.
- Import validates bounded local JSON, preserves compatible metadata and local
  preferences, warns about sensitive paths/unresolved commands, and never runs a
  command during preview/application. Dirty drafts, stale source files and changed
  active configurations are refused. Locked atomic application keeps a protected
  pre-import recovery copy even with retention zero; successful import resets the
  editor history. The backup browser can restore that copy.
- Configuration reference, roadmap and additional physical acceptance cases.

No required external runtime dependency was added. Qt modules already used by the
editor provide the file dialogs; filesystem and validation use the existing native
storage stack. Defaults retain the frontend-specific hover policy (widget immediate,
standalone desktop style). Standard icon size remains frontend-native; exact pixels
are not promised identical between Qt Quick and Qt Widgets.

## Verified locally

- Debian 13 container, Qt 6.8.2/KF6 6.13: complete native build succeeds.
- Pinned PySide6 6.10.2 Python/widget regression: **464 passed, 8 existing skips**.
- Focused shipped-QML flyout checks: **14 passed**; dismissal/hover timer checks:
  **14 passed**, including cancellation and destruction. These are included in the
  Python total, not additional tests.
- Import round-trip, unknown metadata, malformed/unsupported schema, dirty draft,
  stale source/active conflicts, protected backup/restore at retention zero,
  non-execution, cancellation, symlink refusal and exclusive export tests pass.
- Complete native CTest: **8/8 targets passed** (14.77 seconds), including
  standalone appearance/hover cases and native editor QML loading. The expected
  offscreen cross-process focus-seat case remains skipped.

This pass has not rerun the backend differential D-Bus contract, actual disposable
installer/legacy upgrade/rollback, backend-only dependency isolation, or the virtual
X11/Weston/KWin matrix locally. Historical results in other reports are not evidence
for the additions. The eight existing CI jobs are preserved and will run after push;
inspect their results on resume before claiming Debian/Arch/Manjaro qualification.
Every physical acceptance case remains **Not run**.

## Resume here

1. Read the latest PR/push workflow results for the checkpoint. Fix failures and
   verify all eight jobs, including separate Arch/Manjaro package/runtime upgrades.
   Starting `cdeb2c0` had 7/8 passing: Manjaro's Berkeley mirror timed out downloading
   `debugedit-5.3-2`'s signature, before compilation. The GitHub connector's job-log
   tool works; shell redirects to Azure storage remain blocked. Do not ask the user
   to change shell variables for that network allowlist.
2. Complete standalone native/Aero icon-size visual verification with real icons,
   large fonts/fractional DPI, narrow screens and long labels/hints. Verify theme
   integration with Breeze as well as Fusion; no global style replacement is allowed.
3. Expand interaction checks for rapid sibling switching while a child is open,
   nested configured delays, held/fast keys, focus restoration and mirrored flyouts
   on virtual X11/Wayland. QML tests use stub Plasma windows: they do not prove actual
   compositor behavior. Keep keyboard/click activation immediate and text input safe.
4. Exercise new editor controls and file-dialog/preview Apply/Cancel paths through
   actual GUI input, including constrained window sizes and screen-reader names.
   Current session tests cover the import transaction; general QML loading passes.
5. Review import limits further (oversize/parent symlinks, source changes during
   publication, fresh installation without an active file) and exported metadata.
   Preserve unknown compatible fields, local launcher/shortcuts and protected copies.
6. Run backend-only and private-D-Bus contracts plus disposable installer rollback
   against released `3405848`; inspect CI distribution snapshots/checksums. Preserve
   expiring development artifacts through the GitHub connector where possible.
7. Replace this checkpoint status with the requested ten-part completion report
   only when the feature and regression gates pass. Then begin the prepared physical
   Manjaro Wayland/X11 acceptance under separate authorization.

## Local reproduction

Repository: `/workspace/Open-Power-Menu`. Scratch logs and images are not committed.
The existing `opm-review:complete` Docker image has Debian native build/Qt dependencies.
Mount the repository as `/src`, set the working directory to `/src`, and use a private
`dbus-run-session` with network disabled. Full build is `work/review-build`.

```sh
cmake --build work/review-build --parallel 2
dbus-run-session -- ctest --test-dir work/review-build --output-on-failure
PYTHONPATH=/src/work/pyside6 python3 -m pytest -q tests
```

For Python tests, bind the available Node executable as `/usr/local/bin/node`; the
pinned PySide6 target is in `work/pyside6`. Specify `tests` explicitly: a bare pytest
collects the archived legacy source under `work/legacy` and creates import collisions.
The distro PySide6 version differs from the pinned CI version. Do not build shared
binaries concurrently with tests using them. Logs: `work/feature-build.log`,
`work/feature-ctest.log`, `work/feature-pytest.log`, `work/feature-qml-tests.log` and
`work/feature-dismissal-tests.log`.

No merge, tag, release, publication, active workstation installation, dependency
removal or actual host power operation was performed or is authorized by this pause.
