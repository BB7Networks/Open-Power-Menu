#!/usr/bin/env bash
# Prepare the native KPackage archive. NOT a self-contained installer:
# the Python/PySide6 backend must be installed separately.
set -euo pipefail
root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(python3 - "$root" <<'PY_VER'
import json, pathlib, sys
root=pathlib.Path(sys.argv[1])
print(json.loads((root/'plasmoid/metadata.json').read_text())['KPlugin']['Version'])
PY_VER
)"
mkdir -p "$root/dist"
archive="$root/dist/org.openpowermenu.start-$version.plasmoid"
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT
(cd "$root/plasmoid" && zip -qr "$temporary/widget.zip" metadata.json contents)
mv "$temporary/widget.zip" "$archive"
printf 'Built widget-only archive: %s\n' "$archive"
printf 'WARNING: This does not install the Python/PySide6 backend.\n'
printf 'Do NOT advertise it as one-click Store compatible yet.\n'
