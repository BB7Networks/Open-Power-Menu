# Configuration and customization

Open **Configure** from the OPM widget or run `open-power-menu --edit`.
The native editor has General, Layout and Backups pages. Save persists your
changes; reopening the menu refreshes preferences without restarting Plasma.
The configuration lives at `${XDG_CONFIG_HOME:-$HOME/.config}/open-power-menu/menu.json`.

General controls launcher selection and visibility, launcher/custom icon,
native/Aero appearance, menu icons, icon size, density, width/height, hover
and pointer dismissal, access-key hints and [power confirmation](POWER.md).
Disabling automatic pointer dismissal does not disable deliberate outside-click
or Escape dismissal. Keyboard navigation temporarily suspends pointer dismissal.

Layout supports built-ins, installed applications, custom programs/arguments,
submenus, separators, reordering and Undo/Redo. The widget also has an in-menu
layout editor: unlock, move entries, use **Go Back**, then save or cancel.
Changes are reference-based and validated; untrusted command text is not accepted
from a widget selection. Existing custom metadata and identities are preserved.

Use the installed-application picker for KDE desktop-entry handling. Custom
commands use a program and individual arguments; shell operators are not
implicitly evaluated. An explicit shell or D-Bus power command keeps its own
behavior, including bypassing OPM's built-in confirmation policy.

Access keys are configurable and may be disabled per entry. Meta+X uses Plasma's
widget shortcut, preserving custom/disabled bindings. Arrow keys, Enter and
Escape navigate menus; submenu input shares the physical-key guard. On X11,
XInput2 distinguishes physical releases from autorepeat. Wayland fails closed
when a release outside OPM cannot be established. Never exercise power-key
stress against live services; use [private tests](TESTING.md).

Backups provide guarded preview/restore/delete and protected pre-restore copies.
See [configuration recovery and application rollback](RECOVERY.md). Do not
replace a working menu with the historical examples: use the editor to preserve
existing layouts and custom commands.
