# Reviewing and preparing releases

Version **1.0.1** is authorized as the public release candidate. A versioned
build is not a published release. Keep the widget ID `org.openpowermenu.start`
stable and preserve existing menu/panel settings.

## Review gates

1. Confirm `main` includes merged PRs #8 and #9, with the current 1.0.1
   gallery. PR #7 was reviewed and closed as superseded; do not replace the
   newer captures with its historical gallery.
2. Run [automated and physical checks](TESTING.md), including the
   [1.0.1 release checklist](RELEASE-1.0.1.md). Verify real Manjaro Wayland
   Desktop toggling, cross-window pointer dismissal and launcher/shortcut behavior.
3. Test clean installation, upgrade, failure rollback and uninstall from the
   extracted EZ package. Preserve custom menus, widget instances and recovery
   history. Review exact archive checksums and contents before distribution.
4. The feature merges are complete. Obtain explicit approval before **tagging,
   publishing a GitHub Release, or submitting to KDE Store**. The build
   scripts do not publish anything.

## Build review artifacts

```bash
bash scripts/build-release.sh
bash scripts/build-widget-only.sh
(cd dist && sha256sum -c SHA256SUMS)
unzip -t dist/OpenPowerMenu-EZ-v1.0.1.zip
tar -tzf dist/OpenPowerMenu-EZ-v1.0.1.tar.gz
```

The metadata version controls archive names, top-level directory and release-note
selection. Python/CLI/D-Bus report the matching package version, covered by tests.
The complete ZIP/TAR contain backend, widget, assets, screenshots, documentation
and both installer wrappers. Widget-only packaging remains separate.

After review and explicit publication approval, attach the complete EZ ZIP,
TAR.GZ and SHA256SUMS to the approved GitHub release. Do not replace published
versioned artifacts with different contents. Update the README's candidate notice
only when the actual public release exists.

See [KDE Store](KDE-STORE.md) before considering that separate distribution path.
