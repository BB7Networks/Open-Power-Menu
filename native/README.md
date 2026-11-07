# Native v2.0 development preview

The native backend, recovery operations and Qt Quick/Kirigami configuration
editor are implemented. The normal installer and standalone menu still use
Python/PySide6 and remain at **1.0.1**. This preview identifies itself as
**2.0.0-dev**; it is not a complete native replacement installation.

See the [architecture and dependency inventory](../docs/architecture/0001-native-runtime.md),
[migration status](../docs/architecture/native-migration-status.md) and
[version roadmap](../docs/architecture/ROADMAP.md).

## Backend build

Development dependencies: CMake 3.21+, C++17 compiler, Ninja/Make, Qt 6.4+
Core/DBus development packages and Qt Test for tests. Debian/Ubuntu packages:
`cmake ninja-build g++ qt6-base-dev`; Manjaro equivalents:
`cmake ninja gcc qt6-base`. Ordinary future binary installations must not
require a compiler.

```bash
cmake -S . -B build/native -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/native --parallel 2
ctest --test-dir build/native --output-on-failure
dbus-run-session -- python3 native/tests/contract.py \
  --binary build/native/native/open-power-menu-native \
  --probe build/native/native/native-launch-probe
```

The differential/private D-Bus harness uses Python's standard library only;
it checks the backend-only build, including explicit failure when no editor is
installed beside it. Native model, recovery and editor-session tests need no
Python. Catalogs are embedded by CMake, with no Python build step.

## Editor build

Enable `OPM_BUILD_EDITOR` in a separate build directory. It requires Qt 6.6+
Gui, Qml, Quick and QuickControls2, KDE Frameworks 6 Service and Config, and the
Kirigami, Qt Quick Controls/Dialogs/Layouts/Window and Qml WorkerScript runtime
modules. On Debian 13, add `qt6-declarative-dev libkf6service-dev
libkf6config-dev kde-cli-tools qml6-module-org-kde-kirigami
qml6-module-qtquick-controls qml6-module-qtquick-dialogs
qml6-module-qtquick-layouts qml6-module-qtquick-window
qml6-module-qtqml-workerscript qt6-qpa-plugins` to the backend build packages.
See [the tested Docker recipe](tests/editor.Dockerfile) for exact dependencies.

```bash
cmake -S . -B build/editor -G Ninja -DCMAKE_BUILD_TYPE=Release -DOPM_BUILD_EDITOR=ON
cmake --build build/editor --parallel 2
ctest --test-dir build/editor --output-on-failure
# Use a disposable configuration while evaluating the development editor:
build/editor/native/open-power-menu-editor --config /tmp/opm-preview/menu.json
```

General/Layout/Backups share the native validation/storage model. The editor
reuses the widget's QML drag editor, retains unknown JSON metadata in C++, and
supports Undo/Redo, nested editing, explicit conflict recovery and guarded
backup preview/restore/delete. Custom commands use a program and individual
argument fields. No implicit shell parsing occurs.

KService supplies installed applications and localized names. Newly selected
applications use `kioclient6 exec` or `kioclient exec` with the desktop-file
path so KDE handles Terminal, Path, field codes and D-Bus activation. Install
that KDE helper for application selection; previously configured argv are
preserved. KConfig reads panel metadata for launcher discovery without writing
panel settings. Widget snapshot history is displayed read-only; its installer
helper has not yet been ported.

For a staged developer install:

```bash
cmake --install build/editor --prefix /tmp/opm-native-stage
/tmp/opm-native-stage/bin/open-power-menu-native --version
/tmp/opm-native-stage/bin/open-power-menu-editor --version
```

This stages the two executables. No desktop file, widget, D-Bus activation file
or existing installer is replaced. `Edit` launches the native editor beside
the backend and forwards its configuration path literally. If the executable
is absent, it returns false with a diagnostic; it never falls back to Python.

## Configuration and recovery safety

```bash
build/native/native/open-power-menu-native --check
build/native/native/open-power-menu-native --widget-menu-json
build/native/native/open-power-menu-native --config /path/to/test-menu.json --dump-config
```

The loader merges missing defaults in ordinary OPM UTF-8 JSON and preserves
unknown metadata, including signed 64-bit integers. It rejects non-UTF-8
sources, integers outside signed 64-bit range and JSON nesting beyond 256;
these cases need compatibility work before cutover. Integer settings still
reject decimal/exponent notation and booleans as in the Python model.

Reads are bounded to 4 MiB, descriptor-relative and refuse symlink traversal.
Saves use the existing cooperative lock and atomic replacement with revision
checks. Recovery also checks ownership, hard links, directory identity and
source fingerprints. A changed preview must be selected again before restore
or delete. Preview never changes the active file or executes commands.
Protected pre-restore/pre-overwrite copies survive automatic retention, even
when its limit is zero. Unsafe files cannot be restored or deleted through the
browser; corrupt/oversized regular backups can be previewed and safely deleted.

## Private-session D-Bus test

Use an isolated configuration directory. Layout methods can save configuration
and create backups; a preview bus name alone does not make them read-only.

```bash
task_config=$(mktemp -d)
XDG_CONFIG_HOME="$task_config" dbus-run-session -- bash -c '
  build/native/native/open-power-menu-native --service &
  task_backend=$!
  trap "kill $task_backend 2>/dev/null || true" EXIT
  sleep 1
  build/native/native/open-power-menu-native --call Ping
  build/native/native/open-power-menu-native --call GetMenu
'
```

Default bus name: `org.openpowermenu.NativePreview`. Object path and interface
remain `/OpenPowerMenu` and `org.openpowermenu.Service`. The explicit
`--bus-name org.openpowermenu.Service` option is for isolated widget integration
testing; it refuses an existing service owner and never stops that process.
It is not the normal installed service until UI/installer parity is complete.

Supported methods: `Ping`, `GetMenu`, `GetIntegration`, `Run`, `Edit`,
`BeginLayoutEdit`, `SaveLayoutEdit`, `CancelLayoutEdit`, `KeepLayoutEdit`.
No widget-supplied command or arbitrary file path is accepted over D-Bus.

## Runtime without Python

```bash
docker build -f native/tests/editor.Dockerfile -t opm-native-editor:test .
docker run --rm --network none opm-native-editor:test
```

This disposable Debian 13 image builds/tests both executables, then stages them
in a separate runtime containing Qt/KDE dependencies but neither Python/PySide6
nor a compiler. Its private-session smoke test opens the actual editor and
checks that opening a missing configuration does not create it. The backend
CI job also retains its smaller Core/DBus-only runtime smoke test using
`tests/runtime.Dockerfile` and `tests/runtime-smoke.sh`.

These images prove dependency boundaries on Debian 13, not universal ELF
compatibility or physical desktop acceptance. No production activation,
shortcut, Plasma restart, release package or tag is created. Never uninstall
system Python/PySide6 as part of the migration.
