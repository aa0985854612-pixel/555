"""Package PSF's NuGet Windows runtime and app. Requires verified provenance metadata."""
import base64,hashlib,json
import sys
from pathlib import Path,PurePosixPath
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from app.tunnel_binary import verify_binary,ASSETS
version=(root/'VERSION').read_text().strip()
meta=json.loads((root/'artifacts/runtime/provenance.json').read_text())
runtime_package=root/'artifacts/runtime'/('python-'+meta['version']+'.nupkg')
raw=runtime_package.read_bytes()
assert meta['publisher']=='Python Software Foundation' and meta['verified'] is True
assert base64.b64encode(hashlib.sha512(raw).digest()).decode()==meta['sha512_base64']
assert hashlib.sha256(raw).hexdigest()==meta['sha256']
source=root/'release'/('pigledger-'+version+'.zip')
name='pigledger-windows-'+version
out=root/'release'/(name+'.zip')
runtime_hashes={}
def add(z,path,data,mode=0o644):
    info=ZipInfo(name+'/'+path,date_time=(2026,10,13,0,0,0));info.compress_type=ZIP_DEFLATED;info.external_attr=mode<<16;z.writestr(info,data)
with ZipFile(source) as src,ZipFile(runtime_package) as rt,ZipFile(out,'w',compression=ZIP_DEFLATED,compresslevel=9) as target:
    assert src.testzip() is None and rt.testzip() is None
    for f in src.infolist():
        relative='/'.join(f.filename.split('/')[1:])
        if relative:add(target,relative,src.read(f))
    for f in rt.infolist():
        path=PurePosixPath(f.filename)
        assert '..' not in path.parts and not path.is_absolute()
        if f.filename.startswith('tools/') and not f.is_dir():
            relative='runtime/'+f.filename[len('tools/'):]
            data=rt.read(f);add(target,relative,data);runtime_hashes[relative]=hashlib.sha256(data).hexdigest()
    # Retain the original package (including repository signature) for independent verification.
    add(target,'runtime-original/'+runtime_package.name,raw)
    add(target,'runtime-original/provenance.json',json.dumps(meta,indent=2).encode())
    add(target,'runtime-original/extracted-files.sha256.json',json.dumps(runtime_hashes,sort_keys=True,indent=2).encode())
    connector_name=ASSETS['windows-amd64'][0]
    connector=verify_binary(root/'artifacts'/'connectors'/connector_name,'windows-amd64')
    add(target,'connectors/'+connector_name,connector.read_bytes())
    add(target,'connectors/provenance.json',(connector.parent/(connector_name+'.json')).read_bytes())
with ZipFile(out) as z:
    assert z.testzip() is None
    assert name+'/runtime/python.exe' in z.namelist()
    assert name+'/START_WINDOWS.bat' in z.namelist()
    assert name+'/START_PHONE.bat' in z.namelist() and name+'/connectors/'+connector_name in z.namelist()
    assert not any('/.data/' in n or n.endswith('/.env') or n.endswith('/farmadmin-login.txt') or n.endswith('.sqlite3') for n in z.namelist())
digest=hashlib.sha256(out.read_bytes()).hexdigest()
(out.with_suffix('.sha256')).write_text(digest+'  '+out.name+'\n')
print('Windows package:',out.name,'bytes:',out.stat().st_size,'Python:',meta['version'])
print('SHA-256:',digest)
