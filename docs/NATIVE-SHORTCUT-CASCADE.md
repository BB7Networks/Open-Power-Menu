# Experimental Plasma-native Meta+X

This branch does **not** assign Meta+X automatically. KDE owns shortcut
conflicts and the user must opt in through the **Open Power Menu Start Button**
widget's Keyboard Shortcuts setting. Remove the old OPM application shortcut
before binding the same key to the widget.

The widget's Plasma `activated()` signal routes to the existing OPM
`openMenu()` handoff, preserving the selected launcher's close sequence and
panel positioning. Plasma's default activated handler eagerly sets expanded
true; `activatePowerShortcut()` deliberately resets that state when OPM has
not actually requested the Power menu.

The standalone `open-power-menu` application remains usable separately.
No change to `menu.json`, KDE shortcut files, or KWin configuration.

**Live acceptance required:** Meta+X must open the panel-attached Power User
Menu; a second press should close it. Test AppGrid visible/hidden, drafts,
fast switching, and launcher focus on Plasma 6 Wayland and X11. Automated
tests cannot validate KGlobalAccel or native popup placement.

## Cascading drag-and-drop preview

While the menu is unlocked, selecting or hovering over a submenu opens an
adjacent pane inside the **same Plasma popup**. The unchanged saved-menu model
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
