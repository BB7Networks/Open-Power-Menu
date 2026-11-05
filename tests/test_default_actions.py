"""Availability must describe the command that will actually run."""
import json
import subprocess
from unittest.mock import patch

import pytest

from openpowermenu import core
from openpowermenu.editor_helpers import built_in_candidates


@pytest.mark.parametrize('installed,expected', [
    ({'ksystemlog'}, ('ksystemlog',)),
    ({'ksystemlog', 'konsole', 'journalctl'}, ('ksystemlog',)),
    ({'konsole', 'journalctl'}, ('konsole', '--hold', '-e')),
    ({'xterm', 'journalctl'}, ('xterm', '-hold', '-e')),
    ({'konsole', 'xterm', 'journalctl'}, ('konsole', '--hold', '-e')),
    ({'konsole'}, None), ({'journalctl'}, None), (set(), None),
])
def test_logs_preference_and_secondary_requirements(installed, expected):
    with patch.object(core, 'which_executable', side_effect=installed.__contains__):
        selected = core.resolve_action('logs')
        effective, details = built_in_candidates('logs')
    if expected is None:
        assert selected is None
        assert effective == 'Not available on this computer'
        assert all('[not available]' in option for option in details)
    else:
        assert selected.argv[:len(expected)] == expected
        assert selected.argv[0] in effective
        if selected.argv[0] != 'ksystemlog':
            assert selected.argv[3:] == ('journalctl', '-b', '-p', 'warning', '-n', '1000', '--follow', '--no-pager')
        else:
            assert selected.argv == ('ksystemlog',)  # no desktop %c, sudo, or forced root
    if 'journalctl' not in installed:
        assert all('[not available]' in option for option in details[1:])


@pytest.mark.parametrize('installed,module,expected', [
    ({'kcmshell6', 'system-config-printer'}, True, ('kcmshell6', 'kcm_printer_manager')),
    ({'kcmshell6', 'system-config-printer'}, False, ('system-config-printer',)),
    ({'system-config-printer'}, False, ('system-config-printer',)),
    ({'kcmshell6'}, False, None), (set(), False, None),
])
def test_printers_checks_module_and_fallback(installed, module, expected):
    with patch.object(core, 'which_executable', side_effect=installed.__contains__), \
         patch.object(core, 'kcm_is_available', return_value=module):
        command = core.resolve_action('printers')
        effective, details = built_in_candidates('printers')
    assert (command.argv if command else None) == expected
    assert ('[installed]' in details[0]) == ('kcmshell6' in installed and module)
    assert core.COMMANDS['printers']['icon'] == 'preferences-devices-printer'


def test_kcm_probe_exact_name_timeout_errors_and_short_cache():
    core._kcm_modules.cache_clear()
    result = subprocess.CompletedProcess([], 0, 'kcm_printer_manager_extra - Wrong\nkcm_printer_manager - Printers\n', '')
    with patch.object(core.shutil, 'which', return_value='/bin/kcmshell6'), \
         patch.object(core.subprocess, 'run', return_value=result) as run, \
         patch.object(core.time, 'monotonic', return_value=60):
        assert core.kcm_is_available('kcm_printer_manager')
        assert core.kcm_is_available('kcm_printer_manager')
        assert not core.kcm_is_available('printer')
        run.assert_called_once_with(['/bin/kcmshell6', '--list'], capture_output=True,
                                    text=True, errors='replace', timeout=2, check=False)
    for failure in (OSError('missing'), subprocess.TimeoutExpired('kcmshell6', 2)):
        core._kcm_modules.cache_clear()
        with patch.object(core.shutil, 'which', return_value='/bin/kcmshell6'), \
             patch.object(core.subprocess, 'run', side_effect=failure):
            assert not core.kcm_is_available('kcm_printer_manager')
    core._kcm_modules.cache_clear()
    with patch.object(core.shutil, 'which', return_value='/bin/kcmshell6'), \
         patch.object(core.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, 'kcm_printer_manager', '')):
        assert not core.kcm_is_available('kcm_printer_manager')
    core._kcm_modules.cache_clear()


def test_printers_only_added_to_new_defaults(tmp_path):
    assert {'action': 'printers'} in core.load_config(tmp_path / 'new.json')['menu']
    original = {'menu': [{'submenu': 'Personal', 'items': [{'action': 'logs'}]}]}
    path = tmp_path / 'menu.json'
    path.write_text(json.dumps(original))
    loaded = core.load_config(path)
    assert loaded['menu'] == original['menu']
    core.save_config(loaded, path)
    assert core.load_config(path)['menu'] == original['menu']


@pytest.mark.parametrize('menu', [
    [{'command': ['echo', '\x00']}], [{'action': ['bad']}],
    [{'submenu': 'bad', 'items': 'wrong'}], [{'command': 'echo hello'}],
])
def test_corrupted_menu_rejected_on_load(tmp_path, menu):
    path = tmp_path / 'menu.json'
    payload = json.dumps({'menu': menu})
    path.write_text(payload)
    with pytest.raises(ValueError):
        core.load_config(path)
    assert path.read_text() == payload
