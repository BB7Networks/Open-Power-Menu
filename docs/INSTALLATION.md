# Install and upgrade native 2.1

Version 2.1.0 is in stable-release preparation; it has not been published as the
stable release. Reviewed build downloads are linked from the release-preparation
PRs and [Actions](https://github.com/BB7Networks/Open-Power-Menu/actions/workflows/tests.yml).
Actions artifacts require sign-in and expire after 90 days. After explicit
approval, the persistent destination is the
[v2.1.0 release](https://github.com/BB7Networks/Open-Power-Menu/releases/tag/v2.1.0).
Historical [1.0.1](https://github.com/BB7Networks/Open-Power-Menu/releases/tag/v1.0.1),
[RC1](https://github.com/BB7Networks/Open-Power-Menu/releases/tag/v2.1.0-rc1) and
[RC2](https://github.com/BB7Networks/Open-Power-Menu/releases/tag/v2.1.0-rc2) remain available.

Choose the **whole** native EZ ZIP for Manjaro KDE, Debian 13 KDE or Kubuntu
26.04, x86-64. These are distribution-specific binaries, not generic Linux ZIPs.
See [runtime compatibility](COMPATIBILITY.md). A native backend, Configure editor,
standalone menu, widget/input plugin, icon and transactional installer are included.
Installation needs no Python, PySide6 or compiler. Existing KDE Plasma 6 and
matching system Qt/KF6 libraries are required.

For Manjaro, after downloading the ZIP and its matching sidecar:

```sh
sha256sum -c OpenPowerMenu-EZ-v2.1.0-Manjaro-x86_64.zip.sha256
unzip OpenPowerMenu-EZ-v2.1.0-Manjaro-x86_64.zip
cd OpenPowerMenu-EZ-v2.1.0-Manjaro-x86_64
bash install.sh --check
bash install.sh
```

Use `Debian13` or `Kubuntu26.04` in the filename on those systems. Run as your
normal desktop user, **without sudo**. `--check` validates without installing;
`--yes` skips only the interactive approval. The wrapper reports missing runtime
components and prints distro-specific dependency commands for separate review.
It never runs a package manager or partially upgrades Qt/KDE. It works offline
when dependencies are present. Retain the extracted folder and checksums.

A Git source checkout and GitHub's automatic source ZIP are developer sources.
Their root `install.sh`/`uninstall.sh` provide guidance only. They do not install
Python components or guess a binary distribution. For source builds use
[the native build instructions](../native/README.md).

For a new setup, add **Open Power Menu Start Button** through Plasma's Add
Widgets interface, on the same panel as the original launcher. Configure its
launcher selection. Never remove the original launcher. Upgrades use the same
EZ command and keep the existing OPM applet, configuration, access keys,
shortcuts, launcher selection/visibility and recovery history. Released
1.0.1/RC1/RC2 upgrades and same-version reinstalls are qualified in disposable profiles.

The installer never rewrites panels or restarts Plasma. New widget code may
remain cached until you voluntarily sign out/in. Ordinary preference changes
need no restart. Keep Python/PySide6 if rollback to 1.0.1 is still required.
See [recovery and uninstall](RECOVERY.md).

Manjaro's native package remains an alternative:

```sh
sudo pacman -U ./open-power-menu-native-2.1.0-1-x86_64.pkg.tar.zst
open-power-menu-native-setup
```

The first command installs the system package; the second runs user-local setup
without sudo. Verify the downloaded package with the release's `SHA256SUMS` first.
Do not mix foreign-distribution Qt/KDE packages or force dependency versions.

**Power actions can execute immediately.** Upgrades preserve preferences and
explicit custom commands. Read [power behavior](POWER.md); acceptance tests of
power keys must use the [private mock fixture](TESTING.md#private-power-and-keyboard-tests).
