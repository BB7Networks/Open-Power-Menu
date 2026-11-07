# Native migration status

Current milestone: **native recovery and configuration editor implemented**.
The development executables report `2.0.0-dev`. The normal application and EZ
installer remain at 1.0.1. The existing `feature/native-architecture-v1.1`
branch and draft PR #10 retain their development history.

## Implemented

- Qt Core/DBus C++ service and diagnostic CLI with the shared defaults/builtin
  catalog, configuration validation, capability probes and menu presentation.
- Detached argv dispatch, existing integration preferences and D-Bus contracts;
  native `Edit` launches the adjacent native editor, never the Python editor.
- Reference-only in-menu layout transactions, bounded sessions, keepalive,
  unknown/hidden entry preservation, conflict checks and no-op saves.
- Descriptor-relative/no-symlink reads and atomic writes, 4 MiB limits,
  cooperative locking, automatic backups and retention.
- Native recovery enumeration, metadata, preview, restore and deletion. Source
  identity/content checks protect preview-to-action operations. Protected
  pre-restore/pre-overwrite copies survive retention zero. History retains
  metadata rather than every decoded backup in memory.
- Qt Quick/Kirigami General/Layout/Backups window, shared QML drag editor,
  installed-app and builtin pickers, individual command arguments, nested
  entries, duplicate/remove/edit, Undo/Redo and default-layout restoration.
- KService application discovery and KDE desktop-file execution; KConfig
  launcher discovery reads existing panels without changing them.
- Unsaved-draft handling, external-change detection, explicit overwrite preview
  and recovery copies. Unknown JSON metadata remains in C++, avoiding JavaScript
  precision loss; editing a label preserves alternative command candidates.
- Native unit/GUI tests, legacy differential/private D-Bus tests, staged CMake
  installation and separate backend/editor runtime images without Python.

## Remaining before changing the default runtime

1. Native standalone frontend with keyboard, cascading submenus, adaptive screen
   placement, focus, high-DPI and dismissal parity on Wayland/X11.
2. Native widget-snapshot/install helper, D-Bus activation and reversible binary
   EZ installation. CMake currently stages development executables only. Normal
   installation still requires Python/PySide6 and must remain usable.
3. Full migration corpus: unusual legacy encodings/presentation fields and
   integer ranges; distribution/architecture-specific binary compatibility.
4. Clean install, reinstall, upgrade, failed-upgrade rollback and uninstall
   acceptance preserving settings, launcher, shortcuts and recovery history.
5. Physical Plasma integration and release review. Virtual compositor and CI
   checks do not certify Meta+X, multi-monitor placement, launcher handoff,
   remote-desktop operation or standalone behavior.

Access keys, configurable timing, Sleep/Hibernate and other new usability
features remain reserved for **2.1** after 2.0 acceptance. See the
[version roadmap](ROADMAP.md). No release has been merged, tagged or published
by this milestone.

## Compatibility and security findings

Normal OPM-generated UTF-8 configurations are covered by differential tests.
The native preview rejects non-UTF-8 JSON, integers outside signed 64-bit range
and JSON nesting beyond 256 without rewriting the original. Unusual non-string
legacy presentation fields still need a wider compatibility corpus. These
remain cutover gates, not implicit schema migrations.

Native writers use the existing `.menu.lock`; a busy lock produces a retryable
error instead of freezing the event loop. Restoration/deletion additionally
refuse symlinked path components, foreign-owned or hard-linked backup files,
and backup directories writable by other users. A selected backup changing
between preview and action is rejected. Invalid active configuration requires
explicit protected overwrite or valid recovery; opening defaults does not
silently replace it.

Builtin power/desktop commands retain the existing qdbus6/KCM capability
probes and KDE confirmations. No power action is run during tests. Native
launcher discovery is read-only; runtime/installer cutover must still preserve
the user's authorization boundary for panel changes.

## Validation of this milestone

Local native builds use Debian 13, Qt 6.8.2 and KDE Frameworks 6.13. Legacy Qt
regressions use the existing PySide6 6.10.2 environment.

| Check | Result |
| --- | --- |
| Existing Python/Qt regressions | 445 passed, 8 historical-source skips, 18 subtests passed |
| Native Qt Test targets | Model 26, recovery 13, editor session 11, GUI 4 passed, including setup/cleanup |
| Standard-library differential/private D-Bus harness | 9 tests passed, including native editor launch with a literal config path |
| Minimal backend runtime | CLI and Ping/GetMenu/GetIntegration work without Python/PySide6/compiler |
| Minimal editor runtime | Actual Qt Quick editor starts without Python/PySide6/compiler; missing config stays absent |
| Virtual Plasma 6.3.6 X11 and Wayland sessions | Actual editor GUI checks and screenshots passed using Xvfb/KWin X11 and KWin's virtual Wayland backend |
| Staged CMake installation | Both development executables run; production activation remains unchanged |

GUI tests open the actual window and exercise entry validation, duplicate,
Undo/Redo, editing, saving, backup preview, canceled/confirmed restoration and
protected deletion. Session tests additionally cover concurrent writers,
changed overwrite/backup previews and unsaved drafts. Shared widget drag
regressions cover reordering/reparenting and selection/scroll behavior.

CI has four jobs: **Portable tests**, **Qt and D-Bus runtime**, **Native Qt
backend** (Ubuntu 24.04/Qt 6.4) and **Native editor and recovery** (Debian 13).
Current run status is recorded on draft PR #10.

The virtual desktop runs used separate configuration/data/runtime directories,
private D-Bus sessions and software rendering. No active desktop was changed.
The editor emitted no QML warnings in the final GUI tests. Explicit as-needed
scrollbars avoided layout binding loops in Debian's Breeze 6.3.5 style; tests
wait for dialog close animations before clicking the next control. Container
session logs still include unavailable global-shortcut/PipeWire services, so
these runs establish editor interaction coverage, not full desktop integration.

[Performance observations](native-performance.md) compare the released 1.0.1
baseline with native Release binaries, including the editor memory tradeoff.
See [native build instructions](../../native/README.md),
[testing and physical acceptance](../TESTING.md), and the
[architecture decision](0001-native-runtime.md).
