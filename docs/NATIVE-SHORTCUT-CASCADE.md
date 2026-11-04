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
