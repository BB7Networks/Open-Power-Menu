#!/usr/bin/env bash
# Source-checkout guidance only. The distribution-specific EZ archive installs OPM.
set -eu
cat <<'MESSAGE'
Open Power Menu 2.1.0 — native installation

This is a source checkout, not a distribution-specific installation bundle.
No application, dependency, configuration, panel or shortcut was changed.

Obtain the complete native EZ ZIP for Manjaro KDE, Debian 13 KDE or Kubuntu
26.04 (x86-64). Verify its external SHA-256 checksum, extract the whole ZIP,
then run bash install.sh inside that extracted EZ directory as your desktop user.

Installation and current review/download status: docs/INSTALLATION.md
Releases: https://github.com/BB7Networks/Open-Power-Menu/releases
Developer source builds: native/README.md

The Python compatibility fixtures under legacy/ are not a native installer.
MESSAGE
exit 1
