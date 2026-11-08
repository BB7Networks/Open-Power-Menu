# Controlled 2.1 physical acceptance

Status: **not performed**. Use with [2.1 behavior](OPM-2.1.md) and
[the current engineering checkpoint](OPM-2.1-RESULTS.md). Passing CI does not
complete any physical row below. Stable 1.0.1 remains the public release.

## Obtain and verify the controlled development candidate

Use the exact Manjaro artifact linked in the latest
[feature qualification](OPM-2.1-FEATURE-QUALIFICATION.md), after its corrected-source
workflow has passed all eight jobs. Download through authenticated GitHub, unpack
into an otherwise empty directory, and retain the complete download. The baseline
November 8 artifacts expire November 15; a baseline artifact does not contain the
later Breeze/import-feedback corrections. Cloud artifact downloads were blocked;
the report must distinguish remote metadata from downloaded, verified bytes.

From the unpacked artifact directory, before installation:

```sh
cat SOURCE-COMMIT os-release
sha256sum -c PACKAGE.sha256
sha256sum -c OpenPowerMenu-*.tar.gz.sha256
pacman -Q manjaro-release glibc qt6-base qt6-declarative qt6-wayland kirigami kservice kconfig plasma-workspace
uname -m
plasmashell --version
```

Compare those installed versions with `packages.txt` and `runtime-packages.txt`.
Record the exact tested snapshot from this candidate; older engineering inventory
versions are historical, not certification of the current package. Require Manjaro
x86-64, Plasma 6 and matching Qt/KF6/plugin compatibility. A newer rolling Qt/KF6 or
glibc snapshot needs a matching rebuild and qualification; do not force installation
or bypass the installer's OS/ELF/library/plugin checks. Preserve checksum outputs
and inventory files in the acceptance record. The source checksum may refer to a
source archive not included in the artifact; `SOURCE-COMMIT` identifies the source.

After explicit authorization to install in the test account, back up its state:

```sh
backup_dir="$HOME/opm-2.1-acceptance-$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 "$backup_dir"
config_root="${XDG_CONFIG_HOME:-$HOME/.config}"
for name in open-power-menu kglobalshortcutsrc plasma-org.kde.plasma.desktop-appletsrc; do
    if test -e "$config_root/$name"; then cp -a "$config_root/$name" "$backup_dir/"; fi
done
tar -xzf OpenPowerMenu-*.tar.gz -C "$backup_dir"
sudo pacman -U ./open-power-menu-native-dev-*.pkg.tar.zst
open-power-menu-native-setup
open-power-menu --check
open-power-menu --edit
```

Run setup as the ordinary desktop user. The pacman operation stages the package;
setup explicitly installs/activates the per-user native components. It does not
restart Plasma or rewrite panels/shortcuts. Retain released 1.0.1 and its existing
Python/PySide6 runtime. The verified direct upgrade preserves personal menu bytes,
launcher/shortcut choices and backups, and records the complete old component set.
Default-only new entries are not inserted into an existing custom layout.

Verify the rollback path before testing, while retaining both the pacman package
and the extracted bundle. On the user's authorized test system, the tested commands
are `open-power-menu --rollback` or the retained bundle command:

```sh
"$backup_dir/native-bundle/app/bin/open-power-menu-install" --rollback
```

Use `--recover` through that same retained installer for an interrupted transaction;
retain snapshots under the recovery directory. Rollback to 1.0.1 requires its
Python/PySide6 runtime. Do not remove system packages to manufacture that failure.
Do not restore a whole Plasma panel configuration as routine rollback.

Recommended order: capture versions/backups; upgrade/check/editor; General/Layout/
Backups and JSON Cancel/Apply/recovery; harmless standalone and widget navigation;
Native/Aero/Breeze icon sizes and hover delays; launcher/Meta+X; monitor/scaling and
remote-desktop checks with recovery access; rollback/re-upgrade. Only afterward
consider the separately authorized supervised power cases below.

For a failure, record time/case, stderr and read-only `open-power-menu --check`,
`pacman -Q` versions and `journalctl --user -b --since "10 minutes ago"` relevant OPM
lines. `open-power-menu --diagnose-launch` opens a menu: cancel it without selecting
a power action. Keep diagnostics private until paths/arguments and unrelated journal
entries are reviewed. The detailed result sheet and cases below remain **Not run**.

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

## New customization and portability cases — Not run

- Compare widget/standalone default, immediate, 100/300/600 ms hover; leave/re-enter,
  switch siblings rapidly, cross to child, use keys/click before expiry, close/reopen.
- Exercise compact/standard/comfortable, auto/narrow/wide and each icon size with
  icons enabled/disabled, Native/Aero and light/dark desktop themes. Include long
  labels, hints, large fonts, fractional scaling and opposite screen edges.
- Check keyboard focus, fast U/U sequences, held keys and disabled entries with a
  harmless command fixture. Text fields must never activate menu access keys.
- Export a customized nested test configuration; inspect sensitive paths/arguments.
  Import on a second test profile, review warnings and cancel before applying once.
  Verify launcher selection, button icon, shortcuts and panels remain local.
- Apply with retention zero, restore the protected pre-import copy, and reject a
  malformed/unsupported file. Modify source or active config after preview and
  confirm refusal without losing the active file or a later editor draft.

Do not begin this physical phase until the feature checkpoint's automated and
Debian/Arch/Manjaro qualification tasks have completed.

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
