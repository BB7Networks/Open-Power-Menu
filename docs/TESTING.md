# Regression and physical acceptance

Use disposable users, containers and private desktop fixtures. Never run power,
lock or installation tests against a working desktop profile. All power endpoints
must be private mocks. Repository-only checks do not change a user's configuration,
panel or shortcut. Physical acceptance is distinct from CI and remains pending.

## Portable and native checks

```sh
python3 -m pytest -q
python3 scripts/audit-repository.py
cmake -S . -B build/test -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DOPM_BUILD_EDITOR=ON -DOPM_BUILD_STANDALONE=ON
cmake --build build/test --parallel 2
ctest --test-dir build/test --output-on-failure
```

Install test dependencies in a disposable environment. See
[native build dependencies](../native/README.md) and `.github/workflows/tests.yml`.
The Python reference and legacy installation tests remain; PySide6 tests run in a
separate Qt/D-Bus job where unavailable in the portable job. Report skips explicitly.
Legacy installation helpers require `OPM_LEGACY_FIXTURE=1` and explicit private
XDG roots; the tests set these and fake desktop/package tools. They are not a
supported user installation route.

The ten-job CI matrix covers native backend, standalone, portable and Qt/D-Bus
suites; Debian/Kubuntu editor/desktop jobs; and Manjaro, Arch, Debian and Kubuntu
packaging/upgrades. Package tests use exact released 1.0.1/RC1/RC2 source baselines,
private profiles, fault-injection builds, and separately sealed hooks-OFF payloads.
Minimal runtime images prove Python absence where applicable; full Plasma images
then exercise the EZ entrypoint without PySide6 or compilers. Both X11 and virtual
Wayland activate the installed backend/editor. CI paths follow the cleanup inventory.

## Private power and keyboard tests

With dependencies from `native/tests/editor.Dockerfile` in a disposable lab:

```sh
umask 022
python3 native/tests/plasma_keyboard.py \
  --backend "$PWD/build/test/native/open-power-menu-native" \
  --output /tmp/opm-keyboard-new --held-repeat
```

Use a new output directory. The fixture creates private profiles, displays and
D-Bus services; real XTest input on X11 and QtTest input on virtual KWin Wayland
exercise root/flyout holds, fresh-flag repeats, rapid deliberate presses, release
in another window, focus loss, reopening, navigation, custom/disabled keys and
both launcher-visibility states. Records are `requests.jsonl`, `results.json`,
`stress.json` and `plasma.log`. A held U must open once without dispatch; release
and a deliberate next U must dispatch exactly once to the mock.

The real greeter tests also use private final power endpoints. They cover all
three confirmation modes, KDE settings and countdown/cancellation. No live
shutdown, restart, sign-out, suspend, hibernate or lock is an acceptable test.

For physical input in a private nested X11 seat, follow the existing
[manual mock acceptance procedure](history/2.1-development/HELD-KEY-STABILIZATION.md#physical-acceptance-with-private-mocks).
Use a VM if keyboard capture is uncertain; never let the host receive a destructive
sequence. Wayland's virtual checks do not claim physical global-shortcut delivery.

## GUI, publication and review gates

The real dropdown matrix uses Breeze Light/Dark at 100/150/200% scaling and
three window sizes. `native/tests/editor-appearance.sh` produces actual captures.
Existing popup traversal/dismissal and startup suites remain unchanged except
for the Phase 1 PID-based background-window lookup.

The stable publisher is tested with a fake GitHub API: incomplete/corrupt assets,
wrong source, missing approval, pre-existing tags/releases, upload/download
failures and final Stable/Latest flags. No real publish call occurs during tests.
The documentation audit checks local links, baseline inventory destinations and
protected runtime/gallery hashes. See [publishing](PUBLISHING.md).
The `--phase2` inventory/hash check runs on the cleanup branch and its PR only;
the local-link audit remains active on every branch. Later approved work can add
files without rewriting this historical cleanup inventory.

Before stable release, review cleanup and Phase 3, then perform physical desktop
acceptance: Configure Save/reopen, harmless commands, flyouts, Escape/outside click,
repeated Meta+X, launcher visibility, scaling, upgrades and rollback. Record runtime
versions and source commit. Power-key acceptance remains mock-only. Keep the
unconfirmed Phase 1 focus timeout, deferred ghosting and responsiveness visible
in review notes; do not infer they were fixed from a later successful run.
