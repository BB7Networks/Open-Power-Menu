# Automated checks and desktop acceptance

## Automated development workflow

Use Python 3.12 and Node 22 (the CI versions). A virtual environment is optional:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pytest
python -m pytest -q -ra
for script in Install.sh Uninstall.sh scripts/*.sh tools/*.sh; do
    bash -n "$script"
done
python -m compileall -q openpowermenu tests run.py
bash scripts/build-release.sh
bash scripts/build-widget-only.sh
(cd dist && sha256sum -c SHA256SUMS)
unzip -t dist/OpenPowerMenu-EZ-v0.4.17.zip
unzip -t dist/org.openpowermenu.start-0.4.17.plasmoid
tar -tzf dist/OpenPowerMenu-EZ-v0.4.17.tar.gz
```

Optional Qt runtime checks require PySide6 QtCore/QtDBus/QtWidgets/QtTest and
`dbus-run-session` (normally supplied by the distro's D-Bus packages):

On a minimal Debian/Ubuntu image, the Qt wheel also needs the system `libegl1`
package even with the offscreen platform. CI installs it and checks Qt imports
before running tests, so a missing runtime cannot silently skip this job.

```bash
python -m pip install PySide6-Essentials==6.10.2
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_qt_runtime.py
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
Version identifiers remain at 0.4.17; building archives does not tag or publish.

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

Back up the current `~/.config/open-power-menu/menu.json` manually before a
rollback. Copy a chosen `menu.json.bak-<timestamp>` over `menu.json` with the
editor closed, keep it readable only by your user, then reopen Configure. Never
replace `plasma-org.kde.plasma.desktop-appletsrc` for an OPM rollback.

Widget snapshots live under `~/.local/share/open-power-menu/widget-backups/`.
Copy the desired snapshot somewhere safe before uninstalling. On a local desktop,
install/upgrade that snapshot with `kpackagetool6 --type Plasma/Applet --upgrade
<snapshot-directory>` and follow Plasma's normal local widget refresh procedure.
The matching old Python backend must be restored from a trusted complete release
if required; a widget snapshot alone is not a full application rollback.

Do not mark this matrix complete based on offscreen tests. Attach real
[screenshots](images/README.md) only after live acceptance.
