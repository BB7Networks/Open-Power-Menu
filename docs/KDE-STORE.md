# KDE Store and complete native distribution

OPM 2.0 development has two distinct distribution paths. The released 1.0.1
installer remains available; no native package or Store listing has been
published by this milestone.

| Artifact | Contents | Requirements |
| --- | --- | --- |
| Complete native bundle | Plasma 6 widget, backend, editor, standalone, native CLI/transaction utility, activation/desktop integration and icon/docs | Matching distribution/CPU and documented Qt/KF6 runtime; Plasma 6 for widget use |
| `.plasmoid` Store artifact | QML/JavaScript widget and metadata only | Separately installed native backend for configured menus, commands, editing and recovery |

The Store artifact is **not self-contained**. Adding it never downloads or runs
an installer, executes shell commands, or installs system packages. If GetMenu
fails, the popup displays a native-backend setup message, a fixed link to
installation instructions and **Retry connection**. Retry repeats the existing
D-Bus menu/integration reads. It also explains that an already installed backend
may have missing dependencies or session activation problems. A successful retry
restores the normal menu; invalid configuration retains its existing recovery UI.

Use the full native package for the complete experience. Its explicit installer
checks host compatibility, package integrity, libraries/platform plugins, editor
QML and a private service before replacing components. Production-name activation
must pass before commit. See [native installation](../native/packaging/README.md)
and [transaction architecture](architecture/0003-native-packaging.md).

Build both artifacts without publishing them:

```sh
cmake -S . -B build/package -G Ninja -DCMAKE_BUILD_TYPE=Release -DOPM_BUILD_PACKAGE=ON
cmake --build build/package --target native-package --parallel 2
```

This creates a labelled native tar.gz and checksum, plus
`org.openpowermenu.start-2.0.0-dev.plasmoid` with `metadata.json` and `contents/`
at the ZIP root. The legacy `scripts/build-release.sh` and widget helper remain
1.0.1 release tooling; use the native CMake target for native development bundles.

## Backend-free basic mode investigation

BackendSetup.qml is a working isolated QML component that loads and emits Retry
without a backend. The existing selected-launcher activation could support a
limited launcher-only widget. It cannot provide user-configured system/power
commands or recovery by itself. Implementing those in QML would duplicate the
native configuration/availability model or require a new trusted executor.
No executable-engine dependency, duplicate catalog, auto-install mechanism or
reduced command mode is enabled in 2.0. A broader self-contained Store mode needs
a separate architecture decision and is deferred.

## Publication gate

Before publishing, qualify physical Plasma 6 Wayland and X11 sessions with the
full native package and a Store-only account. Verify offline/missing-backend
setup, retry after manual installation, launcher/Meta+X handoff, native editor,
backups, themes, focus, mixed-DPI monitors and removal/undo behavior. Store text
must name the separately installed native package and supported distribution
baselines. Upload the `.plasmoid` to a Plasma 6 category, never the complete EZ
archive as though it were a self-contained widget. Screenshots must show real
behavior. GitHub remains the source/release location; KDE Store is a separately
reviewed listing. Publishing either requires explicit release approval.
