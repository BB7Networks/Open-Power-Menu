#!/usr/bin/env bash
# Explicitly opt in to old installation code; test profiles must supply all roots.
[[ ${OPM_LEGACY_FIXTURE:-} = 1 && -n ${XDG_DATA_HOME:-} && -n ${XDG_CONFIG_HOME:-} && -n ${XDG_BIN_HOME:-} && -n ${XDG_CACHE_HOME:-} ]] || {
    printf '%s\n' 'Legacy compatibility fixture only. Use the native EZ installer; see docs/INSTALLATION.md.' >&2
    exit 1
}
