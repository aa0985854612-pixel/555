"""Download official pinned connector assets using normal TLS and verify SHA-256."""
import argparse,hashlib,json,sys,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.tunnel_binary import ASSETS,CLOUDFLARED_VERSION,RELEASE_URL

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--platform',choices=ASSETS,default='windows-amd64');args=parser.parse_args()
    name,expected=ASSETS[args.platform]
    url=f'https://github.com/cloudflare/cloudflared/releases/download/{CLOUDFLARED_VERSION}/{name}'
    folder=Path(__file__).resolve().parents[1]/'artifacts'/'connectors';folder.mkdir(parents=True,exist_ok=True)
    path=folder/name
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        with urllib.request.urlopen(url,timeout=60) as response:raw=response.read(100*1024*1024+1)
        if len(raw)>100*1024*1024 or hashlib.sha256(raw).hexdigest()!=expected:
            raise RuntimeError('Official connector SHA-256 mismatch; nothing installed.')
        path.write_bytes(raw)
    if args.platform=='linux-amd64':path.chmod(0o755)
    metadata={'publisher':'Cloudflare','version':CLOUDFLARED_VERSION,'asset':name,'url':url,'checksum_source':RELEASE_URL,'sha256':expected,'verified':True}
    (folder/(name+'.json')).write_text(json.dumps(metadata,indent=2)+'\n')
    print('Verified:',name,'bytes:',path.stat().st_size,'SHA-256:',expected)

if __name__=='__main__':main()
