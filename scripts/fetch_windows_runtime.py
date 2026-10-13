"""Fetch pinned PSF runtime from NuGet HTTPS and verify official SHA-512 metadata."""
import base64,gzip,hashlib,json,urllib.request
from urllib.parse import urlsplit
from pathlib import Path
VERSION='3.14.8'
root=Path(__file__).resolve().parents[1]
out=root/'artifacts/runtime';out.mkdir(parents=True,exist_ok=True)
def read(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in ('api.nuget.org','globalcdn.nuget.org'):raise RuntimeError('Unexpected package destination')
    with urllib.request.urlopen(url,timeout=60) as response:
        data=response.read()
        return gzip.decompress(data) if data.startswith(b'\x1f\x8b') else data
reg=json.loads(read(f'https://api.nuget.org/v3/registration5-gz-semver2/python/{VERSION}.json'))
cat=json.loads(read(reg['catalogEntry']))
if cat['authors']!='Python Software Foundation' or cat['packageHashAlgorithm']!='SHA512':raise RuntimeError('Unexpected publisher or checksum algorithm')
raw=read(reg['packageContent'])
if base64.b64encode(hashlib.sha512(raw).digest()).decode()!=cat['packageHash']:raise RuntimeError('Runtime checksum mismatch')
(out/f'python-{VERSION}.nupkg').write_bytes(raw)
metadata={'publisher':cat['authors'],'id':'python','version':VERSION,'url':reg['packageContent'],'catalog_url':reg['catalogEntry'],'sha512_base64':cat['packageHash'],'sha256':hashlib.sha256(raw).hexdigest(),'verified':True}
(out/'provenance.json').write_text(json.dumps(metadata,indent=2))
print('PSF Python',VERSION,'Windows package downloaded with official SHA-512 verified.')
