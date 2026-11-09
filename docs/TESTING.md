# Automated checks and desktop acceptance

## Automated development workflow

Use Python 3.12 and Node 22 (the CI versions). A virtual environment is optional:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pytest
python -m pytest -q -ra
for script in install.sh uninstall.sh scripts/*.sh tools/*.sh; do
    bash -n "$script"
done
python -m compileall -q openpowermenu tests run.py
bash scripts/build-release.sh
bash scripts/build-widget-only.sh
(cd dist && sha256sum -c SHA256SUMS)
unzip -t dist/OpenPowerMenu-EZ-v1.0.1.zip
unzip -t dist/org.openpowermenu.start-1.0.1.plasmoid
tar -tzf dist/OpenPowerMenu-EZ-v1.0.1.tar.gz
```

Optional Qt runtime checks require PySide6 QtCore/QtDBus/QtWidgets/QtTest/QtQuick/QtQml and
`dbus-run-session` (normally supplied by the distro's D-Bus packages):

On a minimal Debian/Ubuntu image, the Qt wheel also needs the system `libegl1`
package even with the offscreen platform. CI installs it and checks Qt imports
before running tests, so a missing runtime cannot silently skip this job.

```bash
python -m pip install PySide6-Essentials==6.10.2
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_qt_runtime.py tests/test_qt_editor.py tests/test_qt_inmenu.py
```

They start temporary session buses, use temporary XDG paths, and stop only their
own processes. Tests adopt/reap their dummy workloads on Linux. The optional Qt
CI job makes these checks required in CI even though a portable machine without
Qt skips them. An absent historical release tree causes separately reported
baseline-comparison skips; it is not counted as a passing test.

Installer tests use temporary XDG directories and a **stub** KPackage tool. They
execute real core/wrapper scripts, preserve custom configuration, simulate prior
0.4.16/0.4.17 widget metadata, check widget backups and uninstall preservation,
and inspect actual ZIP/TAR archives. They do not prove KPackage works on a live
Plasma session or reproduce every byte of the unavailable old installer releases.
Version identifiers are 1.0.1; building archives does not tag or publish.
The wrapper tests run from a source path containing spaces. Archive checks reject
obsolete capitalized wrapper names, stale ZIP members and case-insensitive collisions.

Editor tests use actual Qt trees, undo stacks, modal dialogs and keyboard events;
the drop adapter also receives a constructed `QDropEvent`. They cover nested
moves, cycle/depth/count rejection, metadata, duplication, default reset,
Save/Discard/Cancel, content conflicts, validation focus, and backup preview and
restore. Filesystem tests inject write/copy/replace failures and check retention,
symlink refusal, corrupt/missing history and source preservation. Installer tests
also cover migration collisions, independent snapshot limits, failed upgrades
and uninstall preserving history. Native pointer drags still require the live
[Manjaro editor/recovery procedure](EDITOR-RECOVERY.md#required-manjaro-plasma-6-wayland-acceptance).

In-menu tests execute the shipped JavaScript draft/controller and locked keyboard
handlers in Node. Qt Quick tests load the actual `LayoutEditor.qml` and send mouse
and keyboard events for reordering, reparenting, cancellation, scrolling and popup
interruption. They verify palette propagation and text contrast for representative
light/dark colors and Aero. Backend tests reject injected command fields, missing,
duplicate and unknown references, cycles and limits; real D-Bus tests exercise
saves, conflicts, cancellation and service restarts. CI also parses the changed
QML files. These checks do not load a live Plasma shell or prove native flyout
focus, screen-reader integration or Wayland pointer grabs.

The PR #5 follow-up additionally tests stable viewport anchors/delegate identity,
parent/child selection, popup recreation, full-row click versus drag thresholds,
long-held submenu drags, spring-loaded multi-level movement, passing over targets,
full-parent traversal, invalid/canceled drops and edge scrolling. Backup deletion
tests cover confirmation, corrupt/oversized files, changed identities/content,
owner/path/link refusals, protected copies, literal filenames and UI refresh.
Shortcut tests verify native widget activation/close routing, one-time Meta+X
assignment, preservation of customized or disabled bindings, immediate
instance-removal cleanup and Undo restoration. Standalone launch diagnostics
still test command resolution/quoting, missing KDE tools and failed launches.
These tests **cannot** prove KWin's actual global-key delivery or lifecycle
signals on a physical Plasma desktop.

## Native migration checks

The v2.0 preview adds CMake/Qt Test checks and a Python-standard-library
differential harness; PySide6 is not required for these tests. See
[native development](../native/README.md) for the commands and the isolated
no-Python runtime smoke images. **Native Qt backend** and **Native editor and
recovery** CI jobs run alongside the existing portable and Qt jobs. The editor
job builds Qt Quick/Kirigami on Debian 13, runs all four native test targets,
then opens the actual editor in a separate image without Python or a compiler.

Native tests cover bounded/no-symlink reads, malformed configurations, atomic
saves, backup retention, file-identity/content conflicts, reference-only layout
transactions, capability probes, D-Bus compatibility and detached argv launch.
Recovery tests cover preview/restore/delete, protected copies with retention
zero, malformed/oversized/unsafe backups and changed previews. Editor-session
tests cover metadata and alternative-command preservation, bounded Undo/Redo,
hidden nested entries, unsaved drafts, concurrent writers and overwrite preview
conflicts. GUI tests exercise actual controls, canceled/confirmed restoration
and protected deletion, builtin customization, application replacement and
manual edits after application selection. KService fixtures cover hidden/unavailable apps and
KDE desktop-file dispatch; KConfig discovery leaves panel bytes unchanged.
All power commands are fake tools during automated testing. The existing Python
model is the comparison oracle for normal configurations. Legacy GUI tests stay
in place until the entire native application replaces the normal installation.

These tests do not certify the pending standalone frontend, binary EZ installer
or physical widget integration. See the
[migration gates](architecture/native-migration-status.md) before changing the
installed service or claiming that the complete app no longer needs PySide6.

## Live acceptance matrix (still required)

Use a test account or VM and retain a recovery terminal. Do not restart Plasma
while remote desktop is your only access. Record the workstation, distro, Plasma,
Qt, Wayland, launcher versions, panel position and display scale for every run.

| Area | Check on both workstations |
| --- | --- |
| Native launcher | Kickoff and, where available, Kicker; left-click opens the selected launcher |
| AppGrid | Center 1.9.6; left/right switching and pass-through input on Wayland |
| Panel states | Original button visible, then hidden; repeat on top/bottom/left/right panels |
| Focus | Repeated left/right cancellation; Meta-opened launcher; bounded popup handoff; no extra toggling |
| Flyouts | Nested menus, side choice near screen edges, long menus, alignment and multi-monitor placement |
| Icons | Inherited launcher icon and explicit theme/local icon; no launcher settings changed |
| Logs | KSystemLog installed; then absent with Konsole/journalctl; then XTerm; verify new authorized warning entries appear |
| Printers | Print Manager installed and discoverable; module absent with system-config-printer; neither available |
| Editor | Search/pick/save/launch an app; spaces, localization, terminal/DBus apps; custom quoting and nested entries |
| Configure presentation | Three tabs; concise instructions; Undo/Redo right-aligned and wrapping at narrow widths; unsaved changes survive attempted restore |
| In-menu editing | Locked default; full hidden-entry hierarchy; reorder/reparent; Save/Cancel; interrupted drags; popup close/reopen; no command launches |
| Scroll/drag follow-up | Repeated bottom-of-list moves; full-row drag; 450 ms submenu hover; drag and hold anywhere on the full-width, 48px-high **Go Back** strip through multiple levels; return viewport/selection; long press; edge scrolling |
| In-menu recovery | External edit conflict; backend unavailable/restarted; retained draft and clear recovery instructions |
| Keyboard/theme | Up/Down, Enter, Right/Left, Escape; Alt+Arrow and right-click/Shift+F10 movement menus; wheel/touchpad during drag; visible focus; native light/dark and Aero |
| Native Meta+X | Fresh OPM widget on a free binding; press twice to open/close at **current** button; occupied binding; customize/disable; restart/reinstall preserves preferences; remove and promptly re-add; Undo restores prior key; no orphaned per-instance shortcut |
| Standalone diagnostics | Separate --check/plain/--diagnose-launch; verify Qt visibility/focus and independent Application shortcut with another unused key when needed |
| AppGrid flash | Compare 50 direct and OPM openings, rapid/mixed clicks, unfinished draft, original visible/hidden; capture sequenced traces per [diagnostic guide](SHORTCUT-APPGRID-DIAGNOSTICS.md) |
| Backup cleanup | Confirm/Cancel; corrupt/protected/changed/missing history; active row protected; count refresh on tab return with unsaved edits; browser Refresh retained |
| Backups | Repeated Save, limit 10 then 2, limit 0, Cancel, restore; manual files unchanged |
| Lifecycle | Dummy long-running app survives popup close, backend PID stop/restart; compare PID usage with grouped totals |
| Upgrade | Real archived 0.4.16 and 0.4.17 installs upgraded with a custom menu; verify backend reactivation and widget snapshot |
| Recovery | Show original button, restore menu/widget snapshot locally, uninstall only OPM |

For Logs, keep the warning-priority filter: informational entries will not appear.
Do not generate privileged system events or change journal permissions just to
test it. Use an authorized existing warning source or a disposable test VM.

For Printers, inspect `kcmshell6 --list` for **kcm_printer_manager**. The shell's
presence alone is insufficient. No tool is installed automatically when missing.

## Recovery checks

```bash
~/.local/bin/open-power-menu --show-launcher-button
~/.local/bin/open-power-menu --check
~/.local/bin/open-power-menu --launcher-diagnostics
```

Use Backups → Configuration backups → Manage / Restore Backups to preview and restore a
configuration. Restore retains a separate pre-restore copy even with automatic
backups off. Never replace `plasma-org.kde.plasma.desktop-appletsrc` for OPM recovery.

Widget snapshots now live under
`~/.local/share/open-power-menu-recovery/widget-backups/`; old history is migrated
and uninstall preserves it. See [Editor and recovery](EDITOR-RECOVERY.md) for
snapshot retention, matching-backend rollback and the live test procedure.
Run the [in-menu editing Manjaro acceptance procedure](IN-MENU-EDITING.md#live-manjaro-plasma-6-wayland-acceptance)
on a current 1.0.1 installation, including upgrades from an earlier release.

Do not mark this matrix complete based on offscreen tests. Attach real
[screenshots](images/README.md) only after live acceptance.

## 1.0.1 release candidate

See [release verification](RELEASE-1.0.1.md) for Desktop, optional pointer-leave
dismissal, EZ installation/rollback and the final Manjaro Wayland checklist.

## Native standalone release gate

Build with `OPM_BUILD_STANDALONE=ON` and use disposable configuration/data/cache
profiles and private session buses. See [the standalone recipes](../native/README.md#standalone-menu-development-build).
The dedicated CI job covers Core-only build isolation, Widgets interaction,
minimal runtime exposure without Python/compiler, missing-library diagnostics,
Xvfb/X11, headless Weston and virtual KWin. Set `OPM_WAYLAND_COMPOSITOR=kwin`,
`OPM_OUTPUT_COUNT=2`, `OPM_SCALE=1.25` on `standalone-wayland.sh` for two virtual
outputs at fractional scale. KWin's binary is copied without optional file
capabilities inside the disposable test runtime; no privileged compositor runs.

Before production installer migration/release, repeat on physical Plasma:

- Launcher and shortcut activation under both Wayland and X11, including
  compositor-granted/refused activation and keyboard focus on first opening.
- Parent/child/grandchild hover, rapid crossing, keyboard arrows/Enter/Escape,
  outside click/application focus loss and repeated opening/closing.
- Pointer exit/re-entry at the fixed 1200 ms timeout, keyboard suspension and
  dismissal while a submenu or timer is active.
- Panels at top/bottom/left/right, different work areas, screen-edge collisions,
  adaptive flyout direction, negative/non-primary monitors and mixed
  100/125/150% scales. Wayland global positioning remains compositor controlled.
- Native desktop light/dark themes and Aero, system icons on/off, disabled rows,
  selection contrast, long-menu scrolling, high-DPI and accessibility behavior.
- Harmless literal-argv probes only; detached applications must survive menu
  exit. Confirm power prompts separately with deliberate human supervision.

Virtual sessions and palette captures do not certify this physical gate. Never
restart an active Plasma session or replace production activation for these tests.

## Native packaging acceptance

Export the exact 1.0.1 source baseline for the upgrade tests, then build the
complete disposable test image:

```sh
mkdir -p work/package-legacy
git archive 34058480b6e3bc1ecc1f19d420fb744f570eca34 | tar -x -C work/package-legacy
docker build -f native/tests/packaging.Dockerfile -t opm-native-package:test .
docker run --rm --network none opm-native-package:test
```

The build stage runs the existing five native CTest targets and nine packaging
scenarios with actual temporary XDG profiles and private buses. It invokes the
released legacy installer and activates the real 1.0.1 Python service before
upgrading/rolling back. Test-only crash/failure hooks are compiled out before
copying the bundle to the runtime image. The final image contains no Python,
PySide6 or compiler and verifies the explicit bootstrap, native CLI, editor,
production D-Bus activation, reinstall, removal and rollback. Package hashes,
distro/version/CPU, platform plugins and missing runtime components are checked.

The remaining physical release gate covers the installed widget, Meta+X,
original-launcher masking/restoration, native editor/backups, standalone menu,
light/dark/Aero themes, focus, real panel work areas and mixed-DPI monitors on
Plasma Wayland and X11. Virtual-session and private-bus results do not certify
that gate. No live installation is replaced by these automated tests.
