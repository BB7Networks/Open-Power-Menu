# Version 1.0.1 release review

This document preserves the 1.0.1 pre-publication technical review.
The source was integrated into `main`, and the owner approved public
release after workstation testing. For the current publication status,
tag and downloads, see [GitHub Releases](https://github.com/BB7Networks/Open-Power-Menu/releases).

## Integration

The 1.0.1 code is now in `main`, after merging
[PR #8](https://github.com/BB7Networks/Open-Power-Menu/pull/8) at
`01fbd159991b0918d45f9c8544a032401d9f9e30` and
[PR #9](https://github.com/BB7Networks/Open-Power-Menu/pull/9) at
`046464686d94edaae99848fd11cbd0d7bd8ffa84`. PRs #1–#6 were merged
earlier; their history remains accessible in Git.

[PR #7](https://github.com/BB7Networks/Open-Power-Menu/pull/7) was closed
as superseded after review. Its bounded Qt delegate-wait correction was
included in PR #8, and its useful consolidation findings are reflected here.
The current gallery keeps the owner's PR #8 screenshots and the newer 1.0.1
dark-theme captures rather than replacing them with the historical images.

The earlier runtime-loading follow-up is already integrated:
`load_config()` uses recovery's bounded, no-symlink reads. Its oversized,
missing, symlinked and malformed configuration tests remain in the suite.

## Native Desktop

[KWin Plasma 6.3](https://github.com/KDE/kwin/blob/Plasma/6.3/src/useractions.cpp)
registers action ID **Show Desktop** with `Workspace::slotToggleShowDesktop`,
which calls `setShowingDesktop(!showingDesktop())`.

The registered component is `org.kde.kglobalaccel`, `/component/kwin`,
`org.kde.kglobalaccel.Component`. Its
[interface](https://github.com/KDE/kglobalaccel/blob/Plasma/6.3/src/org.kde.kglobalaccel.Component.xml)
provides read-only `shortcutNames` discovery and `invokeShortcut`, taking the
exact action ID. OPM verifies registration before offering the builtin; the
availability probe has a two-second timeout and a 30-second cache.

In a real Debian 13 / Plasma 6.3.6 / Qt 6.8.2 X11 session, the actual menu action
closed its popup and changed `org.kde.KWin /KWin showingDesktop`
**false → true → false**. The implementation uses D-Bus, with no simulated
keyboard input or X11-specific command. Physical Wayland acceptance remains
required.

Desktop is last in new/default layouts, after the shutdown submenu. Existing
custom menus are unchanged; users can add the builtin through Configure.

## Refresh review

**Retain the existing root-toolbar refresh button.** Opening the menu already
reloads its contents. The button is useful for retrying an unavailable backend
and reloading configuration or application availability while the popup stays
open. Integration polling updates preferences, not the visible menu model.

There are no extra refresh buttons in flyouts. Refresh is disabled during
editing, saves and command launch. Existing availability probes may retain
their bounded 30-second caches.

## Desktop checks completed

In the disposable Plasma X11 session:

- The installed 1.0.1 menu and Configure preference rendered in Breeze Dark.
- Root-to-native-flyout transitions kept the menu open with auto-close enabled.
- The menu stayed open during the leave grace period, then closed after
  1.2 seconds outside the entire menu.
- Keyboard navigation and layout editing suppressed automatic closing.
- Left-click opened the original Kickoff launcher.
- The real installer upgraded the disposable 0.4.17 installation to 1.0.1.
- Left, center and right panel positions were captured after loading final QML.
- Arrows matched actual flyout sides after moving the panel.

Moving the panel exposed a
[libplasma 6.3 notification-order issue](https://github.com/KDE/libplasma/blob/Plasma/6.3/src/plasmaquick/popupplasmawindow.cpp):
`effectivePopupDirectionChanged` is emitted before the new value is assigned.
The indicator now reads that value on the next event-loop turn. This prevents a
stale arrow when reusing a flyout after a panel move.

## Screenshot provenance

`menu-left.png`, `menu-center.png` and `menu-right.png` are direct 720×720
screen-region captures of the installed application at code commit `6ecc58d`.
The original launcher sits beside OPM. `configure-1.0.1.png` shows the new
General preference; its UI is unchanged by the subsequent arrow correction.
No generated UI, compositing or post-capture theme changes were used.

The disposable session uses Debian 13, Plasma 6.3.6, Qt 6.8.2, Breeze Dark,
Xvfb at 1600×1000 and software rendering. The four supplied Manjaro screenshots
from PR #8 remain unchanged in the [gallery](images/README.md).

These captures do not establish physical Wayland or multi-monitor behavior.
The inactive AppGrid adapter still logs its pre-existing undefined
`gridWindow` warning on this virtual desktop; AppGrid needs full-desktop
acceptance. Earlier capture findings and their scope remain in
[the PR #8 review](MENU-FLYOUT-UX.md).

## Automated and package validation

The full local suite passed **445 tests, 8 skips and 18 subtests**. The skips
require historical source trees absent from this checkout. Python compilation,
all shell syntax checks and all seven QML parses passed. Session D-Bus tests need local
socket access; run them outside a sandbox that denies AF_UNIX binding.
Exact final results and archive hashes are recorded with the pull request and
its review artifacts.

Automated installer checks cover extracted EZ installation, upgrades, settings
preservation, uninstall/recovery, explicit PySide6 dependency consent, failed
KPackage installation and interrupted installation via SIGTERM. The installer
stages application files and retains rollback copies until verification passes.

Handled failures and signals restore managed application files. SIGKILL or
power loss cannot run shell cleanup; retained recovery snapshots/transaction
data and reinstall remain the recovery route. The installer never restarts
Plasma. The separate widget-only package does not install the Python backend.

The extracted complete EZ TAR was also exercised with real KPackage in an
isolated Debian Plasma user profile and private session bus: fresh install,
upgrade, installed CLI check and friendly uninstall all passed. Custom menu,
panel sentinel and widget recovery snapshots survived. Friendly uninstall
intentionally resets the hide-original-launcher preference to show the
original button; the remaining preferences and menu were preserved.

Rebuild the complete packages with `bash scripts/build-release.sh`; verify
`dist/SHA256SUMS`. ZIP and TAR must contain identical file bytes, including
the gallery, backend, widget and current release notes. Build the separate
widget with `bash scripts/build-widget-only.sh`.

## Physical Manjaro Wayland acceptance checklist

- Install the complete extracted EZ package as a normal user, then run
  `open-power-menu --check`.
- Check left, center and right panels, multiple monitors and display scaling;
  confirm flyout arrows and no clipping.
- Toggle Desktop both ways with application windows open.
- Enable pointer closing; cross root and nested flyouts, pause inside,
  leave/re-enter, navigate by keyboard, edit/drag, and open Configure.
- Test Meta+X repeatedly and launcher handoff with Kickoff and the supported
  AppGrid version, including shortcut cleanup.
- Upgrade an existing profile and confirm menu, launcher preferences, widget
  instances and recovery snapshots survive.
- Restore a backup with automatic backups disabled; verify conflict handling
  with two editors.
- Uninstall in a disposable profile and confirm the original launcher and
  recovery directory remain.

## Publication gates

The owner approved this first public release after workstation review.
The [versioned release workflow](../.github/workflows/publish-release.yml)
builds EZ packages from the approved commit, verifies checksums and creates
the corresponding tag and release. The checklist above remains the regression
baseline for future Plasma, Wayland and launcher updates. For currently
published artifacts see [Releases](https://github.com/BB7Networks/Open-Power-Menu/releases);
for the release process see [publishing](PUBLISHING.md).
