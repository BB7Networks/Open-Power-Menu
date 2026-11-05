"""Configuration compatibility and persistence for menu entry icons."""
from copy import deepcopy
import json
import pytest
from openpowermenu.core import DEFAULT_CONFIG, load_config, save_config, validate_configuration


def test_menu_icons_legacy_default_and_roundtrip(tmp_path):
    path = tmp_path / 'menu.json'
    config = deepcopy(DEFAULT_CONFIG)
    config.pop('show_menu_icons')
    path.write_text(json.dumps(config))
    assert load_config(path)['show_menu_icons'] is True
    original_menu = deepcopy(config['menu'])
    for visible in (False, True):
        config['show_menu_icons'] = visible
        save_config(config, path)
        loaded = load_config(path)
        assert loaded['show_menu_icons'] is visible
        assert loaded['menu'] == original_menu


@pytest.mark.parametrize('value', [None, 0, 1, '', 'false', [], {}])
def test_menu_icons_reject_non_boolean(value):
    config = deepcopy(DEFAULT_CONFIG)
    config['show_menu_icons'] = value
    with pytest.raises(ValueError, match='show_menu_icons'):
        validate_configuration(config)
