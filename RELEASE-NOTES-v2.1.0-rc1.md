# Open Power Menu v2.1.0-rc1

**Prerelease for controlled physical testing. Stable v1.0.1 remains unchanged.**

**Warning: Shutdown, Restart and Sign out are immediate by default.** With
**Confirm power actions** disabled, deliberate `Meta+X → U → U` requests shutdown
without OPM/KDE's confirmation screen. Enable **Configure → General → Power
Actions → Confirm power actions** before exploring those entries on a real
workstation. Sleep, Hibernate and Lock also affect the live session. Automated
qualification uses private mocks exclusively; it never executes real power or
session-ending operations. Physical acceptance does not require real power tests.

## Included

- Native C++/Qt backend, Configure editor, standalone menu and Plasma 6 widget.
- Permanent Configure/session-environment reliability correction.
- Preserved X11 `Qt.Tool`/`WM_TRANSIENT_FOR` popup-collapse correction and Meta+X
  reopening-race handling.
- KDE-native immediate/confirmed Shutdown, Restart and Sign out dispatch.
- Configurable Win+X-style access keys and one shared physical-key guard across
  the root and native flyouts. X11 uses read-only XInput2 evidence; one held key
  cannot authorize a second power-menu selection. No cooldown or global XKB
  setting changes are used.
- Native icons, desktop/D-Bus integration and the reversible per-user installer.
  Configuration, launcher choices, shortcuts, panel layouts and recovery history
  are preserved. The pacman package has no hooks that restart or rewrite Plasma.

This release starts from the complete 64-file held-key candidate, preserved in
commit `073fc02`, rather than the older development-branch checkout. PR #10 stays
draft and is not merged into the default branch.

## Supported artifacts and verification

The published x86-64 package and complete standalone installation bundle are
built on **Manjaro**, then qualified in a separate Manjaro runtime. They are not
Debian or Arch binaries relabeled for Manjaro. `QUALIFICATION.json` contains the
exact OS, build/runtime package versions, source commit, mock keyboard results
and Actions run link. The package declares minimum dependency versions from that
build snapshot. Do not infer compatibility with an older Manjaro runtime or with
another distribution. Physical Manjaro Plasma/KWin 6.7.5 acceptance remains pending.

The tar.gz bundle is an alternative complete per-user installation, including
the native standalone menu. It is not a statically linked universal executable;
it needs the matching Manjaro Qt/KDE libraries. The `.pkg.tar.zst` package is the
recommended dependency-managed route. The native runtime does not require
PySide6 or a compiler. Keep Python/PySide6 available when retaining a 1.0.1 rollback.

Download the package, tar.gz bundle, `SHA256SUMS`, `SOURCE-COMMIT`, and
`QUALIFICATION.json` from this prerelease. Verify the downloaded files before
installing (GNU sha256sum can ignore assets you did not download):

```sh
sha256sum --ignore-missing -c SHA256SUMS
cat SOURCE-COMMIT
git ls-remote https://github.com/BB7Networks/Open-Power-Menu.git \
  'refs/tags/v2.1.0-rc1' 'refs/tags/v2.1.0-rc1^{}'
```

The peeled tag commit must match `SOURCE-COMMIT`. The release pipeline compares
the supplied source archive with that exact Git tree, verifies every sealed
bundle file, confirms that the package contains the identical bundle, and
downloads the uploaded release assets to verify their checksums before publishing.

## Manjaro installation and upgrade

Use the qualified Manjaro dependency snapshot or a compatible fully updated
system; do not force dependencies or attempt a partial Qt upgrade. Back up your
personal configuration and retain the previous installer. As your normal user:

```sh
# Use Manjaro's normal full-update procedure if the package requires newer libraries.
sudo pacman -U ./open-power-menu-native-2.1.0rc1-1-x86_64.pkg.tar.zst
open-power-menu-native-setup
"${XDG_BIN_HOME:-$HOME/.local/bin}/open-power-menu" --version
"${XDG_BIN_HOME:-$HOME/.local/bin}/open-power-menu" --check
"${XDG_BIN_HOME:-$HOME/.local/bin}/open-power-menu" --edit
```

Run the setup command without sudo. Installing/updating the pacman package
stages the bundle; running setup explicitly installs/updates the current user's
backend, editor, widget, icon and desktop entries. Use these same commands for
an upgrade. If a dependency is unavailable, stop and check the published snapshot
instead of bypassing pacman. If another installation shadows the launcher,
inspect `type -a open-power-menu` and use the explicit per-user path above.

For the standalone installation bundle, install its documented Qt/KDE runtime
dependencies, extract `OpenPowerMenu-2.1.0-rc1-manjaro-*-x86_64.tar.gz`, then run
`sh native-bundle/install.sh` as the normal user. Its OS/CPU/Qt and file-integrity
checks remain enabled. Use one installation route, not both concurrently.

Newly installed widget QML/native modules may require your next sign-out/sign-in
to replace Plasma's cached interface. The installer explains this and lets you
defer; it never restarts Plasma, logs out, or reconstructs the panel. Ordinary
configuration changes do not require a restart. Keep the downloaded bundle for
recovery even after updating the pacman package.

## Automated qualification

Publication is blocked unless the complete Actions qualification succeeds:
native input, model, recovery, session, Configure, GUI, power policy/dispatch and
installer tests; Python/QML/JavaScript and legacy contracts; private X11 and
Wayland standalone tests; Debian, Arch and Manjaro package/runtime tests; actual
1.0.1 upgrade/rollback; startup and popup/dismissal tests; and the full held-key
matrix on Debian and the target Manjaro/Arch builds.

The keyboard matrix uses real X11/XTest input with an application behind OPM,
plus synthetic events with varying repeat flags. It checks held U/R/I/S/H/L,
rapid deliberate U/U, root/flyout focus transfer, dismissal/reopening while held,
release in another window, Meta+X, Escape/arrows/Enter, custom/disabled keys and
both launcher states. Wayland integration uses a private virtual KWin seat with
QtTest input/app activation, not physical compositor-level shortcut injection.
All power endpoints and Lock requests are harmless recorders. The published
qualification record links to the complete passing test run.

## Known issues and physical acceptance limits

- **Deferred cosmetic issue:** X11 may retain faint last-row text behind a
  translucent Plasma taskbar until a redraw. This RC does not claim to fix it.
- A Wayland key whose release occurred outside OPM remains blocked until OPM
  observes a real release; release and press again. This deliberately fails closed.
- Physical keyboard/display behavior, mixed-DPI setups, distro themes and actual
  workstation session integration still need tester acceptance. Successful mocks
  do not certify real shutdown or unsaved-document handling.
- A loaded older widget can remain cached during install/rollback; complete a
  user-controlled sign-out/sign-in when convenient before assessing the new UI.

## Rollback

For an upgrade from 1.0.1, retain its Python/PySide6 runtime. As your normal user:

```sh
"${XDG_BIN_HOME:-$HOME/.local/bin}/open-power-menu" --rollback
# Or use the retained candidate installer even after the launcher was restored:
./native-bundle/app/bin/open-power-menu-install --rollback
```

Use one rollback command once. It restores the preceding captured application,
widget, launchers and activation files without rewriting personal configuration
or panels. A clean install has no previous 1.0.1 snapshot: use `--uninstall` to
remove it. Remove its applet through Plasma first if uninstalling, so the applet
can restore launcher visibility and relinquish its shortcut. Recovery snapshots
remain under `${XDG_DATA_HOME:-$HOME/.local/share}/open-power-menu-recovery/native-installs`.
If interrupted, run the retained installer's `--recover`. Keep the pacman package
until recovery is complete; it can later be removed with
`sudo pacman -R open-power-menu-native` without deleting per-user recovery history.

## Physical acceptance checklist

1. Verify checksums, source commit and dependency snapshot. Back up configuration.
2. First run the nested **private mock** procedure in
   `docs/HELD-KEY-STABILIZATION.md` from the published source archive; capture the
   Xephyr keyboard before Meta+X so the host shortcut cannot receive it.
3. Hold U: the flyout opens once and the mock request count stays unchanged.
   Release/repress U: exactly one request. Rapid U/U must also produce exactly one.
4. Repeat held R/I/S/H/L, focus transfer, menu dismissal/reopening, Escape/arrows,
   custom keys and both launcher states. Never use these power-key stress inputs
   against the live workstation menu.
5. After installation, enable **Confirm power actions** before exploring the live
   menu. Check Configure, harmless commands, shortcut toggling, flyout navigation
   and outside-click/Escape dismissal, with Brave/Dolphin/Konsole behind OPM.
6. Record Plasma/KWin/Qt versions, X11/Wayland, theme, launcher state and any ghosting.
   Check rollback in a disposable profile/VM first. Report failures before final 2.1.0.
