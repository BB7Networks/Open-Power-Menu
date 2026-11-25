"""Native state parsing does not map, activate or repaint a window."""
import importlib.util
from pathlib import Path

path=Path(__file__).resolve().parents[1]/'tools/trace-x11-popup.py'
spec=importlib.util.spec_from_file_location('opm_x11_probe',path)
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_native_map_and_geometry_are_read_only(monkeypatch):
    calls=[]
    def read(*args):
        calls.append(args)
        return 0, '''Absolute upper-left X: -1280
Absolute upper-left Y: 750
Width: 336
Height: 269
Map State: IsUnMapped
'''
    monkeypatch.setattr(probe,'read',read)
    assert probe.window_state('0x123') == {'map':'IsUnMapped',
        'geometry':{'x':-1280,'y':750,'width':336,'height':269}}
    assert calls==[('xwininfo','-id','0x123')]
    monkeypatch.setattr(probe,'read',lambda *args:(1,''))
    assert probe.window_state('0x123')=={'map':'destroyed-or-unavailable'}
