# Complete native development bundle

This is a development installation, not a published 2.1 release. Back up your
personal configuration and complete the physical Plasma release gates first.
Never run the installer as root. It does not install system dependencies.

GUI interaction tests use `xvfb-run` and `xauth` in the disposable build image.
Without that virtual input display, the offscreen fallback explicitly skips the
file-dialog input case; it cannot qualify that workflow. These are test tools,
not native runtime dependencies.

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

When an install, native update or rollback changes the widget files, the installer
prints an activation notice and sends a best-effort passive desktop notification.
Plasma can keep its previous QML in memory even though the backend and files have
updated. Sign out and back in when convenient to load the installed interface;
you may defer. The installer never restarts Plasma or logs you out. It does not
claim that `reloadConfig()` reloads widget code. No widget recreation, panel edits
or session commands are used. An identical widget reinstall needs no notice.

The native service retains the released `Run` contract for an older loaded
frontend. This frontend probes for the request-specific API before dispatch and
can use released `Run` after rollback. No uncertain invocation is retried. A
frontend already cached from the earlier `88db27b` checkpoint cannot acquire
this fallback in memory: after rollback to 1.0.1 it needs logout/login before
commands work. The installer explains this transition limitation. Keep the legacy
Python/PySide6 runtime available for that rollback, as before.

Ordinary settings Save needs no session or backend restart. An active 2.1 widget
refreshes preferences on opening and every five seconds. This includes Auto-fit,
Custom height, density, icons and hints; installing new QML is a different step.

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
for the widget. The bundle uses system styles/icons/platform plugins. SVG-based icon themes such as
Breeze also need the system Qt SVG image/icon plugins (Debian: `qt6-svg-plugins`),
normally supplied by the desktop. PNG-only minimal runtime smoke does not qualify
SVG artwork; the separate visual matrix uses the actual Breeze SVG assets.
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
with no install hooks that change Plasma. From a clean, committed source checkout:

    sh native/packaging/prepare-pacman.sh . work/pacman-source
    cd work/pacman-source
    makepkg

Run makepkg as an ordinary user in a disposable builder for the target distribution,
with the build dependencies installed. The preparation helper refuses tracked edits
or an existing output directory. It archives the exact commit, pins the source SHA-256
in PKGBUILD and records SOURCE-COMMIT and SOURCE.sha256. Untracked files are excluded.
The package disables post-sealing strip/debug transformations so the installed
executables still match their bundle hash inventory. Test fault hooks are compiled out.

Install the matching development package through pacman in a disposable test system,
then explicitly run `open-power-menu-native-setup` from the ordinary desktop user
session. Installing the pacman package alone does not integrate or restart Plasma. This also applies to package updates: run the setup command again to update the
per-user editor and backend. If `open-power-menu --edit` still shows the old
interface, record `type -a open-power-menu` and the resolved executable before
changing anything. The Basic style changes rendering, not which installation
is launched.

[Pacman package CI](../tests/pacman.Dockerfile) builds Arch and Manjaro separately,
tests released 1.0.1 upgrades, and installs each sealed package into a separate runtime
image. Arch and Debian runtime checks require Python to be absent. Manjaro retains
the base image's Python used by pacman-mirrors, while requiring PySide6 to be absent;
all three require no compiler for native installation and operation. This preserves
unrelated system dependencies and does not make Python an OPM runtime dependency.

CI retains development packages, bundles, the separate Store widget, checksums,
source commit, os-release and build/runtime package inventories for seven days.
These are development artifacts, not public releases or physical Plasma certification.
See [qualification results](../../docs/OPM-2.1-RESULTS.md) for the tested snapshots.
Keep distribution/version/CPU, hash, ELF, plugin and activation checks intact.
Platform validation uses the plugins' advertised xcb/wayland capabilities and still
loads them to check Qt compatibility; it does not depend on a particular filename.
