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
VERSION = (ROOT/'native/VERSION').read_text().strip()


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


def greeter_evidence(root):
    cases = [{'platform':'xcb','mode': mode, 'kde_confirm': kde, 'action': action,
              'confirm': mode == 'always' or (mode == 'system' and kde),
              'visible': mode == 'always' or (mode == 'system' and kde),
              'countdown': False, 'result': {'ok': True}, 'elapsed': 2.1}
             for mode in ('system', 'always', 'immediate') for kde in (False, True)
             for action in ('shutdown', 'reboot', 'logout')]
    cases.append({'platform':'xcb','mode': 'always', 'kde_confirm': True, 'action': 'shutdown', 'confirm': True,
                  'visible': True, 'countdown': True, 'result': {'ok': True}, 'elapsed': 30.1})
    (root/'results.json').write_text(json.dumps(cases))
    (root/'requests.jsonl').write_text(''.join(json.dumps({'member': member})+'\n' for member in
        ['logoutAndShutdown']*4+['logoutAndReboot']*3+['logout']*3))
    return cases


def test_greeter_requires_complete_modes_and_cancelled_requests(tmp_path):
    cases = greeter_evidence(tmp_path)
    assert len(release.verify_greeter(tmp_path)['cases']) == 19
    cases.pop(0)
    (tmp_path/'results.json').write_text(json.dumps(cases))
    with pytest.raises(ValueError, match='matrix'):
        release.verify_greeter(tmp_path)
    greeter_evidence(tmp_path)
    with (tmp_path/'requests.jsonl').open('a') as stream:
        stream.write(json.dumps({'member': 'logout'})+'\n')
    with pytest.raises(ValueError, match='requests'):
        release.verify_greeter(tmp_path)


def test_greeter_rejects_invisible_confirmation_and_early_countdown(tmp_path):
    cases = greeter_evidence(tmp_path)
    cases[-1]['elapsed'] = .5
    (tmp_path/'results.json').write_text(json.dumps(cases))
    with pytest.raises(ValueError, match='countdown'):
        release.verify_greeter(tmp_path)
    cases = greeter_evidence(tmp_path)
    cases[-1]['visible'] = False
    (tmp_path/'results.json').write_text(json.dumps(cases))
    with pytest.raises(ValueError, match='mismatch'):
        release.verify_greeter(tmp_path)
