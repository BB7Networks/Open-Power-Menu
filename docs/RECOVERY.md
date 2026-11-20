# Backups, rollback, recovery and removal

Configuration backups and application installation snapshots are separate.
Configure → Backups previews and restores menu configuration with identity,
ownership and conflict checks. Protected pre-restore/pre-overwrite copies remain
available. Application rollback restores the preceding complete application,
widget and activation files; it does not roll personal configuration backwards.

Keep the extracted matching EZ directory. As your desktop user:

```sh
bash install.sh --recover
bash install.sh --rollback
```

Recovery handles an interrupted native transaction. Rollback uses the preceding
captured installation, including 1.0.1/RC1/RC2 when that is the snapshot. Keep the
old Python/PySide6 dependencies for a 1.0.1 rollback; OPM never removes them.
The native dispatcher also supports `open-power-menu --recover` and `--rollback`.
If a wrapper's runtime checks cannot run, the retained matching bundle provides
`native-bundle/app/bin/open-power-menu-install --recover` or `--rollback` with the
same native safeguards. Do not use a foreign distribution's executable.

Snapshots are under
`${XDG_DATA_HOME:-$HOME/.local/share}/open-power-menu-recovery/native-installs`.
External widget history and configuration backups remain in their existing paths.
There is no automatic native installation-history pruning. Do not manually delete
an unfinished transaction or snapshots needed for rollback.

Before removal, remove **only OPM's applet** through Plasma so its existing
handler restores the original launcher and relinquishes its shortcut. Keep the
original launcher. Then, from the retained EZ directory:

```sh
bash install.sh --uninstall
```

Personal configuration and recovery history remain. Root source-checkout scripts
perform no removal and never guess the installed runtime. The historical 1.0.1
archive retains its original uninstall procedure; `legacy/` in the current source
is fixture material only.

Changing installed widget files can require voluntary sign-out/sign-in because
Plasma caches QML. The installer never restarts Plasma, logs out, recreates the
widget or rewrites panels. After rollback to 1.0.1, an older cached frontend may
need that sign-in before dispatch works. Ordinary settings changes need no restart.
