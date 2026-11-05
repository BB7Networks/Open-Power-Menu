# Open Power Menu 0.4.17

For the current branch's action/lifecycle changes, automated checks and remaining
desktop acceptance, read [REVIEW.md](REVIEW.md), [TESTING.md](TESTING.md) and
[PROCESS-LIFECYCLE.md](PROCESS-LIFECYCLE.md). For the subsequent editor changes,
read [EDITOR-RECOVERY.md](EDITOR-RECOVERY.md), and for the new widget controls read
[IN-MENU-EDITING.md](IN-MENU-EDITING.md). The release-history notes below do
not replace those results. Optional PySide6 offscreen tests now run in CI; actual
Plasma/Wayland acceptance remains separate.

A launcher-independent Power User menu for KDE Plasma 6, with an optional unified
Start-button widget. **Left-click** delegates to an existing launcher; **right-click**
shows the Power User menu. The original launcher, its favorites, and its settings
remain installed and untouched.

## New in 0.4.17: easier menu editing

The **General** and **Layout** tabs are unchanged, but adding items is now more
obvious. Open **Configure > Layout > Add...** and choose:

- **Installed application...**: search the applications installed on this PC,
  select one, and review the populated name, icon, and launch command. The
  editor prefers KDE's `kioclient6 exec` desktop-file handler, which preserves
  launcher behavior such as DBus activation, terminal handling and working
  directories. Nothing is executed during browsing.
- **Built-in command**: choose an existing system action. **Runs on this PC**
  shows which command the action currently selects; **Fallback order** lists
  every attempted alternative and whether it is available. Use **Customize this
  command...** to create an independently editable custom command. The original
  built-in keeps its auto-fallback behavior; the custom copy does not.
- **Custom command**: type a program and optional arguments, browse a binary, or
  choose an installed application. For example `dolphin ~/Documents`. Arguments
  with spaces need quotation marks. Commands are passed directly to the program;
  shell syntax such as pipes, redirects and `&&` is not interpreted.
- **Submenu** or **Separator**: group and organize entries.

The Layout tree now has a **Runs on this computer** column, so a command is
visible without opening an item. All saved entries still use the existing
`menu.json` model; legacy menus remain compatible without migration.

Only the Python Configure UI and its helper modules have changed. The proven
v0.4.16 QML launcher adapters, panel masking, click handoff and flyouts are
unchanged. An existing installation can use the new Configure editor immediately
without reloading Plasma. This editor has been exercised by portable tests but
not visually verified against a live PySide6/KDE desktop in the build environment.

## Configure

Open the gear icon at the upper-right of the Power User menu, or run:

```bash
~/.local/bin/open-power-menu --edit
```

The **General** tab now contains:

- **Original launcher:** choose the original panel widget by ID, or auto-detect
  one on the same panel. Toggle **Hide the original launcher's panel button**.
  The launcher selector is available even when the original button is visible.
- **Start button icon:** adopt the selected launcher's icon (default) or use a
  custom theme icon/local image, with a preview.
- **Appearance:** choose the standard native theme or Dark Aero for the menu.
- **Keyboard shortcut:** Set up Meta+X tests the installed standalone menu and opens
  KDE Shortcuts to assign the Application entry. KDE owns conflict handling; OPM
  does not write bindings. General also separates the Emergency Restore command.

The **Backups** tab contains automatic configuration retention plus preview and
restore through **Manage / Restore Backups…**. Explicit recovery copies are kept
even with retention zero. A separate section shows widget snapshot information;
its retention remains controlled by the installer.
The browser can permanently delete one confirmed configuration backup, with
conflict checks and extra warnings for protected copies. Returning to Backups updates
the separate widget count without touching files or unsaved editor settings.

The **Layout** tab contains the Power User menu entries. Add built-in actions,
custom argv commands, nested submenus and separators; edit/remove/reorder them.
Select a submenu before adding an entry to place it inside. **Restore default
layout** changes only the unsaved Layout tab; it will not reset General settings.

**Save** and **Cancel** apply to the complete editor. No files are edited until
Save or an explicitly confirmed backup restore. Closing dirty state offers
Save / Discard / Cancel; external modifications require reload or explicit
overwrite with a recovery copy. Restore is blocked while any tab has unsaved edits.
Layout now supports nested drag-and-drop,
Duplicate and Qt Undo/Redo. Your personal shortcuts and submenu structure remain
intact on upgrade. See the [editor guide](EDITOR-RECOVERY.md) for shortcuts.

### Launcher compatibility

Core behavior is launcher-agnostic: select an applet on the same panel, activate
its Plasma signal for left-click, inherit its Plasma icon, and optionally hide
its panel representation through Plasma's reversible `HiddenStatus` behavior.
Standard Plasma popup launchers are dismissed through `expanded=false`.

AppGrid Center **1.9.6** needs one extra, **opt-in** adapter: its full-screen
Wayland overlay otherwise captures right-clicks over the underlying panel. The
adapter uses AppGrid's own `setInputRect` API to pass pointer input through only
the edge containing the panel. It also uses AppGrid's native in-process close
method; it never patches AppGrid's files. The redundant 1.9.x standalone D-Bus probe was removed in 0.4.12. A
separate-process `Hide` fallback remains for newer AppGrid center builds when
the daemon is already running. **As of 0.4.13, these AppGrid exceptions live
in separate adapter modules**, not the generic Start button logic.

Other third-party full-screen or out-of-process launchers may need their own
small adapters; this release does **not** claim universal popup dismissal for
every launcher. See [`ADAPTERS.md`](ADAPTERS.md), [`AUDIT.md`](AUDIT.md), and [`INTEGRATION.md`](INTEGRATION.md).

### KDE Application Launcher (Kickoff) switching and visual flicker

v0.4.16 addresses a **new focus race** observed when switching from an open
Power User Menu (right-click) to Kickoff (left-click). Previously the OPM popup
was collapsed and the selected native launcher was activated the very next QML
turn. Plasma's earlier native dialog may still be deactivating, causing the
new launcher to appear then immediately close. **Only when Power Menu was
already visible**, activation now waits a bounded 140 ms for popup focus to
settle. A newer right-click cancels the delayed request; an already-open
launcher (e.g. opened via Meta) is not toggled shut a second time. Ordinary
left-click activation stays unchanged.

For the separate, brief **original Kickoff icon flash**, the v0.4.15
`HiddenStatus` binding remains intact. No additional size, geometry, opacity,
visible, or panel-layout overrides were added. The previous repair log being
empty does not prove there was no status transition, so v0.4.16 adds read-only
status/item/container visibility observations during the launcher transition.
After opening Kickoff repeatedly, collect:

```bash
journalctl --user -b --since '5 minutes ago' --no-pager -o cat | \
  grep -E 'Open Power Menu: (launcher visibility|activating launcher after Power Menu popup settled|launcher already open after popup settled)' | tail -n 30
```

If status remains hidden and the panel container/item remain invisible while
an icon is briefly seen, the remaining flash is likely outside OPM's reversible
status binding. Avoid aggressive changes until the actual visible element is
identified.

The focus-timing fix is a **live-test hypothesis**, not yet verified on KDE
Plasma/Wayland. Portable tests cannot reproduce compositor focus transitions.

## Install / upgrade on Manjaro

```bash
tar -xzf OpenPowerMenu-EZ-v0.4.17.tar.gz
cd OpenPowerMenu-v0.4.17
bash install.sh
```

The installer changes only Open Power Menu files. It backs up the previously
installed OPM widget in
`~/.local/share/open-power-menu-recovery/widget-backups/` and preserves
`~/.config/open-power-menu/menu.json` and Plasma's panel settings.
Legacy snapshots are migrated; the default retention is five and uninstall
preserves history. See [recovery](EDITOR-RECOVERY.md#widget-upgrade-history-and-uninstall).

The editor can be tested immediately after the installer. **A Plasma restart is
not required just to test this two-tab editor**, because it's a separate Qt
application. Avoid restarting `plasma-plasmashell.service` during a RustDesk
session. A local Plasma reload **is needed to load the changed widget QML** for
v0.4.16. The editor alone can be tried without a reload. Never reload Plasma
while the RustDesk connection to that machine is your only access.

Verify the backend with:

```bash
~/.local/bin/open-power-menu --check
~/.local/bin/open-power-menu --launcher-diagnostics
```

## Emergency recovery

```bash
~/.local/bin/open-power-menu --show-launcher-button
```

This writes the reversible preference and the widget restores the original
button/input region on its next refresh (approximately five seconds). It never
deletes the original launcher.

## Testing / limitations

Portable Python and JavaScript tests cover the launcher mask, input geometry,
menu switching, editor structure, config validation and rollback. Offscreen
PySide6 tests run in the Qt CI job; the build environment has no live
Plasma/Wayland compositor. The actual v0.4.11 left/right behavior was confirmed by a user
running AppGrid Center 1.9.6; **v0.4.16's focus handoff and visual diagnostics still require local
acceptance**. UI layout, menu editor code, configuration, and masking geometry
were preserved from the previous releases.

For historical release notes see [`CHANGELOG.md`](CHANGELOG.md).
