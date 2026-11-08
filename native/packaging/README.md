# Complete native development bundle

This is a development installation, not a published 2.1 release. Back up your
personal configuration and complete the physical Plasma release gates first.
Never run the installer as root. It does not install system dependencies.

Build with CMake 3.22+ on the target distribution (Debian 13 amd64 is the tested baseline):

    cmake -S . -B build/package -G Ninja -DCMAKE_BUILD_TYPE=Release -DOPM_BUILD_PACKAGE=ON
    cmake --build build/package --target native-package --parallel 2

The bundle includes all three native applications, native CLI/installer,
Plasma 6 widget, icon and documentation. Desktop and D-Bus entries are generated
with the installed absolute paths. `cmake --install` remains developer staging;
use the transactional installer to integrate a complete user-local application.

The native-package target also creates a distribution/CPU-labelled tar.gz,
SHA-256 checksum and a separate widget-only .plasmoid archive in the build folder.
After installing the distro runtime dependencies, extract the matching bundle
and run `sh native-bundle/install.sh` from your desktop user session. The small
bootstrap checks OS/version/CPU before executing the native installer. The direct
native command is also available:

    /absolute/path/native-bundle/app/bin/open-power-menu-install --install /absolute/path/native-bundle

Use temporary XDG_DATA_HOME, XDG_CONFIG_HOME, XDG_CACHE_HOME and XDG_BIN_HOME plus
`dbus-run-session` for development acceptance. Never point development tests at
your live desktop profile. Paths must be clean absolute paths, owned by the
user, with no symlink traversal or group/world writable components. HOME spaces
are supported. Relative XDG paths and mismatching OS/version/CPU are refused.

    open-power-menu --check
    open-power-menu --edit
    open-power-menu --diagnose-launch
    open-power-menu --rollback
    open-power-menu --recover
    open-power-menu --uninstall

The last three commands can also be passed directly to the bundle's installer.
That copy remains usable after uninstall or rollback to legacy. Remove the OPM
applet through Plasma before uninstall; its existing destruction handler restores
launcher visibility and relinquishes its shortcut. The installer never rewrites
panels, launcher selections, global shortcuts, menu.json or configuration backups.
The dispatcher retains standalone options, --edit, --service,
--widget-menu-json and --show-launcher-button. Legacy --launcher-diagnostics and
--restart-owned-service are not dispatcher operations: launcher discovery is in
native Configure, and the installer owns verified service switching.

Installation snapshots are retained under
XDG_DATA_HOME/open-power-menu-recovery/native-installs. Interrupted transactions
are recovered before another operation. --rollback restores the previous full
component set, including legacy application and widget files. Restoring 1.0.1
also restores its Python-based activation and therefore needs its original
runtime; the native installer never installs or removes Python. Legacy embedded
widget-backups remain in the complete old-app snapshot. External widget history
and all personal configuration/recovery data remain at their existing paths.
No automatic history pruning occurs. Review snapshots before deleting them.

Runtime on Debian 13 amd64: libqt6core6t64, libqt6dbus6, libqt6gui6,
libqt6widgets6, libqt6qml6, libqt6quick6, libqt6quickcontrols2-6,
libkf6service6, libkf6configcore6, kde-cli-tools, dbus, qt6-qpa-plugins,
qt6-wayland, qml6-module-org-kde-kirigami, qml6-module-qtquick-controls,
qml6-module-qtquick-dialogs, qml6-module-qtquick-layouts,
qml6-module-qtquick-window, qml6-module-qtqml-workerscript, and their distro
library/font dependencies. Plasma 6 and its QML/KPackage modules are required
for the widget. The bundle uses system styles/icons/platform plugins.
Qt >=6.6 and KF6 Service/Config are required for a complete source build;
Debian artifacts use Qt 6.8.2, KF6 6.13, glibc 2.41 and x86-64. Other distributions
and CPU architectures require matching builds and qualification. No Python,
PySide6, compiler or QML executable engine is required for installation/removal.
A kernel supporting pidfds (Linux 5.3+) is needed to retire a running service.

The Store widget requires the native backend separately. It does not download or
run an installer. See docs/KDE-STORE.md and docs/TESTING.md in the source repository.


## 2.1 optional cleanup and rolling distributions

After a verified legacy upgrade, the optional PySide6 notice defaults to **Keep**.
`open-power-menu --review-dependencies` performs read-only package discovery;
`--dismiss-dependency-review` suppresses reminders. No removal command is run.
See [cleanup guidance](../../docs/DEPENDENCY-CLEANUP.md), including restoring the
old runtime before legacy rollback.

For Arch/Manjaro, use the target distribution's own Qt/KDE packages and build on
that distribution. `PKGBUILD` stages a native bundle and explicit setup launcher,
with no install hooks that change Plasma. Create a reviewed local source archive
with `git archive --prefix=Open-Power-Menu/ -o open-power-menu-source.tar.gz HEAD`,
place it beside PKGBUILD, and run makepkg in a disposable target-system builder.
Pin the source checksum before release. Arch CI does not qualify Manjaro or physical
Plasma. Keep distribution/version/CPU, hash, ELF, plugin and activation checks intact.
