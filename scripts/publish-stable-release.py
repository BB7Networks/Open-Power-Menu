#!/usr/bin/env python3
"""Verify assets by default; publish only with exact source and explicit approval."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlencode

import release_assets as assets

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v'+assets.VERSION
BASE = 'repos/'+assets.REPOSITORY


class GitHub:
    """Small REST transport. Tests substitute an in-memory transport, never gh."""
    def request(self, method, path, data=None, missing_ok=False):
        command = ['gh', 'api', '--method', method, path]
        if data is not None:
            command += ['--input', '-']
        result = subprocess.run(command, input=json.dumps(data) if data is not None else None,
                                text=True, capture_output=True)
        if result.returncode:
            if missing_ok and '(HTTP 404)' in result.stderr:
                return None
            raise RuntimeError('GitHub API failed for '+method+' '+path+'; no publication retry was attempted')
        return json.loads(result.stdout) if result.stdout.strip() else None

    def upload(self, release_id, path):
        url = 'https://uploads.github.com/'+BASE+'/releases/'+str(release_id)+'/assets?'+urlencode({'name': path.name})
        result = subprocess.run(['gh', 'api', '--method', 'POST', url,
                                 '-H', 'Content-Type: application/octet-stream', '--input', str(path)],
                                capture_output=True)
        if result.returncode:
            raise RuntimeError('Draft upload failed: '+path.name)

    def download(self, asset_id, path):
        with path.open('wb') as stream:
            result = subprocess.run(['gh', 'api', BASE+'/releases/assets/'+str(asset_id),
                                     '-H', 'Accept: application/octet-stream'], stdout=stream, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError('Draft download failed: '+path.name)


def publish(directory, commit, *, approved_commit, physical_accepted, github):
    # Check every local precondition before even reading remote release state.
    if approved_commit != commit or not physical_accepted:
        raise ValueError('Exact source approval and physical acceptance are required')
    expected = assets.verify(directory, commit)
    if github.request('GET', BASE+'/git/ref/tags/'+TAG, missing_ok=True) is not None:
        raise ValueError('Tag already exists; refusing to replace history')
    if github.request('GET', BASE+'/releases/tags/'+TAG, missing_ok=True) is not None:
        raise ValueError('Release already exists; review any existing draft manually')
    body = (directory/'RELEASE-NOTES.md').read_text()
    body += '\nPublication approved for source `'+commit+'` after owner-reported physical acceptance.\n'
    release = github.request('POST', BASE+'/releases', {
        'tag_name': TAG, 'target_commitish': commit, 'name': 'Open Power Menu '+TAG,
        'body': body, 'draft': True, 'prerelease': False, 'make_latest': 'false'})
    release_id = release['id']
    if not release['draft'] or release['prerelease'] or release['tag_name'] != TAG:
        raise ValueError('Unexpected draft release state')
    for name in sorted(expected):
        github.upload(release_id, directory/name)
    remote = github.request('GET', BASE+'/releases/'+str(release_id)+'/assets?per_page=100')
    if len(remote) != len(expected) or {r['name'] for r in remote} != set(expected):
        raise ValueError('Draft asset set differs from the qualified set')
    with tempfile.TemporaryDirectory(prefix='opm-draft-verification-') as temporary:
        downloaded = Path(temporary)
        for entry in remote:
            name = entry['name']  # Membership checked above; cannot escape the directory.
            if entry['state'] != 'uploaded' or entry['size'] != (directory/name).stat().st_size:
                raise ValueError('Incomplete draft upload: '+name)
            github.download(entry['id'], downloaded/name)
        if assets.verify(downloaded, commit) != expected:
            raise ValueError('Downloaded draft differs from qualified local artifacts')
    # GitHub may create the tag at draft creation or publication. Pin it ourselves
    # after verification if still absent, and refuse a concurrent differing tag.
    reference = github.request('GET', BASE+'/git/ref/tags/'+TAG, missing_ok=True)
    if reference is None:
        github.request('POST', BASE+'/git/refs', {'ref': 'refs/tags/'+TAG, 'sha': commit})
        reference = github.request('GET', BASE+'/git/ref/tags/'+TAG)
    if reference['object'].get('type') != 'commit' or reference['object'].get('sha') != commit:
        raise ValueError('Stable tag does not point to the approved source')
    # Recheck state immediately before publication. Fail closed on concurrent edits.
    current = github.request('GET', BASE+'/releases/'+str(release_id))
    if not current['draft'] or current['prerelease'] or current['tag_name'] != TAG or current['target_commitish'] != commit:
        raise ValueError('Draft metadata changed before publication')
    current_assets = github.request('GET', BASE+'/releases/'+str(release_id)+'/assets?per_page=100')
    identity = lambda rows: sorted((r['id'], r['name'], r['size'], r['state'], r.get('digest')) for r in rows)
    if identity(current_assets) != identity(remote):
        raise ValueError('Draft assets changed before publication')
    github.request('PATCH', BASE+'/releases/'+str(release_id),
                   {'draft': False, 'prerelease': False, 'make_latest': 'true'})
    latest = github.request('GET', BASE+'/releases/latest')
    if latest['id'] != release_id or latest['draft'] or latest['prerelease'] or latest['tag_name'] != TAG:
        raise ValueError('Publication response is not the expected Stable/Latest release; inspect GitHub before retrying')
    return latest['html_url']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--approved-commit')
    parser.add_argument('--physical-acceptance-approved', action='store_true')
    args = parser.parse_args()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if head != args.commit or subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT):
        raise ValueError('Require a clean checkout of the exact approved source')
    assets.verify(args.assets, args.commit)
    if not args.publish:
        print('Complete stable asset set verified. No tag, draft or public release created.')
        return
    print(publish(args.assets, args.commit, approved_commit=args.approved_commit,
                  physical_accepted=args.physical_acceptance_approved, github=GitHub()))


if __name__ == '__main__':
    main()
