#!/usr/bin/env python3
"""Verify and collect native review or stable-release artifacts. This script cannot tag or publish."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

import release_assets

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--publication', action='store_true', help='Prepare public content; never publish or tag')
    args = parser.parse_args()
    release = module('release', ROOT/'scripts/prepare-native-release.py')
    ez = module('ez', ROOT/'native/packaging/prepare-ez.py')
    manjaro = args.evidence/('opm-native-Manjaro-'+args.commit)
    subprocess.run(['python3', str(ROOT/'scripts/prepare-native-release.py'), '--allow-final-version',
                    '--artifacts', str(manjaro), '--output', str(args.output),
                    '--commit', args.commit, '--tag', 'v2.1.0',
                    '--distribution-evidence', str(args.evidence)], check=True)
    artifacts = []
    for distro, prefix, os_id, os_version in [('Manjaro','native','manjaro','unknown'),
            ('Debian','install','debian','13'),('Kubuntu','install','ubuntu','26.04')]:
        directory = args.evidence/('opm-'+prefix+'-'+distro+'-'+args.commit)
        if (directory/'native-runtime-smoke').read_text().strip() != 'passed':
            raise ValueError('Independent minimal native runtime missing: '+distro)
        for platform in ('xcb','wayland'):
            if (directory/('ez-desktop-'+platform)).read_text().strip() != 'passed':
                raise ValueError('Installed EZ desktop activation missing: '+distro+' '+platform)
            if not (directory/('installed-editor-'+platform+'.png')).is_file():
                raise ValueError('Installed editor capture missing: '+distro+' '+platform)
        bundles = list(directory.glob('OpenPowerMenu-*.tar.gz'))
        archives = list(directory.glob('OpenPowerMenu-EZ-*.zip'))
        if len(bundles) != 1 or len(archives) != 1: raise ValueError('Incomplete artifacts: '+distro)
        bundle, archive = bundles[0], archives[0]
        records, contents = release.inventory(bundle.read_bytes(),'native-bundle/')
        manifest = json.loads(contents['bundle.json'])
        records.pop('bundle.json')
        if manifest['files'] != records or manifest['source_commit'] != args.commit or manifest['version'] != '2.1.0':
            raise ValueError('Bundle provenance mismatch: '+distro)
        if (manifest['os'],manifest['os_version'],manifest['cpu']) != (os_id,os_version,'x86_64'):
            raise ValueError('Wrong distribution binaries: '+distro)
        # Recreate the ZIP from the qualified sealed native payload and this Git
        # tree's wrapper/docs. Reject substituted, incomplete or extra files.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with tarfile.open(bundle) as tar: tar.extractall(root, filter='data')
            regenerated = ez.prepare(root/'native-bundle',root/'rebuilt')
            if regenerated.name != archive.name or regenerated.read_bytes() != archive.read_bytes():
                raise ValueError('EZ archive differs from the qualified payload/source: '+distro)
        for path in (bundle,archive):
            if not (args.output/path.name).exists(): shutil.copy2(path,args.output/path.name)
            artifacts.append({'distribution':distro,'name':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        shutil.copy2(Path(str(archive)+'.sha256'),args.output/(archive.name+'.sha256'))
    report = json.loads((args.output/'QUALIFICATION.json').read_text())
    report.update(ez_artifacts=artifacts,
                  approved_phase1_baseline='0bf2f247ff6406d797112e8223dda4c9b4f0d59d',
                  runtime_installation='Native and extracted EZ; offline',
                  physical_acceptance={
                      'established_by_automation': False,
                      'owner_reported_system': 'Manjaro KDE',
                      'owner_reported_build': 'Earlier EZ installer preparation build; not an attestation of this integrated commit',
                      'owner_reported_scope': ['EZ installation', 'normal menu use', 'Configure behavior'],
                      'real_power_actions_established': False,
                      'physical_held_key_safety_established': False,
                      'final_source_approval': 'Required separately before publication'})
    (args.output/'QUALIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
    if not args.publication:
        (args.output/'REVIEW-STATUS.md').write_text(
            '# Open Power Menu 2.1.0 review artifacts\n\n'
            'Source commit: `'+args.commit+'`. Stable publication is not approved.\n'
            'These are distribution-specific review builds, not a public release.\n'
            'Final source, acceptance-scope and publication approval remain required.\n'
            'Earlier Manjaro installation/menu/Configure acceptance does not establish real power-action or physical held-key safety.\n'
            'The public target is 2.1.0 Stable.\n')
    release_assets.seal(args.output, args.commit, review=not args.publication)
    print('Verified 3 native EZ archives, native bundles, Manjaro package, source and all distribution evidence.')


if __name__ == '__main__': main()
