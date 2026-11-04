# Contributing

Contributions and [bug reports](https://github.com/BB7Networks/Open-Power-Menu/issues)
are welcome. Work on a feature branch and open a pull request; do not commit
directly to `main`. Keep changes small and retain launcher/panel safety.

Open an issue with your Plasma version, distribution, launcher plugin ID,
reproduction steps, and (where possible) relevant lines from:

```bash
journalctl --user -b --no-pager -o cat | grep 'Open Power Menu:' | tail -n 35
```

Do not post sensitive paths, tokens, passwords, private commands, or other
users' information in issues.

Run `python3 -m pytest -q -ra` before sending changes; see [TESTING.md](TESTING.md)
for optional Qt/D-Bus checks and the live desktop acceptance matrix. Report
skips and manual checks separately. The adapter architecture
is described in `ADAPTERS.md`; keep launcher-specific behavior out of the
normal Plasma adapter. Preserve the reversible HiddenStatus behavior and do
not remove users' existing launchers or rewrite the panel configuration.
