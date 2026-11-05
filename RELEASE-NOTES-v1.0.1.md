# Open Power Menu 1.0.1

Release candidate for public review. Publication follows desktop acceptance
and explicit release approval; these notes do not imply a published release.

- Keep your existing Plasma launcher and add a configurable right-click menu.
- Native widget Meta+X, adaptive flyouts and single-pane layout editing with
  Go Back, Save/Cancel, Undo/Redo, conflict checks and recovery.
- Optional menu entry icons and automatic closing after 1.2 seconds outside
  the menu and all open submenus. Keyboard navigation and editing keep it open.
- Desktop at the bottom of new/default layouts toggles KDE's native Show
  Desktop action. Existing customized menus are preserved.
- Complete EZ ZIP/TAR installers, checked upgrades and rollback on install
  failures; user configuration and recovery history survive uninstall.

Use the complete EZ package, extract it and run `bash install.sh` as your
normal desktop user. Do not use sudo. The widget-only `.plasmoid` requires a
separate Python/PySide6 backend installation.

See [release review](docs/RELEASE-1.0.1.md) for verification and remaining checks.
