# Shortcut and AppGrid live diagnostics

PR #5 adds these checks after live Manjaro feedback at `b236efd`. The cloud has
no Plasma, KWin or native display session. The fixes below have source evidence
and automated regression coverage; the reported desktop symptoms need this
local comparison before merge. Nothing here requires restarting Plasma.

## Meta+X: separate dispatch, startup and visibility

1. Install the complete package using `bash install.sh`, then run:

   ```bash
   ~/.local/bin/open-power-menu --check
   ~/.local/bin/open-power-menu
   ```

   If you use `XDG_BIN_HOME`, use the resolved executable shown in **Configure →
   General → Set up Meta+X…** instead. `--check` validates the configuration and
   resolves entries without Qt. The normal command checks GUI startup. Press Esc
   to dismiss without launching an entry. Both commands were exercised in an
   isolated installed cloud profile; the cloud user's default path is not installed.

2. Use **Test menu launch** in setup, or run:

   ```bash
   ~/.local/bin/open-power-menu --diagnose-launch
   ```

   The test invokes that installed executable as an argument array. It displays
   failed startup, nonzero/crashed exits and bounded output. `OPM_LAUNCH` lines
   contain a sequence, monotonic elapsed milliseconds, platform, visibility,
   exposure and focus. They contain no menu titles or command arguments. Ordinary
   configuration error output can contain a local path; review it before sharing.
   Closing setup stops only its own test child.

   | Observation | Next check |
   | --- | --- |
   | Executable missing or FailedToStart | Reinstall; inspect the displayed executable path/permissions |
   | `configuration-error` or --check fails | Recover the configuration before testing the shortcut |
   | Process exits with a Qt/import/platform error | Fix the reported dependency/session issue; use the local desktop terminal |
   | `cli-start`, but no exposed window | Read Qt errors; check platform, installed version and Wayland behavior |
   | Exposed but no active/focused menu | Check compositor placement/activation; record what is actually visible |
   | Test menu works, but Meta+X does nothing | Inspect KDE assignment, conflicts and the application entry |

   A started process is not proof of a visible menu. Qt exposure/focus reports
   still need visual confirmation, and this launch test does not test keyboard dispatch.

3. In KDE Shortcuts choose **Add New → Application… → Open Power Menu**, assign
   **Meta+X**, and **Apply**. The installed entry is `org.openpowermenu.desktop`;
   setup shows its XDG-resolved location. Also try launching that application
   from KDE's application menu to check desktop-entry execution separately.
   The installer quotes Exec paths including spaces and literal percent signs.
   This opens the **standalone saved menu**, not the panel instance or its draft.

4. If an older Command or Script assignment is stale, remove only that OPM
   assignment in KDE, Apply, then add the installed Application entry and Apply.
   Close/reopen Shortcuts and verify the assignment persisted. Cancel a conflict
   or choose another key; preserve unrelated bindings. Test Meta+X on the actual
   desktop, then test changing and removing it. OPM does not write KDE/KWin
   shortcut configuration or restart the shortcut daemon.

5. On Wayland check visibility/focus, Esc, submenu arrows, command selection and
   clicking another application. KWin controls top-level placement; exact cursor
   or panel anchoring is not guaranteed. Repeat on X11 where practical.

### Findings and evidence

- Qt 6.10's [xdg-shell implementation](https://github.com/qt/qtbase/blob/6.10/src/plugins/platforms/wayland/plugins/shellintegration/xdg-shell/qwaylandxdgshellintegration.cpp)
  closes a grabbing popup when it has no transient parent or previous input
  device. The previous standalone root was a parentless QMenu. It now uses a
  frameless top-level QMenu on Wayland and requests normal activation, with
  application-deactivation dismissal. X11 retains the popup path. This is a
  concrete launch defect, but the user's shortcut dispatch has not been observed.
- The Qt tests also reproduced invalid submenu wrappers from PySide6 6.10.2's
  `addMenu(icon, title)` overload. Explicitly parented submenus preserve navigation.
- KDE's [Shortcuts implementation](https://github.com/KDE/plasma-desktop/blob/master/kcms/keys/kcm_keys.cpp)
  supports the Application route using the installed desktop identity. Custom
  commands create another desktop entry. Upstream history includes
  [command-entry name collisions fixed in Plasma 6.2](https://github.com/KDE/plasma-desktop/commit/38cfc065b4b0a994227c0f0751668dd2447d70e6)
  and [deletion of obsolete command entries](https://github.com/KDE/plasma-desktop/commit/dd0d33398549d482605e7373459e2b0d8bf52fd8).
  These establish separate custom-entry lifecycle problems; they do not establish
  a cache/new-assignment defect on the user's current KDE version. Bugzilla access
  was proxy-blocked; public source/history were inspected. Record Plasma/Frameworks/
  Qt versions and the three launch outcomes before attributing this to KDE caching.
- Native panel activation remains deferred: KDE's default applet activation
  changes expansion outside OPM's launcher-close handshake. This follow-up does
  not add a competing activation path.

## AppGrid desktop flash

Record Plasma, Qt, AppGrid version/animation, session type, panel edge, scale and
screen arrangement. Keep the same settings for both comparisons. Select the
same AppGrid instance in Configure; first leave its original button visible.

Start a narrowly filtered capture in a local terminal:

```bash
journalctl --user -f -o short-monotonic _COMM=plasmashell |
  rg --line-buffered 'Open Power Menu: (AppGrid trace|launcher visibility:)' |
  tee "$HOME/opm-appgrid-trace.log"
```

Press Ctrl+C to finish. The shared AppGrid trace sequence orders host and bridge
events; journal timestamps provide monotonic timing. Logs record epochs, pending
callbacks, requested menu, grid/window state, window activity, masking status,
input-mask apply/restore and a draft-present boolean. They omit layout contents,
command arguments, app titles and file paths. Generic Kickoff/Kicker do not emit
AppGrid traces. Existing visibility observations remain read-only.

1. Open/close AppGrid **50 times directly** with its own button. Wait for each
   ordinary animation to finish; note each flash's iteration/time.
2. Repeat **50 times through OPM** at the same pace. First use the visible-original
   state, then enable hiding through Configure and repeat through OPM. Do not
   change AppGrid settings or remove either widget.
3. Repeat rapid successive clicks; Power Menu → AppGrid; AppGrid close → Power
   Menu; and immediate reopen during a close animation. Note these separately
   from the ordinary-paced comparison.
4. Retain an unfinished unlocked draft during these switches. Verify its order,
   selection and scroll position survive and no command runs or save occurs.
5. Repeat on X11 if available. Check Kickoff/Kicker switching separately.

Around a flash, compare `left-request`, `activation-callback`, `grid-open`,
`window-visible`, `window-active`, `dismissal`, and `input-mask-*`. A callback with
an older epoch should produce no activation. A visibility drop while `gridOpen`
stays true is different from a close/reopen. If direct AppGrid also flashes,
retain that comparison when investigating upstream animation/compositor behavior.

### Findings and remaining risk

AppGrid 1.9.6 [closeWindow](https://github.com/xarbit/plasma6-applet-appgrid/blob/v1.9.6/package/variants/center/main.qml)
calls `closeGrid()` even when `gridOpen` is already false.
[GridWindow](https://github.com/xarbit/plasma6-applet-appgrid/blob/v1.9.6/package/contents/ui/views/GridWindow.qml)
starts a close animation whose completion hides the window. The default
[ScaleAnimation](https://github.com/xarbit/plasma6-applet-appgrid/blob/v1.9.6/package/contents/ui/animations/ScaleAnimation.qml)
does not cancel its close animation on reopen.

OPM previously called closeWindow again on an already-closed launcher, including
the delayed right-click follow-up. It now only finishes hiding a still-visible
closing window and never restarts that redundant animation. The AppGrid open signal
also occurs before showGrid finishes; a guard-triggered close now waits one event
loop turn, checks its epoch, and avoids reentering that open call. Generic launcher
behavior and all timer durations remain unchanged.

Models reproduce and guard these lifecycle defects across 50-cycle scenarios,
rapid requests, stale callbacks, hidden/visible originals and drafts. The cloud
cannot reproduce the desktop flash itself. Rapid reopening during a *legitimate*
AppGrid close animation can still exercise upstream animation overlap; input-mask
and native focus transitions also require the live trace. No AppGrid configuration,
animations or widget ownership are changed, and no longer delay is introduced.
