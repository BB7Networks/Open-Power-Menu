"""Explicit session requirements; missing compositors never silently skip tests."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

PROFILES = {
    'manjaro-wayland': ('manjaro', ['wayland']),
    'plasma67-x11': ('arch', ['xcb', 'wayland']),
}


def packages(text):
    return dict(line.split(None,1) for line in text.splitlines() if len(line.split(None,1))==2)


def validate(profile, inventory):
    if profile not in PROFILES: raise ValueError('Unknown qualification profile: '+profile)
    values=packages(inventory)
    plasma=values.get('plasma-workspace','').split(':')[-1]
    kwin=values.get('kwin','').split(':')[-1]
    qt=values.get('qt6-base','').split(':')[-1]
    if profile=='plasma67-x11':
        if not all(v.startswith('6.7.') for v in (plasma,kwin,values.get('kwin-x11',''))):
            raise ValueError('Pinned X11 coverage must use the supported Plasma 6.7 series')
    else:
        # The current rolling runtime is a separate qualification boundary.
        # Changes outside this series require an explicit policy review.
        if not plasma.startswith('6.8.') or not kwin.startswith('6.8.') or not qt.startswith('6.12.'):
            raise ValueError('Current Manjaro qualification requires Plasma 6.8 / Qt 6.12')
        if 'kwin-x11' in values: raise ValueError('Unexpected X11 compositor mixed into Plasma 6.8')
    return values


def verify(root, profile):
    report=json.loads((root/'session-coverage.json').read_text())
    values=validate(profile,(root/'packages.txt').read_text())
    os_id,platforms=PROFILES[profile]
    if report.get('profile')!=profile or report.get('os')!=os_id or report.get('session_platforms')!=platforms:
        raise ValueError('Session qualification profile mismatch')
    required=['plasma-workspace','kwin','qt6-base','kcoreaddons','kconfig','kservice','libplasma']
    if report.get('packages')!={name:values[name] for name in required}:
        raise ValueError('Session profile does not match installed build packages')
    required_binaries=['kwin_wayland','startplasma-wayland']+(['kwin_x11','startplasma-x11'] if 'xcb' in platforms else [])
    if any(not report.get('binaries',{}).get(name) for name in required_binaries):
        raise ValueError('Required session binary missing from qualified runtime')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=PROFILES,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    inventory=subprocess.check_output(['pacman','-Q'],text=True)
    values=validate(args.profile,inventory)
    os_id=next(line[3:].strip('"') for line in Path('/etc/os-release').read_text().splitlines() if line.startswith('ID='))
    expected,platforms=PROFILES[args.profile]
    if os_id!=expected: raise ValueError('Wrong distribution for qualification profile')
    binaries={name:shutil.which(name) for name in ('kwin_x11','kwin_wayland','startplasma-x11','startplasma-wayland')}
    for name in ['kwin_wayland','startplasma-wayland']+(['kwin_x11','startplasma-x11'] if 'xcb' in platforms else []):
        if not binaries[name]: raise ValueError('Required compositor/session binary missing: '+name)
    if args.profile=='manjaro-wayland' and (binaries['kwin_x11'] or binaries['startplasma-x11']):
        raise ValueError('Unexpected native X11 session in the current Manjaro profile')
    report={'profile':args.profile,'os':os_id,'session_platforms':platforms,
            'application_platforms':['xcb','wayland'],'binaries':binaries,
            'packages':{name:values[name] for name in ('plasma-workspace','kwin','qt6-base','kcoreaddons','kconfig','kservice','libplasma')},
            'unsupported_sessions':{'xcb':'Plasma 6.8 removed the native X11 session; covered separately by pinned Plasma 6.7'} if 'xcb' not in platforms else {}}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('OPM_SESSION_COVERAGE '+json.dumps(report),flush=True)


if __name__=='__main__':main()
