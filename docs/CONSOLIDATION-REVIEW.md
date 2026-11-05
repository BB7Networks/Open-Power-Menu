# Main, branch and pull-request consolidation review

Reviewed on 2026-11-05 against `main` at `ac9e057a8d67`.

## Git history and PRs

All six existing PRs are merged into main. Each PR's original head **and** its
merge commit are ancestors of main. Every retained feature/fix branch has zero
commits missing from main; no cherry-pick, rebase or additional feature merge is
needed. The first-parent merge order is #1 → #2 → #3 → #4 → #5 → #6.

| PR | Retained branch | Original head | Main merge |
| --- | --- | --- | --- |
| [#1](https://github.com/BB7Networks/Open-Power-Menu/pull/1) | `fix/windows-installer-filenames` | `4ab1046` | `32bbac4` |
| [#2](https://github.com/BB7Networks/Open-Power-Menu/pull/2) | `feature/config-backup-retention` | `8888039` | `b950f12` |
| [#3](https://github.com/BB7Networks/Open-Power-Menu/pull/3) | `feature/default-actions-and-readiness` | `e3d0de8` | `fab90f8` |
| [#4](https://github.com/BB7Networks/Open-Power-Menu/pull/4) | `feature/editor-recovery-polish` | `5017e33` | `af805cf` |
| [#5](https://github.com/BB7Networks/Open-Power-Menu/pull/5) | `feature/in-menu-editing-ux` | `4c2fc13` | `6a7feec` |
| [#6](https://github.com/BB7Networks/Open-Power-Menu/pull/6) | `feature/native-shortcut-cascade-preview` | `0420a93` | `ac9e057` |

Main's file tree is identical to the final PR #6 tree. Retained branches are
historical references, not competing versions. They can be removed as routine
merged-branch cleanup; this review leaves them available for comparison. There
were no open PRs at the start of this review. The local `work` branch points at
the initial baseline and is also fully included in main.

## Resulting behavior

- Native widget Meta+X from #6 is the current default. The older standalone
  application shortcut remains a diagnostic route, and its removed Configure
  setup button is not restored by this review.
- Editing uses the single-popup row drag and spring navigation from #5, with
  #6's full-width 48 px Go Back target. The retired floating editor component
  and setting are absent. Normal locked-menu flyouts remain separate.
- Configuration validation, bounded/no-symlink reads, atomic saves, backups,
  conflict detection, draft preservation and user-local installer behavior
  remain covered by the full regression suite.
- The earlier runtime-loading follow-up is already in main: `load_config()`
  uses recovery's `current_revision()` and `decode_configuration()`. Tests cover
  the 4 MiB boundary, oversized files, leaf/parent/dangling symlinks, missing
  defaults, malformed input and CLI errors without rewriting the configuration.
- Version identifiers remain 0.4.17. GitHub has no published release or tags;
  the development README must not describe a tagged or published beta.

## Verification and correction

[Main's workflow](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/41948486456)
passed at `ac9e057`: **310 portable tests, 13 skips and 18 subtests** in 9.65s;
**105 Qt/D-Bus tests** in 22.86s.

The fresh local run exposed a timing assumption in the full-parent drag test:
its spring timer changed the draft before the next Qt polish created the target
row delegate. The UI reached the correct parent and row on the next event-loop
pass. The shared test coordinate helper now waits for the actual row, bounded
to one second, instead of assuming the delegate exists after a fixed delay.
Application timing and behavior are unchanged.

After that correction, the complete local suite passed **399 tests, 8 historical-
source skips and 18 subtests** in 72.23s. The skips require old release source
trees unavailable in this checkout; they are not counted as passing tests.
The suite covers Python/Node logic, actual Qt Widgets/Quick interaction, isolated
session D-Bus, installation/upgrade/uninstall, recovery, archives and checksums.
Python compilation, all seven shell syntax checks and all four workflow QML
parses pass. All 41 local links in the changed documentation resolve. Fresh
ZIP/TAR installers contain the seven byte-identical screenshot originals;
archive integrity, widget packaging and release checksums also pass.

## Screenshot and desktop evidence

The earlier README reserved filenames for three Manjaro screenshots, but no
image binaries were present in any branch, PR attachment or release. The current
gallery uses new captures from the actual application; see the
[capture record](images/README.md) for environment, source revision and scope.

Seven original PNGs cover the menu, normal flyout, single-pane Go Back editor,
all three Configure tabs and existing Kickoff launcher. On Debian 13 / Plasma
6.3.6 / Qt 6.8.2 in a virtual X11 session, right-click, submenu hover, Go Back,
Cancel, Configure navigation and left-click handoff to Kickoff were exercised.
No application UI code was modified for these captures.

The session also logged existing QML warnings worth checking on a full desktop:
`main.qml:157` refers to the compact component's `button` ID from outside its
scope, the inactive AppGrid bridge can supply an undefined `gridWindow` to
`Connections`, and Qt 6.8 reports palette binding loops for the editor. The
captured Kickoff/menu path remained usable. These findings are separate from
Git consolidation; the AppGrid path and theme variations still need live review.

Virtual desktop captures demonstrate the displayed UI and documented checks in
that session. They do not establish physical Wayland pointer behavior, multi-
monitor placement, AppGrid's intermittent desktop-flash behavior or native
shortcut cleanup on all supported Plasma versions. Keep the remaining
[desktop acceptance matrix](TESTING.md) before a public release.
