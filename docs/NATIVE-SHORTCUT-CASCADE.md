# Experimental Plasma-native Meta+X

On first run, each Open Power Menu Start Button widget instance attempts to
assign Meta+X through Plasma's native global shortcut API. A persistent widget
flag prevents later restarts from overwriting a user-customized or deliberately
cleared binding. Existing nonempty shortcuts are preserved. KDE handles
conflicts without taking a shortcut from another application. If an older OPM
application shortcut already claims Meta+X, remove it and use the widget's
native Keyboard Shortcuts setting to select Meta+X.

The widget's Plasma `activated()` signal routes to the existing OPM
`openMenu()` handoff, preserving the selected launcher's close sequence and
panel positioning. Plasma's default activated handler eagerly sets expanded
true; `activatePowerShortcut()` deliberately resets that state when OPM has
not actually requested the Power menu.

The standalone `open-power-menu` application remains usable separately.
OPM does not edit `menu.json`, shortcut files, or KWin configuration directly; KDE persists its native widget shortcut as usual.

**Live acceptance required:** Meta+X must open the panel-attached Power User
Menu; a second press should close it. Test AppGrid visible/hidden, drafts,
fast switching, and launcher focus on Plasma 6 Wayland and X11. Automated
tests cannot validate KGlobalAccel or native popup placement.

## Floating layout-edit flyouts

The unlocked editor stays a normal-width menu. Clicking or hovering over a
submenu opens a **separate, row-anchored Qt Popup.Window** beside that item,
instead of widening the parent into a fixed split-pane layout. The flyout
adapts to available space on either side and clamps vertically to the
source screen. Nested submenus advance the focused parent/child level.
Normal locked-menu flyouts are unchanged.

The flyout remains visible when the pointer crosses into the child popup
and dismisses after a short grace interval when it leaves both the parent
row and flyout. Closing the main popup also closes its editing flyout,
without discarding the unsaved draft.

Cross-window reordering uses Qt's native drag/drop with opaque, current-
session item IDs and validation through the existing layout move rules.
If a native Wayland drag between popup windows does not work on the user's
compositor, the editor's Move into submenu command and single-pane
fallback remain available. For cross-window moves, open the submenu
before beginning the drag. No menu commands execute during editing.

**Physical acceptance remains required:** actual KWin/Wayland popup placement,
hover persistence, focus, close/reopen, multi-monitor and fractional scaling,
drag in both directions, and right-edge panel use cannot be established by
headless Qt tests alone.

## Optional single-pane fallback

In the Plasma widget's **General** configuration, uncheck **Show adjacent
submenu while rearranging** to return to the proven navigation-based editor.
This is a widget-only preference; it does not alter or migrate menu.json.
