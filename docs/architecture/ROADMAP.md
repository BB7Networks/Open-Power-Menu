# Native architecture roadmap

Stable release: **1.0.1**. Development target: **2.0.0-dev**.
Continue on `feature/native-architecture-v1.1` and draft PR #10; the historical
branch name does not define the new release version. Existing release tags and
the working legacy installer remain unchanged until production cutover.

## 2.0.0 — Native architecture

1. Native Core/DBus backend, safe storage and layout transactions (implemented).
2. Native recovery and Qt Quick/Kirigami General/Layout/Backups editor (implemented).
3. Native standalone menu (implemented; virtual navigation/focus/flyout/dismissal
   checks pass; physical desktop acceptance remains).
4. Complete native installation and upgrade snapshots/rollback (implemented
   for the Debian 13 amd64 development bundle). Qualify physical Plasma and
   additional distribution/CPU baselines before release.
5. Legacy configuration and integration validation, measured performance, and
   physical Plasma acceptance on Wayland and X11.

The complete normal installation must require neither Python/PySide6 nor a
compiler. Test tooling may still use Python. Keep the legacy app available
until all replacements meet their acceptance gates; never remove system Python
or PySide6 packages, restart Plasma automatically, or change existing launchers
without authorization. A passing backend test does not make 2.0 release-ready.

## 2.0.1 — Maintenance, if needed

Reserve for corrective updates after 2.0.0. Do not create an empty release.

## 2.1.0 — Features and customization

Implement only after 2.0 functional parity and acceptance:

- Windows-inspired access keys after Meta+X, configurable per entry/submenu,
  with duplicate detection within a level, visibility preferences, and binding
  reset independent of layout. Root preset: P Applications, O Power Options,
  V Logs, Y System Information, M Hardware, W Network, K Disks, I Terminal,
  T Task Manager, N Settings, E Files, R Run, U power submenu, D Desktop.
- Power submenu sequences U/U Shutdown, U/R Restart, U/S Sleep, U/H Hibernate,
  U/I Sign out and U/L Lock; preserve KDE permissions, inhibitors and prompts.
- Configurable pointer-leave closing: disabled by default, 0.5–5.0 seconds in
  0.1-second steps, default 1.2 seconds. Preserve flyout crossing, re-entry,
  keyboard navigation and editing safeguards in both frontends.
- Evaluate submenu hover delay, portable configuration import/export,
  individual binding reset, clearer tooltips and accessibility improvements.

No 2.1 settings or power commands are added during the architecture migration.
See [migration status and release gates](native-migration-status.md).
