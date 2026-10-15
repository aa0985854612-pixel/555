"""Explicit additive cloud upgrade; credentials supplied by protected environment."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.cloud_store import CloudStore,upgrade_cloud
from app.accounts import ensure_role_accounts
from app.store import Problem,encode

def main():
 parser=argparse.ArgumentParser(description='Back up and preserve the existing Turso database while adding schema4')
 parser.add_argument('--prepare',action='store_true',help='Add security table; retain schema3 marker for deployment overlap')
 parser.add_argument('--ensure-role-accounts',action='store_true',help='Create missing role accounts with unknown random temporary passwords; never reset existing users')
 parser.add_argument('--admin',default='farmadmin',help='Existing active administrator; no password is changed')
 args=parser.parse_args();cloud=CloudStore()
 try:
  result=upgrade_cloud(cloud,finalize=not args.prepare)
  if args.ensure_role_accounts:
   db=cloud.connect()
   try:actor=db.execute("SELECT id,username,role,active FROM users WHERE username=? AND role='admin' AND active=1",(args.admin,)).fetchone()
   finally:db.close()
   if not actor:raise Problem('existing_administrator_required')
   result['accounts']=[{k:r[k] for k in ('username','role','created') if k in r} for r in ensure_role_accounts(cloud,dict(actor))]
  print(encode(result));return 0
 except Problem as error:print('Upgrade stopped:',error.code,file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
