# Open Power Menu 2.1.0 — EZ installation

This archive contains native binaries for **@LABEL@, x86-64**. Use a published versioned release or an explicitly reviewed Actions build
matching SOURCE-COMMIT. An Actions build does not imply stable publication or
physical desktop acceptance.
Do not install these binaries on a different distribution. No compiler or Python
is needed. An existing KDE Plasma 6 desktop and matching Qt/KDE runtime are required.

1. Download the matching EZ ZIP and its external SHA-256 checksum from the versioned release or reviewed
   GitHub Actions run. Verify with `sha256sum -c <archive>.zip.sha256`.
2. Extract the **whole** ZIP using KDE Ark or `unzip`. Open a terminal in the
   extracted `OpenPowerMenu-EZ-v2.1.0-…` folder. Paths containing spaces work.
3. Run `bash install.sh` as your normal desktop user, **without sudo**. Read the
   checks and approve the install/upgrade prompt. `--check` checks integrity and
   runtime without installing. `--yes` approves an unattended install; it never
   bypasses runtime, integrity, path, or transaction checks.
4. For a new installation, right-click the panel → Add Widgets → Open Power Menu
   Start Button. For upgrades, keep the existing widget and original launcher.
   Right-click OPM → Configure to select the launcher and preferences.

Existing 1.0.1, RC1, RC2 and native installations are upgraded using the same
transactional installer. Custom commands, configuration, access keys, panel
layout, launcher selection/visibility and backup history are preserved.
The installer never rewrites panels or restarts Plasma. Updated widget code can
remain cached until you voluntarily sign out and back in; you may defer this.

**Power actions may execute immediately.** New settings follow KDE; upgrades
preserve your preference. Custom power commands retain their explicit behavior
and can bypass OPM's confirmation mode. Use private mock tests for power-key and
confirmation acceptance. Do not trigger live power actions as an installer test.

## Runtime dependencies

The installer reports missing commands, shared libraries and QML/plugin failures.
It never invokes a package manager. If needed, review and run this command yourself:

```sh
@DEPENDENCIES@
```

Use your distribution's normal full-update procedure. Do not partially upgrade
Qt/KDE, force dependencies, or install foreign-distribution libraries. Installation
works offline when these dependencies are already present. Exact build/runtime
package versions are in the staging qualification evidence.

## Recovery, rollback and removal

Keep this extracted folder and the previous installer. As your normal user:

```sh
bash install.sh --recover    # Finish recovery after an interrupted transaction
bash install.sh --rollback   # Restore the preceding captured installation
bash install.sh --uninstall  # Remove OPM after removing its applet through Plasma
```

Rollback restores application/widget/activation files, not personal configuration.
Before uninstalling, remove **only OPM's applet** through Plasma so it can restore
the original launcher's visibility and relinquish its shortcut. Never remove the
original launcher as part of OPM setup. Personal configuration and snapshots stay.

Snapshots: `${XDG_DATA_HOME:-$HOME/.local/share}/open-power-menu-recovery/native-installs`.
Keep Python/PySide6 when retaining rollback to 1.0.1; OPM never removes them.
If runtime checks prevent using this wrapper, the retained matching bundle's
`native-bundle/app/bin/open-power-menu-install --recover` or `--rollback` retains
the existing native recovery path and all its safeguards.

## Acceptance and limits

Verify Configure Save/reopen, Meta+X, harmless menu items, flyouts and Escape/
outside-click dismissal. Test power keys only in the documented isolated mock
fixture. Report OS, Plasma/Qt version, X11/Wayland and the archive's SOURCE-COMMIT.
Container and virtual-desktop qualification does not certify physical hardware.
X11 translucent-panel ghosting and minor responsiveness work remain deferred.
The KDE Store widget alone does not install the native backend.
