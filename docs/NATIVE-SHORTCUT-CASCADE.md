# Native Meta+X and single-pane layout editing

## Native Plasma shortcut

On the first run of each Open Power Menu Start Button widget instance, OPM
attempts to assign Meta+X through Plasma's native global shortcut API. A
persistent widget flag prevents later restarts from overwriting a customized
or deliberately cleared shortcut. Existing shortcuts are preserved, and KDE
owns shortcut conflicts. If an older application binding already uses Meta+X,
remove that binding and assign the combination in the widget's Keyboard
Shortcuts settings.

KDE registers widget shortcuts under per-instance actions such as
`activate widget 42`. Removing a widget normally starts an Undo grace period,
so a shortcut can remain assigned temporarily even though the button is gone.
OPM now listens for Plasma's explicit `destroyedChanged(true)` signal and
clears **only that widget's** global shortcut immediately. Undo restores the
prior key if it has not been reassigned. Ordinary Plasma exits, UI reloads,
and reinstalling OPM do not invoke this cleanup. Existing orphaned actions
from builds before the fix may still need manual removal in System Settings
→ Keyboard → Shortcuts; OPM never edits or steals another widget's binding.

The Plasma `activated()` signal routes through OPM's existing panel-attached
menu and launcher handoff. The standalone `open-power-menu` command remains
available for diagnostics. OPM does not edit KWin shortcut files.

## Original single-popup editor restored

Layout editing uses the original PR #5 spring-loaded navigation, not a
split-pane editor or floating submenu. The normal-use menu's SideFlyout.qml
is unchanged.

- Unlock the Power User Menu to edit its layout.
- Drag an item over the **center** of a submenu row and hold briefly (default
  450 ms); the submenu replaces the current level **inside the same popup**.
- Continue holding the item while navigating deeper. Release it on a row or in
  the list footer to place it, subject to existing menu-safety checks.
- Inside a submenu, the **full-width, 48 px Go Back strip at the top** acts as
  both a click target and a drag-hover target. Hold the dragged item there to
  navigate one level up, then continue dragging or drop it. The strip shows
  **Top level** and is disabled at the root.
- Briefly crossing a submenu or Go Back does not navigate. An invalid drop
  stays invalid; a full parent menu can still be traversed to reach another
  destination.
- The original in-window MouseArea keeps the pointer grab until release; no
  `Drag.Automatic` cross-window drag is initiated. Wheel scrolling during
  dragging, Escape cancellation, Save and Cancel remain available.
- A suspended or dismissed popup retains the draft; layout changes are saved
  only when the user explicitly selects Save layout.

Experimental split-pane and floating editing flyouts were retired after live
Wayland feedback. Normal-use flyouts are unaffected; layout editing remains a
single in-window drag operation, and native Meta+X is configured separately.

## Acceptance checks

On a real Plasma 6 Wayland session, confirm that dragging over a submenu opens
its full contents without spawning a second window, and that dragging an item
onto the far-right side of Go Back opens the parent without dropping the item.
Repeat through two submenu levels, reorder top-level items, try Escape to
cancel and verify Save/Cancel. Check Meta+X independently. Headless Qt tests
cover menu transitions, the full-width top area and pointer release, but cannot
prove live Wayland pointer behavior.
