# In-menu layout editing

This guide covers the current layout editor in the **0.4.17 source code**.
It combines full-row dragging, spring-loaded submenu navigation, a full-width
**Go Back** drop area, configuration recovery and native widget Meta+X.
The features are in the development source but **not yet a published GitHub
release**. No configuration migration is required. Some detailed validation
notes below record earlier development work; live Plasma acceptance remains
important, especially for Wayland pointer handling.

## What the interface looks like

These are descriptions of the implemented UI, not screenshots:

- **Configure:** General | Layout | Backups. Layout starts with four short
  instruction bullets. Editing actions sit below the tree, with Undo/Redo on
  the right; the toolbar wraps at smaller widths. Backups contains the 0–1,000
  configuration-retention control (default 10), **Manage / Restore Backups…**,
  and a separate widget snapshot path/count/default-five explanation, refreshed on tab visits.
  The backup browser can permanently delete one selected backup after confirmation.
  General includes a separate selectable monospace Emergency Restore command
  with Copy. Native Meta+X is initialized by the widget itself on first run;
  the old standalone shortcut setup wizard has been removed.
- **Locked menu:** the header has Lock, Refresh and Configure icons. Normal
  commands and hover flyouts work here. Native flyouts use the KDE color scheme;
  optional Aero retains its dark background and readable light foreground.
- **Unlocked menu:** a single list shows every entry at the current level,
  including unavailable commands, separators and empty submenus. Entire rows are
  draggable, with a ghost and insertion/destination highlighting. Back navigates up.
  Right-click/Shift+F10 and Alt+Arrow provide accessible movement. **Save layout**
  and **Cancel** remain visible beneath the list.

Click the lock to start. Open a submenu to rearrange its contents. Moving a
submenu preserves its entire subtree. This mode changes positions only; use
Configure to add, remove, rename or edit commands and icons. Clicking an entry
or pressing Enter while unlocked never launches its command.

Drag from any part of a row. Qt's normal movement threshold distinguishes dragging
from clicking; moving a submenu carries every child. The top/bottom edges of a row
insert before/after it. Its center is a submenu destination: a short drop appends
inside, while a **450 ms hover** opens its contents without releasing the pointer.
Hold a dragged item over the **full-width Go Back strip** at the top of a nested menu to open its parent; repeat through several levels. The same strip works as a normal click target, and shows **Top level** when there is no parent.
Briefly passing over a submenu does not open it. Invalid drops show a red ghost
and are canceled; Escape or popup interruption restores the source view.

This is **spring-loaded navigation inside one native popup**, not dragging between
separate flyout windows. One stable pointer surface survives changes of level.
Locked-mode native flyouts and their placement are unchanged. Wheel and edge scrolling work
in long lists. A full parent can be traversed to reach another submenu even when
dropping another sibling into that parent would exceed the 200-entry limit.

The user confirmed full-row dragging and submenu-hover navigation passed live
Wayland checks before the redundant movement rows were removed. Back, Save layout,
Cancel and the header lock remain. Alt+Up/Down reorder, Alt+Left moves out, and
Alt+Right opens a keyboard-operable destination menu. Right-click, Menu, or
Shift+F10 exposes the same movement actions.

During dragging, the list is deliberately noninteractive to preserve the pointer
grab. The pointer handler now consumes wheel input explicitly, preferring pixel
deltas over angle deltas and clamping to the current list's bounds. It recomputes
the drop target without moving the ghost, releasing the grab, or saving. Qt Quick
may suppress zero-angle compatibility ScrollUpdate events; device-generated
touchpad behavior remains part of live acceptance.

## Keeping your place

The previous JavaScript array model was replaced after every move, which reset
ListView state and rebuilt its delegates. The view now updates a stable ListModel
by opaque item ID and moves existing delegates for same-level edits. Each visited
menu remembers its top visible item, relative pixel offset and selection in the
in-memory draft. This handles changing row indexes and ListView's shifting origin.

After a move, the viewport restores that anchor and reveals the selected item
only as needed. Keyboard focus stays on the editor. New submenus start at the top;
returning to a visited menu restores its previous view. Popup destruction and
recreation can restore the same state from the retained draft. These view caches
are excluded from saved layout references and from dirty-state comparisons.

## Save, cancellation and recovery

**Save layout** validates the complete hierarchy, checks for outside changes,
uses the existing backup policy and atomically saves. Success locks and refreshes
the menu. An unchanged layout creates no file or backup. **Cancel** discards the
draft and refreshes from disk without saving or creating a backup.

Clicking the lock with a modified draft asks you to use Save layout or Cancel;
it does not discard changes. Closing the popup, switching to the original
launcher, or interrupting a drag keeps the draft in the applet for the next
right-click. Escape cancels an active drag first. There is no modal confirmation
window competing for Plasma focus.

An external edit, unsafe configuration, failed write or unavailable backend
leaves the draft visible. A conflict requires Cancel and a fresh unlock to load
the newer file; there is no overwrite option in this smaller interface. A
backend restart invalidates its session: the draft remains visible, but Save is
disabled after the restart is detected, with instructions to cancel and unlock
again. Temporary transport failures can be retried while the session survives.

Drafts are in memory, not persistent recovery files. Removing/reloading the
widget or restarting Plasma loses an unsaved draft. Use Save layout before such
actions. Configuration restoration in Configure is blocked while any editor tab
has unsaved changes; preview remains available. See [recovery](EDITOR-RECOVERY.md).

Command launch failures stay visible in the locked menu or OPM button tooltip,
without echoing private arguments. An unavailable backend points to
`open-power-menu --check` and the complete `bash install.sh` installation.
Successful process creation is treated as success; normal later exit codes do
not produce alerts. The detached application-launching implementation is unchanged.

## Keyboard controls

| Context | Keys | Action |
| --- | --- | --- |
| Locked menu/flyout | Up / Down | Select an enabled entry; skip separators |
| Locked menu/flyout | Enter | Launch selected command or open submenu |
| Locked menu/flyout | Right | Open selected submenu |
| Flyout | Left / Escape | Close that level and return focus to its parent |
| Main locked menu | Escape | Close the popup |
| Unlocked list | Up / Down | Select any entry, including hidden/separator entries |
| Unlocked list | Alt+Up / Alt+Down | Reorder the selected entry |
| Unlocked list | Enter / Right | Open the selected submenu; commands remain inactive |
| Unlocked list | Left | Return to the parent level |
| Unlocked list | Alt+Left | Move the entry out, after its parent submenu |
| Unlocked list | Alt+Right | Choose a destination submenu using arrows and Enter |
| Unlocked list | Menu / Shift+F10 / right-click | Open the movement context menu |
| Unlocked list | Escape | Cancel drag, otherwise go back a level, otherwise close and retain draft |
| Unlocked controls | Tab / Shift+Tab | Reach Back, Save and Cancel |
| Configure | Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y | Existing layout Undo/Redo; scoped to Configure |

Menu selection and drag insertion points are visible. Buttons have accessible
names and tooltips. Native screen-reader behavior still needs desktop acceptance.

## Backend and data protection

`BeginLayoutEdit` reads the full validated configuration through the same bounded,
no-symlink reader as recovery. It creates opaque per-session item IDs and returns
only their kind, title, icon and child presentation. It never resolves or runs
commands. Normal `GetMenu` filtering is not used to construct saved layouts.

`SaveLayoutEdit(token, references)` accepts a hierarchy containing only `id` and,
for submenus, `items`. The backend retains each original definition, including
all unknown metadata, and reconstructs the menu from those references. Every ID
must appear exactly once; unknown, duplicate, missing or extra fields are rejected.
Commands, labels and icons cannot be changed through this operation. Cycles,
depth above eight submenu levels and more than 200 entries per menu are rejected.
Both configuration and request sizes are bounded by 4 MiB.

General settings and executable argument values are preserved exactly as data.
JSON is serialized by the existing writer, so original whitespace/key layout is
not promised after a changed save. Cancel and unchanged Save preserve file bytes.
Hidden commands, redundant separators and empty groups remain in the hierarchy.

The starting revision records contents and device/inode identity. Save checks it
and delegates to the existing cooperative lock, repeated revision check, backup
retention and atomic replacement. Concurrent editors cannot silently overwrite
each other. The existing caveat for external tools bypassing OPM's cooperative
lock still applies. QML never writes configuration files directly.

`CancelLayoutEdit` releases a session without writing. `KeepLayoutEdit` renews it
every 60 seconds, including while the popup is closed. The backend keeps at most
four sessions, each expiring after 30 minutes without contact. Sessions touch the
normal service idle timer. Stale callbacks cannot replace a newer widget draft.

The widget's activation guard prevents `Run` during unlocking, editing or saving;
edit IDs are not executable menu keys. Other widgets/CLI clients retain their
normal command behavior. The latest follow-up changes AppGrid close sequencing
and tracing; timer durations, generic launcher behavior, original-button masking,
icons, flyout placement and detached application launching remain unchanged.

## Native Meta+X and optional standalone diagnostics

With PR #6, the Open Power Menu **Start Button widget** attempts to register
**Meta+X once per widget instance** using Plasma's native shortcut API. It
activates the panel-attached Power User Menu rather than launching a separate
standalone window. KDE owns conflicts: OPM will not steal an occupied key.
Later user customization/removal of the key is respected across restarts
and reinstallations.

Plasma exposes per-instance actions such as `activate widget 42`.
The widget listens for the explicit removal lifecycle event and releases its
own shortcut immediately; **Undo** restores the previous assignment where
available. Removing an old pre-fix instance may have left an orphaned binding:
remove it manually in **System Settings → Keyboard → Shortcuts**. See
[native shortcut lifecycle](NATIVE-SHORTCUT-CASCADE.md) for acceptance checks.
Live KDE Wayland dispatch/removal testing is still required.

The standalone command remains useful **for diagnostics, not as the default
shortcut target**. Use `~/.local/bin/open-power-menu --check` to validate
configuration, `open-power-menu` to open the standalone saved menu, and
`open-power-menu --diagnose-launch` for bounded startup/exposure/focus traces.
The legacy application-shortcut route through KDE's
`org.openpowermenu.desktop` entry still exists for isolated testing; avoid
assigning it **the same Meta+X combination** as the widget.

Qt Wayland may reject an unparented grabbing popup. The standalone Wayland
root uses a frameless top-level QMenu with explicitly parented submenus;
X11 retains its popup path. KWin controls standalone placement and focus.
These historical fixes remain relevant to diagnosing the standalone
application independently of the widget.

See [shortcut and AppGrid diagnostics](SHORTCUT-APPGRID-DIAGNOSTICS.md) for
the source evidence and repeated-activation capture procedure.

## Verification

The latest baseline at `b236efd` passed **370 tests, 8 historical-source skips,
and 18 subtests** in 25.12 seconds. The full follow-up suite passes **393 tests,
8 historical-source skips, and 18 subtests** in 28.20 seconds (Python 3.12.14, PySide6 6.10.2,
Node 24; CI uses Node 22). The missing historical release trees remain explicit.
[PR #5 checks](https://github.com/BB7Networks/Open-Power-Menu/pull/5/checks) record
CI results for each pushed head.

Coverage includes actual Qt Widgets/Quick input, mouse and touchpad wheel events,
keyboard/context movement menus, installed-process launch outcomes, standalone
menu/submenu behavior, isolated session D-Bus, configuration/recovery failures,
installer upgrades/uninstall, path quoting, ZIP/TAR/widget archives and checksums.
The shipped AppGrid handlers run 50-cycle scenarios for each combination of
original-button visibility and retained draft, with rapid clicks and stale
callbacks. These models establish event ordering, not visual compositor behavior.
Python compilation, all seven Bash syntax checks and all changed QML parsing pass.

Cloud limitations: no Plasma shell, KDE settings tools or real Wayland/X11 session.
Installed commands are exercised in isolated XDG profiles with a stub KPackage
command. Qt exposure/focus tests run offscreen, including a forced Wayland code
branch. The source-confirmed parentless-popup defect and redundant AppGrid closes
are addressed, but the user's Meta+X failure and intermittent desktop flash cannot
be declared resolved without live checks. Full-row/hover dragging was separately
confirmed by the user; new wheel/context interactions still need desktop acceptance.
Real desktop screenshots and native screen-reader/theme behavior remain live work.

## Live Manjaro Plasma 6 Wayland acceptance

Use a disposable test profile or retain backups and a local recovery terminal.
Record Plasma, Qt, launcher and distribution versions, panel edge, display scale,
screen arrangement and theme. Do not restart Plasma while remote desktop is your
only access. Refresh the widget only through your normal local procedure.

1. Upgrade a PR #4 installation using **`bash install.sh`** from a path containing
   spaces. Compare the saved menu, launcher preferences and recovery snapshots.
2. Confirm the package contains only lowercase root installer/uninstaller wrappers;
   run `open-power-menu --check` and verify the updated backend activates.
3. Inspect all three Configure tabs at normal and narrow widths. Check concise
   instructions, right-aligned/wrapping history controls and snapshot information.
4. Reorder nested entries in Configure, Duplicate, Undo/Redo, and Save. Try restore
   with unsaved General/Layout/Backups changes and confirm nothing is discarded.
5. Right-click the OPM launcher button. Confirm locked normal behavior, then unlock; all
   commands must remain inactive under clicks, Enter and dragging.
6. Drag from row labels and empty row space, including a held submenu press. Test
   before/after insertion, whole groups, a brief pass over a submenu, a deliberate
   450 ms hover, and Back-hover through two levels. Include empty/full groups,
   invalid self/descendant destinations, edge scrolling and Escape. Near the bottom
   of a long list, repeat moves and verify the viewport, selection and focus stay
   in place. Full-row/hover checks were confirmed by the user before removing
   fallback rows; now verify right-click/Shift+F10, Alt+Arrow and the larger list.
   While holding an item, wheel up/down at top/middle/bottom and through nested
   levels; test fast input, touchpad deltas, drop/cancel and popup interruption.
7. Cancel. Compare `menu.json` bytes and backups with the pre-edit state.
8. Repeat and Save. Check the order and every definition/General setting, plus the
   prior-configuration backup according to the selected retention policy.
9. Visit and scroll a parent and child menu; return and verify their saved positions
   and selections. Close/reopen with an unsaved draft and confirm it survives. Save, then stop only
   the test backend and reopen to check persistence. Restart during a draft and
   confirm its recovery message and retained visible state.
10. Include an unavailable application, empty submenu and redundant separators.
    Confirm all remain after saving even when the normal menu filters them out.
11. Check native light/dark themes and Aero, visible focus/drop lines, tooltips and
    screen-reader labels; capture real screenshots only after validation.
12. Exercise the keyboard table above through several nested levels. Test small
    displays and fractional scaling on **top, bottom, left and right panels**,
    including screen boundaries and multi-monitor placement. Repeat hover navigation
    and drag cancellation at each position; compare locked flyouts with the baseline.
13. Use a harmless test command that records invocation; verify editing produces
    none. In locked mode check missing-executable/backend errors and successful
    launch behavior without spurious program-exit alerts.
14. Repeat Kickoff/Kicker switching. For AppGrid, follow the [direct-versus-OPM
    50-cycle procedure](SHORTCUT-APPGRID-DIAGNOSTICS.md#appgrid-desktop-flash): include
    rapid/mixed clicks, original visible/hidden, and an unfinished draft. Record
    sequence numbers around any flash; compare Wayland and X11 where available.
15. Run `open-power-menu --show-launcher-button`; verify the original launcher is
    restored. Confirm a pending draft does not interfere with launcher switching.
16. Save externally from Configure during a draft and verify conflict rejection.
    Restore a backup with retention zero and confirm its protected pre-restore
    copy. In the disposable profile, remove only OPM's widget, run
    `bash uninstall.sh`, and verify menu, backups and widget recovery history remain.
17. In a test profile, clear any stale old OPM shortcut first, then add
    the new widget. Verify native Meta+X opens next to the correct panel
    button and a second press closes it. Remove/re-add the widget promptly;
    the old per-instance shortcut must not block the new instance.
    Check the widget-removal **Undo** path restores the previous assignment,
    and customized/disabled shortcuts stay unchanged after restarting Plasma.
    Test an already-occupied shortcut without taking over another widget.
    Independently run `open-power-menu --check`, plain
    `open-power-menu` and `open-power-menu --diagnose-launch` for standalone
    diagnostics. Repeat on Wayland and X11 when practical.
18. Delete a disposable corrupt backup after confirmation; cancel another deletion.
    Verify the name/date/size and protected-copy warning. Replace a selected backup
    before confirming and check refusal. The active row must never be deletable.
    Check nearby selection afterward, preserve unsaved editor changes, and use
    return to Backups after an upgrade changes the count without closing Configure.
    Verify the configuration browser's manual Refresh still rescans. On General,
    check the separate Emergency Restore command, Copy and selection at narrow
    widths and increased scaling.

## Deferred work

- Full first-run setup wizard and automatic dependency diagnostics.
- General-purpose configuration import/export.
- Broader real-desktop acceptance of native widget Meta+X on different panel
  placements and launcher adapters; the implementation exists in PR #6.
- Search/filtering for very large menus.
- KDE Store backend installation/onboarding.
- Broader cross-distribution packaging and compatibility.

Native cross-window drag behavior can be reconsidered after live Wayland evidence.
Merging source changes does not tag, release or publish software; versioning and
live-desktop release acceptance are handled separately.
