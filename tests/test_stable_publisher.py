"""Exercise publication without network, real tags, releases or power services."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import release_assets as assets
spec = importlib.util.spec_from_file_location('publisher', ROOT/'scripts/publish-stable-release.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)
COMMIT = 'a'*40


@pytest.fixture
def qualified(tmp_path):
    # These are deliberately non-installable transport fixtures. Real payload
    # equivalence is independently enforced by stage-native-ez and the CI matrix.
    for name in assets.payload_names():
        (tmp_path/name).write_text('mock transport payload: '+name)
    (tmp_path/'SOURCE-COMMIT').write_text(COMMIT+'\n')
    (tmp_path/'RELEASE-NOTES.md').write_text('Mock release notes\n')
    report = {'source_commit': COMMIT, 'version': '2.1.0', 'real_power_operations': 0,
              'other_distributions': {d: {} for d in ('Arch', 'Debian', 'Kubuntu')},
              'ez_artifacts': [{'name': n, 'sha256': assets.digest(tmp_path/n)}
                for n in assets.payload_names() if n.endswith('.zip') or ('source' not in n and n.endswith('.tar.gz'))]}
    (tmp_path/'QUALIFICATION.json').write_text(json.dumps(report))
    assets.seal(tmp_path, COMMIT, review=False)
    return tmp_path


class FakeGitHub:
    def __init__(self, fault=None):
        self.fault, self.calls, self.uploads = fault, [], {}
        self.release = None
        self.tag = None

    def request(self, method, path, data=None, missing_ok=False):
        self.calls.append((method, path, copy.deepcopy(data)))
        base = publisher.BASE
        if self.fault == 'http403': raise RuntimeError('HTTP 403')
        if path == base+'/git/ref/tags/v2.1.0':
            if self.fault == 'existing-tag': return {'object': {'sha': COMMIT, 'type': 'commit'}}
            return self.tag
        if path == base+'/releases/tags/v2.1.0':
            return {'id': 1} if self.fault == 'existing-release' else None
        if method == 'POST' and path == base+'/releases':
            self.release = dict(data, id=42, html_url='https://example.invalid/mock-release')
            return copy.deepcopy(self.release)
        if path.endswith('/assets?per_page=100'):
            result = [{'id': i, 'name': n, 'size': len(v), 'state': 'uploaded', 'download_count': len(self.calls)}
                      for i, (n, v) in enumerate(self.uploads.items())]
            if self.fault == 'missing-upload': result.pop()
            if self.fault == 'extra-upload': result.append({'name': '../escape'})
            if self.fault == 'incomplete-upload': result[0]['state'] = 'new'
            return result
        if method == 'POST' and path == base+'/git/refs':
            self.tag = {'object': {'type': 'commit', 'sha': 'b'*40 if self.fault == 'tag-race' else data['sha']}}
            return self.tag
        if method == 'GET' and path == base+'/releases/42':
            result = copy.deepcopy(self.release)
            if self.fault == 'metadata-race': result['target_commitish'] = 'b'*40
            return result
        if method == 'PATCH' and path == base+'/releases/42':
            assert len([c for c in self.calls if c[0] == 'DOWNLOAD']) == len(assets.expected_names())
            self.release.update(data)
            return copy.deepcopy(self.release)
        if path == base+'/releases/latest': return copy.deepcopy(self.release)
        raise AssertionError((method, path))

    def upload(self, release_id, path):
        self.calls.append(('UPLOAD', path.name, None))
        assert self.release['draft'] and release_id == 42
        if self.fault == 'upload-error': raise RuntimeError('Mock upload failed')
        self.uploads[path.name] = path.read_bytes()

    def download(self, asset_id, path):
        self.calls.append(('DOWNLOAD', path.name, None))
        if self.fault == 'download-error': raise RuntimeError('Mock download failed')
        path.write_bytes(self.uploads[path.name]+(b'corrupt' if self.fault == 'download-corrupt' else b''))


def run(root, github, **kwargs):
    return publisher.publish(root, COMMIT, github=github,
        approved_commit=kwargs.get('approved_commit', COMMIT), physical_accepted=kwargs.get('physical_accepted', True))


def test_draft_upload_download_verify_then_stable_latest(qualified):
    github = FakeGitHub()
    assert run(qualified, github) == 'https://example.invalid/mock-release'
    creation = next(c[2] for c in github.calls if c[0] == 'POST' and c[1].endswith('/releases'))
    assert creation['draft'] is True and creation['prerelease'] is False and creation['make_latest'] == 'false'
    publication = [c[2] for c in github.calls if c[0] == 'PATCH']
    assert publication == [{'draft': False, 'prerelease': False, 'make_latest': 'true'}]
    assert github.tag['object']['sha'] == COMMIT
    assert set(github.uploads) == assets.expected_names()


@pytest.mark.parametrize('fault', ['existing-tag', 'existing-release', 'http403', 'upload-error',
    'missing-upload', 'extra-upload', 'incomplete-upload', 'download-error', 'download-corrupt', 'tag-race', 'metadata-race'])
def test_failure_never_makes_draft_public(qualified, fault):
    github = FakeGitHub(fault)
    with pytest.raises((ValueError, RuntimeError)):
        run(qualified, github)
    assert not any(c[0] == 'PATCH' for c in github.calls)
    assert not any(c[0] == 'DELETE' for c in github.calls)


@pytest.mark.parametrize('approval', [{'approved_commit': 'b'*40}, {'approved_commit': None}, {'physical_accepted': False}])
def test_missing_approval_has_no_remote_effect(qualified, approval):
    github = FakeGitHub()
    with pytest.raises(ValueError, match='approval'):
        run(qualified, github, **approval)
    assert github.calls == []


@pytest.mark.parametrize('damage', ['missing', 'extra', 'corrupt', 'symlink', 'duplicate-sha', 'source', 'review', 'wrong-distro'])
def test_local_asset_failure_precedes_api(qualified, damage):
    name = sorted(assets.payload_names())[0]
    path = qualified/name
    if damage == 'missing': path.unlink()
    elif damage == 'extra': (qualified/'unexpected').write_text('extra')
    elif damage == 'corrupt': path.write_text('corrupt')
    elif damage == 'symlink': path.unlink();path.symlink_to(qualified/'SOURCE-COMMIT')
    elif damage == 'duplicate-sha':
        p=qualified/'SHA256SUMS';p.write_text(p.read_text()+p.read_text().splitlines()[0]+'\n')
    elif damage == 'source':
        (qualified/'SOURCE-COMMIT').write_text('b'*40)
    elif damage == 'review':
        (qualified/'REVIEW-STATUS.md').write_text('Not approved');assets.seal(qualified, COMMIT, review=True)
    else:
        p=qualified/'QUALIFICATION.json';report=json.loads(p.read_text());del report['other_distributions']['Debian'];p.write_text(json.dumps(report))
        # Reseal hashes manually: even a consistent checksum set cannot waive qualification.
        manifest=json.loads((qualified/'RELEASE-MANIFEST.json').read_text())
        manifest['assets']=assets.checksums(qualified, {'SHA256SUMS','RELEASE-MANIFEST.json'})
        (qualified/'RELEASE-MANIFEST.json').write_text(json.dumps(manifest))
        (qualified/'SHA256SUMS').write_text(''.join(h+'  '+n+'\n' for n,h in assets.checksums(qualified,{'SHA256SUMS'}).items()))
    github = FakeGitHub()
    with pytest.raises(ValueError): run(qualified, github)
    assert github.calls == []
