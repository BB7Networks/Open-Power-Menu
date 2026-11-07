# Native recovery/editor milestone: performance observations

These are development measurements, not v2.0 release acceptance or a promise
about desktop menu-opening speed. The backend improved in this run. The native
editor's proportional memory use increased; that tradeoff remains visible
below. Standalone and complete installation measurements await their ports.

## Revisions and environment

- Released baseline: `34058480b6e3bc1ecc1f19d420fb744f570eca34` (1.0.1),
  exported unchanged with `git archive`.
- Native implementation: `37b3e45d9f376aac7defc0cd75f48c383be233bf`
  (2.0.0-dev), CMake Release, GCC 14.2, Debian 13 x86-64.
  These measurements precede the final command-picker/layout-reset parity
  follow-up; they are retained with the exact measured source and binary hashes.
- Same fresh disposable container for both implementations: Qt 6.8.2,
  KDE Frameworks 6.13, Python/PySide6 3.13.5/6.8.2.1 for the baseline and test
  client; Linux 6.18.57, glibc 2.41, shared cloud CPU, software rendering.
- The virtual desktop test container and builds were stopped/finished first.
  Each backend/editor ran sequentially on a private D-Bus session and temporary
  XDG profile. No application or power action was executed.
- [Raw results and binary SHA-256 hashes](measurements/native-editor-milestone.json).
  [Reproduction script](../../native/tests/benchmark.py).

## Method

Each configuration uses 25 fresh `--widget-menu-json` processes per backend,
then one service startup observed by polling `Ping`, five untimed `GetMenu`
warmups and 200 timed D-Bus round trips. The same PySide6 client measures both
services. Availability probes use harmless fixture executables. Configurations
are the released defaults and a custom menu with two submenus of 100 commands
each, including spaces in arguments and unknown metadata.

Filesystem caches are warm. Fresh process startup is **not cold boot/startup**;
GetMenu latency includes reading/validation/normalization/IPC but excludes popup
rendering and activation. Service-ready and memory numbers are single
observations, not distributions. RSS/PSS come from `/proc/PID/smaps_rollup`;
editor memory is sampled two seconds after opening the General page. Results
are sensitive to scheduling, filesystem cache and shared library residency.

| Configuration / operation | 1.0.1 median / p95 | Native median / p95 |
| --- | --- | --- |
| Defaults, fresh CLI process (25 samples) | 73.988 / 138.611 ms | 9.403 / 15.765 ms |
| Custom 200 commands, fresh CLI process (25) | 90.326 / 142.130 ms | 10.455 / 20.178 ms |
| Defaults, warm GetMenu round trip (200) | 1.997 / 2.992 ms | 0.786 / 1.168 ms |
| Custom 200 commands, warm GetMenu (200) | 13.739 / 23.102 ms | 5.049 / 6.885 ms |

Service readiness was 254.078 versus 15.415 ms with defaults, and 165.316
versus 13.361 ms with the custom menu. Polling resolution and first library
loads affect these single observations; use the sampled CLI results for a
more useful startup comparison.

## Memory and the editor regression

Values below are MiB (KiB in the raw report), rounded to two decimals. RSS
counts resident pages; PSS apportions pages shared with other processes.
Neither is total desktop memory consumption.

| Configuration / process | 1.0.1 RSS / PSS | Native RSS / PSS |
| --- | --- | --- |
| Defaults, idle backend | 40.10 / 27.48 | 14.93 / 8.25 |
| Custom 200, idle backend | 40.63 / 27.70 | 15.27 / 8.50 |
| Defaults, editor | 76.30 / 63.69 | 79.46 / 71.57 |
| Custom 200, editor | 78.43 / 66.07 | 78.15 / 70.39 |

The native editor uses about **7.88 MiB more PSS** with defaults and **4.32 MiB
more** with the custom menu in this run. Removing Python does not automatically
make a Qt Quick editor smaller than a Qt Widgets editor.

To investigate, the script also groups `/proc/PID/smaps` by mapped file. With
defaults, the native editor maps about 20.68 MiB PSS in Qt Quick/Qml/KDE files;
the legacy editor maps about 11.73 MiB in Python/PySide files. Native anonymous
memory is lower (17.65 versus 20.21 MiB). This supports additional GUI library
residency as a major contributor; it does not establish all allocation causes
or prove the absence of leaks during prolonged editing. The native editor is
an on-demand process, not a new persistent service.

The measured backend gains and removal of the mandatory Python GUI runtime
justify continuing the architecture, while the editor memory cost remains a
release-review item. Repeat on real Plasma systems where Qt/KDE library sharing
differs, and profile longer editing/recovery sessions before declaring the
whole migration complete. No claim of lower memory for every component is made.

## Size and dependency boundaries

The measured Release ELF files occupy 356,416 bytes (backend) and 482,808 bytes
(editor), including embedded catalogs/QML, before distribution packaging. The
baseline's Python sources occupy 173,531 bytes. These are **program payloads
only**, excluding Qt/KDE/PySide/system libraries, widget files and packaging;
they are not comparable complete installed application footprints.

Both native executables passed separate runtime-image checks without Python,
PySide6 or a compiler. The backend uses Qt Core/DBus. The editor adds Qt
Gui/Qml/Quick/Controls, KF6 Service/Config, Kirigami/Qt QML modules and a KDE
desktop-file launcher. See the [dependency inventory](0001-native-runtime.md)
and [tested Debian runtime recipe](../../native/tests/editor.Dockerfile).

At the editor milestone, standalone memory had not been measured; the next
section records the subsequent standalone work. True cold startup, physical
menu-opening latency, total installed dependency footprint, isolated loading,
interaction CPU/frame timing and long-session growth remain unmeasured.
Complete packaging and representative physical-desktop runs are still required.

## Reproduce

Build native Release binaries with the editor enabled as described in
[native development](../../native/README.md). Export the exact baseline into
an otherwise unused directory. Run the benchmark in a disposable environment
with system PySide6 installed only for the baseline/client:

```bash
mkdir -p build/legacy-1.0.1
git archive 34058480b6e3bc1ecc1f19d420fb744f570eca34 | tar -x -C build/legacy-1.0.1
dbus-run-session -- python3 native/tests/benchmark.py \
  --native "$PWD/build/editor/native/open-power-menu-native" \
  --editor "$PWD/build/editor/native/open-power-menu-editor" \
  --legacy-root "$PWD/build/legacy-1.0.1" \
  --native-revision "$(git rev-parse HEAD)" \
  --baseline-revision 34058480b6e3bc1ecc1f19d420fb744f570eca34 \
  --output "$PWD/build/native-measurements.json"
```

Do not run on the active desktop bus. Do not drop host caches or stop a user's
services to manufacture a cold-start result. The script reports observations
and has no pass/fail speedup threshold.

## Native standalone milestone

A separate, quiet disposable Debian 13 container compared released 1.0.1
`3405848` with native Widgets implementation `de763de` (Release/GCC 14.2,
Qt/PySide6 6.8.2, x86-64). Xvfb supplied a private X11 display and a private
D-Bus session; identical temporary default/200-command configurations and
harmless executable capability fixtures were used. Neither frontend executed
power actions. Python/PySide6 are baseline/test tooling only.

Each cell uses 15 fresh processes after one discarded warmup with warm filesystem
caches. Exposure time is wall time from Popen to the first diagnostic reporting
both visible and exposed. It includes interpreter/dynamic-loader, Qt startup,
configuration/probes, window creation and diagnostic delivery. It is an observed
upper bound, with frontend event-loop instrumentation differences; it is not
physical first-pixel, cold-start or shortcut-dispatch latency. Memory is median
of three `/proc/PID/smaps_rollup` samples two seconds after exposure.

| Configuration / metric | Released 1.0.1 | Native Widgets |
| --- | ---: | ---: |
| Default: Exposure diagnostic, median | 253.288 ms | 36.277 ms |
| Default: Fresh `--check` process, median | 95.906 ms | 19.477 ms |
| Default: RSS | 67.59 MiB | 33.94 MiB |
| Default: PSS | 58.54 MiB | 29.61 MiB |
| 200 commands: Exposure diagnostic, median | 267.158 ms | 36.754 ms |
| 200 commands: Fresh `--check` process, median | 111.111 ms | 18.988 ms |
| 200 commands: RSS | 72.58 MiB | 34.82 MiB |
| 200 commands: PSS | 61.28 MiB | 30.21 MiB |

The native standalone uses less memory and reaches an exposed diagnostic sooner
in these runs. Shared-host variance and frontend instrumentation limit the
interpretation; raw samples and p95 values are retained in
[the measurement artifact](measurements/native-standalone-milestone.json), along
with the binary SHA-256 and complete `ldd` inventory. These observations do not
change the editor result above: its previously measured PSS increased from
63.69 to 71.57 MiB. That regression remains a release-review consideration.

The standalone ELF occupies 320,264 bytes before distribution packaging. Direct
Qt dependencies are Core/Gui/Widgets; this Debian Qt Gui build also pulls Qt DBus
transitively. X11/Wayland platform plugins, fonts, desktop styles/icons and
configured application/KDE helpers are runtime dependencies supplied by the
system. The standalone closure contains no QML/Quick/Kirigami or Python/PySide6.
The complete installed dependency footprint is not measured: shared desktop
libraries and packaging choices make program payload size an incomplete proxy.
The separate minimal runtime image proves menu exposure without Python,
PySide6 or a compiler and tests the loader's missing-Widgets-library diagnostic.

Hover/adaptive placement, deep keyboard selection, long-menu scrolling and rapid
pointer movement have functional virtual-session coverage. Submenu frame timing,
interaction latency/CPU and long-session memory are not measured; functional
pass results are not responsiveness benchmarks. Physical Plasma validation and
repeated profiling there remain release gates.

Reproduce after building the standalone Release target and exporting the exact
baseline into `build/legacy-1.0.1` as above:

```bash
dbus-run-session -- xvfb-run -a python3 native/tests/standalone_benchmark.py \
  --native "$PWD/build/standalone/native/open-power-menu-standalone" \
  --legacy-root "$PWD/build/legacy-1.0.1" \
  --native-revision de763de \
  --output "$PWD/build/standalone-measurements.json"
```
