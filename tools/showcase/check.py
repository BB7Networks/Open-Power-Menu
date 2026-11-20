#!/usr/bin/env python3
"""Validate published showcase assets and controlled comparison provenance.

Only the standard library is needed. --baseline additionally checks the frozen
Phase 2 records and protected runtime/gallery hashes for this docs-only review.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[2]
ASSETS=ROOT/'docs/images/2.1'
SOURCE='4e11393c4d289c453044130d79dc54a23049c32c'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',action='store_true');args=p.parse_args()
    manifest=json.loads((ASSETS/'manifest.json').read_text())
    assert manifest['native_source_commit']==SOURCE and manifest['version']=='2.1.0'
    rows=manifest['images'];assert len(rows)==39 and len({r['file'] for r in rows})==39
    assert {p.name for p in ASSETS.glob('*.png')}=={r['file'] for r in rows}
    for row in rows:
        path=ASSETS/row['file'];data=path.read_bytes()
        assert data[:8]==b'\x89PNG\r\n\x1a\n' and data[12:16]==b'IHDR',path
        size=list(struct.unpack('>II',data[16:24]));assert size==row['pixels'],path
        assert len(data)==row['bytes'] and sha(path)==row['sha256'],path
        assert max(size)<=1600 and min(size)>=250,path
        assert row['case'] in manifest['cases'] and len(row['source_frame_sha256'])==64
    assert sum(r['bytes'] for r in rows)<4*1024*1024, 'PNG budget exceeded'
    with (ASSETS/'image-inventory.csv').open() as stream:inventory=list(csv.DictReader(stream))
    assert len(inventory)==len(rows)
    by_name={r['file']:r for r in rows}
    for row in inventory:
        expected=by_name[row['file']]
        assert row['sha256']==expected['sha256'] and int(row['bytes'])==expected['bytes']
        assert [int(row['width']),int(row['height'])]==expected['pixels']
    cases=manifest['cases'];base=cases['menu-standard']
    assert len(cases)==24
    assert cases['menu-default']['profile']=='default'
    assert cases['menu-default']['settings']==json.loads((ASSETS/'native-defaults.json').read_text()), 'Default capture must use the exact native defaults'
    assert base['settings']['menu']!=cases['menu-default']['settings']['menu'], 'Customized example must differ from defaults'
    for name,case in cases.items():
        assert case['power_requests']==[],name
        assert case['source_commit']==SOURCE and case['version']=='2.1.0',name
        assert case['screen']==[1600,1000] and case['scale']==1 and case['dpi']==96,name
        assert case['runtime_packages']==base['runtime_packages'],name
    changes={
        'hints-hidden':{'show_access_key_hints'},'icons-hidden':{'show_menu_icons'},
        'icons-small':{'menu_icon_size'},'icons-large':{'menu_icon_size'},
        'density-compact':{'menu_density'},'density-comfortable':{'menu_density'},
        'width-narrow':{'menu_width'},'width-wide':{'menu_width'},
        'height-custom':{'menu_height_mode','menu_custom_height'},
        'aero-dark':{'appearance'},'aero-light':{'appearance'},'native-dark':set(),
        'launcher-beside':{'hide_original_launcher'},'launcher-adopted-icon':{'button_icon_mode'}}
    for name,allowed in changes.items():
        settings=cases[name]['settings'];original=base['settings']
        differences={k for k in set(settings)|set(original) if settings.get(k)!=original.get(k)}
        assert differences==allowed,(name,differences)
        if name!='native-dark':assert cases[name]['scheme']==base['scheme']
    for name in ('hints-hidden','icons-hidden','icons-small','icons-large'):
        assert cases[name]['popup']['geometry']==base['popup']['geometry'],name
        assert by_name[name+'.png']['pixels']==by_name['menu-standard.png']['pixels']
        assert by_name[name+'.png']['sha256']!=by_name['menu-standard.png']['sha256']
    geom=lambda name:cases[name]['popup']['geometry']
    assert geom('width-narrow')[2]<geom('menu-standard')[2]<geom('width-wide')[2]
    assert geom('density-compact')[3]<geom('menu-standard')[3]<geom('density-comfortable')[3]
    assert geom('height-custom')[3]<geom('menu-standard')[3]
    for name in ('placement-left','placement-center','placement-right'):
        case=cases[name];flyout=case['state']['popup']['flyout']['window']
        assert flyout['visible'] and flyout['geometry'][0] != geom(name)[0]
        assert (flyout['geometry'][0]<geom(name)[0])==(name=='placement-right'),name
    assert geom('placement-left')[0]<geom('placement-center')[0]<geom('placement-right')[0]
    installer=manifest['installer'];assert installer['source_commit']==SOURCE and installer['power_actions_invoked']==0
    assert all(operation['exit_code']==0 for operation in installer['operations'])
    transcript=(ASSETS/'ez-transcript.txt').read_text()
    for expected in ('Archive and runtime checks passed.','Proceed with install? [y/N]: y','Installed. For a new setup:'):
        assert expected in transcript,expected
    readme=(ROOT/'README.md').read_text()
    image_tags=re.findall(r'<a href="([^"]+)"><img src="([^"]+)" alt="([^"]+)" width="(\d+)"></a>',readme)
    assert len(image_tags)==readme.count('<img '),'Every showcase image needs alt text and a full-size link'
    assert len(image_tags)>=39
    for href,src,alt,width in image_tags:
        assert href==src and len(alt)>25 and (ROOT/src).is_file()
        if src.startswith('docs/images/2.1/'):
            assert int(width)<=by_name[Path(src).name]['pixels'][0],src
    for row in rows:assert row['file'] in readme, 'Unlinked image: '+row['file']
    if args.baseline:
        for name in ('phase2-inventory.csv','phase2-added-files.csv'):
            path='docs/maintenance/'+name
            approved=subprocess.check_output(['git','show',SOURCE+':'+path],cwd=ROOT)
            assert (ROOT/path).read_bytes()==approved,'Frozen inventory changed: '+path
        # Protect every runtime/test/build/packaging/legacy file and existing image.
        names=subprocess.check_output(['git','ls-tree','-r','--name-only',SOURCE],cwd=ROOT,text=True).splitlines()
        protected=[n for n in names if n.startswith(('native/','plasmoid/','openpowermenu/','legacy/','assets/','tests/'))
                   or n.endswith(('.png','.svg')) or n in ('CMakeLists.txt','run.py')]
        changed=set(subprocess.check_output(['git','diff','--name-only',SOURCE,'--'],cwd=ROOT,text=True).splitlines())
        assert not changed.intersection(protected), 'Runtime/baseline image changed: '+str(changed.intersection(protected))
        print(f'Frozen Phase 2 inventories and {len(protected)} runtime/test/build/legacy/image paths unchanged.')
    print(f'{len(rows)} PNGs, {len(cases)} capture cases, controlled comparisons, {len(image_tags)} accessible image links and EZ transcript passed.')


if __name__=='__main__':main()
