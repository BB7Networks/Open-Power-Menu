"""Shared exact asset inventory for stable collection and draft verification."""
import hashlib
import json
from pathlib import Path
import re

VERSION = '2.1.0'
REPOSITORY = 'BB7Networks/Open-Power-Menu'
TARGETS = [('Manjaro', 'manjaro-rolling'), ('Debian13', 'debian-13'), ('Kubuntu26.04', 'ubuntu-26.04')]


def payload_names():
    names = {'open-power-menu-native-2.1.0-1-x86_64.pkg.tar.zst', 'OpenPowerMenu-2.1.0-source.tar.gz'}
    for label, os_name in TARGETS:
        names.update({f'OpenPowerMenu-EZ-v2.1.0-{label}-x86_64.zip',
                      f'OpenPowerMenu-2.1.0-{os_name}-x86_64.tar.gz'})
    return names


def expected_names(review=False):
    payload = payload_names()
    return payload | {n+'.sha256' for n in payload} | {
        'SOURCE-COMMIT', 'RELEASE-NOTES.md', 'QUALIFICATION.json', 'RELEASE-MANIFEST.json', 'SHA256SUMS'
    } | ({'REVIEW-STATUS.md'} if review else set())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checksums(directory, excluded=()):
    return {p.name: digest(p) for p in sorted(directory.iterdir()) if p.name not in excluded}


def parse_checksums(text):
    result = {}
    for line in text.splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([^/\\]+)', line)
        if not match or match[2] in result or match[2] in ('.', '..'):
            raise ValueError('Invalid or duplicate checksum entry')
        result[match[2]] = match[1]
    return result


def seal(directory, commit, review):
    for name in payload_names():
        (directory/(name+'.sha256')).write_text(digest(directory/name)+'  '+name+'\n')
    manifest = {'version': VERSION, 'source_commit': commit, 'channel': 'review' if review else 'stable',
                'assets': checksums(directory, {'SHA256SUMS', 'RELEASE-MANIFEST.json'})}
    (directory/'RELEASE-MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (directory/'SHA256SUMS').write_text(''.join(h+'  '+n+'\n' for n, h in checksums(directory, {'SHA256SUMS'}).items()))
    verify(directory, commit, review=review)


def verify(directory, commit, review=False):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Expected an exact 40-character source commit')
    if any(not p.is_file() or p.is_symlink() for p in directory.iterdir()):
        raise ValueError('Assets must be regular files')
    if {p.name for p in directory.iterdir()} != expected_names(review):
        raise ValueError('Incomplete or unexpected stable asset set')
    actual = checksums(directory, {'SHA256SUMS'})
    if parse_checksums((directory/'SHA256SUMS').read_text()) != actual:
        raise ValueError('Asset checksum mismatch')
    manifest = json.loads((directory/'RELEASE-MANIFEST.json').read_text())
    if (manifest['source_commit'], manifest['version'], manifest['channel']) != (commit, VERSION, 'review' if review else 'stable'):
        raise ValueError('Release manifest source/version/channel mismatch')
    if manifest['assets'] != {n: h for n, h in actual.items() if n != 'RELEASE-MANIFEST.json'}:
        raise ValueError('Release manifest asset mismatch')
    if (directory/'SOURCE-COMMIT').read_text().strip() != commit:
        raise ValueError('Source commit mismatch')
    for name in payload_names():
        if parse_checksums((directory/(name+'.sha256')).read_text()) != {name: actual[name]}:
            raise ValueError('External checksum mismatch: '+name)
    qualification = json.loads((directory/'QUALIFICATION.json').read_text())
    if (qualification['source_commit'], qualification['version'], qualification['real_power_operations']) != (commit, VERSION, 0):
        raise ValueError('Qualification source/version/safety mismatch')
    if set(qualification['other_distributions']) != {'Arch', 'Debian', 'Kubuntu'}:
        raise ValueError('Missing distribution qualification')
    recorded = qualification['ez_artifacts']
    bundles = {n for n in payload_names() if n.endswith('.zip') or ('source' not in n and n.endswith('.tar.gz'))}
    if len(recorded) != 6 or {r['name']: r['sha256'] for r in recorded} != {n: actual[n] for n in bundles}:
        raise ValueError('Qualified distribution payload mismatch')
    return checksums(directory)
