import argparse, getpass, os
from .store import Store

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['create-admin','backup']);p.add_argument('--db',default=os.environ.get('PIGLEDGER_DB','/workspace/555/.data/pigledger.sqlite3'));p.add_argument('--username');a=p.parse_args();s=Store(a.db)
    if a.action=='backup':print(s.backup_sqlite());return
    if not a.username:p.error('--username required')
    password=getpass.getpass('管理員密碼（至少12字元）: ')
    if password!=getpass.getpass('再次輸入: '):raise SystemExit('密碼不一致')
    s.create_user(a.username,password);print('管理員已建立')
if __name__=='__main__':main()
