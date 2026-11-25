# Native binary compatibility

| EZ target | Qualified runtime snapshot | Binary boundary |
| --- | --- | --- |
| Manjaro KDE x86-64 | Qt 6.12.0, Plasma 6.8.2, KF6 6.31 | Native Wayland session; matching current Manjaro libraries |
| Debian 13 KDE x86-64 | Qt 6.8.2, Plasma 6.3.6 | Debian 13 libraries and Plasma 6 |
| Kubuntu 26.04 x86-64 | Qt 6.10.2, Plasma 6.6.7 | Ubuntu 26.04 with its KDE packages |

Each distribution compiles its own native payload and tests installation,
activation, upgrades and rollback independently. Exact package versions and
source identity are recorded in each build's `QUALIFICATION.json`. A Manjaro
package's dependencies are bounded by its build snapshot. Do not assume an
older runtime works because it has the same distribution name.

Arch's pinned 2026-09-27 image remains a regression target; there is no public
Arch EZ binary claim. Other architectures or distributions need their own
[source build](../native/README.md) and qualification. The native bootstrap
checks OS/version/CPU; the installer checks hashes, libraries, QML/platform
plugins and the native input plugin before changing an installation.

The recovery audit found Manjaro `plasma-workspace 6.8.2-1`, `kwin 6.8.2-2`,
`qt6-base 6.12.0-5` and KF6 `6.31.0-1`. Its repositories no longer provide
`kwin-x11`; `kwin_x11` and `startplasma-x11` are absent. This is distinct from
the earlier Manjaro Plasma 6.7.5 / Qt 6.11.2 snapshot and its physical acceptance.
The new package and EZ payload must be rebuilt and qualified on the current
runtime; an earlier payload or passing run does not qualify it.

The pinned Arch snapshot retains Plasma/KWin 6.7.5, Qt 6.11.2 and KF6 6.30,
including its native X11 session. CI requires that profile plus Debian/Kubuntu
X11 coverage. Manjaro requires Wayland keyboard, popup, greeter and installation
tests. Xvfb still tests Qt's xcb application plugin separately; this does not
claim a supported Manjaro Plasma X11 session. No foreign Qt/KDE packages are mixed.

Plasma widget use targets KDE Plasma 6. The standalone uses Qt Widgets; the
Configure editor uses Qt Quick/Kirigami. The complete EZ payload requires both.
Python is test/build tooling and retained legacy support, not a native runtime
requirement. Some distro desktop packages independently depend on Python;
OPM never removes it automatically.

X11 tests use private Xvfb/KWin seats and real XTest input. Wayland tests use
virtual KWin and QtTest input; they do not prove physical compositor shortcuts,
activation tokens or absolute placement. A release still needs physical desktop
acceptance, including mixed scaling, launcher variants and real panel placement.
X11 translucent-panel ghosting and minor responsiveness work remain deferred.
An X11 opening-focus timeout has recurred in a private recovery run and remains
unresolved; it is not attributed to the separate Meta+I interference.

The owner reported successful Manjaro EZ installation and normal menu/Configure
use with the earlier installer build. This does **not** establish real power-action
or physical held-key safety, or physical acceptance of every later source commit.
The Kubuntu held-I release/repress timeout was reproduced as competing System
Settings shortcut interference in the private fixture; see the
[recovery evidence](QUALIFICATION-RECOVERY-2.1.0.md).

The [native showcase](SHOWCASE.md) records a separate Debian 13 X11 capture
environment (Qt 6.8.2, Plasma 6.3.6, 100% scale). Its genuine images do not extend
the binary compatibility claims or certify physical compositor behavior.
