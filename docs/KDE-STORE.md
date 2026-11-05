# Publishing to KDE Store / "Get New Widgets"

## Current package: not yet suitable for a one-click Store install

Open Power Menu 1.0.1 consists of **two components**:

1. `plasmoid/` — a valid Plasma 6 QML applet (`metadata.json` + `contents/`).
2. `openpowermenu/`, `run.py`, and the user D-Bus activation service — a
   Python/PySide6 backend that supplies commands and a graphical editor.

**A `.plasmoid` archive installs only #1.** KDE's normal `Get New Widgets`
install flow cannot be assumed to run this repository's shell installer. A
widget installed from KDE Store alone currently displays "Menu backend
unavailable" rather than a functioning right-click Power User menu.

**Do not publish the existing EZ ZIP as a native widget download**, and do not
present a widget-only download as a complete one-click installer.

Before publishing through `Get New Widgets`, implement and test one of:

- **Preferred:** a widget-first, user-consented backend setup experience that
  clearly explains dependencies and offers a safe installation route, followed
  by a fully working menu; or
- a packaging/distribution method that installs the backend independently in a
  documented, verifiable way before the widget is first used.

No automatic shell command execution or silent system package installation
should happen merely because a user added a widget.

## Publishing procedure once that work is completed

### Proposed first-run path (future work)

Keep this separate from the action/lifecycle changes. A missing backend should
show an explicit setup page rather than offer a nonfunctional menu. Explain
which component is missing, link to the complete trusted release and manual
installation instructions, and offer **Retry connection** after installation.
Adding a widget must never execute a downloaded shell script. Package installation
and any authentication remain under the user's control.

Prefer distro packages for Python/PySide6 and a separately installed, versioned
backend package with a user D-Bus activation file. Define a backend/widget
compatibility handshake before adding automated recovery: distinguish absent
service, missing PySide6 and incompatible versions instead of repeatedly polling
or trying reinstall commands. Validate clean-account install, upgrade, offline
failure, retry and removal on supported distros before advertising Store readiness.
The current Ping/version API can inform that design but is not a completed setup
experience. No Store integration is implemented by this PR.

1. Test a clean Plasma 6 account/VM with **no backend previously installed**.
   Make the Store install path complete the setup, or clearly guide the user
   through the required backend installation.
2. Generate a native widget archive with `bash scripts/build-widget-only.sh`.
   It produces `dist/org.openpowermenu.start-<version>.plasmoid`. The ZIP root
   must contain `metadata.json` and `contents/` — not an extra top-level folder.
3. Verify with `unzip -l` and install in a fresh user profile with:

   ```bash
   kpackagetool6 --type Plasma/Applet --install dist/org.openpowermenu.start-1.0.1.plasmoid
   ```

   On an update, use `--upgrade` instead of `--install`.
4. Go to <https://store.kde.org/>, register/sign in to an OpenDesktop / KDE
   Store account, and select **Add Product** (label may vary).
5. Choose the **Plasma 6 Menus** category where available; otherwise a
   corresponding **Plasma 6 Applets** category. Do not choose a Plasma 5
   category. The correct category matters for appearing in Plasma 6's
   "Get New Widgets" browser; category options sometimes vary in the form.
6. Provide the project name, description, the **MIT** license, a link to the
   public GitHub source, Plasma 6 compatibility, and **real screenshots** of
   both click menus and Configure. Upload the `.plasmoid` archive, not the
   entire source-repository or EZ-installer ZIP.
7. Test that it appears in **Add Widgets → Get New Widgets → Download New
   Plasma Widgets**, installs, and works in a new profile. If it does not
   appear, double-check the Store category and product's download attachment.

## GitHub versus Store

- GitHub: canonical source, issues, release notes, full EZ installation ZIP.
- KDE Store: public discovery and installation of a valid Plasma widget
  package. It is a **separate listing**, not an automatic mirror of GitHub.

References:
- <https://develop.kde.org/docs/plasma/widget/setup/>
- <https://develop.kde.org/docs/plasma/widget/properties/>
- <https://store.kde.org/>
