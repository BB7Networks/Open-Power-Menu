"""The user configures shortcuts in KDE; OPM only supplies a command and opens its UI."""
import os
from pathlib import Path
import shlex

import pytest

from openpowermenu.shortcut_setup import installed_application, installed_command, settings_command


def executable(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/bin/sh\nexit 0\n')
    path.chmod(0o755)
    return path


def test_resolve_installed_command_with_spaces_and_literal_shell_characters(tmp_path, monkeypatch):
    folder = tmp_path / "user bin 'quoted' $literal"
    expected = executable(folder / 'open-power-menu')
    monkeypatch.setenv('XDG_BIN_HOME', str(folder))
    assert shlex.split(installed_command()) == [str(expected)]


def test_fallback_to_path_and_missing_installation(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_BIN_HOME', str(tmp_path / 'missing'))
    expected = executable(tmp_path / 'bin/open-power-menu')
    monkeypatch.setenv('PATH', str(expected.parent))
    assert shlex.split(installed_command()) == [str(expected)]
    expected.chmod(0o644)
    assert installed_command() is None


@pytest.mark.parametrize('available,expected', [
    (['kcmshell6', 'systemsettings'], 'kcmshell6'), (['systemsettings'], 'systemsettings'),
    (['kcmshell5'], None), ([], None),
])
def test_only_supported_kde_settings_commands_are_selected(tmp_path, monkeypatch, available, expected):
    for name in available: executable(tmp_path / name)
    monkeypatch.setenv('PATH', str(tmp_path))
    assert settings_command() == ([str(tmp_path / expected), 'kcm_keys'] if expected else None)


def test_application_entry_respects_xdg_precedence_and_hidden_override(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'user'))
    monkeypatch.setenv('XDG_DATA_DIRS', str(tmp_path / 'system'))
    assert installed_application() is None
    desktop = '[Desktop Entry]\nType=Application\nName=Open Power Menu\nExec=/bin/true\n'
    system = tmp_path / 'system/applications/org.openpowermenu.desktop'
    system.parent.mkdir(parents=True)
    system.write_text(desktop)
    assert installed_application() == system
    user = tmp_path / 'user/applications/org.openpowermenu.desktop'
    user.parent.mkdir(parents=True)
    user.write_text(desktop)
    assert installed_application() == user
    user.write_text(desktop + 'Hidden=true\n')
    assert installed_application() is None
