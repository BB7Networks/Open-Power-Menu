"""Publication must reject altered or incomplete native release artifacts."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_release', ROOT/'scripts/prepare-native-release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
COMMIT = 'a'*40
VERSION = '2.1.0-rc1'


def archive(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as tar:
        for name, content in files.items():
            item = tarfile.TarInfo('native-bundle/'+name)
            item.size = len(content)
            item.mode = 0o644
            tar.addfile(item, io.BytesIO(content))
    return output.getvalue()


def bundle():
    names = ['install.sh', 'uninstall.sh', 'open-power-menu.svg',
        'app/bin/open-power-menu', 'app/bin/open-power-menu-native',
        'app/bin/open-power-menu-editor', 'app/bin/open-power-menu-standalone',
        'app/bin/open-power-menu-install', 'widget/contents/ui/NativeInput.qml',
        'widget/contents/ui/nativeinput/libopminputplugin.so',
        'widget/contents/ui/nativeinput/qmldir', 'widget/contents/ui/PopupTrace.qml',
        'widget/contents/config/main.xml']
    files = {name: b'test-only placeholder' for name in names}
    files['SOURCE-COMMIT'] = COMMIT.encode()+b'\n'
    files['widget/metadata.json'] = json.dumps({'KPlugin': {'Version': VERSION}}).encode()
    seal(files)
    return files


def seal(files):
    files.pop('bundle.json', None)
    manifest = {'format': 1, 'source_commit': COMMIT, 'version': VERSION,
        'os': 'manjaro', 'os_version': '', 'cpu': 'x86_64',
        'files': {name: hashlib.sha256(content).hexdigest()+':r' for name, content in files.items()}}
    files['bundle.json'] = json.dumps(manifest).encode()


def test_sealed_bundle_and_source_binding():
    data = archive(bundle())
    manifest, _ = release.verify_bundle(data, COMMIT, VERSION)
    assert manifest['version'] == VERSION
    with pytest.raises(ValueError, match='source commit'):
        release.verify_bundle(data, 'b'*40, VERSION)


def test_changed_binary_is_refused():
    files = bundle()
    files['app/bin/open-power-menu-native'] += b'changed after qualification'
    with pytest.raises(ValueError, match='inventory'):
        release.verify_bundle(archive(files), COMMIT, VERSION)


@pytest.mark.parametrize('missing', ['app/bin/open-power-menu-editor', 'widget/contents/ui/nativeinput/libopminputplugin.so', 'widget/contents/ui/nativeinput/qmldir'])
def test_resealed_incomplete_bundle_is_refused(missing):
    files = bundle()
    del files[missing]
    seal(files)
    with pytest.raises(ValueError, match='Missing required component'):
        release.verify_bundle(archive(files), COMMIT, VERSION)


def test_resealed_wrong_widget_version_is_refused():
    files = bundle()
    files['widget/metadata.json'] = b'{"KPlugin":{"Version":"1.0.1"}}'
    seal(files)
    with pytest.raises(ValueError, match='Widget version'):
        release.verify_bundle(archive(files), COMMIT, VERSION)


def test_archive_traversal_is_refused():
    with pytest.raises(ValueError, match='Unsafe archive path'):
        release.inventory(archive({'../escape': b'bad'}), 'native-bundle/')
