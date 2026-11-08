# Open Power Menu 2.1 development and acceptance

Stable remains **1.0.1**. Development is **2.1.0-dev** on
`feature/native-architecture-v1.1`, draft PR #10. The next public release is
**2.1.0**, directly from 1.0.1. `2.0.0-dev` was an internal architecture milestone.
No merge, tag, release, KDE Store publication or active Plasma installation is part
of this development pass.

## Shared configuration

The JSON schema remains version 1 and unknown metadata is retained. New settings:

| Field | Default | Contract |
|---|---|---|
| `access_keys_enabled` | `true` | Local menu access keys, independent of Meta+X |
| `show_access_key_hints` | `true` | Separate visual-hint preference |
| `auto_close_delay_ms` | `1200` | Integer 500–5000 inclusive, in steps of 100 |
| Entry `access_key` | OPM preset when unambiguous | A–Z or 0–9, case-insensitive; empty explicitly disables |

`auto_close_on_pointer_leave` stays **false** by default; saved values are preserved.
Migration never replaces a customized menu or inserts new entries into it. Sleep
and Hibernate appear in fresh defaults and can be added through the existing editor.
Missing entry bindings gain only unambiguous presets. Existing explicit bindings
reserve their letters; ambiguous duplicate actions remain unbound. Explicit
same-level collisions produce validation feedback. Different levels can reuse keys.
Keys travel with entry definitions across reorder, rename and icon customization.
Duplicating an entry clears its sibling binding. Reset access keys preserves layout,
commands, unknown metadata and other preferences and can be undone.

Root presets: **P** Applications, **O** Power Options, **V** Logs, **Y** System,
**M** Hardware, **W** Network, **K** Disks, **I** Terminal, **T** Task Manager,
**N** Settings, **E** Files, **R** Run/Search, **U** power submenu, **D** Desktop.
Power submenu: **U** Shutdown, **R** Restart, **S** Sleep, **H** Hibernate,
**I** Sign out, **L** Lock. These are OPM presets inspired by Windows, not an exact
mapping of every Windows entry. Meta+X remains a KDE global shortcut. The following
letters are local to the active menu; editing/text entry does not activate them.

Both frontends consume the same native presentation and action resolver. Disabled
entries cannot execute. Widget layout editing and keyboard navigation suspend pointer
dismissal. Root/child flyouts share the timer. Pointer re-entry cancels it, reopening
resets it, and a changed delay starts a full new grace period. Standalone timers are
owned by their menu and stopped on hide/return.

## Native power behavior

Sleep/Hibernate require KDE PowerDevil's freedesktop capability and inhibition
interfaces plus logind's `CanSuspend`/`CanHibernate` authorization. Missing, denied
or failed interfaces leave actions unavailable under `show_unavailable` policy.
The editor shows the current availability reason. Activation rechecks restrictions,
then uses logind `SuspendWithFlags`/`HibernateWithFlags` with
`SD_LOGIND_ROOT_CHECK_INHIBITORS` (0x01) and D-Bus interactive authorization for Polkit.
It never requests `SKIP_INHIBITORS`, and has no unchecked command fallback. logind
honors block/block-weak and delay inhibitors; KDE receives normal sleep signals.
Interface errors are displayed/logged. Existing KDE logout/restart/shutdown prompt
commands are unchanged. Physical power actions require supervised acceptance.

Automated tests inject the D-Bus transport and use harmless command probes. They
must never suspend, hibernate, restart, sign out or shut down a host.

## Distribution qualification

Debian 13 amd64 remains the established build baseline. Complete runtime packages
are listed in [native packaging](../native/packaging/README.md). New code adds no
external runtime package: Qt DBus was already shipped; the standalone now links it
for native power actions. PySide6 is never a native runtime dependency.

[Pacman package CI](../native/tests/pacman.Dockerfile) builds Arch and Manjaro
separately against their own Qt/KDE stacks. [PKGBUILD](../native/packaging/PKGBUILD)
uses an exact committed source archive with SHA-256 pinned by
[prepare-pacman.sh](../native/packaging/prepare-pacman.sh). It stages the sealed bundle
under `/usr/lib` and provides `open-power-menu-native-setup`; it has no automatic
desktop installation or Plasma restart hooks. Post-build stripping is disabled to
preserve the hash inventory. Development artifacts include source and package
checksums plus distribution/package inventories; CI retains them for seven days.
Arch qualification does not certify Manjaro binaries or physical desktop behavior.

Arch and Debian runtime images prove operation without Python; Manjaro retains its
base image's Python for pacman-mirrors and verifies that PySide6 is absent. No runtime
image needs a compiler. All exercise activation, editor startup, reinstall, removal
and rollback through the actual installed bundle, with test fault hooks compiled out.

Retain exact distribution/version/CPU checks, hash inventories, ELF dependency
resolution, platform-plugin loading, QML smoke tests and activation checks. Platform
plugins are identified by their advertised xcb/wayland capabilities and must load
successfully, accommodating Qt filename changes without dropping ABI checks. A rolling
distro update can invalidate an earlier package: rebuild on the intended snapshot
and record Qt, KF6, glibc, package versions and date. A missing VERSION_ID is not a
license to treat different distributions as interchangeable. Never advertise Debian
binaries as universally portable. Publish only builds whose gates have passed.

The Store widget remains separate and requires the matching native backend. Its
missing-backend explanation and Retry connection behavior are retained.

## Physical acceptance checklist — release blocking

Record distro/snapshot, CPU, Plasma/Qt/KF6 versions, session type and result for each
row. Prioritize Manjaro Plasma 6 Wayland, then X11. Virtual sessions are additional
evidence, not substitutes. Obtain explicit authorization before altering a live
installation or supervising power actions.

- [ ] Meta+X open/close; launcher integration and supported AppGrid variants.
- [ ] Original launcher hiding/restoration; shortcuts and panel layout preserved.
- [ ] Left/right click, edge placement, nested arrows/Enter/Escape and access keys.
- [ ] Native/Aero, light/dark themes, hints, edited labels/icons and unavailable items.
- [ ] 0.5/1.2/5.0-second dismissal, parent-child crossing, re-entry, keyboard/editing protection, repeated opens and focus changes.
- [ ] Multi-monitor, mixed/fractional DPI, work areas and remote-desktop use.
- [ ] Native General/Layout/Backups, Undo/Redo, conflicts, recovery and standalone.
- [ ] Direct released 1.0.1 upgrade, profiles with spaces, customized commands/layouts, hidden launcher and disabled/custom shortcut settings.
- [ ] Failed upgrade/recovery; legacy rollback with runtime present and restored runtime after removal.
- [ ] One-time cleanup notice, Keep/Review/Don't show again, absent/incomplete package database and unattended installs.
- [ ] Supervised Sleep/Hibernate availability, Polkit denial/challenge and block/delay inhibitors; KDE confirmation prompts for logout/restart/shutdown.
- [ ] Distribution-specific package installation, X11/Wayland plugins and library compatibility.

Release notes and stable artifacts are gated on implementation, automated checks,
distribution qualification and physical acceptance. Preparation never authorizes
publication. See [development-pass results](OPM-2.1-RESULTS.md) for actual evidence
and outstanding limits; do not infer a pass from this checklist.
