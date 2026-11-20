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
follow KDE confirmation settings. Configure offers Follow KDE system settings,
Always show confirmation and Execute immediately; existing preferences are migrated. Explicit custom commands keep
their behavior and can bypass confirmation. Test power selections only against
private mock services, never by invoking real operations during automated tests.

## Downloads and verification

Choose the EZ ZIP matching your distribution, verify its external `.sha256`,
extract it, run `bash install.sh --check`, then `bash install.sh` as your normal
Plasma user, without sudo. The Manjaro
pacman package and three native bundles are alternative installation formats.
`SOURCE-COMMIT`, the source archive, `RELEASE-MANIFEST.json`, `QUALIFICATION.json`
and `SHA256SUMS` identify and verify the exact source and qualified artifacts.

A version number alone does not certify a runtime. Dependency floors and OS
constraints are checked before installation. Use the recorded build/runtime
inventories; other distributions, older runtimes and ARM are not qualified.
Software-rendered isolated X11/Wayland tests do not establish workstation GPU,
compositor, global-shortcut or panel acceptance.

## Physical acceptance scope

The owner reported successful Manjaro EZ installation and normal-use menu and
Configure behavior during installer preparation. This establishes neither real
power-action behavior nor physical held-key safety, and is not an attestation
that every later source commit was installed on that workstation. All automated
power operations target private mock services. Do not exercise real shutdown,
restart, sign-out, suspend or hibernate as an acceptance shortcut.

The supplied source commit, runtime package inventories and same-run qualification
records identify exactly what was built and tested. A passing virtual fixture is
not physical workstation certification.

## Known issues and recovery

X11 translucent-panel text ghosting and minor responsiveness remain deferred.
An intermittent private X11 focus-readiness timeout during earlier qualification
remains unconfirmed as a production defect. Historical v1.0.1, RC1 and RC2 remain
available; existing recovery snapshots are retained.

A separate Kubuntu X11 hidden-launcher held-key stress test intermittently timed
out waiting for a mock action after deliberate release/repress. The retained
[failure log](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/44805592504)
does not establish the cause. Later runs passed with unchanged production/test
sources; the timeout remains unresolved and is not claimed fixed.

Keep the extracted installer for `bash install.sh --rollback`, `--recover` and
`--uninstall`. Removing the package alone does not remove a per-user activation.
Before uninstalling, remove the OPM widget through Plasma and retain the original
launcher. Do not remove unrelated dependencies or user configuration.
