"""Exercise exact-source/checksum preparation without installing any packages."""
import hashlib
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'native/packaging/prepare-pacman.sh'


@pytest.fixture
def repository(tmp_path):
    repo = tmp_path / 'source with spaces'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    subprocess.run(['git', '-C', str(repo), 'config', 'user.name', 'Test'], check=True)
    subprocess.run(['git', '-C', str(repo), 'config', 'user.email', 'test@example.invalid'], check=True)
    target = repo / 'native/packaging/PKGBUILD'
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / 'native/packaging/PKGBUILD').read_bytes())
    (repo / 'tracked.txt').write_text('reviewed source\n')
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'fixture'], check=True)
    return repo


def prepare(repo, destination):
    return subprocess.run(['sh', str(SCRIPT), str(repo), str(destination)], capture_output=True, text=True)


def test_exact_commit_checksum_and_spaces(repository, tmp_path):
    # Untracked working files must never leak into an archive.
    (repository / 'personal.txt').write_text('not source')
    out = tmp_path / 'package with spaces'
    result = prepare(repository, out)
    assert result.returncode == 0, result.stderr
    archive = out / 'open-power-menu-source.tar.gz'
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    recipe = (out / 'PKGBUILD').read_text()
    assert f"sha256sums=('{digest}')" in recipe
    assert "options=('!strip' '!debug')" in recipe
    assert 'SOURCE_SHA256' not in recipe and "'SKIP'" not in recipe
    with tarfile.open(archive) as source:
        assert 'Open-Power-Menu/tracked.txt' in source.getnames()
        assert 'Open-Power-Menu/personal.txt' not in source.getnames()
    assert (out / 'SOURCE-COMMIT').read_text().strip() == subprocess.check_output(
        ['git', '-C', str(repository), 'rev-parse', 'HEAD'], text=True).strip()


@pytest.mark.parametrize('staged', [False, True])
def test_dirty_source_is_rejected(repository, tmp_path, staged):
    (repository / 'tracked.txt').write_text('unreviewed change')
    if staged:
        subprocess.run(['git', '-C', str(repository), 'add', '.'], check=True)
    out = tmp_path / 'package'
    assert prepare(repository, out).returncode != 0
    assert not out.exists()


def test_existing_output_is_preserved(repository, tmp_path):
    out = tmp_path / 'package'
    out.mkdir()
    (out / 'PKGBUILD').write_text('reviewed earlier')
    assert prepare(repository, out).returncode != 0
    assert (out / 'PKGBUILD').read_text() == 'reviewed earlier'
