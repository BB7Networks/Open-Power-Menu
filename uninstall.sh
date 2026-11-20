#!/usr/bin/env bash
# Do not guess whether a source checkout matches the installed native application.
set -eu
cat <<'MESSAGE'
Open Power Menu 2.1.0 — native removal and recovery

This source checkout does not uninstall an application or change your desktop.
First remove only OPM's applet through Plasma so its launcher/shortcut can be
restored. Keep the original application launcher and your recovery history.

From the retained matching native EZ directory, as your normal desktop user:
  bash install.sh --uninstall
  bash install.sh --rollback    # Restore the preceding application snapshot
  bash install.sh --recover     # Recover an interrupted transaction

Read docs/RECOVERY.md before removal. For an actual historical 1.0.1 install,
use that release's original archive/instructions, not the compatibility fixtures.
No application files, configuration, panels or shortcuts were changed.
MESSAGE
exit 1
