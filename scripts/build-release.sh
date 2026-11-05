#!/usr/bin/env bash
# Build the complete EZ installer for GitHub Releases.
set -euo pipefail
root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(python3 - "$root" <<'PY_VER'
import json, pathlib, sys
root=pathlib.Path(sys.argv[1])
print(json.loads((root/'plasmoid/metadata.json').read_text())['KPlugin']['Version'])
PY_VER
)"
dist="$root/dist"
mkdir -p "$dist"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
stage="$tmp/OpenPowerMenu-v$version"
mkdir -p "$stage"
for n in install.sh uninstall.sh LICENSE README.md CHANGELOG.md run.py "RELEASE-NOTES-v$version.md"; do cp -a "$root/$n" "$stage/"; done
for n in assets examples openpowermenu plasmoid docs; do cp -a "$root/$n" "$stage/"; done
mkdir -p "$stage/scripts"
cp -a "$root/scripts/install-core.sh" "$root/scripts/uninstall-core.sh" "$stage/scripts/"
find "$stage" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$stage" -type f -name '*.pyc' -delete
(
  cd "$tmp"
  zip -qr "$tmp/OpenPowerMenu-EZ-v$version.zip" "$(basename "$stage")"
  tar -czf "$tmp/OpenPowerMenu-EZ-v$version.tar.gz" "$(basename "$stage")"
)
# Replace complete archives; updating an existing ZIP retains obsolete filenames.
mv "$tmp/OpenPowerMenu-EZ-v$version.zip" "$dist/"
mv "$tmp/OpenPowerMenu-EZ-v$version.tar.gz" "$dist/"
(
  cd "$dist"
  sha256sum "OpenPowerMenu-EZ-v$version.zip" "OpenPowerMenu-EZ-v$version.tar.gz" > SHA256SUMS
)
printf 'Complete release ZIP: %s\n' "$dist/OpenPowerMenu-EZ-v$version.zip"
printf 'Complete release TAR: %s\n' "$dist/OpenPowerMenu-EZ-v$version.tar.gz"
printf 'Widget-only archive is NOT included; see docs/KDE-STORE.md.\n'
