# Native packaging and transaction architecture

The complete package is an explicitly built, distribution/architecture-specific
bundle. `OPM_BUILD_PACKAGE=ON` requires all three GUI/service targets plus a
Core/DBus installer and a native compatibility dispatcher. Ordinary install and
removal use these prebuilt executables, never Python, a compiler, pip or a shell
download. The existing 1.0.1 EZ installer/release builder remains available.

Start with Debian 13 amd64 (Qt 6.8, KF6 6.13, glibc 2.41). Bundles record their
build OS/version/CPU and file hashes, and refuse a mismatching host. Manjaro/Arch
and other distributions need builds on their own supported baselines and their
own qualification. A Debian ELF is not a portable Linux package. Libraries,
QML modules and platform plugins come from the target distribution. Source
builders use the same bundle target and installer on their target system.

Install fixed OPM-owned paths under XDG_DATA_HOME and XDG_BIN_HOME. The native
launcher preserves the public `open-power-menu` entry point. The application,
widget, service, desktop files and icon are replaceable components. Configuration,
backup history, panel metadata and shortcuts are never installation payloads.
Snapshots live under open-power-menu-recovery/native-installs, outside the app.
Legacy widget-backups inside the old app are retained in the complete old-app
snapshot; external widget-backups and configuration history are never pruned.

The installer pins directories with no-follow file descriptors, rejects unsafe
ownership/modes, symlinks, special files and hard links, and holds a transaction
lock. Before changing anything, it verifies package hashes, host ABI, all runtime
entry points, editor QML loading and a private native D-Bus service. Existing
files must be an identifiable 1.0.1 installation or match the last native receipt.

Every transaction keeps durable old-component snapshots and hashes. Incoming
components are staged beside their destinations. A durable journal precedes
renames; each rename is atomic, with recoverable gaps between renames.
Recovery restores the full previous set and refuses unexpectedly modified files.
Committed snapshots remain available for explicit rollback. No automatic pruning
of install history is performed in this milestone.

A production session bus is required for activation acceptance. An existing
owner must be this user's installed OPM executable or the identified legacy
run.py service. Linux pidfds bind retirement to that process, never a broad kill
or Plasma restart. The service file is reloaded, activation and Ping/GetMenu/
GetIntegration checked, and only then is the transaction committed. Failure
restores old components/activation. An interrupted transaction is recovered before
another install. Rollback to Python 1.0.1 can require that installation's original
runtime; the native installer itself never invokes Python.

Uninstall preserves personal data/history and refuses removal while a saved
panel still contains the OPM applet: remove that applet in Plasma first so its
existing launcher-mask restoration runs. It never edits panel/shortcut files.

The Store artifact remains a QML-only widget requiring the separately installed
native backend. Missing-backend UI provides installation documentation and Retry,
without downloads or executable-engine commands. A backend-free basic widget is
a separate deferred design, not a second configuration or command engine.

## Backend-free Store proof of concept

A pure QML welcome/retry/documentation surface is implemented as BackendSetup.qml
and can load without the service. A basic launcher-only mode could emit the
existing selected applet activation and expose a fixed help action without
executing commands. It cannot reproduce configured power/system actions or
recovery without a trusted model/executor. Embedding a second catalog, shell
engine or silently installing a native plugin would break the safety boundary.
That limited launcher-only mode is therefore not enabled in 2.0; the isolated
setup component is the proof of concept for backend-free rendering. Full Store
functionality explicitly requires the native package.
