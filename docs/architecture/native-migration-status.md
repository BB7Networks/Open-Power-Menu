# Native migration status

Current milestone: **complete native packaging and reversible user-local upgrades implemented**.
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
  Builtin command preview/customization and application/executable selection
  within command editing preserve the corresponding legacy editor operations.
- KService application discovery and KDE desktop-file execution; KConfig
  launcher discovery reads existing panels without changing them.
- Unsaved-draft handling, external-change detection, explicit overwrite preview
  and recovery copies. Unknown JSON metadata remains in C++, avoiding JavaScript
  precision loss; editing a label preserves alternative command candidates.
- Native unit/GUI tests, legacy differential/private D-Bus tests, staged CMake
  installation and separate backend/editor runtime images without Python.

- Optional `open-power-menu-standalone` Qt Widgets executable: native/Aero menus,
  nested hover flyouts, keyboard/mouse selection, themed optional icons, disabled
  entries, scrolling, anchored placement and fixed 1200 ms pointer dismissal.
  Shared native resolution and detached launch; presentation contains no argv.
  Configuration is read-only and availability changes fail closed at selection.
- Dedicated standalone CI job, staged no-Python runtime and X11/Weston/KWin tests.

## Remaining before changing the default runtime

1. Physical standalone Plasma acceptance: launcher/shortcut handoff, mixed-DPI
   monitors, non-primary output choice, screen work areas/panel edges and desktop
   theme integration. Wayland may refuse global positioning or tokenless focus.
2. Qualify the new native package on physical Plasma and additional distribution/
   CPU baselines before publishing it or replacing the released EZ download.
   The native development bundle installs all components without Python; the
   retained 1.0.1 release installer still requires its original runtime.
3. Full migration corpus: unusual legacy encodings/presentation fields and
   integer ranges; distribution/architecture-specific binary compatibility.
4. Clean install, reinstall, upgrade, failed-upgrade rollback and uninstall
   acceptance preserving settings, launcher, shortcuts and recovery history.
5. Physical Plasma integration and release review. Virtual compositor and CI
   checks do not certify Meta+X, multi-monitor placement, launcher handoff,
   remote-desktop operation or physical standalone behavior.

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

CI retains these five jobs: **Portable tests**, **Qt and D-Bus runtime**, **Native Qt
backend** (Ubuntu 24.04/Qt 6.4), **Native editor and recovery** (Debian 13), and
**Native standalone menu** (minimal Debian runtime plus virtual Ubuntu sessions).
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

## Standalone milestone validation

The implementation uses [Qt Widgets/QMenu](0002-native-standalone.md), keeping
Gui/Widgets off the backend target. Production installation/activation and the
Plasma widget remain unchanged. The shared model and recovery/editor suites
continue passing. The native standalone uses no QML or Python runtime.

| Check | Result |
| --- | --- |
| Full legacy suite | 445 passed, 8 existing skips, 18 subtests passed |
| Combined Release build | All 5 CTest targets pass, including editor/recovery |
| Dedicated standalone Qt Test | 23 passed on KWin Wayland; 22 passed + 1 focus-seat skip on X11/Weston (counts include setup/cleanup) |
| Private backend-only D-Bus contract | 9 passed; lightweight dependency boundary retained |
| Virtual X11/Xvfb | Nested keyboard selection, real command dispatch, mouse selection, left/right hover placement, repeated cancellation and scrolling pass |
| Virtual Wayland/Weston | Interaction tests pass; no input seat, so cross-process activation test explicitly skips |
| Virtual Wayland/KWin 6.3.6 | All standalone checks pass, including separate-process focus loss; repeated with 2 outputs at scale 1.25 |
| Minimal staged Debian runtime | Menu exposes without Python/PySide6/compiler; CLI works without a display; missing Widgets library is named by the ELF loader |
| Appearance | Native light/dark palette and Aero captures inspected; optional icons tested with a disposable theme |

Virtual scaling/output configuration exercises compositor and Qt paths; it does
not certify physical mixed-DPI placement or pointer/shortcut delivery. Logical
geometry tests cover negative/non-primary work areas, oversized menus and edge
clamping. Wayland deliberately leaves absolute placement to the compositor.
The focus test requires KWin's virtual seat and demonstrates application focus
loss without treating submenu transitions as an application switch. Hover tests
inject Qt mouse events because Wayland prohibits cursor warping. Qt's initial
popup click suppression is respected by synthesizing pointer motion before a
click. No power action is executed. No active Plasma session is restarted.

No known functional gap remains in the implemented standalone menu path within
these tested configurations. Production cutover, physical Plasma theme/focus,
real panel/work-area variations, non-primary-output choice and mixed fractional
scales remain unverified. Submenu frame/interaction latency and complete installed
dependency size are not benchmarked. See [measurements](native-performance.md)
and [CLI/dependency differences](../../native/README.md#standalone-menu-development-build).

## Native packaging milestone

`OPM_BUILD_PACKAGE=ON` builds all three applications plus native installer and
compatibility CLI, and creates a labelled tar.gz/checksum and a separate
`.plasmoid`. Desktop/service entries use the installed absolute paths. The
explicit bootstrap checks OS/version/CPU before starting the ELF. The native
installer checks bundle hashes, libraries, X11/Wayland plugins, editor QML,
a private service and actual production-name activation before commit.

Installation uses no-follow held directory descriptors, an exclusive lock,
durable journals/snapshots and component renames without replacement of an
unexpected staging entry. Recovery refuses changed files and supports a process
interrupted between component replacements. Identified old service owners are
retired using pidfds; unrelated owners are refused. No Plasma restart occurs.

Tests cover clean install, reinstall, actual v1.0.1 migration with a running
Python service, rollback, uninstall, dependency/architecture failures, failed
activation, crash and partial-failure recovery, symlinks/collisions, modified
receipts/snapshots and unrelated service ownership. Personal configuration,
backups, panel applets/launcher selections and customized/disabled shortcuts
are checked byte-for-byte. A sixth CI job performs complete-package tests and
installation/removal/rollback in a separate image without Python or a compiler.

Store-only UI explains the missing native backend, links to instructions and
retries the existing D-Bus connection. It never executes an installer. The
backend-free setup surface is tested separately; a full backend-free command
mode is deferred to avoid duplicating the model or adding an executable engine.

Install history is retained without automatic pruning and is restored through
`open-power-menu --rollback`; it is separate from the editor's configuration
backup browser. Embedded legacy widget-backups remain in the old-app snapshot;
external widget history remains untouched. Remove a saved OPM panel applet before
uninstall so its existing launcher/shortcut restoration runs in Plasma.
See [package instructions](../../native/packaging/README.md) and
[decision 0003](0003-native-packaging.md) for supported systems and limits.
