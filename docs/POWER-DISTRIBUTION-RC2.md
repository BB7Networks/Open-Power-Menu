# RC2 power and distribution compatibility

Base: published RC1, `2384a9d03947b9a2e5de8f0ef72ae57e556bc29c`. This work preserves the physically verified X11 Qt.Tool/WM_TRANSIENT_FOR correction, Meta+X ordering, native input guard, session environment resolution and protected action identities. No workstation files or running Plasma session are changed by development tests.

## Confirmed cause of the workstation report

The running backend reported RC1 and `confirm_power_actions:true`; the saved checkbox remained enabled. The installed KDE service was the stock `/usr/lib/ksmserver-logout-greeter`, and all 6,786 plasma-workspace files passed the user's package integrity check. Saved menu inspection then identified custom rows with no `action` field:

| Custom row | Explicit command method on `org.kde.Shutdown /Shutdown` |
| --- | --- |
| Sign Out... | `org.kde.Shutdown.logout` |
| Restart... | `org.kde.Shutdown.logoutAndReboot` |
| Shut down... | `org.kde.Shutdown.logoutAndShutdown` |

Those methods explicitly skip the greeter. Custom labels and ellipses do not select native power behavior. RC1's confirmation preference applies to built-in `action: shutdown/reboot/logout` entries. The report was therefore not reproduced as a native default-dispatch defect. RC1 showed its actual KDE greeter in the isolated Debian, Manjaro and Arch fixtures. Per the user's instruction, custom commands are left alone: there is no conversion UI or implicit migration of them.

The fixture uses a private D-Bus configuration with no standard activation directories. Only the real LogoutPrompt greeter and a harmless Shutdown recorder are activatable; logind and PowerManagement are private recorders on both bus addresses. KDE 6.7 refuses a greeter when Shutdown already owns its name, so confirmed cases run before the immediate mock requests. This fixture ordering does not change production behavior.

## Three-mode implementation

`power_confirmation` is authoritative. `system` uses a fresh KConfig object for `ksmserverrc`, group General, key confirmLogout, default true, matching KDE SessionBackend. It includes layered and immutable settings. The backend never writes KDE preferences or implements a countdown. `always` and `immediate` select the existing exact KDE methods. Permission checks, native sleep/hibernate inhibitor handling, asynchronous results, one-use identities and uncertain-completion refusal remain in place.

Captured session actions contain mode plus effective confirmation. Selection and the final permission-check continuation re-evaluate it; a changed choice fails closed. Changing KDE settings while the backend runs is tested. Enum validation, old-Boolean migration, missing-field behavior, Save/reopen, import/export, backups, custom metadata and rollback shadows are covered. See the release notes for the migration table and RC1 rollback semantics.

Default-off `OPM_SESSION_TRACE=1` adds timestamped `OPM_POWER_TRACE` records at menu capture, service selection and final dispatcher request/reply. Records name the caller stage and resolved route. They do not activate windows, focus the greeter or invoke an extra action. `GetPowerDiagnostics` is read-only: configuration path, backend version/PID/executable, resolved mode and routes, and current service owners obtained from the bus daemon. It does not start power services. A single-line read-only command is:

```sh
qdbus6 org.openpowermenu.Service /OpenPowerMenu org.openpowermenu.Service.GetPowerDiagnostics
```

## Complete action audit

Explicit custom commands retain their original argument arrays. Preferred applications are considered only for built-in actions. KService entries must be valid applications, visible in the current desktop, present, not Hidden/NoDisplay, and pass TryExec/executable checks. KDE's `kioclient exec` handles desktop launch semantics (field codes, working directory, Terminal and activation); OPM does not reconstruct them as shell commands. Missing registered entries cannot bypass a user Hidden override through the same executable fallback.

| Action | Resolution and unavailable behavior |
| --- | --- |
| Installed Applications | Recognized appstream handler; Pamac priority on Manjaro, Discover in KDE; registered GNOME Software, Octopi and Ubuntu App Center/Snap Store alternatives; installed executable fallback |
| File Manager | Default `inode/directory` handler; Dolphin, Nautilus, Thunar, Nemo, PCManFM-Qt fallbacks |
| Terminal | Read-only `xdg-terminal-exec --print-id` validation, including desktop actions; KDE TerminalService/TerminalApplication; Konsole, Kitty, Alacritty, GNOME Terminal, Xfce Terminal, XTerm |
| Settings | Valid System Settings desktop entry/executable; GNOME/Xfce control centers only in their own desktop context |
| Power Options | Installed `kcm_powerdevilprofilesconfig`; GNOME power panel only in GNOME; no generic Settings substitute |
| Network Connections | Installed `kcm_networkmanagement`; NetworkManager connection editor fallback |
| Printers | Installed `kcm_printer_manager`; system-config-printer fallback |
| System Monitor | KDE Plasma System Monitor, GNOME System Monitor, KSysGuard, Xfce task manager |
| Disk Management | KDE Partition Manager, GNOME Disks, GParted; none installed means unavailable |
| Virtual Machines | virt-manager or VirtualBox; none means unavailable |
| Remote Desktop | Recognized default RDP handler; KDE KRDC or Remmina |
| System Logs | KSystemLog; Konsole/XTerm with journalctl only when journalctl exists |
| System | KInfoCenter, Hardinfo2, GNOME info panel only in GNOME |
| Hardware | KInfoCenter in KDE; terminal inxi requires inxi; Hardinfo2 fallback |
| Network Locations | Existing explicit Dolphin directory target preserved |
| Search / Run | KDE KRunner with a registered/activatable service or installed executable; Rofi fallback |
| Desktop | Existing KGlobalAccel Show Desktop capability check preserved |
| Lock | Existing loginctl lock request preserved; private keyboard fixture intercepts it |
| Sleep / Hibernate | Existing native PowerDevil capabilities/inhibition and logind WithFlags policy checks preserved |
| Shutdown / Restart / Sign out | Native KDE LogoutPrompt or Shutdown methods according to the resolved mode; never shell fallback |

Desktop preference, explicit commands, each software-manager candidate, multiple candidates, missing executables, invalid/hidden desktop entries, default terminal actions, RDP preference and module absence are tested in private XDG trees. Each real distro image also records all ordinary-action resolutions and requires its installed primary KDE tools/modules to resolve. Optional missing applications remain unavailable; production never installs software.

## Qualification and delivery

Ten CI jobs cover Debian 13, Kubuntu 26.04 (Ubuntu base plus Plasma 6 packages), current Manjaro and the existing Arch snapshot, independent runtimes, installer transactions, portable/Qt tests and standalone X11/Wayland behavior. Manjaro/Arch and Debian/Kubuntu each retain all four held-key seats. Real native greeter tests cover 18 mode/preference/action combinations plus one stock countdown, canceled cases producing no final request. Visual greeter coverage is X11; Wayland uses private compositor keyboard/standalone fixtures and needs physical acceptance.

The publication job consumes evidence from the same exact commit/run, requires each distro's application and keyboard matrix, verifies the real greeter matrix and native test reports, verifies source archive equality and sealed package/bundle equality, then checks uploaded SHA-256 digests. `QUALIFICATION.json` is the machine-readable source of the final passing run and runtime inventories. The published package/bundle are Manjaro-specific; Debian/Kubuntu get independently tested local source-build/bundle instructions, not relabeled Manjaro binaries.

Local development initially exposed an inconsistent incremental build after reverting temporary editor code; the old destructor accessed offsets beyond the current class size. A clean Release build passed all 13 native suites, and a fresh ASan/UBSan interaction build passed all 33 cases. No production workaround was added. A dependency-fixture failure came from the lab's umask 0000; normal umask 022 preserves the required ownership/permission guard. Qualification uses fresh builds, not those stale binaries.

The deferred X11 taskbar ghosting and minor responsiveness issues are unchanged. Physical acceptance and rollback instructions are in the RC2 release notes and the private mock procedure in `HELD-KEY-STABILIZATION.md`.

## Changed-file inventory

37 files differ from RC1:

- `.dockerignore`
- `.github/workflows/publish-native-release.yml`
- `.github/workflows/tests.yml`
- `README.md`
- `RELEASE-NOTES-v2.1.0-rc2.md`
- `docs/OPM-2.1.md`
- `docs/POWER-DISTRIBUTION-RC2.md`
- `docs/POWER-KEYBOARD.md`
- `native/CMakeLists.txt`
- `native/README.md`
- `native/VERSION`
- `native/applications.cpp`
- `native/applications.hpp`
- `native/editor_catalog.cpp`
- `native/editor_session.cpp`
- `native/model.cpp`
- `native/model.hpp`
- `native/packaging/PKGBUILD`
- `native/packaging/README.md`
- `native/packaging/bundle.cmake.in`
- `native/power.cpp`
- `native/power.hpp`
- `native/qml/Main.qml`
- `native/service.cpp`
- `native/service.hpp`
- `native/tests/application_probe.cpp`
- `native/tests/application_resolution.py`
- `native/tests/editor.Dockerfile`
- `native/tests/editor_gui_test.cpp`
- `native/tests/packaging.Dockerfile`
- `native/tests/packaging.py`
- `native/tests/pacman.Dockerfile`
- `native/tests/plasma_greeter.py`
- `native/tests/session_power_test.cpp`
- `openpowermenu/data/actions.json`
- `scripts/prepare-native-release.py`
- `tests/test_native_release.py`
