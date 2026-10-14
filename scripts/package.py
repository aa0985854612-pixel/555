"""Build the versioned source package without databases, credentials or caches."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo
import hashlib
root=Path(__file__).resolve().parents[1]
version=(root/'VERSION').read_text().strip();name='pigledger-'+version
out=root/'release';out.mkdir(exist_ok=True)
files=[root/f for f in ('README.md','START_WINDOWS.bat','START_PHONE.bat','WINDOWS_README.txt','VERSION','Dockerfile','compose.yaml','Caddyfile','.env.example','.gitignore','.gitattributes','.dockerignore','vercel.json','.vercelignore','pyproject.toml')]
for folder in ('app','api','docs','tests','scripts'):
    files += [p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.sqlite3')]
with ZipFile(out/(name+'.zip'),'w',compression=ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(files):
        info=ZipInfo(name+'/'+p.relative_to(root).as_posix(),date_time=(2026,10,13,0,0,0));info.compress_type=ZIP_DEFLATED;info.external_attr=(0o755 if p.name.endswith('.sh') else 0o644)<<16
        z.writestr(info,p.read_bytes())
with ZipFile(out/(name+'.zip')) as z:
    assert z.testzip() is None
    assert all('/.data/' not in n and '/__pycache__/' not in n and not n.endswith('/.env') for n in z.namelist())
digest=hashlib.sha256((out/(name+'.zip')).read_bytes()).hexdigest()
(out/(name+'.sha256')).write_text(digest+'  '+name+'.zip\n')
print(name+'.zip',len(files),'files', (out/(name+'.zip')).stat().st_size,'bytes')
print('SHA-256:',digest)
