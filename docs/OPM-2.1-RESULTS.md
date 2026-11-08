# 2.1 development checkpoint — November 8, 2026

The user requested a stopping point after the resumed distribution-qualification
pass. This checkpoint implements the 2.1 feature work and preserves stable **1.0.1**.
Development remains **2.1.0-dev** and PR #10 remains draft. No merge, tag, release,
Store publication or modification of an active Plasma desktop occurred.

## Implemented

- Shared access-key metadata and safe migration, root/nested presets, collision
  validation, hint/master preferences, independent reset and editor Undo/Redo.
- Widget and standalone local-key navigation through the same validated action
  definitions; disabled entries cannot execute and global Meta+X is unchanged.
- Configurable 500–5000 ms pointer dismissal, 100 ms steps, default 1200 ms;
  saved enable/disable choice, disabled default, keyboard/editing/re-entry guards.
- Native Sleep/Hibernate capability and policy checks, Polkit authorization and
  logind inhibitor enforcement. Existing KDE shutdown/restart/logout prompts remain.
- Native editor controls, availability details and useful power-error feedback.
- Post-commit, one-time PySide6 review with Keep recommended, literal read-only
  pacman/dpkg/APT queries, separate safe state, unattended operation, and a legacy
  runtime preflight before rollback. No system dependency removal.
- Separate Arch and Manjaro package/upgrade CI, checksum-pinned committed sources,
  sealed PKGBUILD artifacts, independent runtime images and recorded distribution
  inventories. Test fault hooks are compiled out of delivered development bundles.
- Qt platform-plugin discovery follows advertised xcb/wayland capabilities and
  verifies actual loading, supporting filename changes without dropping ABI checks.
- Optional cleanup queries have a five-second total budget, one-second per-query
  timeout and bounded accepted output. Folded pacman dependency lists are retained;
  concurrent notice writes use a separate filesystem lock.
- Updated roadmap/Store/upgrade docs and physical acceptance checklist. Existing
  migration/performance history retained.

No external runtime package was added. The standalone now links Qt DBus, already
part of the complete native bundle. The legacy Python catalogs and stable installer
remain intact. Existing layouts are never replaced or expanded during migration;
Sleep/Hibernate can be added in Layout, while fresh defaults include them.

## Local evidence

- Legacy/widget Python/Qt suite: **455 passed, 8 existing skips, 18 subtests passed**,
  including four new source-archive preparation cases.
- Complete Debian 13 amd64 native build: **8/8 CTest targets passed**, including
  interaction/power, dependency-review and platform-plugin suites, plus existing
  model, recovery, editor session, actual GUI and standalone tests. The final
  dependency-review suite separately passed **14 Qt Test cases** including setup/
  cleanup and the real slow-query timeout case.
- Native/legacy differential and private D-Bus contract: **9 passed**.
- Disposable installation/upgrade suite: **9 passed**, including the actual released
  1.0.1 source at `34058480`, user paths with spaces, activation, rollback, corruption,
  interrupted transactions and personal-state preservation.
- Extended legacy-upgrade check: **1 passed**, verifying the one-time notice and
  refusal to replace native files when the old Python runtime is unavailable.
- Virtual X11: **25 passed, 1 explicit focus-seat skip**. Virtual KWin Wayland:
  **26 passed**, including the new access-key sequence and configured-delay checks.
  These disposable sessions do not certify physical desktop behavior.

Power tests use injected D-Bus transport and harmless probes. No actual host power
operation was executed. Initial migration bugs were caught by existing tests and
fixed before this checkpoint. Initial install/contract failures were caused by a
missing passwd entry for UID 1000 in the disposable toolchain; adding its test user
resolved them. A local pytest collection run accidentally discovered the exported
legacy source under work/; the final suite explicitly targeted tests/ and passed.

## Remaining qualification / next pass

- Final CI results for the resumed code are recorded below. Local Arch/Manjaro
  mirrors are blocked by the environment proxy; distribution checks run in GitHub
  CI. No proxy restrictions were bypassed.
- Physical Manjaro/Plasma acceptance remains incomplete. Container checks do not
  certify live desktop integration. Build separately for each intended snapshot;
  Debian binaries are not portable Manjaro packages.
- Review responsiveness under slow/unavailable power services: capability calls are
  synchronous with a 1500 ms timeout per call; interactive authorization allows a
  longer wait. Real desktop responsiveness and Polkit behavior need acceptance.
- Broader unusual legacy encoding/integer-range migration cases remain a review
  item. The prior editor PSS increase from **63.69 to 71.57 MiB** is retained in
  [performance history](architecture/native-performance.md); no new benchmark in
  this pass supersedes that result.
- Complete every physical Wayland/X11, launcher/AppGrid, mixed-DPI, remote-desktop,
  editor/recovery, upgrade/rollback and supervised power-policy item in
  [the acceptance checklist](OPM-2.1.md).

**Not ready for release-candidate testing as a qualified distribution release.**
Ready for continued development review and controlled testing of the feature
checkpoint. Release notes and stable distribution artifacts remain gated on
qualification and physical acceptance. Preparation never authorizes publication.

## Resumed commits and automated distribution evidence

- `bc1ecc2`: exact source preparation, sealed pacman packages and independent
  Arch/Manjaro package, migration and runtime CI.
- `3f299e5`: Qt platform capability/load checks and existing Manjaro build-user
  compatibility; packaged test hooks verified disabled.
- `120472e`: bounded cleanup queries, folded dependency findings and notice locking.

The earlier seven-job workflow at `abed8f4` passed before this resume. Current
code is `120472e0979e2cfb51ef338089157b4ca6b38ae1`; the PR workflow tests its merge
checkout `7fbf51976ec71fb9367af319c879e348b1aba600`. SOURCE-COMMIT in each artifact
records that exact checkout. [Workflow 42486249856](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42486249856)
is the qualification record: **all eight jobs passed**, including Arch, Manjaro,
Debian packaging, native backend, editor/recovery, Qt/D-Bus, portable regression
and virtual standalone checks. Subsequent checkpoint edits change documentation
only; this result is tied to the code commit above.

Arch passed all eight native CTest targets, nine transaction/legacy-upgrade
scenarios and installed-package runtime checks without Python, PySide6 or a
compiler. Its snapshot uses Qt **6.12.0-3** and KF6 Service/Config **6.31.0-1**.
Debian 13 amd64 passed the complete package/upgrade job and the independent runtime
installation, activation, editor, reinstall, removal and rollback checks without
Python or a compiler (Qt 6.8.2 / KF6 6.13 build baseline).

Manjaro x86-64 independently passed all eight native CTest targets, nine transaction/
legacy-upgrade scenarios and the installed-package runtime checks without PySide6
or a compiler. Its November 8 snapshot uses manjaro-release **26.1.3-1**, Qt
**6.11.2-3**, KF6 Service/Config **6.30.0-1** and glibc
**2.44+r50+g1848099f063e-1**. The base system's Python remains for pacman-mirrors.
The final virtual-menu CI reports **25 passed / 1 focus-seat skip** each under X11
and Weston, and **26 passed** each under KWin and its second-output configuration.

Pacman CI retains the actual development `.pkg.tar.zst`, matching native bundle,
separate widget, checksums, source commit, os-release and build/runtime package
inventories for seven days. Artifact names use the tested PR merge checkout SHA.
These artifacts are for controlled development testing, not a stable release.
Development artifacts: [Arch](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42486249856/artifacts/13619393805)
and [Manjaro](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/42486249856/artifacts/13619178424).

Initial qualification caught two real portability problems: makepkg's default
stripping could invalidate sealed hashes, and newer Qt changed the Wayland plugin
filename. Both are fixed. Manjaro's base already owns UID 1000 and includes Python
for pacman-mirrors; the CI now respects that user and retains this unrelated runtime
while checking that PySide6 and compiler tools are absent.
