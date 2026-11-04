# Editor and recovery

These changes are unreleased and retain the v0.4.17 version identifiers. Configure
now has **General | Layout | Backups** tabs. No saved menu migration is required.
For the separate Lock/Unlock controls in the live menu, see
[in-menu editing](IN-MENU-EDITING.md).

## PR #4 verification baseline (2026-11-04)

- Before changes: **177 passed, 8 skipped, 18 subtests passed**.
- After changes, including runtime-loader safety: **281 passed, 8 skipped,
  18 subtests passed** in the full suite
  with Python 3.12, PySide6 6.10.2, offscreen Qt, isolated D-Bus sessions and Node
  24. CI uses Node 22. All eight skips are unavailable historical release trees.
- Python compilation, all seven Bash scripts checked individually, full ZIP/TAR
  and widget archive integrity, checksums and extracted-backend checks pass.
- At the PR #4 baseline, the entire `plasmoid/` tree, D-Bus service, standalone menu and detached-launch
  module are unchanged from PR #3. An AST comparison also confirms the existing
  core command-resolution functions are unchanged; only loading, saving, retention and
  validation reporting changed there.

PR #5 extends the widget and D-Bus service; its verification is recorded in
[the in-menu editing guide](IN-MENU-EDITING.md#verification).
CI requires a separate Qt job; portable CI deliberately skips Qt-dependent tests
without PySide6. The live acceptance procedure below remains outstanding.

## Organizing the menu

In Configure → Layout, drag an entry onto a submenu to append it inside. Drop
above or below an entry at the indicated line to insert beside it. Dropping in
the empty tree area moves an entry to the end of the top-level menu. A submenu
moves with all descendants and custom metadata. Self/descendant moves are
rejected; the existing limit of eight submenu levels and 200 entries per menu
also applies to drops, adds and duplicates. Invalid operations leave the prior
layout intact.

Duplicate inserts an independent deep copy immediately after the selected item.
Each accepted edit, add, remove, duplicate, move or default-layout reset is one
undo step. Canceled dialogs and ineffective moves create no step. Selection and
expanded/collapsed state are restored with the layout. History lasts until the
editor closes or successfully reloads/restores a configuration.

| Shortcut | Action |
| --- | --- |
| F2 | Edit selected entry |
| Ctrl+D | Duplicate selected entry |
| Delete | Remove selected entry, including submenu children |
| Alt+Up / Alt+Down | Move among siblings |
| Alt+Right | Move into the immediately preceding submenu |
| Alt+Left | Move out of a submenu, immediately after its parent |
| Ctrl+Z | Undo layout change |
| Ctrl+Shift+Z / Ctrl+Y | Redo layout change |

Entry shortcuts apply while the tree has focus. The context menu lists them;
Move Up/Down buttons provide another option. Undo/Redo sit on the right beneath
the tree; the editing controls wrap at narrow widths. The introduction uses a
short rich-text bullet list with an accessible plain-text name. Long labels and
commands have full tooltips, and General and Backups scroll on smaller displays. System theme colors
and selection highlighting are used. General settings participate in dirty
tracking; layout Undo/Redo does not revert General settings.

## Save and conflict handling

The window indicates unsaved changes. Window close, Escape and Cancel all offer
Save / Discard / Cancel when needed. Save validates first; failed validation or
I/O leaves the editor open. Entry validation identifies the nested entry and
focuses its dialog field or tree row. Validation never executes its command.

The editor remembers actual file bytes and device/inode identity, detecting
same-timestamp edits, replacement with identical contents, and deletion. OPM
saves use a cooperative file lock and check the file before writing and again
before atomic replacement. Keep editing leaves disk untouched. Reload asks
before discarding unsaved changes. Explicit overwrite preserves the external
file as `menu.json.pre-overwrite-<UTC timestamp>` before replacing it. If the
external file changes again while that choice is open, overwrite fails safely
and the editor stays open. When the file was deleted there are no bytes to copy.

Files and path components must not be symlinks; configuration and backup files
must be regular files and at most 4 MiB. The editor, CLI and backend share these
reading and validation rules. A missing configuration file or directory returns
fresh defaults without creating files. New files use mode 0600, and temporary
files live beside the target for atomic replacement. Lock files are retained
in the configuration directory. Non-OPM tools do not honor the cooperative lock;
avoid writing concurrently during an explicit restore/overwrite operation.

## Preview and restore

Open Configure → Backups → Configuration backups → Manage / Restore Backups. The current
configuration appears first. History rows show local date/time, byte size and
validity. A preview lists the hierarchy, total entries, General settings and
which settings/sections differ from the active configuration. It reads definitions
without resolving or running commands. Close returns to the editor unchanged.

Select a valid row, choose Restore selected backup, and confirm. Restoration is
blocked while Configure has unsaved changes in any tab; preview remains available.
Save or discard those changes through the editor, then reopen Configure before
restoring. A restore cannot silently replace pending General or Layout changes.
The source is re-read and checked against the preview. A successful
restore saves the current bytes in `menu.json.pre-restore-<UTC timestamp>`, then
atomically installs the validated configuration and refreshes the editor.
Corrupt active JSON can also be preserved this way: opening Configure offers
the backup browser when the active file cannot be parsed.

Automatic saves retain ten previous versions by default; Backups accepts
0–1,000. Zero disables new automatic backups and leaves existing history alone.
Only the exact automatic `menu.json.bak-YYYYMMDDTHHMMSSffffffZ` pattern is rotated,
and only after a successful save. The selected restore source is exempt from
that operation's pruning, so the limit can temporarily be exceeded by one.

Pre-restore and pre-overwrite copies are **independent of automatic retention**,
including when it is zero. They are never automatically pruned. Manually named
`menu.json.bak-my-label` files appear in the browser and are also preserved.
Unrelated names and symlinks are ignored. There is no import/export UI.
Backups stay inside the OPM configuration directory, normally
`~/.config/open-power-menu/` (`XDG_CONFIG_HOME` is respected).

## Delete a selected configuration backup

Select a history row and choose **Delete selected backup…**. The confirmation
shows its name, local date and byte size and defaults to Cancel. Deletion is
permanent and cannot be undone. Pre-restore/pre-overwrite copies have an additional
warning that deleting them removes a protected rollback point. A corrupt or
oversized backup can be deleted without parsing it. After success the list selects
the next nearby history row; a manual Refresh preserves the current selection.

Only one explicitly selected backup is deleted. The active configuration, unrelated
files and widget snapshot directories are never valid targets. Manually named
backups remain protected from automatic rotation and can be removed only by an
explicit deletion action. Deleting history leaves unsaved Configure edits intact.

The backend accepts only recognized basenames within the confined configuration
directory and opens every directory component without following links. Deletion
requires a private, user-owned directory and a regular file owned by the current
user; symlinks, hard links, FIFOs and directories are refused. It fingerprints the
selection's directory identity, inode, size, mtime and ctime, plus bounded content
hashing for files within 4 MiB. After confirmation it rechecks the snapshot under
the existing cooperative writer lock and unlinks relative to that held directory.
Changed/replaced or missing files and permission failures leave the active file
untouched and show an error. As with saves, external tools must not bypass OPM's
cooperative lock while modifying the same directory.

## Widget upgrade history and uninstall

Widget snapshots are separate from `menu.json` backups. Their directory is now
`~/.local/share/open-power-menu-recovery/widget-backups/` (`XDG_DATA_HOME` is
respected). The installer and uninstaller move existing entries from the old
`open-power-menu/widget-backups/` directory before replacing/removing application
files. Name collisions receive a unique `legacy-…` name, preserving both copies.
Manual entries and links are moved as entries; links are never traversed.
Migration failure stops installation/removal, preserving remaining history.
The Backups tab displays the directory, the count of generated snapshot directories,
and the default retention of five. Manual snapshots and symlinks are excluded
from that count. Retention remains an installer setting rather than a GUI preference.
Opening or returning to **Backups** performs a new, read-only count. Enumeration
is shared with the snapshot helper, with no background polling or filesystem watch.
The separate configuration backup browser retains its manual **Refresh** button.
The displayed path remains selectable/copyable. Widget snapshot deletion is not
part of the configuration backup browser.

The installer completes a snapshot of an existing widget **before replacing any
installed application/widget files**. Snapshot-copy failure aborts the upgrade.
A failed KPackage upgrade retains all previous history plus the completed
pre-upgrade snapshot. It does not promise an automatic application rollback.
The installed backend may already have been updated when KPackage fails.

After successful installation only, the newest five generated widget snapshots
are retained. Set an independent limit of 1–1,000 for that installer invocation:

```bash
OPM_WIDGET_BACKUP_RETENTION=10 bash install.sh
```

The minimum is one so every successful upgrade keeps a rollback candidate.
This setting does not change the editor's configuration-backup limit. Only
directories named `org.openpowermenu.start-YYYYMMDD-HHMMSS-nanoseconds` are pruned,
ordered by their timestamped names. Manual names, migrated name collisions and
symlinks are preserved. Nested links in copied/pruned snapshots are not followed.
Prune failure leaves extra history and prints a warning.

Uninstall removes OPM's installed backend, command, desktop/D-Bus entries, icon
and widget. It preserves `menu.json`, all configuration backups, widget recovery
history, and the original launcher and panel settings.

To recover on a local Plasma desktop:

1. Keep a copy of your current configuration and the snapshot you intend to use.
   Inspect the snapshot's `metadata.json` for its widget version.
2. If needed, reinstall the **matching trusted complete release** to restore its
   Python backend. A widget snapshot contains the widget, not the backend. Keep
   the chosen snapshot outside automatic rotation while running that installer.
3. Run `kpackagetool6 --type Plasma/Applet --upgrade /absolute/path/to/snapshot`.
   Use `--install` instead if the widget package is absent. Follow the normal
   local widget-refresh procedure; do not restart Plasma through your only remote
   access session.
4. Run `open-power-menu --check`, verify both click menus and the original launcher,
   then restore a configuration through Manage / Restore Backups if needed. Never replace
   Plasma's panel configuration as part of OPM recovery.

## Required Manjaro Plasma 6 Wayland acceptance

Use a disposable account/VM, or back up your configuration and keep a recovery
terminal. Record Plasma/Qt/launcher versions, scaling, panel position and theme.

1. Open Configure at a smaller window size and at the workstation's normal/high
   scaling in light and dark themes. Check readable labels/tooltips, focus order,
   keyboard access, the right-aligned Undo/Redo controls, and all three tabs.
2. Create nested submenus with a custom command containing quoted arguments.
   Drag entries before/after siblings, into/out of groups, and move whole groups.
   Verify native drop indicators, selection, expansion, and rejected cycles.
3. Duplicate a group, edit only its copy, then use the documented keyboard
   actions, Undo/Redo and default-layout reset. Verify one logical undo per action
   and that General preferences survive layout reset/undo.
4. Change General, Layout and the backup limit. Exercise window-close, Escape and Cancel with all three
   choices. Open two editors, save from one, and check Keep editing, Reload and
   explicit overwrite in the other; inspect the pre-overwrite recovery file.
5. Set configuration retention to two, save several changes, and preview/restore
   history. Repeat with retention zero; verify the pre-restore copy and source
   remain. Try a corrupt/missing backup and confirm the active file is intact.
   With unsaved edits, confirm restore is blocked and the edits remain intact.
   Delete a disposable corrupt backup; cancel deletion of another and verify it
   remains. Check the extra warning for protected copies, changed-file refusal,
   active-row protection, nearby selection after deletion, and snapshot refresh on tab return.
6. Upgrade an existing disposable installation with legacy snapshots and a custom
   menu, using widget retention two. Verify migration, newest snapshots, the old
   widget contents, and unchanged menu/panel. Test a failed upgrade in the VM and
   follow the matching-backend recovery procedure above.
7. Verify original launcher favorites/settings, left-click, right-click, nested
   flyouts, hide/show and icon inheritance. Remove only OPM's panel widget and
   uninstall; confirm both kinds of recovery history and the original launcher
   remain. Reinstall and verify the preserved menu.

Offscreen tests exercise Qt widgets, key events, modal flows and a constructed
Qt drop event. They do not establish native Wayland pointer behavior, KPackage
desktop integration or visual correctness. Real screenshots belong in the
existing capture workflow only after these checks.
