# Controlled 2.1 physical acceptance

Status: **not performed**. Use with [2.1 behavior](OPM-2.1.md) and
[the current engineering checkpoint](OPM-2.1-RESULTS.md). Passing CI does not
complete any physical row below. Stable 1.0.1 remains the public release.

## Prepare a recoverable test system

Prefer a disposable Manjaro Plasma 6 machine, VM with a real input seat, or a
separate test account. A separate account is insufficient isolation for power
operations: suspend affects every session. Prioritize Wayland, then log into a
separate X11 session for remote-desktop compatibility. Obtain explicit permission
before installing or activating development code on a physical desktop.

Record the exact commit, artifact SHA-256, source commit inside the artifact,
distribution snapshot, CPU, Qt/KF6/Plasma versions, session type, GPU, theme,
AppGrid version, panel edge, outputs, primary display and scaling. Build against
the intended Manjaro snapshot; Arch/Debian qualification does not make their
binaries suitable for Manjaro. Verify the bundle inventory before setup.

Keep a local recovery terminal and an independent login available. Save the test
account's configuration, shortcut and widget state before installation; retain the
matching 1.0.1 bundle and its Python/PySide6 runtime for rollback. Use the installer
[documented transaction and rollback commands](../native/packaging/README.md).
Never replace the full panel configuration to repair OPM. Do not restart
plasmashell or alter a remote-desktop-only session for this procedure.

Create a result sheet with one row per case and per session:

| Case | Wayland | X11 | Environment / evidence / failure |
|---|---|---|---|
| Launcher/keyboard | Not run | Not run | |
| Theme/placement | Not run | Not run | |
| Interaction/dismissal | Not run | Not run | |
| Editor/recovery | Not run | Not run | |
| Upgrade/rollback | Not run | Not run | |
| Supervised power | Not run | Not run | Separate authorization required |

## Launcher and keyboard

1. Use a free binding in the test account. Open/close with Meta+X 20 times,
   including rapid toggles, mixed left/right clicks and cancellation with Escape.
   Verify every open anchors to the current panel button. Repeat after moving the
   test panel to each edge; do not modify the production panel.
2. Test the installed AppGrid variant, then Kickoff and Kicker where available.
   Left click must open the selected original launcher. Switch both directions
   with the Power User menu, with the original button visible and hidden. Restore
   the original button and confirm its configuration has not changed.
3. Use harmless Terminal/Files commands to check access-key navigation first.
   For the power submenu, verify U enters it, arrows traverse it, Left returns
   and Escape cancels. **Do not press a final power-action key in this phase.**
   Test visible/hidden hints, disabled access keys, custom bindings and collisions.
4. Customize or disable Meta+X, restart the test account normally, then reopen.
   Verify the choice survives reinstall. Remove/re-add the test widget and test
   Undo removal; verify no orphaned shortcut and no unrelated shortcut changes.
5. Compare 50 direct AppGrid openings with 50 OPM handoffs using
   [the sequenced trace procedure](SHORTCUT-APPGRID-DIAGNOSTICS.md). Record visible
   flashing, focus refusal, extra toggles and the exact triggering sequence.

## Appearance, placement and interaction

1. Check Native light/dark, the user's custom theme and Aero. Inspect custom and
   theme icons, disabled text, focus indication, access hints and long labels.
2. Test parent/child/grandchild hover and keyboard navigation near every screen
   edge. Repeat on each monitor, including a non-primary output, negative monitor
   coordinates and 100/125/150% mixed scaling. Menus must remain usable within the
   available work area. Record compositor positioning/focus refusals explicitly.
3. Use a long harmless menu to exercise scrolling, wheel/touchpad input, hover,
   arrows, Home/End and cancellation. Move quickly between parent and flyout.
4. Enable pointer dismissal with 500, 1200 and 5000 ms settings. Time at least five
   trials each. Cross into children, re-enter before expiry, navigate by keyboard
   and edit the layout; these must cancel/suspend automatic dismissal as designed.
   Change the delay while open, then close/reopen repeatedly. Repeat disabled.
5. Change focus to another application and click outside. Confirm reliable
   dismissal and no delayed callback reopening a closed menu. Check standalone
   and widget independently. Test remote desktop only with an alternate recovery
   path; never use a Plasma restart as part of troubleshooting.
6. Immediately open a cold menu, then enter its power submenu while capability
   discovery completes. Confirm other navigation stays responsive and disabled
   entries cannot run. In the standalone, an open submenu and its current harmless
   selection should survive capability updates. Test service failure/recovery in
   the disposable environment, without stopping the production power service.

## Configuration and recovery

1. Change each General preference, save, close and reopen. Confirm settings,
   labels, custom arguments, access keys and timing persist. Check all three tabs.
2. Reorder/reparent nested entries, rename and change icons. Undo/Redo through
   multiple operations, duplicate entries and reset access keys independently.
   Pick an installed application and launch only a harmless command.
3. Browse and preview backups, cancel a restore, then restore a known test backup.
   Verify the protected pre-restore copy, retention zero and retained unknown
   metadata. Exercise deletion confirmation for protected test copies.
4. Open two editors on a temporary test configuration. Save different edits and
   verify conflict handling retains the second draft. Preview overwrite, change
   the file again, then confirm; stale previews must be refused. Repeat with a
   corrupt temporary active file and a corrupt temporary backup. Keep byte copies
   of all originals and confirm refusal does not rewrite them.
5. Repeat editing and dialog open/close for 20 minutes. Capture process RSS/PSS at
   startup, each tab, after warmup and every five minutes. Record whether memory
   plateaus; allocator retention after editing is not by itself a leak. Compare
   with [the controlled measurements](architecture/native-performance.md).

## Direct 1.0.1 upgrade and rollback

On the disposable test account, first install the exact released 1.0.1 and make a
custom nested menu, alternative command candidates, hidden original launcher,
custom/disabled Meta+X and personal backups. Capture checksums of configuration,
shortcut and panel files. Install the matching development native bundle through
its explicit setup command, then verify those bytes/state remain intact.

Check production-name D-Bus activation, native editor and standalone, reinstall,
intentional failed-install recovery in a disposable copy, rollback to 1.0.1 and
re-upgrade. Review the one-time PySide6 notice using Keep, Review and Don't show
again; it must not remove packages or execute sudo. Test rollback with the legacy
runtime present, then simulate a missing runtime only inside a disposable image:
refusal must occur before replacing the native installation. Do not remove the
workstation's Python/PySide6 to manufacture this case.

## Separately authorized, supervised power acceptance

These cases remain **not run**. Before each actual action, obtain explicit user
permission, save work in every session, confirm local console access, plugged-in
power and a tested recovery path. Hibernate additionally requires working swap,
resume configuration and a known-good recovery boot. Never run actual power
operations in Codex Cloud, CI, a container or an unattended remote session.

| Case | Manual procedure after authorization | Required observation |
|---|---|---|
| Unsupported operation | Inspect KDE/logind support; open menu and editor | Hidden/disabled according to preference; useful reason; no fallback |
| Allowed suspend | Select Sleep once at the local console | Normal KDE/logind path; successful sleep and wake; input/display/network recover |
| Allowed hibernate | Qualify firmware/swap/resume first, then select once | Hibernate and resume succeed without lost session data |
| Polkit challenge | Use a test user requiring authentication | Prompt appears; cancel/deny refuses; separately authorized approval succeeds |
| Polkit deny | Deny the prompt or use existing denied test-user policy | Useful refusal; no command fallback or bypass |
| KDE restriction | Hold a normal test application sleep inhibition | Disabled on refresh; activation rechecks; recover when released |
| logind block | Hold a disposable `systemd-inhibit --what=sleep --mode=block` workload | Action refused even for an inhibitor owned by the same user; useful error |
| logind delay | Hold a disposable delay-inhibitor workload | PrepareForSleep honored within configured delay; record actual timeout/resume |
| Recovery | Release only the owned inhibitor; reopen and retry if authorized | Availability recovers; menu/editor remain responsive after wake |

Do not change Polkit policy or weaken inhibitors to obtain a passing result.
Existing logout/restart/shutdown confirmation behavior needs separate supervised
review. Canceling a prompt and completing its actual power action are separate
results; never infer completion from a prompt alone.

## Diagnostics for a failed case

Collect only what is needed: exact case/time, expected/actual behavior, commit and
artifact checksum, OS/session/Qt/KF6/Plasma/theme/display versions, OPM process ID,
exit status, error text and relevant user-session journal lines around the failure.
The read-only commands `uname -m`, `plasmashell --version`, `echo "$XDG_SESSION_TYPE"`
and `kscreen-doctor -o` can establish the environment. Read `/proc/PID/smaps_rollup`
for a process the test user owns; do not change ptrace/journal permissions.

Native read-only diagnostics are `open-power-menu --check` and standalone
`--diagnose-launch`; the latter opens a menu, so cancel it without selecting a
power operation. Power availability diagnostics do not authorize executing it.
Do not use legacy-only diagnostic flags with the native dispatcher. Redact private
command arguments, home paths and unrelated journal content before sharing.
Report each case as Pass, Fail, Blocked or Not run and link its evidence. A missing
service or unsupported feature is an observed result, not an automatic pass.
