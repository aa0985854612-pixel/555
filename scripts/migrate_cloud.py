"""Run locally with secure environment credentials, never through a public API."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store, Problem, encode
from app.cloud_store import CloudStore, migrate

def main():
    parser=argparse.ArgumentParser(description='Preserve existing SQLite accounts and records in Turso')
    parser.add_argument('--db',required=True,help='Existing private SQLite database, not a new file')
    args=parser.parse_args()
    path=Path(args.db)
    if not path.is_file():parser.error('Existing database does not exist; no database was created')
    try:
        result=migrate(Store(path),CloudStore())
        print(encode(result))
    except Problem as e:
        print('Migration stopped:',e.code,file=sys.stderr);return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
