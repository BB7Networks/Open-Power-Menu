# 2.1 development checkpoint — November 7, 2026 (America/New_York)

The user requested a stopping point before the full release program is complete.
This checkpoint implements the 2.1 feature work and preserves stable **1.0.1**.
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
- Arch container CI and a draft PKGBUILD, plus updated roadmap/Store/upgrade docs
  and physical acceptance checklist. Existing migration/performance history retained.

No external runtime package was added. The standalone now links Qt DBus, already
part of the complete native bundle. The legacy Python catalogs and stable installer
remain intact. Existing layouts are never replaced or expanded during migration;
Sleep/Hibernate can be added in Layout, while fresh defaults include them.

## Local evidence

- Legacy/widget Python/Qt suite: **451 passed, 8 existing skips, 18 subtests passed**.
- Complete Debian 13 amd64 native build: **7/7 CTest targets passed**, including
  new interaction/power and dependency-review suites, plus existing model, recovery,
  editor session, actual GUI and standalone tests.
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

- The new GitHub CI run must complete. The prior six green jobs at `2830d71` are
  historical evidence, not proof that this head passes. The new workflow adds Arch.
- Local Arch package downloads failed with proxy HTTP 403 for
  fastly.mirror.pkgbuild.com and geo.mirror.pkgbuild.com. Arch CI is the next build
  check. PKGBUILD packaging and native installation on Arch remain unqualified.
- No Manjaro build or physical Manjaro/Plasma acceptance has been completed. Build
  separately against its Qt/KF6/glibc snapshot; Debian binaries are not portable
  Manjaro packages. Do not publish an unqualified distribution artifact.
- No new no-Python runtime image or public distributable was produced locally in
  this checkpoint; existing CI recipes cover that gate and need a green run.
- Review runtime responsiveness under slow/unavailable power services, broader
  legacy migration edge cases, real input/focus/hints, and package-manager variation.
- Complete every physical Wayland/X11, launcher/AppGrid, mixed-DPI, remote-desktop,
  editor/recovery, upgrade/rollback and supervised power-policy item in
  [the acceptance checklist](OPM-2.1.md).

**Not ready for release-candidate testing as a qualified distribution release.**
Ready for continued development review and controlled testing of the feature
checkpoint. Release notes and publishable distribution artifacts remain gated on
qualification and physical acceptance. Preparation never authorizes publication.
