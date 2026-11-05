from copy import deepcopy
import json
from types import SimpleNamespace
import pytest
from openpowermenu import core
from openpowermenu.menu_api import public_menu_from_config


def test_default_desktop_placement_and_existing_menu_unchanged(tmp_path):
    menu=core.DEFAULT_CONFIG['menu']
    assert menu[-1]=={'action':'show_desktop'}
    assert menu[-2]['submenu']=='Shut down or sign out'
    assert all(item.get('action')!='show_desktop' for item in menu[-2]['items'])
    saved={'menu':[{'label':'My Desktop','command':['true']}]}
    path=tmp_path/'menu.json';path.write_text(json.dumps(saved))
    assert core.load_config(path)['menu']==saved['menu']
    assert core.load_config(path)['auto_close_on_pointer_leave'] is False


def test_desktop_requires_registered_native_action(monkeypatch):
    monkeypatch.setenv('XDG_CURRENT_DESKTOP','KDE')
    monkeypatch.setattr(core,'which_executable',lambda name:True)
    monkeypatch.setattr(core.shutil,'which',lambda name:'/usr/bin/qdbus6')
    calls=[]
    def probe(argv,**kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0,stdout='Other\nShow Desktop\n')
    monkeypatch.setattr(core.subprocess,'run',probe)
    core._kwin_shortcuts.cache_clear()
    command=core.resolve_action('show_desktop')
    assert command.title=='Desktop' and command.icon=='user-desktop'
    assert command.argv==('qdbus6','org.kde.kglobalaccel','/component/kwin',
                          'org.kde.kglobalaccel.Component.invokeShortcut','Show Desktop')
    assert calls[0][-1].endswith('.shortcutNames') # discovery never toggles
    assert public_menu_from_config({'menu':[{'action':'show_desktop'}]})[0]['close_before_run'] is True
    monkeypatch.setattr(core.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout='Show Desktop Other\n'))
    core._kwin_shortcuts.cache_clear()
    assert core.resolve_action('show_desktop') is None
    monkeypatch.setenv('XDG_CURRENT_DESKTOP','GNOME')
    assert core.resolve_action('show_desktop') is None
    core._kwin_shortcuts.cache_clear()


@pytest.mark.parametrize('value',[None,0,1,'false',[],{}])
def test_auto_close_strict_bool(value):
    config=deepcopy(core.DEFAULT_CONFIG);config['auto_close_on_pointer_leave']=value
    with pytest.raises(ValueError,match='auto_close_on_pointer_leave'):core.validate_configuration(config)
