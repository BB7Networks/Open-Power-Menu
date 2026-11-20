#!/usr/bin/env python3
"""Crop genuine captures without resampling, repainting, annotations or overlays.

The manifest records every crop, source-pixel hash and losslessly encoded result.
The private raw desktops/logs stay outside the repository.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from PIL import Image
from capture import SOURCE


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--captures',type=Path,required=True)
    p.add_argument('--editor-captures',type=Path,required=True)
    p.add_argument('--default-captures',type=Path,help='Optional separate menu-default case directory')
    p.add_argument('--installer',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    cases={}
    for path in sorted(args.captures.glob('*/capture.json')):
        record=json.loads(path.read_text());assert record['source_commit']==SOURCE
        assert record['power_requests']==[]
        cases[path.parent.name]=record
    editor=json.loads((args.editor_captures/'capture.json').read_text())
    assert editor['power_requests']==[] and editor['source_commit']==SOURCE
    cases['configure']=editor
    default_case=args.default_captures or args.captures/'menu-default'
    cases['menu-default']=json.loads((default_case/'capture.json').read_text())
    for name,record in cases.items():record.setdefault('profile','customized')
    images=[]
    def save(name,case,source,crop,method='QScreen.grabWindow(0); unchanged installed application'):
        original=Image.open(source).convert('RGB')
        assert 0<=crop[0]<crop[2]<=original.width and 0<=crop[1]<crop[3]<=original.height
        pixels=original.crop(crop);target=args.output/(name+'.png')
        pixels.save(target,optimize=True)
        images.append({'file':target.name,'case':case,'source_frame':source.name,
            'source_frame_sha256':digest(source),'crop_ltrb':list(crop),'pixels':list(pixels.size),
            'sha256':digest(target),'bytes':target.stat().st_size,'method':method})
    standard=(0,450,352,1000)
    save('menu-default','menu-default',default_case/'screen.png',(0,315,352,1000))
    for case in ('menu-standard','hints-hidden','icons-hidden','icons-small','icons-large','height-custom',
                 'native-dark','aero-dark','aero-light','launcher-beside','launcher-adopted-icon'):
        save(case,case,args.captures/case/'screen.png',standard)
    for case,rectangle in {
        'hero':(0,435,900,1000),'placement-left':(0,435,620,1000),
        'placement-center':(620,435,1240,1000),'placement-right':(980,435,1600,1000),
        'launcher-applications':(0,415,675,1000),'standalone':(0,650,312,1000)
    }.items():save(case,case,args.captures/case/'screen.png',rectangle)
    for preset,case in [('compact','density-compact'),('standard','menu-standard'),('comfortable','density-comfortable')]:
        save('density-'+preset,case,args.captures/case/'screen.png',(0,350,352,1000))
    for preset,case in [('narrow','width-narrow'),('auto','menu-standard'),('wide','width-wide')]:
        save('width-'+preset,case,args.captures/case/'screen.png',(0,450,466,1000))
    for name in ('editing-unlocked','editing-reordered','editing-destination','editing-submenu'):
        crop=(0,20,352,1000) if name!='editing-submenu' else (0,535,352,1000)
        save(name,'editing',args.captures/'editing'/(name+'.png'),crop)
    records=json.loads((args.editor_captures/'editor/editor-captures.json').read_text())
    for row in records:
        path=args.editor_captures/'editor'/(row['name']+'.png')
        width,height=Image.open(path).size
        save(row['name'],'configure',path,(0,0,width,height),row['capture'])
        images[-1]['desktop_crop_xywh']=row['crop'];images[-1]['editor_settings']=row['settings']
    # Keep exact transcript, including normal diagnostics. Excerpts must say so.
    for name in ('transcript.txt','provenance.json'):
        (args.output/('ez-'+name)).write_bytes((args.installer/name).read_bytes())
    manifest={'format':1,'native_source_commit':SOURCE,'version':'2.1.0',
        'capture_note':'Actual native pixels in disposable Debian 13 Plasma/X11 seats. Cropping and lossless PNG encoding only. Not physical hardware acceptance.',
        'power_boundary':'Private session bus also used as system bus, private recorder services; zero menu power requests.',
        'font':'Noto Sans 10 pt','display':[1600,1000],'dpi':96,'scale':1,
        'rendering':'Xvfb, real KWin X11 and plasmashell; Qt Quick software backend',
        'cases':cases,'images':images,'installer':json.loads((args.installer/'provenance.json').read_text())}
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with (args.output/'image-inventory.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['file','case','width','height','bytes','sha256']);writer.writeheader()
        for row in images:writer.writerow({**{key:row[key] for key in ('file','case','bytes','sha256')},'width':row['pixels'][0],'height':row['pixels'][1]})
    print(f'Exported {len(images)} genuine captures; {sum(r["bytes"] for r in images):,} PNG bytes')


if __name__=='__main__':main()
