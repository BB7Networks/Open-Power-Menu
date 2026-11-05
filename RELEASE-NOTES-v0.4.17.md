# Open Power Menu v0.4.17 (beta)

A unified Start button for KDE Plasma 6: left-click to open your existing
launcher; right-click to open a configurable Power User menu.

### Highlights

- General and Layout configuration tabs.
- Searchable installed-application picker for custom menu entries.
- Visible commands and fallback order for built-in actions.
- Reversible hiding of the original launcher button and inherited icon.
- Adapter architecture, including AppGrid Center 1.9.6 Wayland support.
- User-local EZ installer, update and recovery instructions.

### Requirements

KDE Plasma 6, Python 3, PySide6, user D-Bus session. Manjaro is the primary
tested distribution. Third-party launchers may need additional adapters.

### Install

Extract `OpenPowerMenu-EZ-v0.4.17.zip` and run `bash install.sh`
without sudo. Add **Open Power Menu Start Button** from Plasma's widget
chooser; in Configure → General, select your original launcher.

The widget on its own does not include the backend needed for the right-click
menu. Do not upload this release as a one-click KDE Store widget without a
backend setup path.
