# Open Power Menu 2.1.0 — Phase 1 preparation

Version 2.1.0 is used in the staged packages. Stable publication is **not approved**.
No RC3 or additional release candidate is created. The baseline is published RC2,
`2f889df3e5b29f49611f8cf37f41f15e86cad7c1`.

Phase 1 adds distribution-native EZ installers for qualified Manjaro, Debian 13
and Kubuntu 26.04 x86-64 systems, wrapping the existing transactional installer.
Power Actions in Configure uses its natural dropdown width. The confirmation
enum and dispatch behavior are unchanged. The native runtime, widget, editor,
X11 popup/Meta+X fixes, physical-key protection and configuration/recovery systems
continue from RC2.

**Power actions may execute immediately.** Existing preferences and explicit
custom commands retain their behavior. New installations follow KDE settings.
Never exercise power actions against real services during automated acceptance.

Staging downloads, qualification, compatibility and the Phase 1 file inventory
are documented in `docs/EZ-INSTALLER-PHASE1.md`. Repository cleanup, brochure
README/screenshots, merge, stable tag and publication require later review.
Historical v1.0.1, RC1, RC2 and draft PR #10 remain unchanged.

X11 translucent-panel ghosting and minor responsiveness work remain deferred.
Physical workstation acceptance remains pending.
