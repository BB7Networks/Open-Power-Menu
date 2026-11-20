#!/usr/bin/env python3
"""Wrap a sealed, distribution-native bundle; Python is build tooling only."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
DEB_RUNTIME = ('libqt6core6t64 libqt6dbus6 libqt6gui6 libqt6widgets6 libqt6qml6 '
    'libqt6quick6 libqt6quickcontrols2-6 libkf6service6 libkf6configcore6 libxcb-xinput0 '
    'kde-cli-tools dbus qt6-qpa-plugins qt6-svg-plugins qt6-wayland '
    'qml6-module-org-kde-kirigami qml6-module-qtquick-controls qml6-module-qtquick-dialogs '
    'qml6-module-qtquick-layouts qml6-module-qtquick-window qml6-module-qtqml-workerscript plasma-workspace')
TARGETS = {
    ('manjaro', 'unknown'): ('Manjaro', 'Manjaro KDE Plasma 6', 'sudo pacman -Syu --needed qt6-base qt6-declarative qt6-svg qt6-wayland kirigami kservice kconfig kde-cli-tools dbus plasma-workspace'),
    ('debian', '13'): ('Debian13', 'Debian 13 KDE Plasma 6', 'sudo apt update && sudo apt install '+DEB_RUNTIME),
    ('ubuntu', '26.04'): ('Kubuntu26.04', 'Kubuntu 26.04 KDE Plasma 6', 'sudo apt update && sudo apt install '+DEB_RUNTIME),
}


def bundle_inventory(bundle):
    result = {}
    for path in sorted(bundle.rglob('*')):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError('Unsupported bundle member: '+str(path))
        name = path.relative_to(bundle).as_posix()
        if path.is_dir():
            result[name+'/'] = 'directory'
        elif name != 'bundle.json':
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()+(':x' if path.stat().st_mode & 0o111 else ':r')
    return result


def prepare(bundle, output, allow_arch_test=False):
    manifest = json.loads((bundle/'bundle.json').read_text())
    if manifest['format'] != 1 or manifest['files'] != bundle_inventory(bundle):
        raise ValueError('Native bundle integrity mismatch')
    if manifest['cpu'] != 'x86_64' or manifest['version'] != '2.1.0':
        raise ValueError('EZ staging requires final 2.1.0 x86-64 binaries')
    if (bundle/'SOURCE-COMMIT').read_text().strip() != manifest['source_commit']:
        raise ValueError('Bundle source commit mismatch')
    for name in ('open-power-menu', 'open-power-menu-install', 'open-power-menu-native', 'open-power-menu-editor', 'open-power-menu-standalone'):
        if not (bundle/'app/bin'/name).is_file(): raise ValueError('Missing native component: '+name)
    for name in ('widget/contents/ui/nativeinput/libopminputplugin.so', 'widget/contents/ui/PopupTrace.qml', 'widget/metadata.json'):
        if not (bundle/name).is_file(): raise ValueError('Missing widget component: '+name)
    if manifest['os'] == 'arch' and allow_arch_test:
        suffix, label, dependencies = 'Arch-test-only', 'Arch compatibility test only', TARGETS[('manjaro','unknown')][2]
    else:
        suffix, label, dependencies = TARGETS[(manifest['os'], manifest['os_version'])]
    name = 'OpenPowerMenu-EZ-v'+manifest['version']+'-'+suffix+'-'+manifest['cpu']
    output.mkdir(parents=True, exist_ok=True)
    archive = output/(name+'.zip')
    if archive.exists(): raise ValueError('Refusing to replace existing EZ artifact')
    with tempfile.TemporaryDirectory(prefix='opm-ez-build-') as temporary:
        folder = Path(temporary)/name
        folder.mkdir()
        shutil.copytree(bundle, folder/'native-bundle')
        script = (ROOT/'ez-install.sh.in').read_text()
        for key, value in {'VERSION': manifest['version'], 'OS': manifest['os'],
                           'OS_VERSION': '' if manifest['os_version'] == 'unknown' else manifest['os_version'],
                           'CPU': manifest['cpu'], 'LABEL': label, 'DEPENDENCIES': dependencies}.items():
            script = script.replace('@'+key+'@', value)
        (folder/'install.sh').write_text(script)
        (folder/'install.sh').chmod(0o755)
        readme = (ROOT/'README-EZ.md').read_text().replace('@LABEL@', label).replace('@DEPENDENCIES@', dependencies)
        (folder/'README-INSTALL.md').write_text(readme)
        (folder/'SOURCE-COMMIT').write_text(manifest['source_commit']+'\n')
        (folder/'EZ-METADATA.json').write_text(json.dumps({k:manifest[k] for k in ('version','source_commit','os','os_version','cpu')},indent=2)+'\n')
        checksums = ''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.relative_to(folder).as_posix()+'\n'
                            for path in sorted(folder.rglob('*')) if path.is_file())
        (folder/'SHA256SUMS').write_text(checksums)
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
            for path in sorted(folder.rglob('*')):
                item = zipfile.ZipInfo(path.relative_to(folder.parent).as_posix()+('/' if path.is_dir() else ''), (2026,1,1,0,0,0))
                item.create_system = 3
                item.external_attr = ((stat.S_IFDIR if path.is_dir() else stat.S_IFREG) | (0o755 if path.stat().st_mode & 0o111 else 0o644)) << 16
                target.writestr(item, b'' if path.is_dir() else path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    (output/(archive.name+'.sha256')).write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--allow-arch-test', action='store_true', help='Internal Arch compatibility fixture, never a public EZ release asset')
    args = parser.parse_args()
    print(prepare(args.bundle, args.output, args.allow_arch_test))
