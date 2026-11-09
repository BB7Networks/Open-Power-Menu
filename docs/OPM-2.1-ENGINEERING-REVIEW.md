# 2.1 engineering review — November 8, 2026

Starting checkpoint: `2937ac646200ef7884b9c6c4fa7c568e2fbb0b3a`.
Engineering code commits: `3fd2cd9` and the pending-presentation race fix `5976e8b`.
Branch: `feature/native-architecture-v1.1`; existing PR #10 remains draft.
The initial workspace was a clean stable 1.0.1 checkout (`34058480`); the fetched
development branch exactly matched the handoff. No unexpected work was discarded.
Stable 1.0.1, production desktop integration and published artifacts were not changed.

## Power responsiveness

`DBusPower::check` previously made three sequential blocking reads per action:
PowerDevil `CanSuspend`/`CanHibernate`, PowerDevil `HasInhibit`, and logind
`CanSuspend`/`CanHibernate`. Each read had a 1500 ms timeout. `Model::normalize`
called this for every power entry, on every menu reconstruction and selection.
Duplicate entries multiplied requests. Both defaults together could approach nine
seconds if preceding reads answered near their timeout before a later read failed.
A completely silent KDE service fails at the first read: about three seconds for
both actions. Missing services normally fail quickly.

The standalone called normalization in its constructor on the Widgets UI thread.
`EditorCatalog::builtinDetails` also performed it on the QML UI thread, creating a
fresh manager on each query. `Service::GetMenu` blocked the backend event thread;
Plasma's asynchronous request kept its own event loop alive but waited for a menu.
Thus these were demonstrated delays, not only a theoretical physical-review item.

A private D-Bus fixture accepts only the three read methods; session and system
addresses both target that owned bus. Three `GetMenu` round trips per scenario
include the fresh CLI client's process/IPC overhead. Debian 13 amd64, Qt 6.8.2,
Release/GCC 14.2, Linux 6.18.57, shared cloud CPU, warm filesystem caches:

| Fixture | Checkpoint median | Asynchronous median |
|---|---:|---:|
| Healthy replies | 8.54 ms | 5.54 ms |
| Every reply delayed 300 ms | 1793.92 ms | 4.76 ms |
| Missing service | 7.36 ms | 4.57 ms |
| KDE service never replies | 2909.43 ms | 4.71 ms |

Small sample sizes establish the multi-second defect and its removal under these
fixtures; they are not physical first-pixel benchmarks or statistical speed claims.
These measurements isolate power reads. Existing non-power executable/KCM/shortcut
probes still use `QProcess::waitForFinished(2000)` plus a bounded kill/reap wait,
with a 30-second cache; this is not a claim that all command discovery is
asynchronous. Physical end-to-end opening latency still needs measurement.
The fixture asserts healthy/slow results eventually enable both actions and
missing/unresponsive results leave both unavailable. No power operation executes.
Reproduce with `python3 native/tests/power_benchmark.py --binary <native-backend>
--output <report.json>`; PySide6 is test tooling, not a native runtime dependency.

The replacement has five concurrent reads per generation, sharing `HasInhibit`,
a 1500 ms total discovery deadline and five-second demand-driven cache. Repeated
entries/calls coalesce while pending. Expiry returns unknown/unavailable and begins
one refresh. Service-owner changes invalidate the cache; generation tokens reject
late, duplicate and out-of-order replies. Context guards protect destroyed owners.
No background polling runs for idle caches. The editor owns a persistent manager
and refreshes the displayed reason. Standalone reconciles live actions/submenus
rather than deleting a focused menu. A power-only menu can display a disabled
loading row while discovery runs, then report no available commands if needed.

The widget uses the additive `PowerCapabilitiesPending` method and at most eight
250 ms refreshes while expanded, guarded by its existing request epoch and editing
state. An older backend can reject the optional method without breaking its API.
The method remembers whether the last presentation was pending, avoiding a race
where fast completion between the two calls could leave the initial disabled
presentation displayed. This avoids requiring newer Plasma SignalWatcher support. Existing menu JSON,
configuration schema, command resolution and global Meta+X contracts remain.
CLI diagnostics alone may await a settled discovery with a 1600 ms ceiling.

Selection does not start a cache refresh that could renumber already presented
keys. Cached capability is presentation information, never execution authority.
The existing activation path rechecks KDE restrictions and system authorization,
then uses interactive logind `*WithFlags(1)` with root inhibitor checking and no
unchecked fallback. Unknown/disabled entries cannot dispatch. Authorization and
inhibitor regression tests retain the previous policy cases.

**Remaining limit:** actual activation still performs synchronous fresh checks
(up to three 1500 ms reads) and a possible 120-second interactive authorization
call. Standalone performs this after its popup returns; the backend `Run` service
thread can still wait during authorization. This pass fixes capability discovery,
not the execution API. Supervised policy/denial/inhibitor/wake acceptance and
physical responsiveness during an outstanding authorization remain release gates.

## Editor lifecycle and memory

The historical 63.69 → 71.57 MiB PSS comparison remains valid for its original
revisions. This pass repeats the original same-container application benchmark
and separately exercises the actual QML window in a developer-mode GUI harness.
The harness is invoked only with `native-editor-gui-tests --profile-memory
<report.json>` on a private bus; ordinary CTest behavior is unchanged.

Three fresh harness processes use native defaults, software/offscreen rendering,
all three tabs, 500 label edits, 250 Undo and 250 Redo operations, 50 animated
dialog open/close cycles and 100 backup refresh/preview cycles each. Samples follow
startup, tab visits and each 100-edit batch. QML garbage collection and a final
reload are observed; optional glibc `malloc_trim(0)` is a diagnostic, never a
production allocator change. Readings are process RSS/PSS, not total desktop use.
The harness additionally loads Qt Test and fixtures, so its absolute PSS must not
be compared directly with the standalone editor application baseline.

The final application comparison records **62.77 → 71.65 MiB PSS** for
released defaults (increase 8.88 MiB), and **64.33 → 70.57 MiB** for the custom
200-command layout. These are single application observations per cell. They do
not supersede the original revision-specific measurements with a universal claim.

| Harness phase | Median PSS, three processes | Range |
|---|---:|---:|
| Startup, General at two seconds | 78.03 MiB | 77.97–78.21 |
| Layout | 78.16 MiB | 78.12–78.29 |
| Backups preview | 78.49 MiB | 78.44–78.63 |
| After 100 edits / 10 dialogs | 100.17 MiB | 100.06–100.25 |
| After 500 edits / 50 dialogs | 98.41 MiB | 98.29–98.54 |
| Reloaded, idle two seconds | 98.40 MiB | 98.28–98.54 |
| Diagnostic allocator trim | 85.33 MiB | 85.16–85.54 |

Tracked window descendants were 1805 at startup and after every edit batch, with
1807 during initial backup preview. Warm batches fluctuate around 98–101 MiB;
this workload shows no progressive per-batch growth. Reload does not return PSS
to startup levels. Allocator trimming releases about 13 MiB, but a residual remains;
allocator caching is part of the explanation, not proof of the entire cause.

The measured plateau and allocator retention are recorded with raw samples in
[the measurement report](architecture/measurements/2.1-engineering-review.json).
Window QObject-descendant counts stay stable after transient backup rows. The
editor Undo history already has count and serialized-size bounds; backup history
retains metadata rather than every decoded document. This workload does not
establish leak freedom or explain all retained allocations. Long physical sessions
and desktop library-sharing differences still need acceptance.

Review also identified viewport records for deleted submenus retained in the
native QML draft's `views` map. `syncLayout` now drops records whose parent IDs no
longer exist, preserving the root and surviving submenu records. A real-QML test
checks deletion, preserved root scroll state and Undo without resurrecting stale
viewport state. No editor redesign or production allocator trimming was added.

## Migration edge cases

The differential corpus now covers null/bool/integer/string presentation values,
exact signed 64-bit label/icon formatting, extension metadata and alternative
command preservation. Native integer display previously converted through double;
large integer labels/icons now remain exact. Array/object presentation values are
refused instead of silently becoming empty text. Decimal/exponent presentation
numbers are refused before Qt can erase their lexical distinction (`1.0` versus
`1`); users can explicitly convert the intended presentation to text in a copy.
These restrictions apply to actual menu label/icon fields, not unknown metadata.
No automatic reduced-configuration migration is performed.

Non-UTF-8 bytes, signed-range overflow in both directions, excessive menu nesting
and corrupt source data are tested with byte-for-byte preservation of the active
file and a personal backup. Existing recovery, protected previews, unknown
metadata and legacy-runtime rollback safeguards remain. These are targeted
compatibility cases, not a claim to accept every historical JSON extension.

## Validation and physical readiness

Local results: all eight native CTest targets pass; the expanded backend-only
private D-Bus/differential suite passes 12 tests; nine real disposable transaction/
legacy-upgrade cases pass. The pinned PySide6 6.10.2 regression suite passes 455
with eight existing historical-source skips. Native X11 checks run on Xvfb;
Wayland/KWin and distribution packaging passed all eight jobs in both workflows
for `fe9a367`; this includes independent Debian, Arch and Manjaro builds.
Final run links and exact tested commits belong in [checkpoint results](OPM-2.1-RESULTS.md).

Initial local failures were toolchain/setup findings: missing Git/ZIP, the distro
PySide6 6.8 legacy interaction behavior, and running the backend-only contract
against a full editor-enabled directory. Corrected runs use complete tooling,
the pinned PySide6 and the intended backend-only build. The new lifecycle test
also explicitly establishes the QML draft before simulating viewport state.
A preliminary overlapping measurement/build run was discarded; retained final
measurements run after the build completes.

[The focused physical procedure](OPM-2.1-PHYSICAL-ACCEPTANCE.md) is ready for user
execution. All its physical rows remain Not run. It covers Manjaro Wayland/X11,
AppGrid/Kickoff/Kicker, Meta+X, custom themes/icons, panel edges, multiple monitors,
fractional scaling, dismissal, configuration/recovery, 1.0.1 upgrade/rollback,
read-only dependency review and diagnostics. Actual power actions require separate
explicit permission, local console access and recovery preparation.

Engineering evidence and passing distribution CI support controlled, supervised
physical acceptance of the development candidate. It does not establish a qualified
release candidate or authorize a production replacement, merge, tag or publication.
Remaining blockers are physical integration, supervised power/authorization/wake
behavior, longer editor sessions and final distribution-snapshot verification.
