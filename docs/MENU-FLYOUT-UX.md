# Menu flyout UX refinements

Historical development notes: these refinements began from `main` at
`ac9e057` while the project was version 0.4.17. They were merged in PR #8
and are now part of the **1.0.1 source** on `main`. The launcher handoff,
native shortcut lifecycle, single-pane editor and recovery paths remain
unchanged. See [release review](RELEASE-1.0.1.md) for current status.

## Behavior

- Root and nested menu rows share `MenuEntryContent.qml`. Both arrow gutters
  stay reserved for every row. Left/right changes do not move labels; hiding
  entry icons removes their 18 px column and 8 px gap.
- Before opening, an indicator uses the existing `chooseSide()` screen-space
  policy. While its flyout is visible, it follows Plasma's horizontal
  `effectivePopupDirection`, falling back to the requested direction when
  Plasma reports a non-horizontal value. Placement and vertical clamping are
  unchanged.
- Model replacement and hide/show reset `activeIndex` and close child flyouts.
  Highlighting uses the current selection; hover, keyboard and accessibility
  input can establish a new selection. Explicit keyboard entry still focuses
  the first enabled item; returning from a child retains the parent selection.
- `show_menu_icons` is a boolean defaulting to true. Configure → General saves
  it through the existing revision/backup writer. D-Bus carries it to the
  widget and all nested flyouts. The standalone Qt menu follows it too.
  Menu definitions, launcher icons, toolbar icons and editor tree icons remain
  intact. Missing values enable icons; non-boolean values fail validation.

## Verification

Tests exercise configuration compatibility, strict validation and round trips;
actual Configure dirty/save/reload behavior; standalone QMenu icons at three
levels; live isolated D-Bus integration; and the widget's actual integration
callback. Qt Quick tests run the shipped flyout and row QML with stub Plasma
window/theme primitives, exercising real bindings, layout, model replacement,
keyboard and hover input. These stubs do not implement KWin popup placement.
The workflow parses the new row component and runs the flyout tests explicitly.

The full local suite passed **418 tests, 8 historical-source skips and 18
subtests** in 45.34 seconds. Python compilation, all seven shell syntax checks,
five QML parses, screenshot paths/original bytes and package checks passed.
Positive spring-navigation tests now wait for their target state with a
one-second bound; brief-hover rejection checks retain their timed assertions.
The delegate wait from PR #7 is included to avoid querying rows before polish.

A separate disposable Debian 13 / Plasma 6.3.6 / Qt 6.8.2 X11 session rendered
the new row component, a left-opening flyout with its arrow on the left and no
initial child selection, and the General checkbox. Saving the preference hid
icons in both root and flyout while retaining toolbar/launcher icons. This is
an X11 smoke check, not a physical Wayland acceptance result.

## Manjaro Plasma Wayland checklist

Use a disposable profile or retain a configuration backup. Record Plasma/Qt
versions, launcher, screen arrangement, panel position and scale.

1. Open OPM near the left and right screen edges, then away from the corners.
   Open two nested submenu levels. Each arrow must sit on the edge where its
   own child opens, including a compositor flip. Labels must stay aligned and
   flyouts must retain bottom-edge alignment and remain on screen.
2. Hover Remote Desktop under Remote & Work, then move to Shut down or sign
   out. The new flyout must start without a selected row. Enter it with the
   pointer, then repeat using Up/Down, Enter/Right, Left and Escape. Confirm
   child return, command activation and dismissal still work.
3. Uncheck Show icons in Power User Menu, save, reopen and navigate all levels.
   Labels should reclaim icon space; arrows, separators and highlights should
   remain correct. Launcher/lock/refresh/configure icons must remain visible.
   Restart/reopen, then re-enable the preference and verify the original icons.
4. Check native Meta+X toggling and left/right-click launcher handoff. Unlock
   the menu, drag into a submenu, use Go Back, then Cancel and Save in separate
   trials. Confirm Configure Undo/Redo, external-edit conflicts and backup
   restoration still preserve the icon preference and existing menu entries.

## Screenshots

Four original PNGs were supplied in `opm - .zip` on 2026-11-05. They were copied
byte-for-byte; the README only sets display widths. They illustrate the user's
existing desktop and are not proof that this new branch passed desktop checks.
No Configure or layout editor capture was included in this delivery.

| Supplied filename | Repository asset |
| --- | --- |
| `opm - center - side-by-side.png` | `images/power-user-menu.png` |
| `opm - left - right click.png` | `images/submenu-flyout.png` |
| `opm - left - left click.png` | `images/application-launcher.png` |
| `opm - center - combined.png` | `images/combined-launcher.png` |

PR #7 was closed as superseded after its consolidation findings and Qt
delegate timing correction were reviewed. The current gallery retains
the supplied product screenshots rather than the older Debian capture set.
PRs #8 and #9 are merged into `main`.
