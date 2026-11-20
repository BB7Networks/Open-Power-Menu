#!/usr/bin/env python3
"""Verify and collect Phase 1 artifacts. This script cannot tag or publish."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

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
    args = parser.parse_args()
    release = module('release', ROOT/'scripts/prepare-native-release.py')
    ez = module('ez', ROOT/'native/packaging/prepare-ez.py')
    manjaro = args.evidence/('opm-native-Manjaro-'+args.commit)
    subprocess.run(['python3', str(ROOT/'scripts/prepare-native-release.py'), '--staging',
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
    report.update(stage='Phase 1 review; stable publication NOT approved', ez_artifacts=artifacts,
                  baseline='2f889df3e5b29f49611f8cf37f41f15e86cad7c1', runtime_installation='Native and extracted EZ; offline')
    (args.output/'QUALIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
    review = (ROOT/'docs/EZ-INSTALLER-PHASE1.md').read_text().replace(
        '](images/phase1/', '](https://raw.githubusercontent.com/BB7Networks/Open-Power-Menu/'
        + args.commit + '/docs/images/phase1/')
    (args.output/'PHASE1-REVIEW.md').write_text(review)
    hashes=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
                  for p in sorted(args.output.iterdir()) if p.is_file() and p.name != 'SHA256SUMS')
    (args.output/'SHA256SUMS').write_text(hashes)
    print('Verified 3 native EZ archives, native bundles, Manjaro package, source and all distribution evidence.')


if __name__ == '__main__': main()
