# Open Power Menu

**One Start button. Two useful menus.**

The Windows right-click Start / Win+X menu is a good idea. Microsoft has made
some questionable decisions over the years, but this is one worth keeping.
Open Power Menu brings that workflow to **KDE Plasma 6**, alongside the
application launcher you already like.

| Click the OPM Start button | What opens |
| --- | --- |
| **Left-click** | Your existing application launcher: Kickoff, Kicker, or a supported alternative |
| **Right-click** | Your configurable Power User menu: system tools, settings, apps and shortcuts |

OPM started during a personal KDE desktop customization project: keep a useful,
familiar workflow without recreating Windows wholesale. It is not another
Windows-themed application launcher. Keep your launcher, favorites and panel;
add quick access to the tools you use.

> **Beta · v0.4.17 release baseline.** Changes under development are listed in
> [Unreleased](CHANGELOG.md). Manjaro / Plasma 6 and AppGrid Center 1.9.6 have
> been tested on a live Wayland desktop. New changes still need the
> [desktop acceptance checks](docs/TESTING.md).

Real screenshots are being collected. See the [capture guide](docs/images/README.md)
for the Start button, both menus and Configure views. No mock screenshots are
presented as the application.

## What you get

- A configurable menu of built-in system tools, installed applications, custom
  commands, nested submenus and separators.
- Optional, reversible hiding of the original launcher's **button**, preserving
  the launcher itself, its configuration and its favorites.
- Native KDE launcher support and a dedicated AppGrid Center 1.9.6 adapter.
- **Configure → General** for launcher selection, button icon and appearance;
  **Layout** for editing with Duplicate and Undo/Redo; **Backups** for recovery.
- Unlock the menu to rearrange entries, then **Save layout** or **Cancel**.
  Commands stay inactive while editing.
- Per-user installation, upgrades that preserve your menu, and a recovery command.

**System Logs** prefers KSystemLog. Without it, Konsole or XTerm follows the
current boot's warning-and-higher journal entries, starting with up to 1,000
lines. Both the terminal and `journalctl` must be installed. Journal access
uses your normal permissions; OPM does not force root execution.

**Printers** prefers KDE Print Manager when its configuration module is installed,
then `system-config-printer`. New defaults include it beside Disk Management;
your existing saved layout stays unchanged. Add it through the built-in selector
if you already have a custom menu. OPM never installs these optional tools silently.

## Install on KDE Plasma 6

1. Get the complete **EZ installer ZIP** from [Releases](https://github.com/BB7Networks/Open-Power-Menu/releases)
   when available, or download/clone this repository. Extract the whole archive.
2. Open a terminal **inside the extracted folder**, then run:

   ```bash
   bash install.sh
   ```

   Run as your normal desktop user, without `sudo`. Setup checks for Python 3,
   `kpackagetool6` and PySide6 (QtCore, QtDBus, QtWidgets). On Manjaro it can offer
   to install the system `pyside6` package after asking permission.
3. Right-click the Plasma panel → **Add Widgets** → add **Open Power Menu Start
   Button** on the same panel as your existing launcher.
4. Right-click the new button → gear icon → **General**. Choose your launcher,
   test both mouse buttons, then optionally hide the original button.

For updates, run the new package's `install.sh` again. Existing `menu.json`
contents are preserved. Previous OPM widgets are backed up under
`~/.local/share/open-power-menu-recovery/widget-backups/`. The newest five
snapshots are kept; existing snapshots are migrated automatically and survive
uninstall. To choose a different limit, run
`OPM_WIDGET_BACKUP_RETENTION=10 bash install.sh` (1–1,000).
No automatic Plasma restart is performed. Test a widget refresh locally rather
than interrupting remote access.

The `install.sh` / `uninstall.sh` wrappers use distinct core filenames under
`scripts/`. The source and complete archives are safe to clone or extract on
Windows; **running OPM still requires Linux and Plasma 6**.

**KDE Store limitation:** a `.plasmoid` archive installs only the widget, not
its Python/PySide6 backend. It is not a complete one-click installation.
Use the full installer; see [Store readiness](docs/KDE-STORE.md).

## Make it yours

For a quick rearrangement, right-click the Start button and select the **lock**
icon. Drag any part of an entry to move it. Pause over a submenu to open it while
dragging, or over **Back** to move up a level. The list keeps your place as you
rearrange entries, including wheel scrolling during a drag. Right-click or press
Shift+F10 for movement actions; Alt+Arrow shortcuts remain available. All entries
appear, including unavailable applications and empty submenus. **Save layout**
checks for conflicts and preserves your command definitions; **Cancel** leaves
the saved menu untouched. Closing the popup keeps the draft for your next visit.
See [in-menu editing and keyboard shortcuts](docs/IN-MENU-EDITING.md).

For **Meta+X**, open **Configure → General → Keyboard shortcut → Set up Meta+X…**.
Use **Test menu launch**, then choose **Add New → Application… → Open Power Menu**
in KDE Shortcuts and assign/apply the key. This opens the standalone menu.
KDE handles conflicts and lets you change or remove the assignment. See the
[shortcut and AppGrid diagnostic guide](docs/SHORTCUT-APPGRID-DIAGNOSTICS.md) if nothing appears.

Open **Configure → Layout → Add → Installed application**, search by name or
description, and choose an app. Its name, icon and launch command are filled in
for review. Save the entry, then Save the complete editor. On KDE, the picker
prefers `kioclient6` so the desktop file controls activation, terminal handling,
working directory and field-code expansion.

Choose **Built-in command** to see what runs on this workstation and the ordered
fallbacks. **Customize this command** creates an independent custom entry; the
original built-in keeps its automatic fallback behavior.

For custom commands, give the executable name or path and its arguments:
`dolphin ~/Documents`, or `tool "two words"`. Arguments containing spaces need
quotes. OPM passes argument arrays directly; pipes, `>`, `&&` and command
substitution are not interpreted. Commands needing terminal output should open
a terminal explicitly; detached applications do not inherit OPM's standard streams.

Drag entries before/after other entries or into submenus. Entire submenus move
with their children. **Duplicate** makes an independent copy after the selected
entry. Use **Ctrl+Z** to undo and **Ctrl+Shift+Z** or **Ctrl+Y** to redo layout
changes. Right-click an entry to see editing and keyboard movement shortcuts;
Move Up/Down buttons remain available.

Changes stay in memory until **Save**. Closing with unsaved Configure
changes offers **Save / Discard / Cancel**. If another editor changes the file,
choose to keep editing, reload it, or explicitly overwrite with a recovery copy.

**Configure → Backups → Configuration backups** keeps 10 previous automatic
versions by default, with a limit of 0–1,000. Setting 0 stops new backups and
preserves existing history. Pruning happens only after a successful save;
manually named backups remain untouched. Select **Manage / Restore Backups…** to preview
entries and settings, then restore a valid backup. Restore preserves the current
file as a separate recovery copy even with automatic backups disabled. Save or
discard pending editor changes and reopen Configure before restoring. The Backups
tab also shows the separate widget recovery directory and generated snapshot count.
The count refreshes when you open or return to Backups. The separate configuration
backup browser retains its **Refresh** button. In that browser,
**Delete selected backup…** permanently removes one confirmed backup; the active
configuration is protected, and recovery copies receive an additional warning.

## Recovery and removal

Restore the original launcher button:

```bash
~/.local/bin/open-power-menu --show-launcher-button
```

The widget applies this reversible preference on its next refresh. OPM never
removes the original launcher or edits its favorites or panel configuration.

Remove **only the OPM Start button** from the panel, then run `bash uninstall.sh`
from the complete extracted package. Your menu remains at
`~/.config/open-power-menu/menu.json`, together with its backups. Widget snapshots
remain in the separate recovery directory above; legacy snapshots are moved there
before removing application files. For rollback steps, see
[editor and recovery](docs/EDITOR-RECOVERY.md).

## Compatibility and roadmap

Requires KDE Plasma 6, Python 3, PySide6 and a user D-Bus session. Native
Kickoff/Kicker and AppGrid Center use separate adapters. Other third-party
fullscreen launchers may need an adapter. Portable/offscreen tests cannot prove
Wayland pointer delivery, popup alignment or focus handoff on a physical panel.

Next priorities:

- Complete the two-workstation acceptance matrix and publish real screenshots.
- Test more panel positions, launcher variants and clean-account upgrades.
- Provide a clear, user-driven backend installation route for KDE Store users.
- Evaluate separate desktop application scopes only with real Plasma/systemd
  evidence; process ancestry alone does not mean an app dies with OPM.

See the [review findings](docs/REVIEW.md) and [process lifecycle report](docs/PROCESS-LIFECYCLE.md).
The [in-menu editing guide](docs/IN-MENU-EDITING.md#deferred-work) records further
setup, native panel shortcuts, search and packaging work deferred from this change.

## Development and support

```bash
python3 -m pip install pytest
python3 -m pytest -q -ra
bash scripts/build-release.sh
```

Python and Node run the portable regression suite. Optional offscreen Qt/D-Bus
checks have a separate CI job; setup is described in [Testing](docs/TESTING.md).
The release builder produces local artifacts and does not publish a release.

[Report a bug](https://github.com/BB7Networks/Open-Power-Menu/issues) with your
Plasma version, distribution, launcher and reproduction steps. See
[Contributing](docs/CONTRIBUTING.md), [adapter design](docs/ADAPTERS.md) and
[release process](docs/PUBLISHING.md).

Independent community project, not affiliated with KDE. **MIT license:** [LICENSE](LICENSE).
