#!/usr/bin/env bash
# Reversible user-local removal. Never remove another launcher or its settings.
set -euo pipefail
here="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ $EUID -ne 0 ]] || { printf 'Do not run this as root.\n' >&2; exit 1; }
[[ -f "$here/scripts/uninstall-core.sh" ]] || { printf 'Uninstall files missing; extract the whole ZIP.\n' >&2; exit 1; }
bin_home="${XDG_BIN_HOME:-$HOME/.local/bin}"
if [[ -x "$bin_home/open-power-menu" ]]; then
    "$bin_home/open-power-menu" --show-launcher-button || true
fi
printf '\nBefore removing Open Power Menu, remove ONLY its new Start button\n'
printf 'from the KDE panel (Enter Edit Mode -> Remove widget).\n'
printf 'Do not remove your original application launcher.\n'
read -r -p 'Have you removed the Open Power Menu widget from your panel? [y/N]: ' reply || reply=''
if [[ ! "$reply" =~ ^[yY]([eE][sS])?$ ]]; then
    printf 'Cancelled. Your original launcher button has been restored if possible.\n'
    exit 0
fi
bash "$here/scripts/uninstall-core.sh"
printf '\nYour personal menu settings were not removed.\n'
