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

## Cascading drag-and-drop preview

While the menu is unlocked, clicking a submenu or resting the pointer
on it briefly opens an adjacent pane inside the **same Plasma popup**.
The flyout remains open while moving into its child pane; it closes after
a short delay once the pointer leaves both the parent row and child pane.
Cross-pane drags suspend hover dismissal until release. The unchanged saved-menu model
remains authoritative; two visible views only move the same opaque item IDs.
Dragging between parent and child is supported with native pointer movement
and no second Wayland window or arbitrary command execution.

The menu grows to a maximum of 650 px while the flyout is open and respects
available screen width. Opening another submenu advances the two-pane view to
that level; Back remains available, and normal keyboard navigation is retained.
The right-pane scroll view remembers its position. All changes remain a draft
until Save; Cancel discards them.

**Experimental:** The editor's in-process split pane is NOT a native
cross-window Plasma flyout and still needs real Wayland acceptance, especially
on a right-edge panel, narrow display and fractional scaling. The stable PR #5
branch has not been modified.

## Optional single-pane fallback

In the Plasma widget's **General** configuration, uncheck **Show adjacent
submenu while rearranging** to return to the proven navigation-based editor.
This is a widget-only preference; it does not alter or migrate menu.json.
