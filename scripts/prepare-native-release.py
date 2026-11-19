#!/usr/bin/env python3
"""Verify qualified native assets before creating a GitHub prerelease."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def inventory(data, prefix):
    records, contents = {}, {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
        for entry in archive:
            name = entry.name.removeprefix('./')
            if name.startswith('/') or '..' in PurePosixPath(name).parts:
                raise ValueError('Unsafe archive path: '+name)
            if not name.startswith(prefix):
                continue
            relative = name[len(prefix):].rstrip('/')
            if not relative:
                continue
            if entry.isdir():
                relative += '/'
                value = 'directory'
            elif entry.isfile():
                content = archive.extractfile(entry).read()
                contents[relative] = content
                value = hashlib.sha256(content).hexdigest()+(':x' if entry.mode & 0o111 else ':r')
            else:
                raise ValueError('Unsupported archive member: '+name)
            if relative in records:
                raise ValueError('Duplicate archive member: '+name)
            records[relative] = value
    return records, contents


def verify_bundle(data, commit, version):
    records, contents = inventory(data, 'native-bundle/')
    manifest = json.loads(contents['bundle.json'])
    del records['bundle.json']
    if manifest.get('format') != 1 or manifest['files'] != records:
        raise ValueError('Sealed bundle contents do not match their inventory')
    if manifest.get('source_commit') != commit or contents['SOURCE-COMMIT'].decode().strip() != commit:
        raise ValueError('Bundle source commit mismatch')
    if manifest['version'] != version or manifest['os'] != 'manjaro' or manifest['cpu'] != 'x86_64':
        raise ValueError('Unexpected bundle version or supported distribution')
    if json.loads(contents['widget/metadata.json'])['KPlugin']['Version'] != version:
        raise ValueError('Widget version mismatch')
    required = ['install.sh', 'uninstall.sh', 'open-power-menu.svg',
        'app/bin/open-power-menu', 'app/bin/open-power-menu-native',
        'app/bin/open-power-menu-editor', 'app/bin/open-power-menu-standalone',
        'app/bin/open-power-menu-install', 'widget/contents/ui/NativeInput.qml',
        'widget/contents/ui/nativeinput/libopminputplugin.so',
        'widget/contents/ui/nativeinput/qmldir', 'widget/contents/ui/PopupTrace.qml',
        'widget/contents/config/main.xml']
    for name in required:
        if not contents.get(name):
            raise ValueError('Missing required component: '+name)
    return manifest, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    version = (ROOT/'native/VERSION').read_text().strip()
    if args.tag != 'v'+version or '-rc' not in version:
        raise ValueError('Only the matching native prerelease tag may publish')
    current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if current != args.commit or (args.artifacts/'SOURCE-COMMIT').read_text().strip() != current:
        raise ValueError('Checkout/artifact source commit mismatch')
    source = (args.artifacts/'open-power-menu-source.tar.gz').read_bytes()
    source_hash = hashlib.sha256(source).hexdigest()
    if (args.artifacts/'SOURCE.sha256').read_text().split()[0] != source_hash:
        raise ValueError('Source archive checksum mismatch')
    expected = subprocess.check_output(['git', 'archive', '--format=tar', '--prefix=Open-Power-Menu/', current], cwd=ROOT)
    if inventory(source, 'Open-Power-Menu/')[0] != inventory(expected, 'Open-Power-Menu/')[0]:
        raise ValueError('Source archive differs from the exact tagged source')
    packages = list(args.artifacts.glob('*.pkg.tar.zst'))
    bundles = list(args.artifacts.glob('OpenPowerMenu-*.tar.gz'))
    if len(packages) != 1 or len(bundles) != 1:
        raise ValueError('Expected one Manjaro package and one complete bundle')
    package, bundle = packages[0], bundles[0]
    for path, sidecar in [(package, 'PACKAGE.sha256'), (bundle, bundle.name+'.sha256')]:
        digest, filename = (args.artifacts/sidecar).read_text().split()
        if Path(filename).name != path.name or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Build artifact checksum mismatch: '+path.name)
    manifest, records = verify_bundle(bundle.read_bytes(), current, version)
    packaged = subprocess.check_output(['zstd', '-dc', str(package)])
    package_records, _ = inventory(packaged, 'usr/lib/open-power-menu-native/bundle/')
    if package_records.pop('bundle.json') != inventory(bundle.read_bytes(), 'native-bundle/')[0]['bundle.json']:
        raise ValueError('Packaged bundle manifest differs from standalone bundle')
    if package_records != records:
        raise ValueError('Pacman package and standalone installation bundle differ')
    _, package_contents = inventory(packaged, '')
    expected_setup = b'#!/bin/sh\nexec /usr/lib/open-power-menu-native/bundle/install.sh "$@"\n'
    if package_contents['usr/bin/open-power-menu-native-setup'] != expected_setup:
        raise ValueError('Unexpected pacman setup launcher')
    package_info = package_contents['.PKGINFO'].decode()
    if 'pkgname = open-power-menu-native\n' not in package_info or 'pkgver = '+version.replace('-rc', 'rc')+'-1\n' not in package_info:
        raise ValueError('Package version mismatch')
    seats = {}
    for platform, expected_count in [('xcb', 27), ('wayland', 25)]:
        for visibility in ['visible', 'hidden']:
            name = platform+'-'+visibility
            seat = args.artifacts/'keyboard-tests'/name
            stress = json.loads((seat/'stress.json').read_text())
            actions = json.loads((seat/'results.json').read_text())
            requests = [json.loads(line) for line in (seat/'requests.jsonl').read_text().splitlines()]
            if len(requests) != expected_count or len(stress) != (8 if platform == 'xcb' else 7) or len(actions) != 12:
                raise ValueError('Incomplete held-key qualification: '+name)
            seats[name] = {'stress': stress, 'ordinary_actions': actions, 'mock_request_count': len(requests)}
    args.output.mkdir() # Refuse to overwrite an earlier publication set.
    for path in [package, bundle]:
        shutil.copy2(path, args.output/path.name)
    source_name = 'OpenPowerMenu-'+version+'-source.tar.gz'
    (args.output/source_name).write_bytes(source)
    (args.output/'SOURCE-COMMIT').write_text(current+'\n')
    qualification = {'source_commit': current, 'version': version,
        'os': manifest['os'], 'os_version': manifest['os_version'], 'cpu': manifest['cpu'],
        'os_release': (args.artifacts/'os-release').read_text(),
        'build_packages': (args.artifacts/'packages.txt').read_text().splitlines(),
        'runtime_packages': (args.artifacts/'runtime-packages.txt').read_text().splitlines(),
        'keyboard_seats': seats, 'real_power_operations': 0,
        'physical_acceptance': 'Pending; no physical workstation modified',
        'workflow': 'https://github.com/'+os.environ.get('GITHUB_REPOSITORY', 'BB7Networks/Open-Power-Menu')+'/actions/runs/'+os.environ.get('GITHUB_RUN_ID', '')}
    (args.output/'QUALIFICATION.json').write_text(json.dumps(qualification, indent=2)+'\n')
    notes = (ROOT/('RELEASE-NOTES-v'+version+'.md')).read_text()
    notes += '\n## Qualified artifact provenance\n\nSource commit: `'+current+'`.\n\n'
    notes += 'Qualification workflow: '+qualification['workflow']+'\n\n'
    notes += 'Package: `'+package.name+'`\n\nBundle: `'+bundle.name+'`\n\n'
    notes += 'The exact Manjaro build/runtime package inventory is in `QUALIFICATION.json`. '
    notes += 'The package requires dependency versions at least as new as its build snapshot. '
    notes += 'An older or different Manjaro runtime is not certified by this release.\n'
    (args.output/'RELEASE-NOTES.md').write_text(notes)
    hashes = ''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name+'\n' for path in sorted(args.output.iterdir()))
    (args.output/'SHA256SUMS').write_text(hashes)
    print('Verified source, versions, sealed package/bundle equivalence and all four mock keyboard seats:', current)


if __name__ == '__main__':
    main()
