"""Single-origin HTTP service. Run behind HTTPS reverse proxy in production."""
import argparse, csv, io, json, os, secrets, hashlib, time, threading, mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from http.cookies import SimpleCookie
from pathlib import Path
from datetime import date
from .store import Store, Problem, VERSION, KINDS, encode, verify_password
from .domain import herd, age, combined_weights, consumption, performance, day, Invalid

STATIC=Path(__file__).parent/'static'

def selected_ids(data, query):
    def get(key):return query.get(key,[''])[0]
    return [b['id'] for b in data['batches'] if (not get('batch_id') or b['id']==get('batch_id')) and (not get('barn_id') or b['barn_id']==get('barn_id')) and (not get('group') or (b.get('group') or next((x['group'] for x in data['barns'] if x['id']==b['barn_id']),''))==get('group'))]


def filter_rows(kind,data,query):
    get=lambda key:query.get(key,[''])[0]
    ids=set(selected_ids(data,query));scoped=any(get(k) for k in ('batch_id','barn_id','group'))
    rows=[]
    candidates=data[kind]+legacy_history_rows(data) if kind=='movements' else data[kind]
    for r in candidates:
        rd=r.get('date') or r.get('start') or r.get('entry_date','')
        if get('from') and (r['end']<=get('from') if kind=='usages' else rd<get('from')):continue
        if get('to') and rd>get('to'):continue
        if get('type') and r.get('type')!=get('type'):continue
        if get('vendor') and r.get('vendor')!=get('vendor'):continue
        if get('item') and get('item').lower() not in r.get('item','').lower():continue
        if kind=='deliveries':
            if scoped and not any(a['batch_id'] in ids for a in r['allocations']):continue
        elif kind=='batches':
            if r['id'] not in ids:continue
        elif r.get('batch_id') and r['batch_id'] not in ids and r.get('target_batch_id') not in ids:continue
        elif r.get('legacy_source') and not r.get('batch_id') and scoped:
            if get('batch_id') or get('barn_id') or not (set(r['legacy_members'])&ids):continue
        rows.append(r)
    return sorted(rows,key=lambda r:r.get('date') or r.get('start') or r.get('entry_date',''),reverse=True)

def legacy_history_rows(data):
    """Read-only source events; excluded from live deltas already in baseline stock."""
    import uuid
    output=[]
    for book in data.get('workbooks',[]):
        for source in book['report']['rows']:
            members=[b for b in data['batches'] if b.get('legacy_source')==book['id'] and b.get('legacy_row')==source['key']]
            for index,event in enumerate(source['events']):
                allocations=event['allocations'] or [{'barn':None,'quantity':event['quantity']}]
                for allocation in allocations:
                    batch=next((b for b in members if b['legacy_barn']==allocation['barn']),None)
                    rid=str(uuid.uuid5(uuid.NAMESPACE_URL,book['id']+':'+event['cell']+':'+str(index)+':'+str(allocation['barn'])))
                    output.append({'id':rid,'revision':1,'date':event['date'],'type':event['type'],'quantity':allocation['quantity'],'batch_id':batch['id'] if batch else None,'legacy_batch':source['name'],'legacy_members':[b['id'] for b in members],'legacy_source':book['id'],'source_cell':book['report']['sheet']+'!'+event['cell'],'note':event['text']+(' [以儲存公式的正常出豬數為準，死亡另計]' if event.get('formula_count_corrected') else '')})
    return output


def statistics(data,query):
    get=lambda k:query.get(k,[''])[0]
    until=get('to') or date.today().isoformat();start=get('from')
    day(until)
    if start:day(start)
    if start and start>until:raise Invalid('invalid_period')
    ids=selected_ids(data,query)
    cumulative=herd(data['batches'],data['movements'],until,ids)
    scoped=any(get(k) for k in ('batch_id','barn_id','group'))
    supported=[d for book in data.get('workbooks',[]) for row in book['plan']['rows'] for d in row['snapshots']]
    if not scoped and supported and until<min(supported):
        for field in ('entry','sold','culled','dead','remaining','outgoing','denominator','survival'):cumulative[field]=None
        cumulative['historical_unknown']=True
    stats={'as_of':until,'cumulative':cumulative,'ids':ids,'interval':None,'batches':[]}
    chosen=set(ids)
    if start:
        delta=dict(entry=sum(b['entry_count'] or 0 for b in data['batches'] if b['id'] in chosen and start<=b['entry_date']<=until),sale=0,cull=0,death=0,arrival=0,adjustment=0,transfer_in=0,transfer_out=0)
        for m in data['movements']:
            if not start<=m['date']<=until:continue
            if m['type']=='transfer':
                if m['batch_id'] in chosen and m['target_batch_id'] not in chosen:delta['transfer_out']+=m['quantity']
                if m['target_batch_id'] in chosen and m['batch_id'] not in chosen:delta['transfer_in']+=m['quantity']
            elif m['batch_id'] in chosen:delta[m['type']]+=m['quantity']
        stats['interval']=delta
        if any(b['id'] in chosen and b.get('legacy_group') and start<=b['legacy_group']['as_of'] and until>=b['entry_date'] for b in data['batches']) or (not scoped and supported and until<min(supported)):
            stats['legacy_interval_unknown']=True
            stats['interval']={key:None for key in delta}
    scoped=any(get(k) for k in ('batch_id','barn_id','group'))
    deliveries=[d for d in data['deliveries'] if d['date']<=until and (not start or d['date']>=start)]
    stats['delivery_kg']=sum(sum(a['kg'] for a in d['allocations'] if a['batch_id'] in chosen) if scoped else d['kg'] for d in deliveries)
    stats['unallocated_kg']=sum(d['kg'] for d in deliveries if not d['allocations'])
    uses=[u for u in data['usages'] if u['active'] and u['batch_id'] in chosen and u['end']<=next_day(until) and (not start or u['start']>=start)]
    excluded=[u for u in data['usages'] if u['active'] and u['batch_id'] in chosen and u['start']<=until and u['end']>(start or '0001-01-01') and u not in uses]
    values=[consumption(u,data['deliveries']) for u in uses]
    stats['consumption_kg']=sum(values) if values and all(v>=0 for v in values) else None
    stats['usage_count']=len(uses);stats['excluded_usage_count']=len(excluded)
    stats['negative_usage']=any(v<0 for v in values)
    perfs=[]
    for b in data['batches']:
        if b['id'] not in chosen or b['entry_date']>until:continue
        p=performance(b,data['batches'],data['movements'],data['weights'],data['usages'],data['deliveries'],until,start,until)
        perfs.append(p)
        stats['batches'].append({'id':b['id'],'age_days':age(b,until),'herd':herd(data['batches'],data['movements'],until,[b['id']]),'performance':p})
    periods={(p['first']['date'],p['last']['date']) for p in perfs if p.get('first') and p.get('last')}
    comparison_period=next(iter(periods)) if len(periods)==1 else (start,until) if not periods and start else None
    empty_ids=set()
    if comparison_period:
        first,last=comparison_period
        for item in stats['batches']:
            bid=item['id']
            n0=herd(data['batches'],data['movements'],first,[bid],before=True)['remaining']
            n1=herd(data['batches'],data['movements'],last,[bid],before=True)['remaining']
            activity=any(first<=m['date']<=last and (m['batch_id']==bid or m.get('target_batch_id')==bid) for m in data['movements'])
            activity|=any(w['batch_id']==bid and first<=w['date']<=last for w in data['weights'])
            activity|=any(u['batch_id']==bid and u['active'] and u['start']<last and u['end']>first for u in data['usages'])
            if n0==0 and n1==0 and not activity:
                empty_ids.add(bid);item['performance']['reasons']=['empty_fcr_period']
        perfs=[item['performance'] for item in stats['batches'] if item['id'] not in empty_ids]
    stats['empty_fcr_batches']=len(empty_ids)
    comparable=len({(p.get('first',{}).get('date'),p.get('last',{}).get('date')) for p in perfs})==1
    if perfs and all(p['fcr'] is not None for p in perfs) and comparable:
        feed=sum(p['feed'] for p in perfs);gain=sum(p['gain'] for p in perfs)
        stats['aggregate_fcr']=feed/gain;stats['fcr_period']=[perfs[0]['first']['date'],perfs[0]['last']['date']]
    else:stats['aggregate_fcr']=None
    stats['incomplete_fcr_batches']=sum(p['fcr'] is None for p in perfs)
    stats['fcr_period_mismatch']=bool(perfs) and not comparable
    return stats


def next_day(s):
    from datetime import timedelta
    return (day(s)+timedelta(days=1)).isoformat()


class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,store,secure=False):
        super().__init__(address,Handler)
        self.store=store;self.secure=secure;self.instance=secrets.token_hex(8);self.login_attempts={};self.lock=threading.Lock();self.public_host=None


class Handler(BaseHTTPRequestHandler):
    server_version='PigLedger/'+VERSION
    def log_message(self,fmt,*args):
        # Never log query strings, request bodies, passwords or session cookies.
        print('%s %s %s'%(self.log_date_time_string(),self.command,urlparse(self.path).path),flush=True)
    def send(self,obj,status=200,content_type='application/json; charset=utf-8',headers=None):
        raw=obj if isinstance(obj,bytes) else encode(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','same-origin')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; worker-src 'self'; manifest-src 'self'; frame-ancestors 'none'")
        self.send_header('Cache-Control','no-store' if self.path.startswith('/api/') else 'no-cache')
        if self.server.secure:self.send_header('Strict-Transport-Security','max-age=31536000')
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(raw)
    def body(self):
        size=int(self.headers.get('Content-Length','0'))
        if size>20*1024*1024:raise Problem('payload_too_large',413)
        if size<=0:return {}
        try:return json.loads(self.rfile.read(size))
        except (ValueError,UnicodeError):raise Problem('invalid_json')
    def session(self,required=True):
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:raise Problem('login_required',401)
        token=cookie.get('session')
        if token:
            db=self.server.store.connect()
            try:
                row=db.execute('SELECT u.id,u.username,u.role,u.active,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(hashlib.sha256(token.value.encode()).hexdigest(),time.time())).fetchone()
                if row and row['active']:return dict(row)
            finally:db.close()
        if required:raise Problem('login_required',401)
    def protect(self,user):
        if not hmac_safe(self.headers.get('X-CSRF-Token',''),user['csrf']):raise Problem('csrf_failed',403)
        origin=self.headers.get('Origin')
        if origin and (urlparse(origin).netloc!=self.headers.get('Host') or (self.server.public_host and urlparse(origin).scheme!='https')):raise Problem('csrf_failed',403)
    def do_GET(self):self.run('GET')
    def do_POST(self):self.run('POST')
    def do_PUT(self):self.run('PUT')
    def do_DELETE(self):self.run('DELETE')
    def run(self,method):
        try:self.dispatch(method)
        except Problem as e:self.send({'error':e.code,'details':e.details},e.status)
        except Invalid as e:self.send({'error':str(e)},400)
        except (ValueError,TypeError,KeyError) as e:self.send({'error':'invalid_request'},400)
        except Exception as e:
            print('Unhandled error:',type(e).__name__,str(e),flush=True)
            self.send({'error':'server_error'},500)
    def dispatch(self,method):
        url=urlparse(self.path);path=url.path;query=parse_qs(url.query,keep_blank_values=True)
        store=self.server.store
        if self.server.public_host and self.headers.get('Host')!=self.server.public_host:
            raise Problem('invalid_host',403)
        if path=='/api/health' and method=='GET':
            db=store.connect()
            try:db.execute('SELECT 1').fetchone()
            finally:db.close()
            return self.send({'ok':True,'version':VERSION,'profile_id':hashlib.sha256(str(store.path.resolve()).encode()).hexdigest()[:16]})
        if path=='/api/login' and method=='POST':
            origin=self.headers.get('Origin')
            if origin and (urlparse(origin).netloc!=self.headers.get('Host') or (self.server.public_host and urlparse(origin).scheme!='https')):raise Problem('csrf_failed',403)
            body=self.body();username=body.get('username','');password=body.get('password','')
            if not isinstance(username,str) or not isinstance(password,str) or len(password)>512:raise Problem('invalid_credentials',401)
            key=(self.client_address[0],username)
            with self.server.lock:
                failures=[t for t in self.server.login_attempts.get(key,[]) if t>time.time()-900]
                if len(failures)>=10:raise Problem('login_limited',429)
                self.server.login_attempts[key]=failures+[time.time()]
            db=store.connect()
            try:
                user=db.execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone()
                if not user or not verify_password(password,user['hash']):raise Problem('invalid_credentials',401)
                token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
                db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
                db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],csrf,time.time()+43200));db.commit()
                with self.server.lock:self.server.login_attempts.pop(key,None)
                return self.send({'id':user['id'],'username':user['username'],'role':user['role'],'csrf':csrf,'version':VERSION},headers={'Set-Cookie':'session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'+('; Secure' if self.server.secure else '')})
            finally:db.close()
        if path.startswith('/api/'):
            user=self.session()
            if method!='GET':self.protect(user)
            if path=='/api/me' and method=='GET':return self.send(user|{'version':VERSION})
            if path=='/api/logout' and method=='POST':
                db=store.connect();db.execute('DELETE FROM sessions WHERE user_id=? AND csrf=?',(user['id'],user['csrf']));db.commit();db.close()
                return self.send({'ok':True},headers={'Set-Cookie':'session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
            if path=='/api/snapshot' and method=='GET':
                db=store.connect()
                try:
                    db.execute('BEGIN')
                    revision=self.server.instance+':'+str(db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0])
                    if query.get('since',[''])[0]==revision:return self.send({'unchanged':True,'version':VERSION,'cursor':revision})
                    return self.send(store.snapshot(db)|{'version':VERSION,'cursor':revision})
                finally:db.close()
            if path=='/api/statistics' and method=='GET':return self.send(statistics(store.snapshot(),query))
            if path=='/api/audit' and method=='GET':
                store.require(user,True);db=store.connect()
                try:return self.send([dict(r) for r in db.execute('SELECT a.*,u.username FROM audit a LEFT JOIN users u ON a.user_id=u.id ORDER BY seq DESC LIMIT 500')])
                finally:db.close()
            if path=='/api/users':
                store.require(user,True)
                if method=='GET':
                    db=store.connect()
                    try:return self.send([dict(r) for r in db.execute('SELECT id,username,role,active,revision FROM users')])
                    finally:db.close()
                if method=='POST':
                    b=self.body();return self.send(store.create_user(b.get('username'),b.get('password'),b.get('role'),user['id']),201)
            if path.startswith('/api/users/') and method=='PUT':
                store.require(user,True);rid=path.split('/')[-1];b=self.body();db=store.connect()
                try:
                    db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT id,username,role,active,revision FROM users WHERE id=?',(rid,)).fetchone()
                    if not old:raise Problem('not_found',404)
                    if b.get('role') not in ('admin','staff','viewer') or not isinstance(b.get('active'),bool):raise Problem('invalid_user')
                    if old['role']=='admin' and old['active'] and (b['role']!='admin' or not b['active']) and db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]<=1:raise Problem('last_admin')
                    if any(old[k]!=b.get('before',{}).get(k) for k in ('role','active','revision')):raise Problem('revision_conflict',409)
                    if b.get('password'):
                        if not 12<=len(b['password'])<=512:raise Problem('invalid_user')
                        from .store import password_hash
                        db.execute('UPDATE users SET hash=? WHERE id=?',(password_hash(b['password']),rid))
                    db.execute('UPDATE users SET role=?,active=?,revision=revision+1 WHERE id=?',(b['role'],b['active'],rid));db.execute('DELETE FROM sessions WHERE user_id=?',(rid,))
                    store.audit(db,user['id'],'update','users',rid,dict(old),{'role':b['role'],'active':b['active']});db.commit();return self.send({'ok':True})
                finally:db.close()
            if path=='/api/backup' and method=='GET':
                store.require(user,True)
                return self.send(store.export_backup(),headers={'Content-Disposition':'attachment; filename="pigledger-'+VERSION+'-'+date.today().isoformat()+'.json"'})
            if path=='/api/import' and method=='POST':return self.send(store.import_backup(user,self.body()))
            if path=='/api/workbook/preview' and method=='POST':
                store.require(user,True)
                cleaned=store.validate('workbooks',self.body(),store.snapshot(),user)
                return self.send({'filename':cleaned['filename'],'sha256':cleaned['sha256'],'report':cleaned['report'],'plan':cleaned['plan']})
            if path=='/api/workbook/import' and method=='POST':
                return self.send(store.import_workbook(user,self.body(),self.headers.get('Idempotency-Key')),201)
            if path.startswith('/api/workbooks/') and path.endswith('/file') and method=='GET':
                import base64
                from urllib.parse import quote
                rid=path.split('/')[3];book=next((b for b in store.snapshot()['workbooks'] if b['id']==rid),None)
                if not book:raise Problem('not_found',404)
                return self.send(base64.b64decode(book['base64']),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(book['filename'])})
            if path=='/api/export' and method=='GET':
                kind=query.get('kind',['movements'])[0]
                if kind not in ('movements','deliveries','usages','weights'):raise Problem('unknown_kind')
                data=store.snapshot();rows=filter_rows(kind,data,query)
                batches={b['id']:b for b in data['batches']};barns={b['id']:b['name'] for b in data['barns']}
                out=io.StringIO();writer=csv.writer(out)
                writer.writerow(['id','revision','date','end_exclusive','barn','batch','type_or_source','quantity','unit','mean_kg','age_days','vendor','item','note','allocations','status','sample_count','individual_weights_kg','pen','selected_allocated_kg','calculation_source','source_cell'])
                for r in rows:
                    batch=batches.get(r.get('batch_id'),{})
                    q=consumption(r,data['deliveries']) if kind=='usages' else r.get('quantity',r.get('kg',r.get('total_kg','')))
                    values=[r['id'],r['revision'],r.get('date',r.get('start','')),r.get('end',''),barns.get(batch.get('barn_id'),''),batch.get('name',r.get('legacy_batch','')),r.get('type',r.get('method','sample' if kind=='weights' else 'delivery')),q,'heads' if kind=='movements' else 'kg',r['total_kg']/r['count'] if kind=='weights' else '',r.get('age_days',''),r.get('vendor',''),r.get('item',''),r.get('note',''),encode(r.get('allocations',[])),('active' if r['active'] else 'excluded') if kind=='usages' else '',r.get('count',''),encode(r.get('individual_kg',[])),r.get('pen',''),sum(a['kg'] for a in r.get('allocations',[]) if a['batch_id'] in set(selected_ids(data,query))) ,'legacy_excel_readonly' if r.get('legacy_source') else r.get('method','recorded'),r.get('source_cell','')]
                    # Spreadsheet formula injection protection; original fields remain intact in backups.
                    writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for v in values])
                return self.send(('\ufeff'+out.getvalue()).encode(),content_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="'+kind+'-'+VERSION+'.csv"'})
            parts=path.strip('/').split('/')
            if len(parts) in (2,3) and parts[1] in KINDS:
                kind=parts[1];rid=parts[2] if len(parts)==3 else None
                if method=='GET':return self.send(filter_rows(kind,store.snapshot(),query))
                if (method=='POST' and not rid) or (method in ('PUT','DELETE') and rid):
                    result=store.mutate(user,kind,self.body(),self.headers.get('Idempotency-Key'),rid,method=='DELETE')
                    return self.send(result,201 if method=='POST' else 200)
            raise Problem('not_found',404)
        if method!='GET':raise Problem('not_found',404)
        name='index.html' if path=='/' else path.lstrip('/')
        target=(STATIC/name).resolve()
        if not target.is_relative_to(STATIC.resolve()) or not target.is_file():raise Problem('not_found',404)
        return self.send(target.read_bytes(),content_type=mimetypes.guess_type(str(target))[0] or 'application/octet-stream')


def hmac_safe(a,b):
    import hmac
    return hmac.compare_digest(a,b)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8080);parser.add_argument('--db',default=os.environ.get('PIGLEDGER_DB','/workspace/555/.data/pigledger.sqlite3'));parser.add_argument('--secure',action='store_true',default=os.environ.get('PIGLEDGER_SECURE')=='1');args=parser.parse_args()
    store=Store(args.db);server=Server((args.host,args.port),store,args.secure)
    print('PigLedger',VERSION,'listening on',args.host,args.port,flush=True)
    server.serve_forever()

if __name__=='__main__':main()
