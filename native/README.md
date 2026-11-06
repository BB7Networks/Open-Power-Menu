# Native backend development preview

This is the first v2.0 migration milestone, based on released 1.0.1. It is a
working native backend, **not a replacement installation of the complete app**.
The normal installer and its Python/PySide6 editor and standalone menu remain
available. Native Configure, standalone UI and full recovery-browser operations
are not implemented yet; `Edit` explicitly returns false.

See the [architecture decision and dependency inventory](../docs/architecture/0001-native-runtime.md)
and [migration status](../docs/architecture/native-migration-status.md).

## Build from source

Development dependencies: CMake 3.21+, C++17 compiler, Ninja/Make, Qt 6.4+
Core/DBus development packages, and Qt Test for tests. On Debian/Ubuntu these
come from `cmake`, `ninja-build`, `g++` and `qt6-base-dev`. Manjaro provides
`cmake`, `ninja`, `gcc` and `qt6-base`. This is a developer source-build path;
future ordinary binary installations must not require compilers.

```bash
cmake -S . -B build/native -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/native --parallel 2
ctest --test-dir build/native --output-on-failure
dbus-run-session -- python3 native/tests/contract.py \
  --binary build/native/native/open-power-menu-native \
  --probe build/native/native/native-launch-probe
```

Python is used only for the differential test harness above. The compiled
backend embeds the shared catalogs and neither links nor invokes Python.
Its runtime libraries are Qt Core/DBus, libc and the C++ runtime; configured
applications and optional capability tools remain external commands.

For a staged developer install:

```bash
cmake --install build/native --prefix /tmp/opm-native-stage
/tmp/opm-native-stage/bin/open-power-menu-native --version
```

Only `bin/open-power-menu-native` is installed. No desktop file, widget,
D-Bus activation file or existing installer is replaced.

## Read-only comparison

```bash
build/native/native/open-power-menu-native --check
build/native/native/open-power-menu-native --widget-menu-json
build/native/native/open-power-menu-native --config /path/to/test-menu.json --dump-config
```

The native loader accepts the normal UTF-8 configurations produced by OPM,
merges missing defaults, and preserves unknown metadata within Qt's JSON
representation. It rejects integers outside signed 64-bit range and nesting
over 256 levels instead of silently rounding or recursing without a bound.
Non-UTF-8 hand-authored configurations need compatibility work before cutover.
The legacy implementation remains available for those cases. Integer settings
still reject decimal/exponent notation and booleans as in the Python model.

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
It is not the normal installed service until UI parity is complete.

Supported methods: `Ping`, `GetMenu`, `GetIntegration`, `Run`, `BeginLayoutEdit`,
`SaveLayoutEdit`, `CancelLayoutEdit` and `KeepLayoutEdit`. `Edit` fails explicitly
while the native configuration frontend is pending. No widget-supplied command
or arbitrary file path is accepted over D-Bus.

## Runtime without Python

`tests/runtime.Dockerfile` is a disposable Debian 13 smoke image containing Qt
Core/DBus and D-Bus tools, with neither Python/PySide6 nor a compiler. Build the
binary on Debian 13, put it beside that Dockerfile as `open-power-menu-native`,
then build/run the image. This proves the backend's dependency boundary; it
does not prove native GUI parity or distribution compatibility for that ELF.
Use the environment's configured proxy and CA trust for networked image builds.

Mount `native/tests/runtime-smoke.sh` in that image and run it with `sh`; it
checks Python's absence, validates a missing configuration using defaults, and
starts/calls the native service on a private D-Bus session. It uses a temporary
configuration directory and never connects to the desktop session bus.

No v2.0 release package, tag, global shortcut or Plasma restart is created by
these development commands. Do not uninstall PySide6 from a user's system.
