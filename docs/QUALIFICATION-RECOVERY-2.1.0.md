# Stable qualification recovery

Recovery starts at main `1740d277a63c2bf4204235e8fe21526147bf6997`, whose tree
matches previously approved source `a27f1c7e10be8b25b0d42eb2f48c3a9aafea0085`.
The [blocked publisher](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/45616890237)
created no stable tag, release draft or public assets. This work remains on
[draft PR #15](https://github.com/BB7Networks/Open-Power-Menu/pull/15).
Publication requires separate approval of the new exact source and evidence.

## Current Manjaro and retained X11 coverage

The [repository audit](https://github.com/BB7Networks/Open-Power-Menu/actions/runs/45623657135)
installed packages from each distribution's own repositories. Manjaro has Plasma
6.8.2, Qt 6.12.0 and KF6 6.31, and only its native Wayland session. Pinned Arch
2026-09-27 has Plasma/KWin 6.7.5, Qt 6.11.2 and KF6 6.30 with both compositors.
Exact versions and required binaries are recorded in `session-coverage.json`.
Missing or mismatched profiles fail verification; no session is silently skipped.
See [compatibility boundaries](COMPATIBILITY.md).

The first recovery run reached Manjaro's private Wayland seat, then failed
compositor readiness. KWin 6.8's virtual backend supports OpenGL, while the
fixture requested QPainter. Its software render device also requires
`/dev/udmabuf`. CI now provisions that buffer device on the disposable GitHub
runner and passes it only to the offline Manjaro test container, using software
OpenGL and no hardware render nodes. The stock distribution compositor and
libraries remain intact. All Wayland fixtures check the standard D-Bus
`Compositing.active` property before testing; a socket alone cannot qualify a
failed renderer. This environment adaptation still requires fresh CI evidence.

## Debian root/flyout geometry

Eleven independent local `xcb-ready` cases using the original application source
passed. The original CI assertion has not been reproduced locally. Retained
[successful geometry traces](evidence/qualification-recovery/debian-theme-margins.json)
show outer height 382 with padding 12, followed by height 378 with padding 8;
content remains 370. The flyout's independent height is 106.

Comparing outer heights across exposure/theme initialization assumes immutable
Plasma margins. The corrected test requires unchanged content height, matching
minimum/maximum/actual height, current frame padding and work-area bounds. It
also observes the current visible flyout, rather than an older visible sample.
The existing two-pixel outer-frame rounding allowance is unchanged. Deterministic
tests accept the captured padding transition and reject clipped, resized,
hidden or oversized roots. No product sizing code or delay was changed.

## Kubuntu held-I release/repress

The original unmodified application binaries passed an initial complete X11
matrix. A diagnostic repetition reproduced the hidden-launcher failure at the
deliberate I repress (Sign out). [Timestamped evidence](evidence/qualification-recovery/kubuntu-held-i.json)
shows that holding I while sending Meta+X also invoked KDE's Meta+I System
Settings shortcut. That asynchronously opened window received the release and
fresh press. OPM remained at 19 private mock requests, rather than the expected
20, because it did not receive that final key. No duplicate action occurred.

XI2 recorded the physical release and fresh press. Xvfb, KWin, plasmashell and
the mock/backend processes were alive at the assertion; the X11 disconnection
followed fixture teardown. This matches the older held-I log's System Settings
launch and changed focus, without inferring the cause from focus alone.

The fixture shadows only System Settings' default application shortcut in its
private XDG directory. Real OPM Meta+X, held I, other held keys, rapid presses,
both launcher states and exact request-count assertions remain. Production QML,
XI2 admission, focus handling and X11 popup protections are unchanged.

An additional private run timed out waiting for X input focus during opening
after the held-U scenario. That is a separate unresolved observation. Later
passes do not diagnose or fix it; retain it in publication review.

## Additional fixture failures exposed during recovery

Pinned Arch reached the editor-launch suite and exposed an empty JSON read.
The test probe created its evidence path before writing its contents, while the
parent used path existence as readiness. The probe now commits that file
atomically with `QSaveFile`; the assertions and product launcher are unchanged.
The corrected local editor-launch suite passed.

Archived package transfers also exceeded pacman's ten-second connection or
low-speed limits. Dependency installation disables that transfer timeout while
retaining the overall CI deadline, signatures and fixed repository snapshot.
The archive server subsequently reset an HTTP/2 package stream before any
transaction. Pinned Arch transfers now use curl over HTTPS/HTTP 1.1, with bounded
network retries. This retries downloads only; no test assertion is retried.
Offline qualification explicitly uses umask 022, matching installation tests'
secure ancestor requirements; an inherited umask 0000 correctly caused the
local dependency fixture to refuse an unsafe directory.

## Evidence and qualification gates

Fixtures record scenario, assertion, timestamps, mock requests, input/focus,
geometry and process state before teardown. The XI2 observer is test-only,
read-only and never installed. CI annotations expose bounded evidence without
artifact downloads; full private desktop evidence is retained even on failure.
Native Wayland greeter tests observe actual KWin layer-shell windows and cancel
with input on the private compositor. They use the real stock greeter and private
final power recorders, including the full countdown.

Only fresh successful checks on the PR's exact head and the same-run 21-file
nonpublishing asset verification qualify a replacement source. Historical traces
above explain findings; they are not qualification credit. Physical Manjaro
acceptance established earlier EZ installation and normal menu/Configure use,
not destructive actions, physical held-key safety or the new rolling runtime.
Deferred X11 panel ghosting, existing releases and workstation installations
remain untouched.
