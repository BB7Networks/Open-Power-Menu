# Native v2.1 development preview

The native backend, recovery operations and Qt Quick/Kirigami configuration
editor and an optional Qt Widgets standalone frontend are implemented.
The normal installer and production standalone entry point still use Python/PySide6 and remain at **1.0.1**. This preview identifies itself as
**2.1.0-dev**; it is not a complete native replacement installation.

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
Builtin editing shows the effective command and fallback order, with an option
to customize it as an independent command. Command editing can select another
installed application or browse an executable; layout reset also restores the
unavailable-entry option, with Undo preserving the previous draft.

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

## Standalone menu development build

See [the architecture comparison](../docs/architecture/0002-native-standalone.md).
Qt Widgets is optional and never linked into the backend-only target. It can
be enabled alongside the editor or independently:

```bash
cmake -S . -B build/standalone -G Ninja -DCMAKE_BUILD_TYPE=Release -DOPM_BUILD_STANDALONE=ON
cmake --build build/standalone --parallel 2
ctest --test-dir build/standalone --output-on-failure
cmake --install build/standalone --prefix /tmp/opm-standalone-stage
/tmp/opm-standalone-stage/bin/open-power-menu-standalone --config /tmp/opm-preview/menu.json --diagnose-launch
```

Build: Qt 6.4+ Core/Gui/Widgets (`qt6-base-dev`), CMake 3.21+, C++17 and Qt Test
when testing. Runtime: Qt 6 Core/Gui/Widgets shared libraries, libc/libstdc++ and
the distribution's transitive dependencies, a Qt platform plugin for the
session, fonts and the desktop icon/theme provider. Debian 13 runtime packages:
`libqt6widgets6 qt6-qpa-plugins` for X11; add `qt6-wayland` for Wayland. No QML,
Kirigami, Python, PySide6 or compiler is needed by this executable. Configured
actions still need their own applications/KDE command helpers, as in 1.0.1;
unavailable applications follow `show_unavailable`. The Qt dynamic loader names
missing shared libraries; Qt reports missing platform plugins before main can
create a menu. Install matching distro Qt runtime packages rather than copying
an ELF to an incompatible system.

Default invocation opens the menu independently of Plasma or a backend service.
`--anchor cursor|bottom-left|bottom-right`, `--theme native|aero`,
`--diagnose-launch`, `--list`, `--check`, `--default-config` and `--version` are
supported; `--config FILE` selects a disposable profile. `--list` and `--check`
print native normalized menu JSON rather than the legacy textual tree. These
read-only diagnostics (and help/version) need no display. Service/widget/editor
operations remain on their dedicated existing native executables; the native
standalone does not replace the legacy command wrapper in this milestone.

The configuration is read without writes for each process opening. Commands
resolve against the validated opening snapshot, never action data or supplied
argv. If availability changes the normalized tree before selection, execution
is refused; reopen to refresh it. Detached applications survive the menu process.
The existing power catalog retains KDE's normal confirmations. Pointer dismissal
uses the existing preference and configurable 500–5000 ms delay (1200 ms default) across all submenus;
keyboard navigation suspends it until mouse movement resumes.

Wayland uses a frameless root toplevel and a single activation request. The
compositor may refuse activation or global placement, particularly without a
launcher token. Absolute cursor/anchor placement and knowledge of the global
pointer are not guaranteed by Wayland. Qt handles child popup placement and
adaptive direction. X11 uses native QMenu popup handling. The initial minimum
width is 292 logical pixels; long menus scroll using Qt's menu scrollers.

```bash
# Dedicated minimal-runtime acceptance, including missing-library diagnostics:
docker build -f native/tests/standalone.Dockerfile -t opm-standalone:test .
docker run --rm --network none opm-standalone:test
# Interaction on private virtual displays (test tooling only):
dbus-run-session -- xvfb-run -a env QT_QPA_PLATFORM=xcb build/standalone/native/native-standalone-tests
dbus-run-session -- sh native/tests/standalone-wayland.sh build/standalone/native/native-standalone-tests
```

Both staging and these recipes leave production binaries, activation, shortcuts,
widget and the 1.0.1 EZ installer unchanged. Physical Plasma, mixed fractional-DPI
monitors, work-area/panel variations and launcher activation remain release gates.

## Complete native installation and upgrades

Build `OPM_BUILD_PACKAGE=ON` and the `native-package` target for the full native
bundle, CPU/distribution-labelled archive, checksum and Store-only widget.
This option requires the backend, editor and standalone together. The prebuilt
native installer and dispatcher handle user-local integration and reversible
upgrades without Python or a compiler. The 1.0.1 release installer is retained.

See [package installation and exact runtime dependencies](packaging/README.md),
[transaction architecture](../docs/architecture/0003-native-packaging.md), and
[Store requirements](../docs/KDE-STORE.md). Debian 13 amd64 is the tested native
bundle baseline. Other distributions/architectures require matching builds and
acceptance; a Debian binary is not a Manjaro package. Physical Plasma acceptance
remains mandatory before publishing or changing the normal released download.

## Stabilized selection and activation contract

Native 2.1 menu keys are opaque, expiring presentation identities. Clients must
use the key returned by `GetMenu`, not construct positional paths. The widget
uses `StartRun`/`RunResult` for request-specific asynchronous power completion;
legacy `Run` returns its final boolean through a delayed reply. See the
[runtime stabilization contract and tests](../docs/OPM-2.1-RUNTIME-STABILIZATION.md).
