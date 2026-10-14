"""Pinned, unmodified Cloudflare release assets. Never run an unverified connector."""
import hashlib
from pathlib import Path

CLOUDFLARED_VERSION='2026.10.0'
ASSETS={
    'windows-amd64':('cloudflared-windows-amd64.exe','86aee4017b26625cee8484c113558f48effa4cd47f7aa05fcf425604e5d2b23c'),
    'linux-amd64':('cloudflared-linux-amd64','d33ff2d14475178d2012c2c56beba87389ac5ded27649519f198a7d3134a99db'),
}
RELEASE_URL='https://github.com/cloudflare/cloudflared/releases/tag/'+CLOUDFLARED_VERSION

def verify_binary(path,platform):
    path=Path(path)
    if not path.is_file():raise RuntimeError('Connector missing. Extract the FULL Windows ZIP, including connectors/.')
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=ASSETS[platform][1]:
        raise RuntimeError('Connector checksum mismatch. Download and extract a fresh official PigLedger package.')
    return path.resolve()
