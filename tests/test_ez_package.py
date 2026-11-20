"""EZ packaging must preserve a single sealed native payload and refuse damage."""
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile
import pytest

spec=importlib.util.spec_from_file_location('ez',Path(__file__).resolve().parents[1]/'native/packaging/prepare-ez.py')
ez=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ez)


def fixture(root, os_id='debian', version='13'):
    bundle=root/'native-bundle';bundle.mkdir()
    for name in ['app/bin/'+n for n in ('open-power-menu','open-power-menu-install','open-power-menu-native','open-power-menu-editor','open-power-menu-standalone')]+['widget/contents/ui/nativeinput/libopminputplugin.so','widget/contents/ui/PopupTrace.qml','widget/metadata.json']:
        path=bundle/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('test payload\n')
        if name.startswith('app/bin'): path.chmod(0o755)
    (bundle/'empty').mkdir()
    (bundle/'SOURCE-COMMIT').write_text('a'*40+'\n')
    manifest={'format':1,'version':'2.1.0','source_commit':'a'*40,'os':os_id,'os_version':version,'cpu':'x86_64','files':ez.bundle_inventory(bundle)}
    (bundle/'bundle.json').write_text(json.dumps(manifest))
    return bundle


@pytest.mark.parametrize('os_id,version,label',[('manjaro','unknown','Manjaro'),('debian','13','Debian13'),('ubuntu','26.04','Kubuntu26.04')])
def test_native_payload_checksums_and_modes(tmp_path,os_id,version,label):
    bundle=fixture(tmp_path,os_id,version)
    archive=ez.prepare(bundle,tmp_path/'out')
    assert label in archive.name and 'v2.1.0-' in archive.name
    with zipfile.ZipFile(archive) as z:
        prefix=archive.stem+'/'
        names=z.namelist()
        assert prefix+'native-bundle/empty/' in names
        for path in bundle.rglob('*'):
            if path.is_file(): assert z.read(prefix+'native-bundle/'+path.relative_to(bundle).as_posix())==path.read_bytes()
        assert z.getinfo(prefix+'native-bundle/app/bin/open-power-menu').external_attr >> 16 & 0o111
        assert not any(n.endswith('run.py') for n in names)
        checks={line.split('  ',1)[1]:line.split('  ',1)[0] for line in z.read(prefix+'SHA256SUMS').decode().splitlines()}
        assert set(checks)=={n[len(prefix):] for n in names if not n.endswith('/') and n!=prefix+'SHA256SUMS'}
        for name,digest in checks.items(): assert hashlib.sha256(z.read(prefix+name)).hexdigest()==digest
    with pytest.raises(ValueError,match='replace'): ez.prepare(bundle,tmp_path/'out')
    assert ez.prepare(bundle,tmp_path/'other').read_bytes()==archive.read_bytes()


@pytest.mark.parametrize('damage',['corrupt','missing','symlink','wrong-source','wrong-cpu','unsupported'])
def test_refuse_invalid_bundle(tmp_path,damage):
    bundle=fixture(tmp_path)
    path=bundle/'widget/contents/ui/nativeinput/libopminputplugin.so'
    if damage=='corrupt': path.write_bytes(b'changed')
    elif damage=='missing': path.unlink()
    elif damage=='symlink': path.unlink();path.symlink_to('/etc/os-release')
    else:
        manifest=json.loads((bundle/'bundle.json').read_text())
        manifest[{'wrong-source':'source_commit','wrong-cpu':'cpu','unsupported':'os'}[damage]]='different'
        (bundle/'bundle.json').write_text(json.dumps(manifest))
    with pytest.raises((ValueError,KeyError)): ez.prepare(bundle,tmp_path/'out')
