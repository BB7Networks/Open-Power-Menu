# Open Power Menu changelog

## Unreleased - default actions and development review

- Prefer KSystemLog for System Logs; retain warning-priority journal output with
  a live 1,000-line terminal fallback and per-candidate dependency checks.
- Add Printers to new defaults and the built-in selector, preferring an installed
  KDE Print Manager module before system-config-printer. Preserve saved layouts.
- Reap exited backend children and detach launched applications' standard streams;
  retain argv execution, detached sessions and normal user permissions.
- Prevent automatic backup collisions from overwriting files or following symlinks.
- Validate loaded menu trees; preserve literal picker arguments, improve localized
  desktop-entry parsing and reject unsupported fallback launch semantics.
- Add real offscreen Qt/D-Bus, lifecycle, isolated installer and archive checks.
- Refresh the README, add a real screenshot capture plan, and document process
  accounting findings, recovery, live acceptance and the separate Store roadmap.

## Unreleased - configurable configuration backup retention

- Keep the latest 10 timestamped configuration backups by default.
- Add Configure -> General -> Configuration backups with a 0-1000 limit.
- Keep manual backups and preserve existing history when backups are disabled.
- Only prune automatic backups after an atomic save succeeds.

## 0.4.17 - menu editor onboarding

- Add a searchable installed-application chooser, reading standard XDG desktop
  entries and launching them using the native KDE desktop-file handler.
- Show the active built-in command plus ordered fallback commands and availability.
- Add a non-destructive "Customize this command" conversion from built-in to
  custom command (never modifies built-in definitions).
- Include command previews in the menu tree, executable browse, and examples.
- Preserve the existing JSON menu format and existing General/Layout settings.
- Keep the field-tested 0.4.16 widget QML and launcher integrations unchanged.
- Correct version labels for the installer, widget, CLI and service.

---

## 0.4.16 — Native Power-to-Launcher focus handoff; read-only flicker tracing

- Fix a probable KDE popup focus race when switching from open Power User Menu
  to a native launcher: close Power Menu first, then wait 140 ms before the
  selected launcher's activation signal so focus teardown cannot immediately
  hide the new popup. Normal left-click retains existing one-turn activation.
- Use the existing request epoch to cancel a stale deferred activation on a
  newer right-click, and avoid a second activation when a Meta shortcut has
  already opened the selected launcher during the handoff.
- Observe (do not override) generic launcher `status`, panel container/item
  visibility, and expanded state during changes. This traces the brief Kickoff
  duplicate-icon flicker even when no previous hide-repair log was emitted.
- Do not alter AppGrid's proven Wayland input pass-through, adapter dispatch,
  `HiddenStatus` reversible binding, menu editor or user configurations.
- 120 portable tests / 11 subtests passing; live Plasma timing requires user
  acceptance and the new logs are diagnostic, not proof of a flicker fix.

## 0.4.15 — Synchronous generic hide guard for native launcher flash

- Reassert the existing `HiddenStatus` Binding in the same `statusChanged`
  call stack instead of deferring to the next QML event turn. A reentrancy
  guard protects against a nested status signal; an asynchronous retry is
  retained only if binding evaluation is deferred by Qt.
- Avoid re-traversing the panel scene every five seconds for an unchanged,
  still-selected and still-present launcher. Polling still verifies the exact
  selection via the generic Plasma applet list; a missing/replaced launcher
  goes through the existing safe fallback.
- Keep the 2.5-second retry budget, with a higher safety cap to avoid hiding
  failure during rapid legitimate menu toggles. The guard restores the original
  launcher if status changes are persistently incompatible.
- Leave AppGrid-specific adapters, widget hiding mechanism, icon selection,
  menu entries, editor and Plasma panel configuration unchanged.
- Portable tests verify immediate repair, nested notifications, stale retry
  invalidation and generic launcher selection. Actual panel rendering still
  requires confirmation on Manjaro/Wayland.

## 0.4.14 — Native Plasma launcher icon stability

- Address intermittent reappearance of the original launcher button when
  opening standard Plasma launchers such as Kickoff. The five-second editor
  preference refresh now **keeps an existing hide binding on the same applet**
  instead of releasing/recreating it when a popup transition temporarily
  makes the old item/container visibility check fail.
- If native code or the launcher changes the applet's `status`, a guarded
  `statusChanged` connection schedules re-evaluation of the same reversible
  HiddenStatus `Binding` instead of writing `status`, `visible`, or panel
  layout properties imperatively. Reassertions are bounded to avoid fights
  with incompatible widgets, and queued work is invalidated on unhide/switch.
- Preserve all known-good AppGrid Center 1.9.6 Wayland panel pass-through,
  applet hiding setup, adapter routing, menu editor and user JSON. No changes
  to Plasma's panel config, AppGrid, or KDE's launchers.
- Add portable executable Node tests for transient popup visibility, external
  status override, stale repair callbacks and bounded fallback. Confirm on a
  live Manjaro Plasma 6 desktop; QML's runtime binding behavior cannot be
  fully emulated by the test harness.

## 0.4.13 — Extract launcher adapters (no new user-facing features)

- Preserve the existing generic same-panel Plasma launcher selection,
  `activated()` signal, icon inheritance, and reversible `HiddenStatus` mask.
- Route native popup operations through `adapters/LauncherAdapters.js`:
  `PlasmaLauncher.js` handles Kickoff, Kicker, and all unrecognized plugins;
  `AppGridLauncher.js` handles only `dev.xarbit.appgrid` Center.
- Move the proven AppGrid 1.9.6 full-screen panel input pass-through into
  `AppGridPanelBridge.qml`. Its rectangle geometry and safety checks remain.
- Keep optional AppGrid standalone D-Bus `NameHasOwner` / `Hide` inside the
  AppGrid adapter, not the generic widget; never start an absent daemon.
- Reduce the host main.qml by roughly 190 lines; preserve menu visuals,
  configurations, editor tabs, flyouts, and safe-release behavior.
- Expanded Node/Python tests verify adapter dispatch, no cross-launcher
  window manipulation, request cancellation, input-region restoration,
  import paths, and unchanged user data. Live Wayland acceptance pending.

## 0.4.12 — Two-tab Configure editor and compatibility audit

- Reorganize the graphical Configure editor into **General** (launcher picker,
  reversible button hiding, inherited/custom icon with preview, menu style) and
  **Layout** (menu tree, nested submenus, add/edit/remove/move, unavailable items).
- Keep Save and Cancel outside both tabs. The Layout reset now resets **only**
  the unsaved menu layout and unavailable-entry setting, never launcher/icon/
  appearance preferences.
- Keep the launcher picker enabled even if its original button is visible;
  choosing the exact launcher also affects direct left-click and icon inheritance.
- Remove the obsolete standalone D-Bus probe from AppGrid Center 1.9.x's
  in-process close branch. Keep the separate-process D-Bus `Hide` fallback only
  for AppGrid builds that do not expose the in-process window. No other
  launcher/window state is modified by this optimization.
- Preserve the live-proven v0.4.11 status Binding, input-region pass-through,
  popup/flyout QML, icon adoption, and custom menu format without modification.
- Document the code audit and launcher-agnostic compatibility boundaries in
  `AUDIT.md`.

## 0.4.11 — Allow panel clicks through AppGrid 1.9.6's full-screen overlay

- Diagnose the missing right-click callback: AppGrid's full-screen overlay
  intercepts the pointer before OPM receives the click.
- Use AppGrid's **existing** `setInputRect(QWindow*,x,y,w,h)` to exclude a safe
  edge strip covering the Plasma panel while AppGrid is open. This method was
  verified in the v1.9.6 source; no AppGrid files or preferences are edited.
- Only enable the adapter for a selected, hidden `dev.xarbit.appgrid` launcher;
  refuse a different screen or a mask that overlaps the centered AppGrid grid.
- Restore normal pointer input on launcher close, opt-out and widget teardown;
  defer to AppGrid while drag-and-drop is active.
- Log explicit delivery of the Start button's right-click and mask changes.
- Align the CLI/package metadata version strings, which lagged prior releases.

# Changelog

## Unreleased - editor usability and recovery

- Add validated drag-and-drop between submenus, independent Duplicate, Qt
  Undo/Redo, keyboard movement, context actions and selection-aware controls.
- Track unsaved General/Layout changes and offer Save / Discard / Cancel on close.
- Detect externally changed, replaced or deleted configuration files; provide
  reload or explicit overwrite with an independent recovery copy.
- Add General → Manage backups with local timestamps, validity, non-executing
  previews and atomic restore, including recovery from corrupt active JSON.
- Preserve pre-restore/pre-overwrite copies even with automatic retention off;
  reject symlink paths and preserve the restore source and manual backups.
- Keep five widget snapshots by default, independently configurable through
  `OPM_WIDGET_BACKUP_RETENTION`. Migrate old history to a separate recovery
  directory, prune only after successful installation, and preserve it on uninstall.
- Extend offscreen Qt, configuration safety and installer failure regression
  coverage. Launcher QML, command selection and detached process behavior stay
  unchanged; live Manjaro Plasma 6 Wayland acceptance remains required.

## 0.4.10

- For the compiled in-process AppGrid 1.9.6 variant, call its native
  closeWindow() and immediately hide the owned GridWindow if it remains visible
  during a close animation, so a new Power Menu does not overlap it.
- Record state before and after launcher activation/dismissal, rather than
  logging only the already-mutated after-state.
- Observe the selected AppGrid root's gridOpenChanged signal for diagnostics.
- Keep existing launcher hiding, icon inheritance, configuration, and
  adaptive flyouts unchanged. Existing saved menus are preserved.


## 0.4.9

- Stop treating a false local AppGrid `gridOpen` as proof that the visible
  AppGrid window is closed. Call the idempotent `closeWindow()` method when
  available, and probe for the actual standalone daemon.
- `NameHasOwner` checks the bus before using the non-toggling D-Bus `Hide`,
  avoiding unwanted D-Bus activation.
- Wait for a successful owner check/Hide response; cancel stale callbacks after
  subsequent left/right clicks and log the outcome for live diagnosis.
- Preserve the proven `HiddenStatus` hide, icon adoption and all existing UI.


## 0.4.8 - Same-instance launcher handoff

- Match left-click activation to the exact launcher widget configured for
  right-click dismissal. Avoid Plasma global launcher selection across panels
  and screens when a target is known.
- Prefer selected `Plasma::Applet.activated()` (the same signal Plasma emits in
  its own global activation). Fall back to global activation only if no explicit
  target is configured.
- Preserve all v0.4.7 visual behavior, icons, menu editor, HiddenStatus and
  safe recovery; improve logs for source-instance mismatch.

# Changelog

## 0.4.7 — Wait for original launcher to close before opening Power Menu

- Fix the 0.4.6 handoff design: right-click no longer opens Power Menu immediately after merely *requesting* closure. AppGrid 1.9.x can have `gridOpen=false` while its standalone-in-QML GridWindow is still visible during animation. The handoff waits until that window is no longer visible.
- If an older AppGrid close method fails or is inaccessible, fall back to its standard `activated()` signal **only when the window is positively known to be open**. This avoids accidentally opening a closed launcher.
- For newer daemon-based AppGrid, wait for its idempotent `Hide()` D-Bus reply before opening Power Menu. Stale replies from superseded clicks cannot change newer requests.
- Keep the latest-click-wins generation guard; a second right-click cancels a pending right-click, and left-click cancels pending Power opening. A close that never completes results in a visible diagnostic rather than two open menus.
- Add close-strategy and state diagnostics to the Plasma journal to make further compatibility failures actionable.
- Do not modify any saved panel/app launcher settings. Preserve the proven HiddenStatus hiding, icon inheritance, menu editor and existing flyouts.
- Automated QML-JS tests simulate the original window remaining visible throughout its close animation. Live Plasma/Wayland acceptance is still required.


## 0.4.6 — Close custom launcher windows on right-click

- Fixed v0.4.5 right-click not closing AppGrid Center v1.9.x: it uses a separate QML GridWindow with `gridOpen` and `closeWindow()`, not the normal `expanded` popup. Close it using its existing, non-toggling method.
- For AppGrid builds using a standalone daemon, request `dev.xarbit.appgrid.Standalone.Hide` over session D-Bus; do not guess at window titles or kill processes.
- Observe legacy `gridOpenChanged` to handle Meta and delayed launch activations.
- Preserve existing HiddenStatus launcher hiding, icon matching, flyout behavior, and safe configuration.


## 0.4.5 — Exclusive menus and launcher icon matching

- Right-click closes the selected launcher's standard Plasma popup (via its live AppletQuickItem `expanded` property) before showing Power User; left-click closes Power User and its flyouts before delegating to Plasma. A rapid-click generation guard prevents an unsent left activation from reopening the original after right wins.
- Listen to the original launcher's `expandedChanged` event to dismiss Power User when the original opens through another route, including Meta.
- Prefer the selected launcher's live Plasma icon for Open Power Menu's visible button. Offer custom icon mode through the native menu editor, with theme-name entry, local image picker and preview.
- Validate new `button_icon_mode` and `button_icon` settings, transport through existing GetIntegration, retain existing saved menu and widget-icon fallback.
- Preserve v0.4.4 native HiddenStatus integration, v0.4.1 content-sized popup, v0.3.4 adaptive and bottom-aligned flyouts.


## 0.4.4 — Plasma-native HiddenStatus integration and configuration-page repair

- Use KDE panel's own `HiddenStatus` instead of fragile opacity / one-pixel size bindings. The status-binding is reversible; the panel itself hides the applet item and the layout container. This directly addresses the reported v0.4.3 failures for AppGrid widget 59 on panel 2.
- Keep opt-in launcher ID selection and same-panel checks. Verify that the entire container hides; fail visibly and safely if it does not.
- Correct widget configuration root properties (`title` and `cfg_*Default`) to avoid the reported configuration warnings.
- Retain existing custom menu JSON, popup sizing, adaptive flyouts, original launcher, and recovery option. Actual Wayland AppGrid popup position remains unverified.


## 0.4.3 — Launcher-independent selection and reversible Qt bindings

- Replace the AppGrid-only matcher with a picker for any panel launcher applet ID; auto-detect a unique known launcher or explicitly select a third-party launcher.
- Read existing Plasma panel applet IDs read-only and list them via `--launcher-diagnostics`.
- Work around Plasma 6's absent QML-root parent chain by searching the same window scene for its ContainmentItem, validating the source panel and applet instance.
- Switch direct size/opacity writes to conditional Qt Bindings, preserving the original widget's layout expressions when the checkbox is cleared.
- Verify that masking applied, otherwise leave the original button visible with an error tooltip.
- Preserve v0.4.2 settings, v0.4.1 popup sizing, working flyouts and one-click launcher delegation.
- Experimental: live Plasma 6 / Wayland behavior remains unverified.

## 0.4.2 — Reversible, experimental original AppGrid button hiding

- Add an opt-in check box in the existing Qt Configure editor to hide/unhide the old AppGrid panel button.
- Add a guarded, same-panel Plasma AppGrid adapter: no applet removal, plugin patch, panel file edits, or side-panel relocation.
- Hide compact presentation by setting icon opacity to zero and limiting the original layout slot to one pixel; preserve and restore the runtime values on unhide/destruction.
- Detect unsupported or ambiguous source widgets and refuse to hide anything in those cases.
- Add a read-only GetIntegration D-Bus method and automatic widget refresh of visibility preference.
- Add an emergency `--show-launcher-button` recovery command and tests for safe config saves, refusal and runtime undo.
- **Experimental:** does not claim certified compatibility with all AppGrid/Plasma panel versions; requires live testing.


## 0.4.1 — Remove unused bottom space

- Size the primary Plasma popup to the **visible menu content** rather than a 590px fixed preferred height. The content scrolls only when taller than the screen-safe limit.
- Keep the existing upper-right icon controls and untouched v0.3.4 cascading flyouts.
- Add a user-local panel snapshot helper to make the one-button launcher experiment reversible, without editing any panel configuration.
- Document that the delegated launcher might open from its original widget position when moved to a secondary panel; this remains a live-session experiment, not an automatic hide feature.

## 0.4.0 — Configuration and launcher integration preparation

- Move Refresh and Configure to icon-only controls at the right of the popup header.
- Configure now opens a full graphical menu editor with add/remove/edit/reorder, nested sections, and safe custom argument commands.
- Add backup + atomic save for menu.json with validation.
- Make Network Locations opt-in for new users without changing any existing personal menu.
- Add D-Bus Edit method, CLI `--edit`, and safe upgrade-time restart of only our own backend process.
- Retain v0.3.4's bottom-aligned, adaptive left/right flyouts unchanged.
- Keep AppGrid delegation unchanged; document a reversible one-visible-button experiment rather than automatically tampering with another widget's configuration.

## 0.3.4

- Align bottom of side flyouts with their parent row while respecting screen bounds.

### Packaging correction (Windows Git checkout)

- Moved lower-case installation scripts into `scripts/*-core.sh` to prevent
  Windows case-insensitive filename collisions with `install.sh` and `uninstall.sh`.
  No widget or application-runtime behavior changed.
