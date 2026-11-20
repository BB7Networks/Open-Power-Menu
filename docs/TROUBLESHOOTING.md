# Troubleshooting native 2.1

First identify the exact archive, `SOURCE-COMMIT`, distribution, Qt/Plasma version
and X11/Wayland session. The [compatibility table](COMPATIBILITY.md) is a tested
runtime boundary, not a guarantee for arbitrary Qt/KDE installations.

- **Source installer does nothing:** this is intentional. Download the matching
  complete native EZ ZIP; see [installation](INSTALLATION.md).
- **Missing library, QML module or native plugin:** run the EZ wrapper's `--check`
  and read its dependency diagnostic. Use the distribution's packages and full
  update procedure. Do not copy foreign libraries or only the widget QML.
- **Backend or Configure unavailable:** `open-power-menu --version` and
  `open-power-menu --check` are read-only checks. Keep the matching complete
  native payload together. The [session investigation](history/2.1-development/SESSION-RELIABILITY.md)
  records the permanent environment resolution; no shell restart is required.
- **Old widget behavior after an update/rollback:** Plasma may retain loaded QML.
  Sign out/in when convenient; the installer does not do it automatically.
- **Confirmation differs from the checkbox:** inspect whether the row is a
  native built-in or a custom command; see [power behavior](POWER.md). Do not
  trigger another live power action to diagnose it.
- **Shortcut conflicts:** inspect the existing widget's Keyboard Shortcuts in
  Plasma. Preserve deliberate custom/disabled assignments. Do not rewrite panels.
- **Need to undo an install:** retain the extracted archive and use
  [recovery/rollback](RECOVERY.md).

Default-off popup/session diagnostics remain available. The archived
[X11 capture guide](history/2.1-development/X11-POPUP-DIAGNOSTICS.md) and
[RC2 diagnostics](history/2.1-development/POWER-DISTRIBUTION-RC2.md) describe the
existing gates. Diagnostics must not request focus or dispatch extra actions.
The physically verified X11 Qt.Tool/transient-parent correction is preserved.

Known limitations: translucent-panel text ghosting and minor responsiveness are
deferred. One earlier private X11 focus-readiness timeout did not recur on an
unchanged debug retry; its cause is unconfirmed. Physical acceptance remains
required before stable publication. Wayland placement/activation and releases
outside OPM have the documented compositor/fail-closed limitations.
