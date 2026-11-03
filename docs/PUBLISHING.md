# Initial GitHub release and follow-up publishing

These commands are intended for a Manjaro/KDE machine with Git and `gh`.

## Create the public GitHub repository

Unpack the **GitHub-ready source ZIP** in a project workspace (not directly
into `~/.local/share/plasma`). Open a terminal in the extracted
`Open-Power-Menu-GitHub-Ready` folder.

```bash
gh auth status                         # If needed: gh auth login
git init -b main
git add .
git commit -m "Initial public beta: Open Power Menu v0.4.17"
gh repo create Open-Power-Menu --public --source=. --remote=origin --push
```

By default, `gh repo create` uses the account you're signed into; to publish
under an organization, pass `ORG/Open-Power-Menu` instead. Verify the intended
owner before creating the repository. Don't publish it under an employer or
shared organization without permission.

After publishing, update README links and `plasmoid/metadata.json` with the
real repository URL/maintainer details, and commit those small documentation
changes. Keep the `org.openpowermenu.start` widget ID stable — changing it
would create a separate widget for existing users.

## Create a release download

```bash
bash scripts/build-release.sh
sha256sum -c dist/SHA256SUMS
# Then create a GitHub release, attach the complete EZ installer:
gh release create v0.4.17 dist/OpenPowerMenu-EZ-v0.4.17.zip   --title "Open Power Menu v0.4.17 (beta)"   --notes-file RELEASE-NOTES-v0.4.17.md
```

The release script produces ZIP and TAR.GZ archives for ordinary users.
**Neither archive is a standalone `.plasmoid` for the KDE Store.**

## Prepare to list the widget in the KDE Store

Read [KDE-STORE.md](KDE-STORE.md) before publishing. The current widget-only
archive cannot install the required Python/PySide6 backend through the native
Get New Widgets workflow. Do not list it as one-click working until the setup
path has been implemented and tested on a clean Plasma 6 account.

Before a public listing, also:
- confirm the license/attribution for every included file and icon,
- take a few actual KDE screenshots (both click modes and Configure),
- test on another user's account/machine and a clean KDE install,
- publish clear issues/security reporting and the compatibility matrix.
