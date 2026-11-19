# Open Power Menu v2.1.0-rc2

Prerelease for controlled physical acceptance. Stable v1.0.1, RC1 and draft PR #10 remain intact. This candidate continues RC1 commit `2384a9d03947b9a2e5de8f0ef72ae57e556bc29c` and preserves the native backend/editor, X11 Qt.Tool popup correction, Meta+X reopening fix, session reliability and XInput2 held-key protection.

**Power actions can execute immediately.** New installations follow KDE's confirmation setting. Upgrades preserve the previous immediate/confirmed choice. **Always show confirmation** applies to built-in Shutdown, Restart and Sign out; explicit custom commands retain their own behavior. Use private mocks for every power-action acceptance test.

## Changes and diagnosis

The reported immediate actions with confirmation enabled were traced to three saved custom `qdbus6 org.kde.Shutdown` commands, explicitly selecting `logout`, `logoutAndReboot` and `logoutAndShutdown`. These rows were not native built-in actions. RC1's native confirmed routes displayed the real KDE greeter correctly in disposable Debian, Manjaro and Arch tests. No custom-command conversion is included.

Configure now offers:

- **Follow KDE system settings:** read the effective KConfig `ksmserverrc [General] confirmLogout` preference, including system layers, immutable policy and KDE's default (`true`). Changes while OPM is running are honored.
- **Always show confirmation:** explicitly request KDE's native greeter.
- **Execute immediately:** request KDE's normal session-ending operation without its greeter.

KDE owns the countdown. OPM adds no timer and changes no KDE settings. A changed mode or effective route invalidates a previously captured power selection, including changes during permission checks.

Built-in application selection now uses standard preferred applications where available, validated KService desktop entries and desktop/distribution-aware fallbacks. Missing settings modules are unavailable instead of opening generic settings. User commands, labels, menu layout and access keys are preserved. See [the detailed report and action audit](docs/POWER-DISTRIBUTION-RC2.md).

## Migration

The new setting is `power_confirmation`: `system`, `always`, or `immediate`.

| Existing state | RC2 behavior |
| --- | --- |
| No configuration file | Follow KDE system settings |
| RC1 `confirm_power_actions: true` | Always show confirmation |
| RC1 `confirm_power_actions: false` | Execute immediately |
| Existing file missing that field | Execute immediately, preserving RC1 behavior |
| Explicit new enum | Preserve that mode |

Reading does not rewrite the file. Save/import/export/backups use the existing storage transactions. A legacy Boolean shadow remains for rollback: `system` and `always` save `true`; `immediate` saves `false`. RC1 therefore uses confirmation after rollback from system mode. The enum remains preserved as compatible metadata if RC1 subsequently saves the file; on return to RC2 it takes precedence.

## Downloads and supported systems

The published x86-64 `.pkg.tar.zst` and complete `.tar.gz` native installation bundle are **Manjaro binaries**. They contain the backend, editor, standalone menu, widget, native input plugin, icons, desktop integration and reversible installer. They require the matching Qt/KDE runtime; they are not universal Linux binaries and must not be installed on Debian or Kubuntu.

`QUALIFICATION.json` records the exact source commit, Manjaro build/runtime packages, independent Debian 13 and Kubuntu 26.04 desktop/runtime qualification, the Arch 2026-09-27 compatibility snapshot, application audits, private greeter results and all keyboard seats. The package enforces minimum library versions from its build snapshot. An older/different Manjaro runtime is not certified. Physical workstation acceptance remains pending.

Debian 13 and Kubuntu 26.04 have separate native source-build, runtime, install and rollback tests. No `.deb` is published. Build the complete bundle on the intended OS using [native packaging instructions](native/packaging/README.md) and the exact dependencies in the corresponding Docker recipe. Those locally built bundles enforce their own OS/version/architecture. GNOME desktop integration is not qualified; the widget requires Plasma 6.

## Verify and install on Manjaro

Download the package, bundle, `SHA256SUMS`, `SOURCE-COMMIT` and `QUALIFICATION.json` from this release. Check before installation:

```sh
sha256sum --ignore-missing -c SHA256SUMS
cat SOURCE-COMMIT
git ls-remote https://github.com/BB7Networks/Open-Power-Menu.git \
  'refs/tags/v2.1.0-rc2' 'refs/tags/v2.1.0-rc2^{}'
```

The peeled tag commit must match `SOURCE-COMMIT`. The pipeline compares the source archive with that Git tree, validates the sealed bundle and package equivalence, and downloads the uploaded assets to verify their checksums before publication.

Back up your configuration and retain the previous installer. Use Manjaro's normal full-update procedure if dependencies require it; do not force dependencies or partially upgrade Qt. Then:

```sh
sudo pacman -U ./open-power-menu-native-2.1.0rc2-1-x86_64.pkg.tar.zst
open-power-menu-native-setup
"${XDG_BIN_HOME:-$HOME/.local/bin}/open-power-menu" --version
"${XDG_BIN_HOME:-$HOME/.local/bin}/open-power-menu" --check
"${XDG_BIN_HOME:-$HOME/.local/bin}/open-power-menu" --edit
```

Run setup without sudo. The same commands upgrade RC1 or stable 1.0.1. Pacman stages the bundle; setup explicitly installs it for the current user. It preserves configuration, shortcuts, panel layouts and recovery history. Keep Python/PySide6 if retaining a stable 1.0.1 rollback.

Alternatively, extract the Manjaro native bundle and run `sh native-bundle/install.sh` as your normal user, after installing matching runtime dependencies. Use one route at a time. Never use the legacy Python source installer to install this native candidate.

Plasma can cache old widget code until the next user-controlled sign-out/sign-in. The installer reports this and permits deferral; it never restarts the session or rewrites panels. Do not assess a new widget while an older copy remains loaded.

## Automated qualification and limits

Publication requires all ten qualification jobs to pass. Coverage includes native input/model/storage/editor/GUI/power tests; the 18-case power-mode matrix; stale selections, external and locked KDE preferences; missing/denied/malformed/uncertain services; real X11 KDE greeter presentation, Escape cancellation and stock countdown into private mocks; application alternatives and missing capabilities; Python/QML/JavaScript and private D-Bus contracts; X11/Wayland standalone and widget keyboard tests; launcher visible/hidden; Configure/session startup; popup/dismissal tests; and clean install, update, reinstall, recovery and rollback from both released v1.0.1 and independently rebuilt RC1.

Held-key coverage retains real X11 input with an application behind the widget, deliberately incorrect repeat flags, rapid U/U, root/flyout transfer, U/R/I/S/H/L holds, cross-window release, dismissal/reopening, Meta+X, arrows/Escape/Enter and custom/disabled bindings. Wayland uses a private virtual KWin seat with QtTest input; it is not proof of physical compositor-level shortcut handling. Real greeter visual/countdown coverage is X11. Every power endpoint is a harmless private recorder; no real power operation is executed.

Known issues:

- X11 translucent-panel text ghosting and minor responsiveness work remain deferred.
- A Wayland key released outside OPM remains blocked until OPM observes a real release; release and press again. This deliberately fails closed.
- Hardware, mixed DPI, workstation themes, actual unsaved-document handling and physical input still require acceptance. Mock success does not certify real shutdown.
- The Arch compatibility job uses its dated Plasma 6.7 snapshot; current Arch Plasma 6.8 is not qualified by that job.

## Rollback

As your normal user, run once:

```sh
"${XDG_BIN_HOME:-$HOME/.local/bin}/open-power-menu" --rollback
# Or, from a retained extracted RC2 bundle:
./native-bundle/app/bin/open-power-menu-install --rollback
```

This restores the preceding captured application/widget/activation files without rewriting personal configuration or panels. For a clean install with no previous application, use `--uninstall`; first remove its applet through Plasma so it can restore launcher visibility and relinquish its shortcut. Keep recovery snapshots under `${XDG_DATA_HOME:-$HOME/.local/share}/open-power-menu-recovery/native-installs`. If interrupted, use the retained installer's `--recover`. Remove the staged pacman package only after recovery is complete.

## Physical acceptance without real power actions

1. Verify checksums, source commit and runtime inventory. Back up configuration.
2. In a disposable VM, or the nested private desktop described in `docs/HELD-KEY-STABILIZATION.md`, run the held-key fixture. For Xephyr, grab its keyboard before Meta+X; if capture is uncertain, use a VM.
3. Hold U: one submenu opening and no mock request. Release/repress: exactly one request. Test rapid U/U, other power keys, focus transfer, reopen while held, custom keys and both launcher states.
4. Run `native/tests/plasma_greeter.py` with the built backend and a fresh output directory. It checks all three modes and KDE preferences, cancellation and the stock countdown using an allowlisted private bus and mock final endpoints.
5. On the installed workstation, check only harmless menu commands, Configure Save/reopen, Meta+X, flyouts, Escape/outside-click dismissal, preferred applications and unavailable settings tools. Do not select live power entries to test confirmation; custom commands may explicitly bypass it.
6. Record Plasma/KWin/Qt versions, X11/Wayland, theme, launcher state and any ghosting. Report failures before final v2.1.0.
