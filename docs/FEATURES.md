# Native 2.1 feature reference

Audited against approved source **`4e11393c4d289c453044130d79dc54a23049c32c`**.
This describes native 2.1.0, including defaults added by C++ over the shared JSON
catalog. The old Python implementation is not the authority for these values.
The [machine-readable default dump](images/2.1/native-defaults.json) comes from
that source's built `open-power-menu-standalone --default-config`.

[Visual tour](../README.md) · [Configuration guide](CONFIGURATION.md) ·
[Capture provenance](SHOWCASE.md)

## Preferences and defaults

These are new-configuration defaults. Upgrades retain saved preferences and
custom layouts. General settings apply after **Save**, then reopening the menu.
The JSON path is `${XDG_CONFIG_HOME:-$HOME/.config}/open-power-menu/menu.json`.
`version: 1` is the configuration schema version, not the application version.

| Setting / JSON key | Allowed values | New default | Scope and implementation |
| --- | --- | --- | --- |
| Appearance / `appearance` | `native`, `aero` (Aero Dark), `aero-light` (Aero Light) | `native` | Menu surfaces; native follows the desktop palette. [Model](../native/model.cpp), [widget](../plasmoid/contents/ui/main.qml), [standalone](../native/standalone.cpp). Configure itself retains the KDE style. |
| Original launcher / `launcher_applet_id` | `0` automatic; positive applet ID up to 2,147,483,647 | `0` | Select an existing launcher, on the same panel. Explicit missing IDs do not activate an unrelated launcher. [Catalog](../native/editor_catalog.cpp), [visibility/integration](../plasmoid/contents/ui/LauncherVisibility.js). |
| Hide original button / `hide_original_launcher` | Boolean | `false` | Reversible visibility; the original applet remains installed. [Visibility](../plasmoid/contents/ui/LauncherVisibility.js), [widget](../plasmoid/contents/ui/main.qml). |
| Button icon source / `button_icon_mode` | `launcher`, `custom` | `launcher` | Adopt the selected launcher's icon or choose your own. [Launcher adapter](../plasmoid/contents/ui/adapters/PlasmaLauncher.js). |
| Custom button icon / `button_icon` | Theme icon name, absolute local image path or local `file://` URL | Empty | PNG, SVG/SVGZ, JPG/JPEG, WebP, ICO. Validated local paths; remote URLs are not supported. [Icon validation](../native/model.cpp), [General UI](../native/qml/Main.qml). |
| Menu icons / `show_menu_icons` | Boolean | `true` | Hides entry icons, not launcher or toolbar icons. [Entry content](../plasmoid/contents/ui/MenuEntryContent.qml), [standalone](../native/standalone.cpp). |
| Icon size / `menu_icon_size` | `small`, `standard`, `large` | `standard` | Nominal 14/18/24 logical pixels, bounded by font metrics. [Metrics](../plasmoid/contents/ui/MenuMetrics.js), [interaction](../native/interaction.cpp). |
| Density / `menu_density` | `compact`, `standard`, `comfortable` | `standard` | Row spacing grows for fonts/icons; nominal widget rows 28/34/42 logical pixels. [Metrics](../plasmoid/contents/ui/MenuMetrics.js), [standalone](../native/standalone.cpp). |
| Width / `menu_width` | `auto`, `narrow`, `wide` | `auto` | Font-aware sizing, constrained to available work area. [Widget](../plasmoid/contents/ui/main.qml), [flyout](../plasmoid/contents/ui/SideFlyout.qml), [standalone](../native/standalone.cpp). |
| Widget height / `menu_height_mode` | `auto`, `custom` | `auto` | Auto-fit or user-requested popup height; this setting does not set standalone height. [Widget](../plasmoid/contents/ui/main.qml). |
| Custom height / `menu_custom_height` | Integer 120–10,000 logical pixels | `600` | Used only in custom mode; runtime minimum and display/work-area limits still apply. [Validation](../native/interaction.cpp), [widget](../plasmoid/contents/ui/main.qml). |
| Pointer-leave closing / `auto_close_on_pointer_leave` | Boolean | `false` | Optional automatic dismissal; outside click and Escape remain available. Keyboard navigation and layout editing protect the menu. [PointerDismissal](../plasmoid/contents/ui/PointerDismissal.qml), [standalone](../native/standalone.cpp). |
| Closing delay / `auto_close_delay_ms` | 500–5,000 ms, 100 ms steps in Configure | `1200` | UI displays seconds. Root and open flyouts count as one menu region. [Interaction](../native/interaction.hpp), [General UI](../native/qml/Main.qml). |
| Submenu hover / `submenu_hover_delay_ms` | `-1` existing/system behavior; `0` immediate; 100–600 ms in 100 ms steps | `-1` | Selecting Delayed starts at 300 ms. Arrow-key navigation remains direct. [HoverOpen](../plasmoid/contents/ui/HoverOpen.qml), [General UI](../native/qml/Main.qml). |
| Keyboard access / `access_keys_enabled` | Boolean | `true` | Enables letter/digit selection. Does not disable ordinary arrows/Enter/Escape or the widget shortcut. [AccessKeys](../plasmoid/contents/ui/AccessKeys.js), [interaction](../native/interaction.cpp). |
| Key hints / `show_access_key_hints` | Boolean | `true` | Separate stored preference; visible only while access keys are enabled. Disabling hints leaves access keys usable. [Model](../native/model.cpp), [entry content](../plasmoid/contents/ui/MenuEntryContent.qml). |
| Power Actions / `power_confirmation` | `system`, `always`, `immediate` | `system` | Follow KDE system settings, Always show confirmation, Execute immediately. Applies to native Shutdown/Restart/Sign out only. [Power](POWER.md), [implementation](../native/power.cpp). |
| Legacy confirmation / `confirm_power_actions` | Boolean compatibility field | `true` | Not an additional current UI mode. Old true/false settings migrate to always/immediate. The shadow field remains conservative for rollback. [Decode/migration](../native/model.cpp). |
| Unavailable commands / `show_unavailable` | Boolean | `false` | Hide unavailable entries, or show them disabled. Tools are discovered, not installed by OPM. [Normalization](../native/model.cpp), [Layout UI](../native/qml/Main.qml). |
| Automatic backup count / `backup_retention` | Integer 0–1,000 | `10` | Zero disables ordinary automatic backups; protected recovery copies remain. [Storage](../native/storage.cpp), [Backups UI](../native/qml/Main.qml). |
| Standalone anchor / `anchor` | `cursor`, `bottom-left`, `bottom-right` | `cursor` | Standalone placement hint; Wayland placement belongs to the compositor. [Standalone](../native/standalone.cpp), [CLI](../native/standalone_main.cpp). |

### Per-widget Plasma settings

These live in Plasma's applet configuration, separately from the shared native
menu JSON. See [configuration schema](../plasmoid/contents/config/main.xml) and
[Plasma settings UI](../plasmoid/contents/ui/configGeneral.qml).

| Setting | Default / choices | Meaning |
| --- | --- | --- |
| `leftAction` | `launcher`; alternative `power` | Default: left-click opens the selected application launcher, right-click opens OPM. Choosing Power User Menu for left-click makes **both** buttons open OPM; it does not swap the buttons. |
| `buttonIcon` | `start-here-manjaro` | Fallback icon when the adopted/custom icon cannot be resolved. Different from native `button_icon`. |
| `popupDiagnostics` | `false` | Optional timestamped lifecycle logs; no diagnostic overlay. Leave off in normal use. |
| Keyboard Shortcuts | Meta+X if unassigned | A new eligible widget requests Meta+X once. Existing, changed and deliberately cleared assignments are preserved. `opmDefaultShortcutTried` is an internal marker, not a user preference. |

Generic Plasma launchers use the normal applet activation path. AppGrid Center
has a specific adapter; this is not a promise that every third-party launcher
works. The new gallery actually captures **Kickoff**. See
[adapter dispatch](../plasmoid/contents/ui/adapters/LauncherAdapters.js) and
[AppGrid matching](../plasmoid/contents/ui/adapters/AppGridLauncher.js).

## Built-in tools and selection

The [shared action catalog](../openpowermenu/data/actions.json), native
[overrides/normalization](../native/model.cpp), [preferred applications](../native/applications.cpp)
and [editor catalog](../native/editor_catalog.cpp) determine these entries.
Custom labels/icons may replace their presentation. Availability is checked
against installed executables, desktop/session facilities and power policy.

| Built-in ID | Default title | Resolution / purpose | Preset key |
| --- | --- | --- | --- |
| `applications` | Installed Applications | Distro-aware software manager: Pamac preferred on Manjaro, Discover on KDE, then supported alternatives | P |
| `power` | Power Options | Desktop power settings; distinct from session-ending actions | O |
| `logs` | System Logs | KSystemLog or supported journal/terminal viewer | V |
| `system` | System Information | KInfoCenter, HardInfo or desktop alternative | Y |
| `hardware` | Hardware Information | Installed hardware viewer or terminal report | M |
| `network` | Network Connections | Desktop connection editor / network KCM | W |
| `disks` | Disk Management | KDE Partition Manager, GNOME Disks or GParted | K |
| `printers` | Printers | Printer configuration KCM or system-config-printer | — |
| `vms` | Virtual Machine Manager | virt-manager or VirtualBox | — |
| `terminal` | Terminal | KDE's preferred terminal first, then installed fallbacks | I |
| `monitor` | Task Manager / System Monitor | Plasma System Monitor or supported alternative | T |
| `files` | File Manager | Preferred `inode/directory` application, then fallbacks | E |
| `settings` | Settings | Desktop settings application | N |
| `run` | Search / Run | KRunner or supported runner; opens the runner, not an OPM search field | R |
| `remote` | Remote Desktop | Preferred RDP handler, KRDC/Remmina fallback | — |
| `network_locations` | Network Locations | Dolphin opens `~/Network Locations`; entry requires that directory | — |
| `lock` | Lock | Session lock request | L |
| `logout` | Sign out | Native KDE session request under selected confirmation policy | I |
| `reboot` | Restart | Native KDE session request under selected confirmation policy | R |
| `shutdown` | Shut down | Native KDE session request under selected confirmation policy | U |
| `sleep` | Sleep | Native KDE/logind capability, inhibitor and authorization checks | S |
| `hibernate` | Hibernate | Native KDE/logind capability, inhibitor and authorization checks | H |
| `show_desktop` | Desktop | KDE Show Desktop toggle; restores windows on a second use | D |

Confirmation-capable titles gain an ellipsis when confirmation is effective.
Sleep/Hibernate are native additions; session-ending built-ins replace the
legacy command arrays with native dispatch. A custom command that calls a power
service directly retains its own behavior and can bypass confirmation.

The **Shut down or sign out** submenu has preset U. Presets are scoped per menu
level, so Terminal I and Sign out I do not conflict. The submenu is recognized by
its built-in contents, not just its label. Presets are not assigned to arbitrary
custom entries. See [preset rules](../native/interaction.cpp).

## Keyboard and pointer interaction

| Interaction | Behavior | Implementation |
| --- | --- | --- |
| Meta+X | Toggle the widget through Plasma's native applet shortcut; change it in widget Keyboard Shortcuts | [Widget](../plasmoid/contents/ui/main.qml) |
| Up / Down | Navigate available rows; normal navigation repeats are allowed | [Widget](../plasmoid/contents/ui/main.qml), [flyout](../plasmoid/contents/ui/SideFlyout.qml), [standalone](../native/standalone.cpp) |
| Right / Enter | Enter a submenu; Enter activates a selected command | Same three frontends |
| Left / Escape | Go back from a submenu; Escape closes the root menu | Same three frontends |
| Letter or digit | Select the matching enabled entry, when access keys are enabled | [AccessKeys](../plasmoid/contents/ui/AccessKeys.js), [native input](../native/physical_keys.cpp) |
| Held activation key | One physical hold cannot count as two power-menu selections; X11 uses XInput2 release evidence | [Physical key guard](../native/physical_keys.cpp), [input bridge](../plasmoid/contents/ui/NativeInput.qml) |
| Outside click | Intentional dismissal independent of optional pointer-leave closing | [Widget](../plasmoid/contents/ui/main.qml), [flyout](../plasmoid/contents/ui/SideFlyout.qml) |
| Refresh toolbar button | Reload the open menu and retry a previously unavailable backend | [Widget](../plasmoid/contents/ui/main.qml) |

Per-entry access keys are one **A–Z or 0–9**, or empty to disable. They must be
unique within each menu level. Configure preserves explicit assignments;
**Reset access keys** restores unambiguous presets and is undoable.
On Wayland, an unobserved release outside OPM cannot establish a new physical
press; destructive selection fails closed. Do not verify power keys against real
session services. See [private keyboard tests](TESTING.md#private-power-and-keyboard-tests).

## Editing, persistence and recovery

| Capability | Supported behavior | Source |
| --- | --- | --- |
| In-menu layout editor | Unlock; drag/reorder; hold over a submenu to enter; move through Go Back; Save layout / Cancel. Commands remain inactive while editing. Closing retains the unfinished draft. | [LayoutEditor](../plasmoid/contents/ui/LayoutEditor.qml), [controller](../plasmoid/contents/ui/LayoutController.js) |
| Keyboard rearrangement | Alt+Up/Down reorders; Alt+Left moves out; Alt+Right offers destination submenus; Menu / Shift+F10 offers movement commands | [LayoutEditor](../plasmoid/contents/ui/LayoutEditor.qml) |
| Full Configure Layout | Add built-in, installed application, custom command, submenu or separator; edit, duplicate, remove; rearrange; reset access keys or default layout | [Main UI](../native/qml/Main.qml), [entry dialog](../native/qml/EntryDialog.qml), [session](../native/editor_session.cpp) |
| Custom commands | Executable plus individual arguments; labels, icons and access keys. No implicit shell parsing. Installed-application picker retains desktop-entry launch semantics. | [Entry dialog](../native/qml/EntryDialog.qml), [applications](../native/applications.cpp), [launch](../native/launch.cpp) |
| Undo / Redo | Draft history in Configure, including preferences and layout; save validates the active configuration identity | [EditorSession](../native/editor_session.cpp) |
| Conflict recovery | Keep the draft, reload, or explicitly overwrite with a protected copy; do not silently replace another editor's changes | [EditorSession](../native/editor_session.cpp), [storage](../native/storage.cpp) |
| Import / Export | Preview and validate JSON imports against the selected source and active revision. Export includes the draft and creates a new file; it does not overwrite an existing export. Review private paths/arguments before sharing. | [EditorSession](../native/editor_session.cpp) |
| Backups | Preview / restore / delete with identity and ownership checks; protected pre-restore and pre-overwrite copies. Backups tab also inventories widget upgrade history read-only. | [Storage](../native/storage.cpp), [editor catalog](../native/editor_catalog.cpp) |
| Layout validation | Up to 8 nested levels and 200 entries per menu; 4 MiB configuration limit; valid UTF-8; duplicate layout fields rejected; unknown metadata preserved | [Model](../native/model.cpp), [storage](../native/storage.cpp) |
| Standalone | `open-power-menu`; same configured tools, access keys and power policy; Qt Widgets menu with cursor/corner anchor hints | [CLI](../native/standalone_main.cpp), [standalone](../native/standalone.cpp) |
| Configure without widget | `open-power-menu --edit`; native Qt Quick/Kirigami editor with current session environment resolution | [Editor coordinator](../native/editor_launch.cpp), [editor main](../native/editor_main.cpp) |
| Read-only CLI | `--list`, `--check`, `--default-config`; `--config`, `--anchor`, `--theme` select standalone inputs | [CLI](../native/standalone_main.cpp) |
| EZ installation | Distro-matched sealed native payload; hashes/runtime/plugin checks; reversible user-local transaction. No automatic dependency installation or Plasma restart. | [EZ wrapper](../native/packaging/ez-install.sh.in), [installer](../native/packaging/installer.cpp) |
| Update / rollback / recover | Preserve menu, shortcut assignments, launcher selection and panel layout; previous complete installation snapshot; interrupted-transaction recovery; configuration and application history remain separate | [Recovery guide](RECOVERY.md), [installer](../native/packaging/installer.cpp) |

The standalone does not contain the Plasma toolbar or the in-menu layout editor;
use Configure for editing. The separate KDE Store widget is not a complete native
installation. See [installation](INSTALLATION.md), [compatibility](COMPATIBILITY.md)
and [known limitations](../README.md#known-limitations).
