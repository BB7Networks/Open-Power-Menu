# Shortcut and AppGrid live diagnostics

These checks originated in Manjaro Plasma 6 development testing. GitHub
Actions provides portable and offscreen Qt coverage, but no full Plasma, KWin
or native Wayland desktop session. Use these local comparisons for
desktop-specific focus or shortcut behavior. Nothing requires restarting Plasma.

## Meta+X: native panel shortcut versus standalone diagnostics

**Current behavior:** Meta+X belongs to the **Open Power Menu
Start Button widget** using Plasma's native shortcut API. The former
**Configure → General → Set up Meta+X…** wizard was removed. The installed
standalone application remains available for diagnosis, but assigning it
Meta+X *as well* can create a conflict with the widget.

### Check the native widget shortcut first

1. Add OPM to the desired panel and verify right-click opens its menu from
   that button. On a newly created widget with a free binding, OPM attempts
   to assign Meta+X once; a second press should close the panel-attached menu.
2. Open **System Settings → Keyboard → Shortcuts** and search Meta+X.
   KDE stores widget actions under instance-specific names such as
   `plasmashell: activate widget 42`. If Meta+X opens at an old panel location,
   check whether an old or removed widget still owns the key.
3. Clear **only the obsolete OPM binding**, Apply, then assign the combination
   to the current widget through its native Keyboard Shortcuts settings.
   Do not edit `kglobalshortcutsrc` by hand or take over another app's binding.
4. Test removal and re-add promptly. OPM clears the removed widget's own
   shortcut as soon as its removal lifecycle signal arrives. Undo should
   restore the previous assignment where available. Changing/disabling the
   shortcut must survive ordinary Plasma reloads and reinstallations.
5. Record distribution, Plasma/Qt/KWin versions, screen arrangement, panel
   edge, AppGrid/Kickoff choice, active widget ID and the result of left-click,
   right-click and Meta+X separately. Headless CI cannot verify delivery.

See [native widget lifecycle and Go Back](NATIVE-SHORTCUT-CASCADE.md).

### Check standalone menu startup separately

1. Install the complete package using `bash install.sh`. If `XDG_BIN_HOME`
   differs from the default, use your installed binary path instead of the
   examples below:

   ```bash
   ~/.local/bin/open-power-menu --check
   ~/.local/bin/open-power-menu
   ~/.local/bin/open-power-menu --diagnose-launch
   ```

   `--check` validates configuration without starting Qt. The plain command
   opens the standalone menu. `--diagnose-launch` records bounded startup,
   exposure, visibility and focus information (`OPM_LAUNCH` records);
   a started process alone does not prove a visible window.

2. Use the diagnostic output to separate an executable/import failure from a
   popup visibility/focus failure. Traces contain no menu titles or arguments,
   but review output for local paths before sharing.

   | Observation | Next check |
   | --- | --- |
   | Executable missing / FailedToStart | Reinstall and inspect path and permissions |
   | `configuration-error` or `--check` failure | Recover the configuration |
   | Qt, import or platform error | Verify dependencies in the actual user session |
   | `cli-start` but no exposed window | Check native Wayland/X11 popup and focus |
   | Exposed but not active | Check compositor placement and activation |
   | Standalone opens; Meta+X doesn't | Check the **widget's** shortcut owner, not the standalone launcher |

3. Only if deliberately testing a **separate Application shortcut**, use KDE's
   `org.openpowermenu.desktop` entry with a *different unused combination*.
   This path opens the standalone saved menu at a compositor-controlled
   location, not the panel-attached widget or an unfinished layout draft.
   Keep this fallback distinct from the native widget shortcut.

4. On Wayland check visibility, focus, Escape, submenu navigation, selection
   and outside-click dismissal; repeat on X11 when available. Native panel
   placement and standalone placement are different test cases.

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
- **Historical PR #5 finding:** native applet activation used to change
  expansion outside OPM's launcher-close handshake. OPM now routes the
  Plasma widget's activated() event through the guarded OPM handoff. Its
  actual Wayland shortcut dispatch and instance-removal behavior still need
  live verification.

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
