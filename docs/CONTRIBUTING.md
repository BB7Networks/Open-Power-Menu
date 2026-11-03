# Contributing

Contributions and bug reports are welcome once a GitHub repository is published.

Open an issue with your Plasma version, distribution, launcher plugin ID,
reproduction steps, and (where possible) relevant lines from:

```bash
journalctl --user -b --no-pager -o cat | grep 'Open Power Menu:' | tail -n 35
```

Do not post sensitive paths, tokens, passwords, private commands, or other
users' information in issues.

Run `python3 -m pytest -q` before sending changes. The adapter architecture
is described in `ADAPTERS.md`; keep launcher-specific behavior out of the
normal Plasma adapter. Preserve the reversible HiddenStatus behavior and do
not remove users' existing launchers or rewrite the panel configuration.
