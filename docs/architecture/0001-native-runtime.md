# Native runtime migration

Status: accepted for v1.1 development; production cutover is gated on parity.
Baseline: main `34058480b6e3bc1ecc1f19d420fb744f570eca34` (released 1.0.1).

## Decision

Use a small, out-of-process C++17 backend built with CMake and Qt 6 Core/DBus.
Keep the existing Plasma QML launcher integration, native Meta+X binding,
flyouts, row content, pointer-dismissal policy and layout editor. Put the
configuration model and guarded storage in a reusable native library. A later
Qt Quick/Kirigami editor and standalone frontend can use that library without
embedding Python or running another command interpreter.

The first native target is an explicit development executable. The normal
installer, D-Bus activation file and working Python UI remain available until
the replacement passes the migration gates. A successful native backend build
alone is not proof that the complete application no longer needs PySide6.

## Alternatives considered

| Approach | Benefit | Cost / decision |
| --- | --- | --- |
| Qt Core/DBus C++ service + existing Plasma QML | Small runtime, stable IPC, process isolation, shared native storage | Chosen; port and test safety behavior rather than translating the whole UI at once |
| Mostly QML with a small in-process C++ plugin | Fewer IPC calls | File descriptors, locks, command execution and backup safety still need native code; loading that code into plasmashell adds ABI and crash risk |
| Python standard library service with another D-Bus binding | Smaller port | Still requires Python and a new binding/event loop; does not meet the preferred runtime goal |
| Shell scripts/qdbus as the backend | Little compilation | Poor fit for validated JSON, transactions, conflicts and recovery; rejected |
| C++ Qt Widgets rewrite of every window | Closest mechanical port | Duplicates the existing QML editing/navigation infrastructure; prefer Qt Quick reuse for the next UI milestone |

## Dependency inventory

| Feature | 1.0.1 runtime | Native destination |
| --- | --- | --- |
| Config validation, command candidates, menu normalization | Python standard library | Qt Core + POSIX file operations |
| Session service and layout transactions | Python + PySide6 Core/DBus | Qt Core/DBus; same method signatures |
| Detached command launch | Python subprocess | QProcess detached argv execution |
| General/Layout/Backups editor, Undo/Redo, dialogs | Python + PySide6 Core/Gui/Widgets | Qt Quick/Controls + Kirigami, shared native model; pending |
| Standalone menu and Wayland toplevel | Python + PySide6 Widgets | Native Qt Quick frontend; pending |
| Backup reads, conflicts, atomic writes, restore/delete | Python + POSIX descriptors/flock | Native descriptor-relative storage with equivalent recovery tests |
| Panel button, Meta+X, launcher handoff, AppGrid adapter | Plasma 6, Qt Quick, Plasma/Kirigami QML modules | Reuse; no Python in the widget itself |
| In-menu drag, Go Back, draft reference trees | Existing QML/JavaScript + service | Reuse; port service transactions |
| Application discovery/desktop Exec semantics | Python scanner; kioclient6, GIO or conservative fallback | Prefer KDE's application model/KService in the native editor; preserve existing picker argv literally in backend |
| Widget snapshots and reversible EZ installer | Bash, Python, kpackagetool6; optional kbuildsycoca6/busctl | Native snapshot/install helper before installer cutover; pending |
| Built-in tools | Installed applications, kcmshell6, qdbus6, loginctl as applicable | Preserve candidate availability and KDE confirmations; don't install missing tools |

Build dependencies for native development: CMake, a C++17 compiler, Qt 6
development headers/tools, and Ninja or Make. Qt Test is used only for tests.
Python/pytest and Node remain development compatibility-test tools. They are
not linked into, embedded in, or spawned by the native model/service.

The native backend itself needs Qt Core, Qt DBus, the C++ runtime and libc.
The eventual GUI adds the Qt Quick/Controls and KDE QML modules already used
on Plasma. Binary packages must declare actual distro/architecture/Qt/glibc
requirements; a locally built ELF is not a universal Linux binary. Ordinary
binary installations must not compile on the user's desktop.

## Compatibility and safety contract

- Keep the existing JSON schema and unknown metadata. Shared checked-in JSON
  supplies defaults and built-in candidates to both implementations, embedded
  in the native binary at build time; Python is not a build requirement.
- Preserve D-Bus presentation data and position-based command keys. A key is
  resolved against validated local configuration; the widget never sends argv.
  Future access keys belong to item metadata, independent of those positions.
- Use argument arrays with no implicit shell. Preserve literal application
  picker arguments, environment inheritance and detached process lifetime.
- Use bounded reads (4 MiB), reject symlinks in every path component, reject
  special files without blocking, and retain file identity plus content for
  conflict checks. QSaveFile alone does not satisfy this contract.
- Coordinate writes with the existing `.menu.lock` flock; stage private files,
  sync before atomic replacement, preserve backups, and check revisions again
  immediately before replacement. Keep explicit restoration copies even when
  automatic backup retention is zero.
- Preserve bounded reference-only layout sessions, all original definitions,
  unknown properties and hidden entries. Invalid saves retain the draft.
- Never replace a running service owner, restart Plasma, rewrite the panel,
  remove PySide6, or switch the normal installer during an incomplete port.

## Milestones and cutover gates

1. Audit/decision, shared catalog and CMake native foundation.
2. Native configuration reads, validation, resolution, D-Bus dispatch and layout
   transactions with differential and private-session tests.
3. Native recovery browser operations, full configuration editing model,
   application discovery, Qt Quick editor and standalone parity.
4. Native snapshot/install helper; distro-specific binary packaging, missing
   dependency diagnostics, clean installs and failure-safe upgrades. Keep
   source builds separate from ordinary EZ binary installation.
5. Item access keys, visibility modes and independent binding reset; then
   configurable closing/hover delay and native Sleep/Hibernate capability
   checks. Preserve KDE policies, inhibitors and confirmations.
6. Complete automated regression and physical Plasma Wayland/X11 acceptance;
   only then change the default runtime and remove mandatory PySide6.

The native editor is a separate migration milestone because its recovery,
conflict, Undo/Redo and drag behavior cannot safely be replaced by a reduced
settings window. New UX features should use the shared model after that
contract stabilizes. No release is created by these development milestones.
