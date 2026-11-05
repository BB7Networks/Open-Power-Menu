# Open Power Menu

**One Start button, two menus — for KDE Plasma 6.**

Open Power Menu is an optional unified Start button that works with an existing
Plasma application launcher. **Left-click** opens your original app launcher;
**right-click** opens a configurable Power User menu. You can hide the original
launcher *button* without deleting or modifying the launcher, its favorites,
or your panel configuration.

> **Version 0.4.17 · Beta.** Tested on Manjaro / KDE Plasma 6. The AppGrid
> Center 1.9.6 integration was tested on a live Wayland desktop. Not every
> third-party launcher has been tested; fullscreen launchers may need an adapter.

## Features

- Launcher-independent by default: supports the Plasma applet interface,
  including KDE Application Launcher (Kickoff) and Application Menu (Kicker).
- AppGrid Center 1.9.6 adapter for its fullscreen Wayland input overlay.
- Built-in commands, custom commands, nested submenus, and separators.
- **Configure → General** for integration, icon and appearance; **Layout** for
  menu entries, including an installed-application picker and command previews.
- Per-user install and uninstall. Keeps custom menu settings on upgrade.

## Install (recommended)

1. Download the **EZ installer ZIP** from Releases tab once the
   GitHub repository is published, or use a ZIP of this repository.
2. Extract it, open a terminal in the extracted folder, and run:

   ```bash
   bash Install.sh
   ```

   Do **not** use `sudo` for the installer. It checks for Python 3,
   `kpackagetool6`, and PySide6. On Manjaro it can offer to install PySide6
   using the system package manager after asking permission.
3. Right-click the Plasma panel → **Add Widgets** → search for **Open Power
   Menu Start Button**, and add it beside your existing launcher.
4. Right-click the new Start button → gear icon → **General**. Select your
   launcher, test both clicks, then optionally hide the original button.

For updates, run the new `Install.sh` again. Menu settings are preserved.

**Configuration backups:** Configure -> General -> Configuration backups controls
how many prior versions of `menu.json` are kept (10 by default). The oldest
automatic backups are pruned only after a successful save. Setting it to 0
disables new backups without deleting existing backup files. Manual backups
are not deleted.

The setup wrappers use `scripts/install-core.sh` and `scripts/uninstall-core.sh`,
so source archives work correctly on Windows as well as Linux.

**The current installation requires both the QML widget and a Python/PySide6
backend.** Installing only `plasmoid/` through KDE Store / Get New Widgets
*does not* install that backend. KDE Store one-click support is a planned
packaging improvement, not a feature of this release. See
[Store publishing notes](docs/KDE-STORE.md).

## Usage

In **Configure → Layout → Add**, choose an installed app (search by name), a
built-in action, a custom command, a submenu or a separator. Built-in actions
show the command they use and fallback order. Custom commands run as your own
user without a shell; pipes and redirection are not interpreted.

The widget does not require modifying or uninstalling your original launcher.
It can launch programs with your user account's permissions, so review commands
and source before installing a release from an untrusted source.

## Recovery / uninstall

Restore your original launcher button:

```bash
~/.local/bin/open-power-menu --show-launcher-button
```

To uninstall, remove **Open Power Menu Start Button** from the panel, then run
`bash Uninstall.sh` from your extracted package. Your personal menu JSON is
retained at `~/.config/open-power-menu/menu.json`.

## Development

```bash
python3 -m pytest -q
bash scripts/build-release.sh
```

Python/Node are used for portable regression tests. See
[development notes](docs/DEVELOPER-README.md), [adapter design](docs/ADAPTERS.md),
and [release process](docs/PUBLISHING.md).

## Compatibility and support

- **Requires:** KDE Plasma 6, Python 3, Qt for Python (PySide6) and user D-Bus.
- **Tested:** Manjaro KDE, Plasma 6, AppGrid Center 1.9.6; native Kickoff integration.
- **Limitations:** Third-party full-screen launchers may require a dedicated adapter.
- **Bugs/ideas:** Please open a GitHub issue after publishing this repository.

This is an independent community project, **not affiliated with KDE**.

**License:** MIT. See [LICENSE](LICENSE).
