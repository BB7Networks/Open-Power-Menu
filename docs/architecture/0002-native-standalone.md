# Native standalone frontend decision

Use a separate C++ Qt Widgets executable, `open-power-menu-standalone`, built
with `OPM_BUILD_STANDALONE=ON`. The Core/DBus backend remains independent of
Widgets, Gui, QML and KDE GUI frameworks. Production installation and activation
remain unchanged during development staging.

Widgets directly translates the released QMenu implementation: cascading hover
menus, keyboard navigation, accessibility, scrolling, themed icons and adaptive
submenu placement are Qt responsibilities. The existing native model supplies
normalization, availability and command resolution. A private validated config
snapshot and opaque selection keys separate command execution from presentation.
If availability changes the displayed tree, execution fails closed rather than
allowing a normalized index to select a different command.

Qt Quick could share some Plasma presentation components, but those components
depend on Plasma context and custom flyout/focus logic. An independent Quick
window would require adapters and more bespoke navigation, accessibility,
scrolling and popup management. It also adds QML/Quick runtime modules. Widgets
requires Qt Gui/Widgets and the appropriate platform plugin; actual memory and
latency must be measured rather than inferred from dependency counts. The
editor's use of Quick does not justify imposing it on the standalone menu.

On X11 QMenu uses its normal popup behavior. On Wayland the root is a frameless
xdg toplevel: a newly launched process has no guaranteed input serial for a
grabbing root popup. Request activation once, allowing the compositor to honor
the launch token or refuse it. Never manufacture serials, force activation or
use X11 positioning workarounds. Qt handles child popup placement and direction.
Root anchors select the cursor's screen and clamp to its available work area in
logical coordinates; Wayland can ignore requested global placement. Absolute
anchors and multi-monitor placement therefore remain compositor controlled.

One lifetime-bound dismissal controller tracks every menu, with the released
fixed 1200 ms delay. Parent/child transitions share a timer, entering cancels it,
keyboard navigation suspends it, and application focus loss is deferred briefly
to avoid transient submenu transitions. No delay preference is added for 2.0.

Virtual compositor tests are regression evidence, not certification of physical
Plasma shortcut activation, mixed-DPI monitors or launcher handoff. Those remain
release gates before production installer migration.
