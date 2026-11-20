# Open Power Menu 2.1.0

Open Power Menu 2.1 brings the native C++/Qt backend, Configure editor and
standalone menu together with the Plasma 6 widget. Distribution-specific EZ
installers include the actual native runtime and transactional installation,
upgrade, recovery and rollback support for qualified Manjaro, Debian 13 and
Kubuntu 26.04 x86-64 systems.

The release includes X11 popup and Meta+X reopening corrections, physical-key
protection across root and flyout windows, configurable Win+X-style access keys,
native KDE power dispatch, and persistent Configure/session environment handling.
The Power Actions dropdown fits its choices. Existing menu configurations,
shortcuts and panel layouts are preserved.

## Power behavior

**Shutdown, Restart and Sign out may execute immediately.** New installations
follow KDE confirmation settings. Configure offers KDE Settings, Always Confirm
and Immediate; existing preferences are migrated. Explicit custom commands keep
their behavior and can bypass confirmation. Test power selections only against
private mock services, never by invoking real operations during automated tests.

## Downloads and verification

Choose the EZ ZIP matching your distribution, verify its external `.sha256`,
extract it and run `bash install.sh` as your normal Plasma user. The Manjaro
pacman package and three native bundles are alternative installation formats.
`SOURCE-COMMIT`, the source archive, `RELEASE-MANIFEST.json`, `QUALIFICATION.json`
and `SHA256SUMS` identify and verify the exact source and qualified artifacts.

A version number alone does not certify a runtime. Dependency floors and OS
constraints are checked before installation. Use the recorded build/runtime
inventories; other distributions, older runtimes and ARM are not qualified.
Software-rendered isolated X11/Wayland tests do not establish workstation GPU,
compositor, global-shortcut or panel acceptance.

## Known issues and recovery

X11 translucent-panel text ghosting and minor responsiveness remain deferred.
An intermittent private X11 focus-readiness timeout during earlier qualification
remains unconfirmed as a production defect. Historical v1.0.1, RC1 and RC2 remain
available; existing recovery snapshots are retained.

Keep the extracted installer for `bash install.sh --rollback`, `--recover` and
`--uninstall`. Removing the package alone does not remove a per-user activation.
Before uninstalling, remove the OPM widget through Plasma and retain the original
launcher. Do not remove unrelated dependencies or user configuration.
