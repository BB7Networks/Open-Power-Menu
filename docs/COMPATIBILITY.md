# Native binary compatibility

| EZ target | Qualified runtime snapshot | Binary boundary |
| --- | --- | --- |
| Manjaro KDE x86-64 | Qt 6.11.2, Plasma 6.7.5 | Manjaro build and matching current distro libraries |
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
One earlier X11 focus-readiness timeout did not recur on the unchanged debug
retry; it is recorded evidence, not a confirmed or fixed production defect.

The owner reported successful Manjaro EZ installation and normal menu/Configure
use with the earlier installer build. This does **not** establish real power-action
or physical held-key safety, or physical acceptance of every later source commit.
An intermittent Kubuntu X11 hidden-launcher keyboard-test timeout also remains
unresolved; [test evidence](TESTING.md#acceptance-scope-and-unresolved-results)
distinguishes it from the earlier focus-readiness timeout.

The [native showcase](SHOWCASE.md) records a separate Debian 13 X11 capture
environment (Qt 6.8.2, Plasma 6.3.6, 100% scale). Its genuine images do not extend
the binary compatibility claims or certify physical compositor behavior.
