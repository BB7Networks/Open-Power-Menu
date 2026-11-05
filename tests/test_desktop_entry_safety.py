from pathlib import Path
from unittest.mock import patch

import pytest

from openpowermenu.desktop_apps import (
    DesktopApplication, application_command, application_menu_item, desktop_exec_argv, read_desktop_application,
)
from openpowermenu.core import get_item_info


def test_locale_modifier_and_escaped_display_strings(tmp_path):
    file = tmp_path / 'sample.desktop'
    file.write_text('[Desktop Entry]\nType=Application\nName=Default\nName[sr@latin]=Latin\\sname\nExec=example\n')
    with patch('openpowermenu.desktop_apps.locale.getlocale', return_value=('sr_RS@latin', 'UTF-8')):
        assert read_desktop_application(file).name == 'Latin name'


def test_two_levels_of_exec_escaping_and_literal_metacharacters():
    # Four backslashes in the file become two after string unescaping and one
    # after Exec's double-quote argument parsing. Shell syntax remains literal.
    argv = desktop_exec_argv(r'tool "a\\\\b" "semi;colon" "$(touch /tmp/no)" %%', 'Name', '', Path('/tmp/app.desktop'))
    assert argv == ['tool', 'a\\b', 'semi;colon', '$(touch /tmp/no)', '%']


def test_working_directory_never_silently_dropped_without_launcher():
    app = DesktopApplication('Example', '', Path('/tmp/example.desktop'), 'example', working_directory='/tmp')
    with patch('openpowermenu.desktop_apps.shutil.which', return_value=None):
        with pytest.raises(ValueError, match='working directory'):
            application_command(app)
    with patch('openpowermenu.desktop_apps.shutil.which', side_effect=lambda name: name == 'kioclient6'):
        assert application_command(app) == ['kioclient6', 'exec', '/tmp/example.desktop']


def test_gio_does_not_silently_drop_desktop_filename_field():
    app = DesktopApplication('Example', '', Path('/tmp/example.desktop'), 'example %k')
    with patch('openpowermenu.desktop_apps.shutil.which', side_effect=lambda name: name == 'gio'):
        with pytest.raises(ValueError, match='%k'):
            application_command(app)
    with patch('openpowermenu.desktop_apps.shutil.which', return_value=None):
        assert application_command(app) == ['example', '/tmp/example.desktop']


def test_picker_names_and_paths_are_not_expanded_as_custom_variables():
    app = DesktopApplication('$HOME {home} ~', '', Path('/tmp/$HOME {home}/app.desktop'), 'example %c')
    with patch('openpowermenu.desktop_apps.shutil.which', side_effect=lambda name: name == 'kioclient6'), \
         patch('openpowermenu.core.which_executable', return_value=True):
        _, _, resolved = get_item_info(application_menu_item(app))
    assert resolved.argv == ('kioclient6', 'exec', '/tmp/$HOME {home}/app.desktop')
    with patch('openpowermenu.desktop_apps.shutil.which', return_value=None), \
         patch('openpowermenu.core.which_executable', return_value=True):
        _, _, resolved = get_item_info(application_menu_item(app))
    assert resolved.argv == ('example', '$HOME {home} ~')
