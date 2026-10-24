"""Stage chat photo transcription only. This command never confirms or writes feed orders."""
import argparse,hashlib,json,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION,encode
from app.cloud_store import CloudStore
from app.feed import bin_label
from app.feed_drafts import save_draft

def stage(store,user,document):
    data=store.snapshot(include_source=False);sources=document.get('sources',[]);rows=[]
    for index,incoming in enumerate(document['rows']):
        if 'record' in incoming:record=dict(incoming['record'])
        else:
            record={k:incoming.get(k,'') for k in ('date','vendor','item','note','feed_bin_id')};record['kg']=None if incoming.get('tons') is None else float(incoming['tons'])*1000
        label=incoming.get('bin_label',incoming.get('bin',''))
        if not record.get('feed_bin_id') and label:
            bins=[b for b in data['feed_bins'] if b['active'] and label in (b['name'],bin_label(b))]
            if len(bins)==1:record['feed_bin_id']=bins[0]['id']
        raw=encode([sources,index,record,label]);key=str(uuid.uuid5(uuid.NAMESPACE_URL,'pigledger-photo-row:'+raw))
        rows.append({'key':key,'record':record,'bin_label':label,'warning':incoming.get('warning',''),'choice':incoming.get('choice','auto')})
    body={'draft':{'title':document.get('title','每日飼料登記（照片待核對）'),'source':'chat_photo','sources':sources,'rows':rows}}
    request_key='photo-draft-'+hashlib.sha256(encode(body).encode()).hexdigest();result=save_draft(store,user,body,request_key)
    draft=next(r for r in store.snapshot(include_source=False)['feed_drafts'] if r['id']==result['id'])
    return {'id':draft['id'],'revision':draft['revision'],'status':draft['status'],'count':len(draft['rows']),'known_tons':sum(float(r['record']['kg'] or 0) for r in draft['rows'])/1000,'feed_orders_written':False,'version':VERSION}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-db');parser.add_argument('--username',required=True);parser.add_argument('--input',default='-');args=parser.parse_args()
    if args.local_db:
        if not Path(args.local_db).is_file():parser.error('Existing database required')
        store=Store(args.local_db)
    else:store=CloudStore();store.assert_ready()
    db=store.connect()
    try:
        row=db.execute('SELECT id,username,role,active FROM users WHERE username=?',(args.username,)).fetchone()
        if not row or not row['active']:raise ValueError('Active operator required')
        user=dict(row)
    finally:db.close()
    text=sys.stdin.read() if args.input=='-' else Path(args.input).read_text();result=stage(store,user,json.loads(text));print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
