# Real Open Power Menu screenshots

The project uses **actual Plasma 6 captures**, never generated mockups or
screens that suggest unimplemented features. Capture on a live desktop after
[acceptance testing](../TESTING.md), and retain reproducible UI information.

## Captured screenshots

Three genuine Manjaro / Plasma 6 screenshots have been prepared. Their image
binaries are awaiting repository upload; the names below are reserved for the
gallery. The README links to this guide instead of embedding images until the
assets are available, avoiding broken screenshots.

| File to commit | What the capture shows |
| --- | --- |
| `power-user-menu.png` | Main Power User Menu, its top-right controls and the OPM launcher button on the panel |
| `submenu-flyout.png` | Normal-use **Shut down or sign out** submenu opening beside its parent row |
| `configure-general.png` | **Configure → General**, including launcher selection, button hiding, emergency restore, icon and appearance |

When image files have been uploaded, embed the gallery in the README:

```md
![Power User Menu attached to the Manjaro panel](docs/images/power-user-menu.png)
![Shut down or sign out submenu flyout](docs/images/submenu-flyout.png)
![Configure General tab](docs/images/configure-general.png)
```

The General screenshot does **not** show Layout or Backups; describe those
tabs with their own screenshots when available. A menu displayed normally
does not demonstrate the separate, single-pane **editing** interaction.

## Additional capture checklist

| Suggested file | What to capture |
| --- | --- |
| `launcher-button.png` | Close-up of the OPM button and original launcher relationship |
| `application-launcher.png` | Left-click result with native Kickoff/Kicker |
| `appgrid-launcher.png` | Left-click result with AppGrid Center 1.9.6 |
| `configure-layout.png` | Layout tree and responsive Undo/Redo toolbar |
| `configure-backups.png` | Configuration backup limits, Restore and widget snapshots |
| `backup-delete.png` | Safe backup deletion confirmation in a disposable profile |
| `in-menu-editing.png` | **Go Back** strip, spring-loaded move, destination highlight and Save/Cancel |
| `in-menu-conflict.png` | A retained draft and safe external-change message |
| `installed-application-picker.png` | Search and selected-app details |

Use Spectacle or another desktop screenshot utility with readable scaling
and modest crops. Record distro, Plasma/Qt versions, session (Wayland/X11),
launcher version, display scale, panel edge and whether the original button
is hidden. Keep the original pixels and don't composite separate states into
one implied screen. Use a clean demo profile: avoid private hostnames, network
shares, credentials, notifications and other users' information.

Screenshot assets belong under `docs/images/`. Update the README and
`CHANGELOG.md` only after the image files are actually tracked in Git; do not
present a capture plan as if a public screenshot already exists.
