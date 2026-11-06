# Native migration status

This branch targets v1.1.0 development. The native binary identifies itself as
`1.1.0-dev`; the working application and EZ installer remain at 1.0.1 until
the native UI and installation path reach parity.

## Implemented

- Qt 6 Core/DBus C++ service and diagnostic CLI, built with CMake.
- One shared checked-in catalog for Python and native defaults/builtins.
- Configuration loading, default merging, validation, capability probes,
  menu normalization and presentation-only serialization.
- Re-resolved position-key dispatch with detached argv execution; application
  picker arguments stay literal, and service exit does not stop applications.
- Integration preferences and the existing D-Bus method signatures.
- Reference-only layout editing, session bounds/expiry/keepalive, unknown
  property preservation, conflict detection, and unchanged-layout no-op saves.
- Descriptor-relative no-symlink reads and writes, regular-file/4 MiB checks,
  cooperative locking, atomic replacement, automatic backups and retention.
- Native unit tests, legacy/native differential tests, private D-Bus tests,
  and a CI job that builds without installing PySide6.

## Remaining before changing the default runtime

1. Native recovery list/preview/restore/delete API and editor model, retaining
   protected copies, changed-source checks and explicit overwrite recovery.
2. Qt Quick/Kirigami General/Layout/Backups UI with application/builtin pickers,
   custom commands, Undo/Redo, nested editing and configuration conflicts.
   Reuse the shipped QML drag editor rather than dropping its behavior.
3. Native standalone frontend with keyboard, hover, focus and dismissal parity.
   **The preview's `Edit` returns false**, and no standalone GUI is claimed.
4. Native widget-snapshot/install helper and reversible binary installation.
   Source CMake installation currently stages only the preview executable;
   the normal EZ installer still requires Python/PySide6.
5. Windows-inspired configurable access keys, visibility/reset preferences,
   0.5–5.0-second automatic closing, optional hover delay/import/export, and
   capability-aware Sleep/Hibernate following KDE policy.
6. Full physical Plasma acceptance and release review before runtime cutover.

The editor and recovery browser are the next reviewable milestone. Replacing
them with a reduced UI, or launching the Python editor invisibly from the
native service, would leave the dependency goal unfinished while hiding the
loss of parity. The preview instead keeps that boundary explicit.

## Compatibility limits to close

- Normal OPM-generated UTF-8 JSON is covered by differential tests. Native
  preview rejects non-UTF-8 sources, integers outside signed 64-bit range and
  JSON nesting beyond 256. These errors do not rewrite the original file.
- Ordinary labels/icons are strings; unusual legacy non-string presentation
  fields need a wider compatibility corpus before production cutover.
- The command catalog retains existing qdbus6/KCM probes and available-tool
  selection. Converting builtin power/desktop calls to direct Qt DBus should
  preserve the verified KDE interfaces and capability checks.
- Native writes use the same `.menu.lock` but return a retryable busy error
  instead of blocking the D-Bus event loop behind another writer indefinitely.
- No native recovery UI, ordinary binary EZ package or physical native-widget
  integration has been certified by headless tests.

## Acceptance still required

Local validation for this milestone (Debian 13, Qt 6.8.2 native build):

| Check | Result |
| --- | --- |
| Existing Python/Qt regression suite | 445 passed, 8 historical-source skips, 18 subtests passed |
| Native Qt Test model/storage/layout executable | 26 passed, 0 failed, 0 skipped (includes test setup/cleanup) |
| Python standard-library differential/private D-Bus harness | 8 tests passed |
| Minimal runtime image without Python, PySide6 or compiler | CLI validation and Ping/GetMenu/GetIntegration passed |
| Staged CMake installation | Preview binary runs; no production service activation installed |

CI also builds on Ubuntu 24.04/Qt 6.4 and repeats the no-Python runtime test.
The draft PR records its current results. Python/Qt regression tests use the
existing PySide6 6.10.2 test environment; the native harness does not import it.

Check Kickoff/Kicker and supported AppGrid handoff; Meta+X open/close and removal;
launcher-button hide/restore; theme/icons; nested flyouts and placement across
monitors/scales; keyboard versus mouse interaction; in-menu drag/Go Back;
configuration conflicts, backups and restoration; standalone focus on both
Wayland and X11; clean native install, failed upgrade and uninstall preserving
the original launcher and recovery data. Do not restart an active Plasma
session to run these checks.

See [native build/test instructions](../../native/README.md) and the
[architecture decision](0001-native-runtime.md). Exact milestone validation
results are recorded in the draft PR.
