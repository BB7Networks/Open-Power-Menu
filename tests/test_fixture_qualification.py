"""Qualification checks must accept theme framing but reject content loss."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'native/tests'))
from plasma_startup import validate_flyout_root
sys.path.pop(0)
spec=importlib.util.spec_from_file_location('profiles',ROOT/'scripts/qualification_profiles.py')
profiles=importlib.util.module_from_spec(spec);spec.loader.exec_module(profiles)


def geometry(padding):
    return {'open':True,'window':[8,558,336,370+padding,True],
            'flyout':{'visible':True,'height':106},'preferred':370,'min':370,
            'max':370,'actual':370,'padding':padding,'area':952}


def test_theme_margin_change_preserves_content_geometry():
    validate_flyout_root(geometry(12),geometry(8))


@pytest.mark.parametrize('change',[
    {'window':[8,558,336,400,True]}, {'actual':360}, {'preferred':360},
    {'window':[8,558,336,378,False]}, {'flyout':{'visible':False}}, {'area':377},
])
def test_flyout_still_rejects_root_layout_regressions(change):
    with pytest.raises(AssertionError): validate_flyout_root(geometry(12),{**geometry(8),**change})


def test_current_wayland_profile_cannot_replace_pinned_x11():
    current='plasma-workspace 6.8.2-1\nkwin 6.8.2-2\nqt6-base 6.12.0-5\n'
    profiles.validate('manjaro-wayland',current)
    with pytest.raises(ValueError,match='6.7'): profiles.validate('plasma67-x11',current)
    with pytest.raises(ValueError,match='mixed'): profiles.validate('manjaro-wayland',current+'kwin-x11 6.7.5-1\n')


def test_pinned_x11_profile_requires_its_compositor():
    pinned='plasma-workspace 6.7.5-1\nkwin 6.7.5-1\nqt6-base 6.11.2-3\n'
    with pytest.raises(ValueError,match='6.7'): profiles.validate('plasma67-x11',pinned)
    profiles.validate('plasma67-x11',pinned+'kwin-x11 6.7.5-1\n')


def test_long_failure_evidence_survives_docker_tail_noise(tmp_path):
    log=tmp_path/'failure.log'
    failure={'time_ms':1,'event':'failure-before-teardown','scenario':'held-I',
             'assertion':'exact original assertion','focus':{'window':'42'},
             'processes':[],'state':{'ignored':'x'*10000},'requests':[{'member':'logout'}]}
    log.write_text('#17 OPM_FIXTURE '+json.dumps(failure)+'\n'+('RUN unhelpful repeated command\n'*100))
    result=subprocess.check_output([sys.executable,str(ROOT/'scripts/report-ci-failure.py'),str(log)],text=True)
    assert 'held-I' in result and 'exact original assertion' in result and 'logout' in result
