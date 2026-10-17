"""Single-origin HTTP service. Run behind HTTPS reverse proxy in production."""
import argparse, csv, io, json, os, secrets, hashlib, time, threading, mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from http.cookies import SimpleCookie
from pathlib import Path
from datetime import date,datetime,timezone,timedelta
from .store import Store, Problem, VERSION, KINDS, encode, verify_password, validate_password
from .domain import herd, age, combined_weights, consumption, performance, day, Invalid
from .history import source_history,source_rows,cohort_key

STATIC=Path(__file__).parent/'static'

def selected_ids(data, query):
    def get(key):return query.get(key,[''])[0]
    return [b['id'] for b in data['batches'] if (not get('batch_id') or b['id']==get('batch_id')) and (not get('barn_id') or b['barn_id']==get('barn_id')) and (not get('cohort') or cohort_key(b)==get('cohort')) and (not get('group') or (b.get('group') or next((x['group'] for x in data['barns'] if x['id']==b['barn_id']),''))==get('group'))]


def filter_rows(kind,data,query):
    get=lambda key:query.get(key,[''])[0]
    ids=set(selected_ids(data,query));scoped=any(get(k) for k in ('batch_id','barn_id','group','cohort'))
    rows=[]
    candidates=list({r['id']:r for r in ((source_history(data,kind)+data[kind]) if kind in ('movements','weights') else data[kind])}.values())
    for r in candidates:
        rd=r.get('entry_date','') if kind=='batches' else r.get('date') or r.get('start') or ''
        if get('missing')=='1' and r.get('date') and not r.get('unresolved') and not (r.get('source_mean') and r.get('count') is None):continue
        if (get('from') or get('to')) and not rd:continue
        if get('from') and (r['end']<=get('from') if kind=='usages' else rd<get('from')):continue
        if get('to') and rd>get('to'):continue
        if kind=='movements' and get('type') and r.get('type')!=get('type'):continue
        if get('cohort') and r.get('cohort') and r['cohort']!=get('cohort'):continue
        if kind=='feed_orders' and get('feed_bin_id') and r.get('feed_bin_id')!=get('feed_bin_id'):continue
        if get('vendor') and r.get('vendor')!=get('vendor'):continue
        if get('item') and get('item').lower() not in r.get('item','').lower():continue
        if kind=='feed_orders' and r.get('feed_bin_id'):
            from .feed import order_scope
            attribution=order_scope(r,data,ids if scoped else None)
            if scoped and not attribution['related']:continue
            r=r|{'scope_attribution':attribution}
        elif kind in ('deliveries','feed_orders'):
            if scoped and not any(a['batch_id'] in ids for a in r['allocations']):continue
        elif kind=='batches':
            if r['id'] not in ids:continue
        elif r.get('batch_id') and r['batch_id'] not in ids and r.get('target_batch_id') not in ids:continue
        elif r.get('legacy_source') and not r.get('batch_id') and scoped:
            if get('batch_id'):continue
            if get('barn_id'):
                if r.get('barn_id')!=get('barn_id'):continue
            elif get('cohort'):
                if r.get('cohort')!=get('cohort'):continue
            elif not (set(r['legacy_members'])&ids):continue
        rows.append(r)
    return sorted(rows,key=lambda r:r.get('date') or r.get('start') or '',reverse=True)

def legacy_history_rows(data):
    return source_history(data,'movements')


def statistics(data,query):
    get=lambda k:query.get(k,[''])[0]
    until=get('to') or datetime.now(timezone(timedelta(hours=8))).date().isoformat();start=get('from')
    day(until)
    if start:day(start)
    if start and start>until:raise Invalid('invalid_period')
    ids=selected_ids(data,query)
    cumulative=herd(data['batches'],data['movements'],until,ids)
    scoped=any(get(k) for k in ('batch_id','barn_id','group','cohort'))
    supported=[d for book in data.get('workbooks',[]) for row in book['plan']['rows'] for d in row['snapshots']]
    if not scoped and supported and until<min(supported):
        for field in ('entry','sold','culled','dead','remaining','outgoing','denominator','survival'):cumulative[field]=None
        cumulative['historical_unknown']=True
    stats={'as_of':until,'cumulative':cumulative,'ids':ids,'interval':None,'batches':[]}
    chosen=set(ids)
    if get('summary')=='1':
        stats['batches']=[{'id':b['id'],'age_days':age(b,until),'herd':herd(data['batches'],data['movements'],until,[b['id']])} for b in data['batches'] if b['id'] in chosen]
        # Include ended barns in the cohort, and calculate from their combined
        # denominator/deaths. Unknown per-barn entry counts can still have a
        # reliable complete-cohort source total; percentages must not be averaged.
        members_by_cohort={}
        for b in data['batches']:
            if b['id'] in chosen:members_by_cohort.setdefault(cohort_key(b),[]).append(b)
        stats['cohorts']=[{'cohort':key,'name':members[0]['name'],'ids':[b['id'] for b in members],
            'herd':herd(data['batches'],data['movements'],until,[b['id'] for b in members])}
            for key,members in members_by_cohort.items()]
        return stats
    if start:
        delta=dict(entry=sum(b['entry_count'] or 0 for b in data['batches'] if b['id'] in chosen and start<=b['entry_date']<=until),sale=0,cull=0,death=0,arrival=0,adjustment=0,transfer_in=0,transfer_out=0)
        for m in filter_rows('movements',data,{k:v for k,v in query.items() if k!='type'}|{'from':[start],'to':[until]}):
            if m.get('archive') or not m.get('date'):continue
            if not start<=m['date']<=until:continue
            if m['type']=='transfer':
                if m['batch_id'] in chosen and m['target_batch_id'] not in chosen:delta['transfer_out']+=m['quantity']
                if m['target_batch_id'] in chosen and m['batch_id'] not in chosen:delta['transfer_in']+=m['quantity']
            elif m['batch_id'] in chosen or (m.get('legacy_members') and set(m['legacy_members'])<=chosen):delta[m['type']]+=m['quantity']
        stats['interval']=delta
        unresolved=[r for r in source_history(data) if r.get('unresolved') and set(r.get('legacy_members',[]))&chosen]
        partial=[r for r in source_history(data) if r.get('date') and start<=r['date']<=until and not r.get('batch_id') and set(r.get('legacy_members',[]))&chosen and not set(r.get('legacy_members',[]))<=chosen]
        missing={r['type'] for r in unresolved+partial}
        if any(b['id'] in chosen and b.get('legacy_group') and start<=b['entry_date']<=until and b['entry_count'] is None for b in data['batches']):
            groups={b['legacy_group']['id']:b for b in data['batches'] if b['id'] in chosen and b.get('legacy_group') and start<=b['entry_date']<=until}
            for batch in groups.values():
                group=batch['legacy_group']
                if set(group['members'])<=chosen:delta['entry']+=group['snapshots'][group['as_of']]['entry']-sum(b['entry_count'] or 0 for b in data['batches'] if b['id'] in group['members'])
                else:missing.add('entry')
        if missing or (not scoped and supported and until<min(supported)):
            stats['legacy_interval_unknown']=True
            stats['known_interval']=dict(delta)
            stats['interval']={key:(None if key in missing or (not scoped and supported and until<min(supported)) else value) for key,value in delta.items()}
    scoped=any(get(k) for k in ('batch_id','barn_id','group','cohort'))
    deliveries=[d for d in data['deliveries'] if d['date']<=until and (not start or d['date']>=start)]
    stats['delivery_kg']=sum(sum(a['kg'] for a in d['allocations'] if a['batch_id'] in chosen) if scoped else d['kg'] for d in deliveries)
    from .feed import order_scope
    order_values=[order_scope(o,data,chosen if scoped else None) for o in data.get('feed_orders',[]) if o['date']<=until and (not start or o['date']>=start)]
    order_values=[v for v in order_values if v['related']]
    stats['feed_order_known_kg']=sum(v['kg'] or 0 for v in order_values)
    stats['feed_order_kg']=None if any(v['kg'] is None for v in order_values) else stats['feed_order_known_kg']
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
        source_weights=[w for w in source_history(data,'weights') if w.get('batch_id')==b['id'] and not w.get('archive')]
        p=performance(b,data['batches'],data['movements'],data['weights']+source_weights,data['usages'],data['deliveries'],until,start,until)
        if p.get('first') and any(r.get('date') and p['first']['date']<=r['date']<=p['last']['date'] and b['id'] in r.get('legacy_members',[]) for r in source_history(data)):
            p['composition_changed']=True
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
    stats['cohorts']=[]
    for key in dict.fromkeys(cohort_key(b) for b in data['batches'] if b['id'] in chosen):
        members=[b for b in data['batches'] if b['id'] in chosen and cohort_key(b)==key and b['entry_date']<=until]
        if not members:continue
        weights=[w for w in source_history(data,'weights') if w.get('cohort')==key and w.get('date') and w['date']<=until and (not start or w['date']>=start)]
        means=combined_weights(weights)
        estimate=None
        if len(means)>=2:
            first,last=means[0],means[-1];days=(day(last['date'])-day(first['date'])).days
            estimate={'first':first,'last':last,'days':days,'delta':last['mean']-first['mean'],
                'adg':(last['mean']-first['mean'])/days,'source':'source_mean','estimated':True,'fcr':None,
                'composition_changed':any(r.get('date') and first['date']<=r['date']<=last['date'] and r.get('cohort')==key for r in source_history(data))}
        death_query={'cohort':[key],'from':[start or until],'to':[until],'type':['death']}
        for field in ('barn_id','batch_id','group'):
            if get(field):death_query[field]=[get(field)]
        deaths=filter_rows('movements',data,death_query)
        ages={age(b,until) for b in members}
        uncertain=[r for r in source_history(data) if r.get('cohort')==key and r.get('type')=='death' and (not r.get('batch_id') or r['batch_id'] in chosen) and (not r.get('date') or ((start or until)<=r['date']<=until and not r.get('batch_id')))]
        unknown_cohort=any(not r.get('date') or not set(r.get('legacy_members',[]))<=chosen for r in uncertain)
        stats['cohorts'].append({'cohort':key,'name':members[0]['name'],'entry_date':members[0]['entry_date'],'herd':herd(data['batches'],data['movements'],until,[b['id'] for b in members]),
            'age_days':next(iter(ages)) if len(ages)==1 else None,'age_mixed':len(ages)>1 and None not in ages,'period_deaths':None if unknown_cohort else sum(r['quantity'] for r in deaths if not r.get('archive')),
            'known_period_deaths':sum(r['quantity'] for r in deaths if not r.get('archive')),
            'barns':[{'id':b['id'],'barn_id':b['barn_id'],'herd':herd(data['batches'],data['movements'],until,[b['id']]),
                'age_days':age(b,until),'known_period_deaths':sum(r['quantity'] for r in deaths if r.get('batch_id')==b['id']),
                'period_deaths':None if any(not r.get('batch_id') or r['batch_id']==b['id'] for r in uncertain) else sum(r['quantity'] for r in deaths if r.get('batch_id')==b['id'])} for b in members],
            'source_performance':estimate if not get('barn_id') and not get('batch_id') else None,
            'missing_fields':[field for field in ('entry','dead') if any(herd(data['batches'],data['movements'],until,[b['id']])[field] is None for b in members)]})
    death_start=start or until
    scope={k:v for k,v in query.items() if k in ('batch_id','barn_id','cohort','group')}
    death_rows=filter_rows('movements',data,scope|{'from':[death_start],'to':[until],'type':['death']})
    relevant=[r for r in source_history(data) if r['type']=='death' and (not scoped or r.get('batch_id') in chosen or (not r.get('batch_id') and (set(r.get('legacy_members',[]))&chosen or get('cohort')==r.get('cohort'))))]
    incomplete=any((not r.get('date') and (not r.get('archive') or get('cohort')==r.get('cohort'))) or (r.get('date') and death_start<=r['date']<=until and scoped and not r.get('batch_id') and not set(r.get('legacy_members',[]))<=chosen) for r in relevant)
    known=sum(r['quantity'] for r in death_rows)
    stats['death_summary']={'from':death_start,'to':until,'scope':{k:v[0] for k,v in scope.items()},'known':known,'total':None if incomplete else known,'rows':death_rows}
    # The compact list uses the same scope as history/CSV, including dated
    # archived source events. Archives never become new stock or batch records.
    stats['death_groups']=[{k:c[k] for k in ('cohort','name','entry_date','age_days','age_mixed','period_deaths','known_period_deaths','barns')} for c in stats['cohorts']]
    for source in source_rows(data,archives=True):
        if not source['archive']:continue
        row=source['row'];key=cohort_key(row)
        rows=[r for r in death_rows if r.get('archive') and r.get('cohort')==key]
        if not rows and get('cohort')!=key:continue
        if any(c['cohort']==key for c in stats['death_groups']):continue
        undated=any(r.get('archive') and r.get('cohort')==key and r['type']=='death' and not r.get('date') for r in relevant)
        barns=[]
        for number in row['barns']:
            barn=next((b for b in data['barns'] if str(b['name']).replace('第','').replace('棟','').strip()==str(number)),None)
            if get('barn_id') and (not barn or barn['id']!=get('barn_id')):continue
            count=sum(r['quantity'] for r in rows if r.get('barn_number')==number)
            barns.append({'id':None,'barn_id':barn['id'] if barn else None,'name':str(number)+'棟','age_days':None,
                'period_deaths':None if undated or any(r.get('barn_number') is None for r in rows) else count,'known_period_deaths':count})
        stats['death_groups'].append({'cohort':key,'name':row['name'],'entry_date':row['entry_date'],'archive':True,
            'age_days':None,'period_deaths':None if undated else sum(r['quantity'] for r in rows),
            'known_period_deaths':sum(r['quantity'] for r in rows),'barns':barns})
    from .review import check_coverage
    stats['death_check_coverage']=check_coverage(data,ids,death_start,until)
    return stats


def next_day(s):
    from datetime import timedelta
    return (day(s)+timedelta(days=1)).isoformat()


def client_snapshot(snapshot,cursor):
    dashboard=statistics(snapshot,{'summary':['1']})
    cohorts={cohort_key(b):{'key':cohort_key(b),'name':b['name'],'entry_date':b['entry_date'],'archive':False} for b in sorted(snapshot['batches'],key=lambda b:b['entry_date'],reverse=True)}
    for source in source_rows(snapshot,archives=True):
        if source['archive']:cohorts.setdefault(cohort_key(source['row']),{'key':cohort_key(source['row']),'name':source['row']['name'],'entry_date':source['row']['entry_date'],'archive':True})
    for key,c in cohorts.items():
        c['barns']=[b['name'] for b in snapshot['barns'] if any(x['barn_id']==b['id'] and cohort_key(x)==key for x in snapshot['batches'])]
        if c['archive']:
            row=next((x['row'] for x in source_rows(snapshot,archives=True) if cohort_key(x['row'])==key),None)
            c['barns']=[str(n)+'棟' for n in row['barns']] if row else []
    from .review import daily_review, data_quality
    return snapshot|{'daily_review':daily_review(snapshot,dashboard['as_of']),'data_quality':data_quality(snapshot,dashboard['as_of'],dashboard), 'cohorts':list(cohorts.values()),'dashboard':dashboard,'version':VERSION,'cursor':cursor,
        'workbooks':[{k:b.get(k) for k in ('id','revision','filename','sha256','base_book_id','pending_cohorts')}|{'as_of':b['report']['as_of']} for b in snapshot['workbooks']]}


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
                row=db.execute('SELECT u.id,u.username,u.role,u.active,u.revision,s.csrf,COALESCE(a.must_change,0) AS must_change FROM sessions s JOIN users u ON u.id=s.user_id LEFT JOIN account_security a ON a.user_id=u.id WHERE s.token_hash=? AND s.expires>?',(hashlib.sha256(token.value.encode()).hexdigest(),time.time())).fetchone()
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
        if path=='/api/activate' and method=='POST':
            origin=self.headers.get('Origin')
            if origin and urlparse(origin).netloc!=self.headers.get('Host'):raise Problem('csrf_failed',403)
            body=self.body();username=body.get('username','')
            if hasattr(store,'reserve_login_attempt'):store.reserve_login_attempt(('activate',self.client_address[0],username))
            from .accounts import activate
            result=activate(store,username,body.get('token'),body.get('password'))
            if hasattr(store,'clear_login_attempts'):store.clear_login_attempts(('activate',self.client_address[0],username))
            return self.send(result)
        if path=='/api/login' and method=='POST':
            origin=self.headers.get('Origin')
            if origin and (urlparse(origin).netloc!=self.headers.get('Host') or (self.server.public_host and urlparse(origin).scheme!='https')):raise Problem('csrf_failed',403)
            body=self.body();username=body.get('username','');password=body.get('password','')
            if not isinstance(username,str) or not isinstance(password,str) or len(password)>512:raise Problem('invalid_credentials',401)
            key=(self.client_address[0],username)
            if hasattr(store,'reserve_login_attempt'):
                # Shared persistent limiter survives Vercel cold starts.
                store.reserve_login_attempt(key)
            else:
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
                if hasattr(store,'clear_login_attempts'):store.clear_login_attempts(key)
                else:
                    with self.server.lock:self.server.login_attempts.pop(key,None)
                security=db.execute('SELECT must_change FROM account_security WHERE user_id=?',(user['id'],)).fetchone()
                return self.send({'id':user['id'],'username':user['username'],'role':user['role'],'revision':user['revision'],
                    'must_change':bool(security and security['must_change']),'csrf':csrf,'version':VERSION},headers={'Set-Cookie':'session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'+('; Secure' if self.server.secure else '')})
            finally:db.close()
        if path.startswith('/api/'):
            user=self.session()
            if user.get('must_change') and path not in ('/api/me','/api/logout','/api/password'):raise Problem('password_change_required',403)
            if method!='GET':self.protect(user)
            if path=='/api/daily-checks/preview' and method=='GET':
                from .review import bulk_check_preview, farm_today
                store.require(user)
                return self.send(bulk_check_preview(store.snapshot(include_source=False),user,query.get('date',[farm_today()])[0]))
            if path=='/api/daily-checks/bulk' and method=='POST':
                from .review import save_bulk_checks
                result=save_bulk_checks(store,user,self.body(),self.headers.get('Idempotency-Key'))
                if '_snapshot' in result:
                    snapshot=result.pop('_snapshot');seq=result.pop('_sequence');result['sync']=client_snapshot(snapshot,self.server.instance+':'+str(seq))
                return self.send(result,201)
            if path=='/api/void-preview' and method=='GET':
                from .operations import void_preview
                return self.send(void_preview(store,user,store.snapshot(include_source=False),query.get('kind',[''])[0],query.get('id',[''])[0]))
            if path in ('/api/void','/api/weighings') and method=='POST':
                from .operations import void_record,save_weighing
                result=(void_record if path=='/api/void' else save_weighing)(store,user,self.body(),self.headers.get('Idempotency-Key'))
                if '_snapshot' in result:
                    snapshot=result.pop('_snapshot');seq=result.pop('_sequence');result['sync']=client_snapshot(snapshot,self.server.instance+':'+str(seq))
                return self.send(result,201)
            if path=='/api/me' and method=='GET':return self.send(user|{'version':VERSION})
            if path=='/api/password' and method=='POST':
                from .accounts import change_password
                body=self.body();result=change_password(store,user,body.get('current_password'),body.get('new_password'))
                return self.send(result,headers={'Set-Cookie':'session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
            if path=='/api/logout' and method=='POST':
                db=store.connect();db.execute('DELETE FROM sessions WHERE user_id=? AND csrf=?',(user['id'],user['csrf']));db.commit();db.close()
                return self.send({'ok':True},headers={'Set-Cookie':'session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
            if path=='/api/snapshot' and method=='GET':
                db=store.connect()
                try:
                    db.execute('BEGIN')
                    revision=self.server.instance+':'+str(db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0])
                    if query.get('since',[''])[0]==revision:return self.send({'unchanged':True,'version':VERSION,'cursor':revision})
                    snapshot=store.snapshot(db,include_source=False)
                    return self.send(client_snapshot(snapshot,revision))
                finally:db.close()
            if path=='/api/daily-review' and method=='GET':
                from .review import daily_review, farm_today
                return self.send(daily_review(store.snapshot(include_source=False),query.get('date',[farm_today()])[0]))
            if path=='/api/statistics' and method=='GET':return self.send(statistics(store.snapshot(include_source=False),query))
            if path=='/api/weekly-report' and method=='GET':
                from .weekly import weekly_report
                return self.send(weekly_report(store.snapshot(include_source=False),query))
            if path=='/api/audit' and method=='GET':
                store.require(user,True);db=store.connect()
                try:return self.send([dict(r) for r in db.execute('SELECT a.*,u.username FROM audit a LEFT JOIN users u ON a.user_id=u.id ORDER BY seq DESC LIMIT 500')])
                finally:db.close()
            if path=='/api/users':
                store.require(user,True)
                if method=='GET':
                    db=store.connect()
                    try:return self.send([dict(r) for r in db.execute('SELECT u.id,u.username,u.role,u.active,u.revision,COALESCE(s.must_change,0) AS must_change FROM users u LEFT JOIN account_security s ON s.user_id=u.id')])
                    finally:db.close()
                if method=='POST':
                    b=self.body();return self.send(store.create_user(b.get('username'),b.get('password'),b.get('role'),user['id'],must_change=True),201)
            if path.startswith('/api/users/') and path.endswith('/setup') and method=='POST':
                from .accounts import issue_setup
                b=self.body();return self.send(issue_setup(store,user,path.split('/')[3],b.get('revision')))
            if path.startswith('/api/users/') and method=='PUT':
                store.require(user,True);rid=path.split('/')[-1];b=self.body();store.backup_sqlite(label='before-user-update');db=store.connect()
                try:
                    db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT id,username,role,active,revision FROM users WHERE id=?',(rid,)).fetchone()
                    if not old:raise Problem('not_found',404)
                    if b.get('role') not in ('admin','staff','viewer') or not isinstance(b.get('active'),bool):raise Problem('invalid_user')
                    if old['role']=='admin' and old['active'] and (b['role']!='admin' or not b['active']) and db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]<=1:raise Problem('last_admin')
                    if any(old[k]!=b.get('before',{}).get(k) for k in ('role','active','revision')):raise Problem('revision_conflict',409)
                    if b.get('password') is not None and b.get('password')!='':
                        if rid==user['id']:raise Problem('use_own_password_form')
                        validate_password(b['password'])
                        from .store import password_hash
                        db.execute('UPDATE users SET hash=? WHERE id=?',(password_hash(b['password']),rid))
                        db.execute('INSERT INTO account_security(user_id,must_change) VALUES(?,1) ON CONFLICT(user_id) DO UPDATE SET must_change=1,setup_hash=NULL,setup_expires=NULL',(rid,))
                    username=b.get('username',old['username'])
                    if not isinstance(username,str) or not 1<=len(username.strip())<=80:raise Problem('invalid_user')
                    if db.execute('SELECT 1 FROM users WHERE username=? AND id<>?',(username.strip(),rid)).fetchone():raise Problem('username_exists',409)
                    db.execute('UPDATE users SET username=? WHERE id=?',(username.strip(),rid))
                    db.execute('UPDATE users SET role=?,active=?,revision=revision+1 WHERE id=?',(b['role'],b['active'],rid));db.execute('DELETE FROM sessions WHERE user_id=?',(rid,))
                    store.audit(db,user['id'],'update','users',rid,dict(old),{'username':username.strip(),'role':b['role'],'active':b['active'],'password_changed':bool(b.get('password'))});db.commit();return self.send({'ok':True})
                finally:db.close()
            if path=='/api/backup' and method=='GET':
                store.require(user,True)
                return self.send(store.export_backup(),headers={'Content-Disposition':'attachment; filename="pigledger-'+VERSION+'-'+date.today().isoformat()+'.json"'})
            if path=='/api/import' and method=='POST':return self.send(store.import_backup(user,self.body()))
            if path=='/api/workbook/preview' and method=='POST':
                store.require(user,True)
                cleaned=store.validate('workbooks',self.body(),store.snapshot(include_source=False),user)
                return self.send({'filename':cleaned['filename'],'sha256':cleaned['sha256'],'report':cleaned['report'],'plan':cleaned['plan'],'update_summary':cleaned.get('update_summary')})
            if path=='/api/workbook/import' and method=='POST':
                return self.send(store.import_workbook(user,self.body(),self.headers.get('Idempotency-Key')),201)
            if path.startswith('/api/workbooks/') and path.endswith('/file') and method=='GET':
                import base64
                from urllib.parse import quote
                rid=path.split('/')[3];db=store.connect()
                try:row=db.execute("SELECT data FROM records WHERE id=? AND kind='workbooks' AND deleted=0",(rid,)).fetchone();book=json.loads(row['data']) if row else None
                finally:db.close()
                if not book:raise Problem('not_found',404)
                return self.send(base64.b64decode(book['base64']),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(book['filename'])})
            if path.startswith('/api/workbooks/') and path.endswith('/details') and method=='GET':
                rid=path.split('/')[3];book=next((b for b in store.snapshot(include_source=False)['workbooks'] if b['id']==rid),None)
                if not book:raise Problem('not_found',404)
                return self.send(book)
            if path=='/api/export' and method=='GET':
                kind=query.get('kind',['movements'])[0]
                if kind not in ('movements','feed_orders','deliveries','usages','weights'):raise Problem('unknown_kind')
                data=store.snapshot(include_source=False);rows=filter_rows(kind,data,query)
                batches={b['id']:b for b in data['batches']};barns={b['id']:b['name'] for b in data['barns']}
                out=io.StringIO();writer=csv.writer(out)
                writer.writerow(['id','revision','date','end_exclusive','barn','batch','type_or_source','quantity','unit','mean_kg','age_days','vendor','item','note','allocations','status','sample_count','individual_weights_kg','pen','selected_allocated_kg','calculation_source','source_cell','section','weighing_session_id','weighing_session_number','feed_bin','feed_bin_barns','feed_target_batches','feed_scope_state'])
                for r in rows:
                    batch=batches.get(r.get('batch_id'),{})
                    if kind=='feed_orders' and len(r['allocations'])==1:batch=batches.get(r['allocations'][0]['batch_id'],{})
                    q=consumption(r,data['deliveries']) if kind=='usages' else r.get('quantity',r.get('kg',r.get('total_kg','')))
                    mean=(r.get('mean_kg') if r.get('source_mean') else r['total_kg']/r['count']) if kind=='weights' else ''
                    values=[r['id'],r['revision'],r.get('date',r.get('start','')),r.get('end',''),barns.get(batch.get('barn_id') or r.get('barn_id'),r.get('barn_number') or ''),batch.get('name',r.get('legacy_batch','')),r.get('type',r.get('method','sample' if kind=='weights' else 'feed_order' if kind=='feed_orders' else 'delivery')),q,'heads' if kind=='movements' else 'kg',mean,r.get('age_days',''),r.get('vendor',''),r.get('item',''),r.get('note',''),encode(r.get('allocations',[])),('active' if r['active'] else 'excluded') if kind=='usages' else '',r.get('count',''),encode(r.get('individual_kg',[])),r.get('pen',''),sum(a['kg'] for a in r.get('allocations',[]) if a['batch_id'] in set(selected_ids(data,query))) ,'source_mean' if r.get('source_mean') else 'legacy_excel_readonly' if r.get('legacy_source') else r.get('method','recorded'),r.get('source_cell',''),r.get('section',''),r.get('session_id',''),r.get('session_number','')]
                    if kind=='feed_orders' and r.get('feed_bin_id'):
                        from .feed import order_scope
                        scoped=any(query.get(k,[''])[0] for k in ('batch_id','barn_id','group','cohort'))
                        attribution=order_scope(r,data,selected_ids(data,query) if scoped else None)
                        values[4]='、'.join(r['feed_bin_snapshot']['barn_names']);values[5]='、'.join(batches[x]['name'] for x in r['target_batch_ids']);values[19]=attribution['kg']
                        values.extend([r['feed_bin_snapshot']['name'],'、'.join(r['feed_bin_snapshot']['barn_names']),encode(r['target_batch_ids']),attribution['state']])
                    else:values.extend(['','','',''])
                    # Spreadsheet formula injection protection; original fields remain intact in backups.
                    writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for v in values])
                return self.send(('\ufeff'+out.getvalue()).encode(),content_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="'+kind+'-'+VERSION+'.csv"'})
            parts=path.strip('/').split('/')
            if len(parts) in (2,3) and parts[1] in KINDS:
                kind=parts[1];rid=parts[2] if len(parts)==3 else None
                if method=='GET':return self.send(filter_rows(kind,store.snapshot(include_source=False),query))
                if (method=='POST' and not rid) or (method in ('PUT','DELETE') and rid):
                    if method=='DELETE':
                        store.require(user,True);raise Problem('void_preview_required')
                    result=store.mutate(user,kind,self.body(),self.headers.get('Idempotency-Key'),rid,method=='DELETE',return_snapshot=True)
                    if '_snapshot' in result:
                        snapshot=result.pop('_snapshot');sequence=result.pop('_sequence')
                        result['sync']=client_snapshot(snapshot,self.server.instance+':'+str(sequence))
                    return self.send(result,201 if method=='POST' else 200)
            raise Problem('not_found',404)
        if method!='GET':raise Problem('not_found',404)
        name='index.html' if path=='/' else path.lstrip('/')
        target=(STATIC/name).resolve()
        if not target.is_relative_to(STATIC.resolve()) or not target.is_file():raise Problem('not_found',404)
        content_type={'.webp':'image/webp','.png':'image/png','.svg':'image/svg+xml','.webmanifest':'application/manifest+json'}.get(target.suffix.lower()) or mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
        return self.send(target.read_bytes(),content_type=content_type)


def hmac_safe(a,b):
    import hmac
    return hmac.compare_digest(a,b)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8080);parser.add_argument('--db',default=os.environ.get('PIGLEDGER_DB','/workspace/555/.data/pigledger.sqlite3'));parser.add_argument('--secure',action='store_true',default=os.environ.get('PIGLEDGER_SECURE')=='1');args=parser.parse_args()
    store=Store(args.db);server=Server((args.host,args.port),store,args.secure)
    print('PigLedger',VERSION,'listening on',args.host,args.port,flush=True)
    server.serve_forever()

if __name__=='__main__':main()
