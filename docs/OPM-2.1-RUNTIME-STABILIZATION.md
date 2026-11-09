# OPM 2.1 pre-acceptance runtime stabilization

Starting checkpoint: `f16942e`, branch `feature/native-architecture-v1.1`, draft
PR #10. Target remains `2.1.0-dev`; released 1.0.1 is unchanged. This pass addresses
the two reproduced runtime P1 findings from the release-readiness audit.

## Selection identity

`GetMenu` retains the existing JSON shape, but its `key` values are opaque
presentation identities. Each response captures the exact storage revision
(bytes, device and inode), displayed menu, and resolved command/power selection.
A fresh random identity is prefixed to each positional key. A service restart
cannot recreate it. Clients must pass the returned key verbatim; bare positional
paths are refused with a reopen/refresh message.

Each presentation allows one activation attempt, expires after 120 seconds and
is independently retained. There are at most 16 presentations; older ones are
safely evicted. Another client's refresh cannot change an existing key's meaning.
The service checks the revision before resolution and again immediately before
command launch; it checks the selected command arguments, resolved executable,
power action and availability against the captured selection. It launches that
validated selection, never frontend-supplied arguments. Configuration changes,
reordering, removal, alternative-command changes and disabled selections fail
closed. A configuration change after the final filesystem check cannot retarget
the already captured argv to a replacement item.

Menu keys are short-lived bearer identities, permitting existing callers to read
and activate through separate D-Bus connections. Disconnecting a connection does
not renew, recreate or rebind a key. Operation results, unlike menu keys, are bound
to the initiating unique D-Bus connection. Multiple widgets on one Plasma
connection still have distinct presentation and operation identities.

The standalone captures the same resolved selection, retains its own menu, and
checks its source revision before activation and during asynchronous policy
checks. It does not share a global presentation with another window/process.

## Asynchronous power activation and API

Production activation uses asynchronous D-Bus calls in this order:

1. Fresh KDE capability.
2. Fresh KDE inhibitor check.
3. Fresh logind capability/authorization (`yes` or `challenge`).
4. The corresponding logind `WithFlags` request, with interactive authorization
   and flag value 1. No `SKIP_INHIBITORS` or shell fallback is introduced.

Read deadlines remain 1.5 seconds each; interactive authorization is bounded to
120 seconds. Selection revision/identity and initiating-client lifetime are
checked before advancing to another step. A client disappearing before dispatch
prevents dispatch. Once a request reaches logind, disappearance cannot undo it:
the manager continues tracking completion and never retries it automatically.
Owner changes invalidate pending work. A late reply cannot complete a newer
operation. Only one power operation can be active per manager.

If an already-dispatched operation times out, loses contact or has an invalid
reply, its completion may be unknown. Further power activation remains refused
for that manager's lifetime. Other service requests remain usable. Do not retry
an uncertain operation automatically; first resolve the system's actual state.
The idle timer keeps the service alive while authorization or uncertain execution
is tracked. All callbacks guard object lifetime.

The widget uses two additive methods, both returning JSON strings:

- `StartRun(key)` returns either `{state: "pending", operation: "..."}` or a final
  `{state: "finished", ok: boolean, error: "...", operation: "..."}`. Pending is
  never represented as successful execution.
- `RunResult(operation)` returns pending or the final result only to the
  initiating D-Bus connection. Completed results are retained for 120 seconds,
  with a limit of 64 operation records. Expired/foreign identities are refused.

The widget polls every 250 ms while pending, guards duplicate submissions and
uses the request's own error. It does not use a service-wide LastError read or
retry activation after transport failure. Loss of contact or its 130-second
waiting bound is reported as unresolved rather than successful.

`Run(key) -> bool` remains available for older callers, with a delayed D-Bus reply
that reports final completion. It accepts the new opaque key; positional-only
callers must refresh/use `GetMenu`. The native diagnostic CLI allows 130 seconds
for this method. Legacy `LastError` is scoped by calling connection. The updated
widget and backend are distributed together; the old Python-only development
installer is not the native installation path. Released 1.0.1 rollback restores
its complete original widget/backend pair.

The standalone awaits final completion through a Qt event loop after its popup
closes. Input/events/timers continue; no blocking power D-Bus transport remains
on its execution path. The old synchronous injected transport is retained only
for deterministic policy test fixtures.

## Regression evidence

The added private-bus and injected-transport tests cover:

- Same-title replacement; independently opened presentations; A after B's
  refresh; reorder/deletion; identical-byte inode replacement; valid execution.
- Disabled/enabled transitions, changed command alternatives, malformed,
  consumed/replayed, expired and evicted identities, and a new service instance.
- Delayed checks/authorization, challenge/denial/cancellation, missing services,
  timeouts, late/malformed replies, owner invalidation, client disappearance,
  duplicate requests, request-specific results and inhibitor flags.
- Standalone revision refusal and Qt event processing during delayed refusal.

A real private D-Bus round trip for Ping/GetMenu/GetIntegration completed in
**1 ms** while the fake authorization request waited **2.2 seconds**. A separate
service test handled 100 such combined request sets in **9–10 ms** during that
wait. These are controlled local observations, not physical latency guarantees.
The fixture always refuses activation; no real power action occurs.

Local qualification at this implementation includes eight passing native CTest
targets, 15 backend/private-D-Bus contracts, and 466 portable/legacy/widget tests (plus the subsequent focused activation-poll test)
with eight historical skips and 18 subtests. The Python Qt tests use the existing
pinned PySide6 6.10.2 environment. A preliminary broad discovery incorrectly
included the archived legacy test tree, and an alternate Qt 6.8 Python image
exposed two legacy input-harness failures; neither attempt qualifies the final
suite. The final intended toolchain passes without weakening those tests.

Nine disposable installation/upgrade/rollback cases pass, including released
1.0.1 migration. The corrected native bundle passes install, activation, editor
smoke, reinstall, removal and rollback in the existing Debian runtime image
without Python, PySide6 or a compiler. Distributable fault hooks are OFF.
Virtual X11 and Weston each pass 43 standalone cases with the existing one
focus-seat skip; KWin and two-output KWin at scale 1.25 each pass all 44.

The normal eight-job CI matrix remains intact. Final workflow IDs, source SHAs,
package identity and available checksums are recorded in the completion handoff;
CI artifacts certify their own source, never the old `462a351` build. Local raw
logs are under ignored `work/stabilization/`.

## Remaining gates

The two optional P2 changes are limited to accurate fresh-import success text
and placing/clarifying the close-delay and default-hover explanations. General
has not been redesigned. Native runtime dependencies remain C++/Qt/KF6/system
libraries; Python/PySide6 remain legacy/test tools only.

Before physical installation, independently verify the corrected Manjaro
artifact's outer/inner checksums, SOURCE-COMMIT, bundle inventory, fault hooks
OFF, CPU and recorded Qt/KF6/glibc snapshot. If cloud artifact retrieval remains
blocked, preserve metadata and perform authenticated download/verification on
an authorized machine. Do not modify network settings or substitute an Arch or
Debian binary for Manjaro.

Use [physical acceptance](OPM-2.1-PHYSICAL-ACCEPTANCE.md) with the new candidate.
Both Wayland and X11 remain required gates. Physical integration and actual
Sleep/Hibernate, Polkit, inhibitors and wake/resume are still **Not run** and
require separate user-led authorization/supervision.

Publication-oriented P1 work remains separate: adapt the legacy release pipeline
to native assets/coherent RC/final versions, and provide an ordinary-user native
binary installation/update/recovery/rollback/removal guide. Neither publication
nor changes to the active desktop are part of this stabilization pass.
