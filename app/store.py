import sqlite3, json, uuid, hashlib, secrets, hmac, os
from pathlib import Path
from datetime import datetime, timezone
from .domain import Invalid, day, number, herd, consumption, age

VERSION='1.3.0'
KINDS=('barns','batches','movements','deliveries','usages','weights','workbooks')
SCHEMA='''
CREATE TABLE IF NOT EXISTS records(kind TEXT NOT NULL, id TEXT PRIMARY KEY, revision INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS records_kind ON records(kind,deleted);
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','staff','viewer')), active INTEGER NOT NULL DEFAULT 1, revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS requests(user_id TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(user_id,key));
CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, user_id TEXT NOT NULL, action TEXT NOT NULL, kind TEXT NOT NULL, record_id TEXT NOT NULL, before_value TEXT, after_value TEXT);
'''

class Problem(Exception):
    def __init__(self, code, status=400, details=None):
        self.code, self.status, self.details = code, status, details


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False)

def re_barn_number(value):
    import re
    match=re.fullmatch(r'\s*第?(\d+)棟\s*',value)
    return int(match[1]) if match else None


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def verify_password(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.exists() and self.path.stat().st_size > 0
        db = self.connect()
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version > 3:
            db.close()
            raise RuntimeError('Database schema is newer than this application')
        if existed and version < 3:
            self.backup_sqlite(db, 'before-migration')
        db.executescript(SCHEMA)
        if 'revision' not in {r['name'] for r in db.execute('PRAGMA table_info(users)')}:
            db.execute('ALTER TABLE users ADD COLUMN revision INTEGER NOT NULL DEFAULT 1')
        db.execute('PRAGMA user_version=3');db.commit()
        db.close()
        if self.path.exists():
            os.chmod(self.path, 0o600)

    def connect(self):
        db=sqlite3.connect(self.path,timeout=20)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA busy_timeout=20000')
        return db

    def backup_sqlite(self, db=None, label='backup'):
        owned=db is None
        db=db or self.connect()
        folder=self.path.parent/'backups'
        folder.mkdir(exist_ok=True)
        target=folder/(label+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.sqlite3')
        dest=sqlite3.connect(target)
        db.backup(dest)
        dest.close()
        os.chmod(target,0o600)
        if owned: db.close()
        return target

    def snapshot(self, db=None):
        owned=db is None
        db=db or self.connect()
        data={k:[] for k in KINDS}
        for r in db.execute('SELECT * FROM records WHERE deleted=0 ORDER BY rowid'):
            if r['kind'] not in data: raise RuntimeError('Unknown entity in database')
            data[r['kind']].append(json.loads(r['data']) | {'id':r['id'],'revision':r['revision']})
        self.enrich_legacy(data)
        if owned: db.close()
        return data

    def enrich_legacy(self,data):
        books={book['id']:book for book in data['workbooks']}
        for b in data['batches']:
            if not b.get('legacy_source'):continue
            book=books.get(b['legacy_source'])
            if not book:continue
            row=next((r for r in book['report']['rows'] if r['key']==b['legacy_row']),None)
            plan=next((p for p in book['plan']['rows'] if p['key']==b['legacy_row']),None)
            if not row or not plan:continue
            members=[x['id'] for x in data['batches'] if x.get('legacy_source')==book['id'] and x.get('legacy_row')==row['key']]
            b['legacy_group']={'id':book['id']+':'+row['key'],'members':members,'expected_members':len(row['barns']),'snapshots':plan['snapshots'],'as_of':book['report']['as_of']}
            b['legacy_heads']={book['report']['as_of']:plan['current'].get(str(b['legacy_barn']),plan['current'].get(b['legacy_barn']))}
            if book['plan']['counts_as_of']!=book['report']['as_of']:
                b['legacy_heads'][book['plan']['counts_as_of']]=plan['before'].get(str(b['legacy_barn']),plan['before'].get(b['legacy_barn']))
            b['legacy_values']={}
            for snapshot_date in plan['snapshots']:
                values={'entry':b['entry_count']}
                for field,typ in [('sold','sale'),('culled','cull'),('dead','death')]:
                    all_events=[e for e in row['events'] if e['type']==typ]
                    dated=[e for e in all_events if e['date']<=snapshot_date]
                    complete=sum(e['quantity'] for e in all_events)==row['totals'][field] and all(sum(a['quantity'] for a in e['allocations'])==e['quantity'] for e in dated)
                    values[field]=sum(a['quantity'] for e in dated for a in e['allocations'] if a['barn']==b['legacy_barn']) if complete else None
                b['legacy_values'][snapshot_date]=values

    def create_user(self, username, password, role='admin', actor='bootstrap'):
        if role not in ('admin','staff','viewer') or not isinstance(username,str) or not 1<=len(username.strip())<=80 or not isinstance(password,str) or not 12<=len(password)<=512:
            raise Problem('invalid_user')
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            uid=str(uuid.uuid4())
            db.execute('INSERT INTO users(id,username,hash,role) VALUES(?,?,?,?)',(uid,username.strip(),password_hash(password),role))
            self.audit(db,actor,'create','users',uid,None,{'username':username.strip(),'role':role})
            db.commit()
            return {'id':uid,'username':username.strip(),'role':role,'active':True}
        except sqlite3.IntegrityError:
            raise Problem('username_exists',409)
        finally: db.close()

    def create_initial_admin(self, username, password):
        # First-run creation is atomic. Never reset or replace an existing account.
        if not isinstance(username,str) or not 1<=len(username.strip())<=80 or not isinstance(password,str) or not 12<=len(password)<=512:raise Problem('invalid_user')
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT COUNT(*) FROM users').fetchone()[0]:raise Problem('already_initialized',409)
            uid=str(uuid.uuid4())
            db.execute('INSERT INTO users(id,username,hash,role) VALUES(?,?,?,?)',(uid,username.strip(),password_hash(password),'admin'))
            self.audit(db,'desktop-first-run','create','users',uid,None,{'username':username.strip(),'role':'admin'})
            db.commit()
            return {'id':uid,'username':username.strip(),'role':'admin'}
        finally:db.close()

    def audit(self, db, user, action, kind, rid, before, after):
        db.execute('INSERT INTO audit(timestamp,user_id,action,kind,record_id,before_value,after_value) VALUES(?,?,?,?,?,?,?)',(now(),user,action,kind,rid,encode(before) if before is not None else None,encode(after) if after is not None else None))

    def require(self, user, admin=False):
        if not user: raise Problem('login_required',401)
        if user['role']=='viewer' or (admin and user['role']!='admin'): raise Problem('forbidden',403)

    def validate(self, kind, d, data, user):
        def text(key, required=False):
            v=d.get(key,'')
            if not isinstance(v,str) or len(v)>2000 or (required and not v.strip()): raise Invalid('invalid_text')
            d[key]=v.strip()
        def lookup(k, rid):
            found=next((x for x in data[k] if x['id']==rid),None)
            if not found: raise Invalid('missing_reference')
            return found
        def qty(key, positive=False, integer=False, default=None):
            d[key]=number(d.get(key,default),positive,integer)
            return d[key]
        def batch(key='batch_id', datekey='date'):
            b=lookup('batches',d.get(key))
            if day(d[datekey])<day(b['entry_date']): raise Invalid('before_entry')
            if b.get('legacy_group') and kind=='movements' and d[datekey]<=b['legacy_group']['as_of']:
                if not (kind=='movements' and d.get('type')=='adjustment' and d[datekey]==b['legacy_group']['as_of'] and user['role']=='admin'):raise Invalid('legacy_period_locked')
            if b['status']=='ended' and user['role']!='admin': raise Problem('batch_ended',403)
            return b
        d={k:v for k,v in d.items() if k not in ('id','revision','created_at','created_by','updated_at','deleted')}
        allowed={
            'barns':{'name','group'},
            'batches':{'barn_id','name','group','entry_date','entry_count','entry_age_days','age_date','status','cohort_id','legacy_source','legacy_row','legacy_barn','note'},
            'movements':{'date','batch_id','type','quantity','note','target_batch_id','total_weight_kg'},
            'deliveries':{'date','kg','display_unit','vendor','item','note','allocations'},
            'usages':{'start','end','batch_id','method','kg','opening','closing','transfer_in','transfer_out','loss','note','active','vendor','item'},
            'weights':{'date','batch_id','age_days','pen','count','total_kg','individual_kg','sampling','note','representative'},
            'workbooks':{'filename','base64','counts_text','counts_as_of','closed_barns','source_url','sha256','report','plan'},
        }[kind]
        d={k:v for k,v in d.items() if k in allowed}
        if kind=='barns':
            text('name',True); text('group')
            if any(x['name']==d['name'] for x in data['barns']): raise Invalid('duplicate_barn')
        elif kind=='batches':
            lookup('barns',d.get('barn_id'));text('name',True);text('group')
            day(d.get('entry_date'))
            if d.get('legacy_source'):
                book=lookup('workbooks',d['legacy_source'])
                source=next((r for r in book['report']['rows'] if r['key']==d.get('legacy_row')),None)
                if not source or d.get('legacy_barn') not in source['barns']:raise Invalid('missing_reference')
                if d.get('entry_count') is not None:
                    if len(source['barns'])!=1 or d['entry_count']!=source['totals']['entry']:raise Invalid('legacy_entry_unknown')
                if d['entry_date']!=source['entry_date']:raise Invalid('legacy_source_conflict')
                text('note')
            else:
                qty('entry_count',False,True)
                if d['entry_count']<0: raise Invalid('invalid_number')
            if d.get('entry_age_days') is not None:
                qty('entry_age_days')
                if d['entry_age_days']<0: raise Invalid('invalid_number')
            else: d['entry_age_days']=None
            d['age_date']=d.get('age_date') or d['entry_date'];day(d['age_date'])
            if d.get('status') not in ('active','ended'): raise Invalid('invalid_status')
            if any(x['barn_id']==d['barn_id'] and x['name']==d['name'] for x in data['batches']): raise Invalid('duplicate_batch')
            # Transfer destination is a separate zero-entry batch tied to the source cohort.
            if d.get('cohort_id') and not d.get('legacy_source'):
                sources=[x for x in data['batches'] if (x.get('cohort_id') or x['id'])==d['cohort_id'] or x['id']==d['cohort_id']]
                if not sources or d['entry_count']!=0: raise Invalid('invalid_transfer_batch')
                source=sources[0]
                if d['entry_age_days'] is None:
                    d.update(entry_age_days=source['entry_age_days'],age_date=source['age_date'])
            elif not d.get('legacy_source'): d['cohort_id']=None
        elif kind=='movements':
            day(d.get('date'));b=batch();text('note')
            k=d.get('type')
            if k not in ('sale','death','cull','arrival','transfer','adjustment'): raise Invalid('invalid_type')
            qty('quantity',k!='adjustment',True)
            if not d['quantity']: raise Invalid('invalid_number')
            if k=='adjustment': self.require(user,True)
            if d.get('total_weight_kg') is not None: qty('total_weight_kg',True)
            if k=='transfer':
                target=batch('target_batch_id')
                if b['id']==target['id'] or (b.get('cohort_id') or b['id'])!=(target.get('cohort_id') or target['id']): raise Invalid('transfer_cohort_mismatch')
            else: d.pop('target_batch_id',None)
        elif kind=='deliveries':
            day(d.get('date'));qty('kg',True);text('item');text('note')
            if d.get('display_unit') not in ('kg','ton'):raise Invalid('invalid_unit')
            if d.get('vendor') not in ('','養全','新農科'):raise Invalid('invalid_vendor')
            allocations=d.get('allocations',[])
            if not isinstance(allocations,list) or len(allocations)>500:raise Invalid('invalid_allocations')
            seen=set()
            for a in allocations:
                if not isinstance(a,dict):raise Invalid('invalid_allocations')
                b=lookup('batches',a.get('batch_id'))
                if b['entry_date']>d['date']:raise Invalid('before_entry')
                if b['status']=='ended' and user['role']!='admin':raise Problem('batch_ended',403)
                a['kg']=number(a.get('kg'),True)
                if b['id'] in seen:raise Invalid('duplicate_allocation')
                seen.add(b['id'])
            if allocations and abs(sum(a['kg'] for a in allocations)-d['kg'])>1e-7:raise Invalid('allocation_total_mismatch')
            d['allocations']=[{'batch_id':a['batch_id'],'kg':a['kg']} for a in allocations]
        elif kind=='usages':
            day(d.get('start'));day(d.get('end'));batch(datekey='start');text('note');text('item')
            d['vendor']=d.get('vendor','')
            if d['vendor'] not in ('','養全','新農科'):raise Invalid('invalid_vendor')
            if d['end']<=d['start']:raise Invalid('invalid_period')
            if not isinstance(d.get('active',True),bool):raise Invalid('invalid_status')
            d['active']=d.get('active',True)
            if d.get('method')=='direct':
                if qty('kg')<0:raise Invalid('invalid_number')
            elif d.get('method')=='inventory':
                for k in ('opening','closing','transfer_in','transfer_out','loss'):
                    if qty(k,default=0)<0:raise Invalid('invalid_number')
                d.pop('kg',None)
            else:raise Invalid('invalid_method')
            overlap=[u['id'] for u in data['usages'] if d['active'] and u['active'] and u['batch_id']==d['batch_id'] and u['start']<d['end'] and u['end']>d['start']]
            if overlap:raise Problem('overlapping_usage',409,overlap)
        elif kind=='weights':
            day(d.get('date'));b=batch();text('pen');text('sampling');text('note')
            values=d.get('individual_kg')
            if values:
                if not isinstance(values,list) or len(values)>20000:raise Invalid('invalid_weights')
                values=[number(x,True) for x in values]
                d.update(individual_kg=values,count=len(values),total_kg=sum(values))
            else:qty('count',True,True);qty('total_kg',True);d['individual_kg']=[]
            if d.get('age_days') is None:d['age_days']=age(b,d['date'])
            elif qty('age_days')<0:raise Invalid('invalid_number')
            if not isinstance(d.get('representative',False),bool):raise Invalid('invalid_status')
            d['representative']=d.get('representative',False)
        elif kind=='workbooks':
            from .legacy import unpack,review,reconcile,parse_counts
            text('filename',True);text('source_url')
            raw=unpack(d.get('base64'));report=review(raw)
            closed=d.get('closed_barns',[])
            if not isinstance(closed,list) or any(isinstance(n,bool) or not isinstance(n,int) for n in closed):raise Invalid('invalid_counts')
            plan=reconcile(report,parse_counts(d.get('counts_text')),d.get('counts_as_of'),closed)
            if any(x['issue']=='large_adjustment' for x in plan['issues']):raise Invalid('large_allocation_adjustment')
            d.update(sha256=report['source_sha256'],report=report,plan=plan,closed_barns=closed)
        return d

    def validate_global(self, data):
        data={kind:[dict(r) for r in rows] for kind,rows in data.items()}
        self.enrich_legacy(data)
        bid={b['id']:b for b in data['batches']}
        barns={b['id'] for b in data['barns']}
        for b in data['batches']:
            if b['barn_id'] not in barns:raise Invalid('referenced_record')
        for kind in ('movements','weights','usages'):
            for r in data[kind]:
                if r['batch_id'] not in bid:raise Invalid('referenced_record')
                dates=[r['start']] if kind=='usages' else [r['date']]
                if any(d<bid[r['batch_id']]['entry_date'] for d in dates):raise Invalid('before_entry')
                if r.get('target_batch_id'):
                    if r['target_batch_id'] not in bid:raise Invalid('referenced_record')
                    if r['date']<bid[r['target_batch_id']]['entry_date']:raise Invalid('before_entry')
                    source,target=bid[r['batch_id']],bid[r['target_batch_id']]
                    if (source.get('cohort_id') or source['id'])!=(target.get('cohort_id') or target['id']):raise Invalid('transfer_cohort_mismatch')
        for d in data['deliveries']:
            for a in d['allocations']:
                if a['batch_id'] not in bid:raise Invalid('referenced_record')
                if d['date']<bid[a['batch_id']]['entry_date']:raise Invalid('before_entry')
        # Daily deltas allow retroactive validation in O(records log records),
        # rather than rescanning the entire farm for each batch and date.
        deltas={b['id']:{(b['legacy_group']['as_of'] if b.get('legacy_group') else b['entry_date']):(b['legacy_heads'][b['legacy_group']['as_of']] if b.get('legacy_group') else b['entry_count'])} for b in data['batches']}
        def apply(batch_id, date, change):
            dates=deltas[batch_id];dates[date]=dates.get(date,0)+change
        for m in data['movements']:
            if bid[m['batch_id']].get('legacy_group') and m['date']<=bid[m['batch_id']]['legacy_group']['as_of']:
                if m['type']!='adjustment' or m['date']!=bid[m['batch_id']]['legacy_group']['as_of']:raise Invalid('legacy_period_locked')
            change=m['quantity'] if m['type'] in ('arrival','adjustment') else -m['quantity']
            apply(m['batch_id'],m['date'],change)
            if m['type']=='transfer':apply(m['target_batch_id'],m['date'],m['quantity'])
        for changes in deltas.values():
            balance=0
            for date in sorted(changes):
                balance+=changes[date]
                if balance<0:raise Invalid('insufficient_heads')
        for book in data['workbooks']:
            for row in book['report']['rows']:
                members=[b for b in data['batches'] if b.get('legacy_source')==book['id'] and b.get('legacy_row')==row['key']]
                if len(members)!=len(row['barns']) or {b['legacy_barn'] for b in members}!=set(row['barns']):raise Invalid('legacy_source_conflict')
        active_by_batch={}
        for u in data['usages']:
            if u['active']:active_by_batch.setdefault(u['batch_id'],[]).append(u)
        for rows in active_by_batch.values():
            rows.sort(key=lambda u:u['start'])
            if any(a['end']>b['start'] for a,b in zip(rows,rows[1:])):raise Invalid('overlapping_usage')

    def mutate(self, user, kind, payload, request_key, rid=None, delete=False):
        self.require(user,admin=kind in ('barns','batches','workbooks') or rid is not None)
        if kind not in KINDS:raise Problem('unknown_kind',404)
        if kind=='workbooks':raise Problem('legacy_source_readonly',403)
        if not isinstance(payload,dict) or not isinstance(request_key,str) or not 16<=len(request_key)<=128:raise Problem('idempotency_required')
        fingerprint=hashlib.sha256(encode([kind,rid,delete,payload]).encode()).hexdigest()
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT * FROM requests WHERE user_id=? AND key=?',(user['id'],request_key)).fetchone()
            if prior:
                if prior['fingerprint']!=fingerprint:raise Problem('idempotency_mismatch',409)
                return json.loads(prior['result'])
            data=self.snapshot(db)
            previous=None
            if rid:
                previous=next((r for r in data[kind] if r['id']==rid),None)
                if not previous:raise Problem('not_found',404)
                if payload.get('revision')!=previous['revision']:raise Problem('revision_conflict',409,previous)
                data[kind]=[r for r in data[kind] if r['id']!=rid]
            rid=rid or str(uuid.uuid4())
            if delete:
                output={'id':rid,'deleted':True,'revision':previous['revision']+1}
                tombstone=previous|{'revision':output['revision'],'updated_at':now()}
                db.execute('UPDATE records SET deleted=1,revision=revision+1,data=? WHERE id=?',(encode(tombstone),rid))
            else:
                cleaned=self.validate(kind,payload,data,user)
                output=cleaned|{'id':rid,'revision':previous['revision']+1 if previous else 1,'created_at':previous.get('created_at',now()) if previous else now(),'created_by':previous.get('created_by',user['id']) if previous else user['id'],'updated_at':now()}
                data[kind].append(output)
                db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,data=excluded.data',(kind,rid,output['revision'],encode(output)))
            self.validate_global(data)
            self.audit(db,user['id'],'delete' if delete else 'update' if previous else 'create',kind,rid,previous,output)
            db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],request_key,fingerprint,encode(output)))
            db.commit()
            return output
        except Invalid as e:raise Problem(str(e))
        finally:db.close()

    def import_workbook(self,user,payload,request_key):
        self.require(user,True)
        if not isinstance(payload,dict) or not isinstance(request_key,str) or not 16<=len(request_key)<=128:raise Problem('idempotency_required')
        cleaned=self.validate('workbooks',dict(payload),self.snapshot(),user)
        fingerprint=hashlib.sha256(encode(['workbook',payload]).encode()).hexdigest()
        # Back up before any account/record mutation, including legacy ingestion.
        self.backup_sqlite(label='before-workbook-import')
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT * FROM requests WHERE user_id=? AND key=?',(user['id'],request_key)).fetchone()
            if prior:
                if prior['fingerprint']!=fingerprint:raise Problem('idempotency_mismatch',409)
                return json.loads(prior['result'])
            data=self.snapshot(db)
            existing=next((book for book in data['workbooks'] if book['sha256']==cleaned['sha256']),None)
            if existing:
                result={'book_id':existing['id'],'already_imported':True,'barns_added':0,'batches_added':0}
            else:
                book_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'pigledger-workbook:'+cleaned['sha256']))
                def insert(kind,content,rid=None):
                    output=content|{'id':rid or str(uuid.uuid4()),'revision':1,'created_at':now(),'created_by':user['id'],'updated_at':now()}
                    db.execute('INSERT INTO records(kind,id,revision,deleted,data) VALUES(?,?,1,0,?)',(kind,output['id'],encode(output)))
                    self.audit(db,user['id'],'import-workbook',kind,output['id'],None,output if kind!='workbooks' else {'sha256':cleaned['sha256'],'filename':cleaned['filename']})
                    data[kind].append(output);return output
                insert('workbooks',cleaned,book_id);barns_added=batches_added=0
                for row in cleaned['report']['rows']:
                    plan=next(p for p in cleaned['plan']['rows'] if p['key']==row['key']);cohort_id=None
                    for barn_number in row['barns']:
                        barn=next((b for b in data['barns'] if re_barn_number(b['name'])==barn_number),None)
                        if not barn:
                            barn=insert('barns',{'name':str(barn_number)+'棟','group':''});barns_added+=1
                        if any(b['barn_id']==barn['id'] and b['name']==row['name'] for b in data['batches']):raise Problem('legacy_source_conflict',409)
                        head=plan['current'].get(str(barn_number),plan['current'].get(barn_number))
                        batch={'barn_id':barn['id'],'name':row['name'],'group':row['name'],'entry_date':row['entry_date'],'entry_count':row['totals']['entry'] if len(row['barns'])==1 else None,'entry_age_days':row['entry_age_days'],'age_date':row['entry_date'],'status':'ended' if head==0 else 'active','cohort_id':cohort_id,'legacy_source':book_id,'legacy_row':row['key'],'legacy_barn':barn_number,'note':'來源表合併名稱；分棟數為暫定核對分配。首次進場計齡，原始明細、公式與備註保存在 Excel 來源。'}
                        created=insert('batches',self.validate('batches',batch,data,user));cohort_id=cohort_id or created['id'];batches_added+=1
                self.validate_global(self.snapshot(db))
                result={'book_id':book_id,'already_imported':False,'barns_added':barns_added,'batches_added':batches_added}
            db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],request_key,fingerprint,encode(result)));db.commit();return result
        finally:db.close()

    def export_backup(self):
        self.backup_sqlite(label='export')
        db=self.connect()
        try:
            db.execute('BEGIN')
            return {'format':'pigledger-backup','schema':3,'version':VERSION,'exported_at':now(),'records':[dict(r) for r in db.execute('SELECT * FROM records')],'users':[dict(r) for r in db.execute('SELECT * FROM users')],'audit':[dict(r) for r in db.execute('SELECT * FROM audit ORDER BY seq')]}
        finally:db.close()

    def import_backup(self, user, document):
        self.require(user,True)
        if not isinstance(document,dict) or document.get('format')!='pigledger-backup' or document.get('schema') not in (1,2,3):raise Problem('invalid_backup')
        self.backup_sqlite(label='before-import')
        db=self.connect()
        added=skipped=0
        try:
            db.execute('BEGIN IMMEDIATE')
            for r in document.get('records',[]):
                if str(uuid.UUID(r['id']))!=r['id']:raise Problem('invalid_backup')
                if r['kind'] not in KINDS or not isinstance(r['revision'],int) or r['revision']<1 or r['deleted'] not in (0,1):raise Problem('invalid_backup')
                parsed=json.loads(r['data'])
                if parsed.get('id')!=r['id'] or parsed.get('revision')!=r['revision']:raise Problem('invalid_backup')
                existing=db.execute('SELECT * FROM records WHERE id=?',(r['id'],)).fetchone()
                if existing:
                    if existing['kind']!=r['kind']:raise Problem('backup_conflict',409,r['id'])
                    if existing['revision']==r['revision'] and (existing['data']!=r['data'] or existing['deleted']!=r['deleted']):raise Problem('backup_conflict',409,r['id'])
                    # Never overwrite current edits or resurrect tombstones. Review as a separate correction.
                    if r['revision']>existing['revision']:raise Problem('backup_conflict',409,r['id'])
                    skipped+=1;continue
                # Imported schemas go through the same server validation; references checked after all rows load.
                db.execute('INSERT INTO records(kind,id,revision,deleted,data) VALUES(?,?,?,?,?)',(r['kind'],r['id'],r['revision'],r['deleted'],r['data']))
                added+=1
            data=self.snapshot(db)
            for kind in KINDS:
                for r in data[kind]:
                    others={k:[x for x in rows if not (k==kind and x['id']==r['id'])] for k,rows in data.items()}
                    cleaned=self.validate(kind,r,others,user)
                    if any((r.get(k, '') if k in ('vendor','item') else r.get(k))!=v for k,v in cleaned.items()):raise Problem('invalid_backup')
            self.validate_global(data)
            for u in document.get('users',[]):
                if str(uuid.UUID(u['id']))!=u['id']:raise Problem('invalid_backup')
                if u['role'] not in ('admin','staff','viewer') or u['active'] not in (0,1):raise Problem('invalid_backup')
                parts=u['hash'].split(':')
                if len(parts)!=2 or len(bytes.fromhex(parts[0]))!=16 or len(bytes.fromhex(parts[1]))!=64:raise Problem('invalid_backup')
                current=db.execute('SELECT * FROM users WHERE id=? OR username=?',(u['id'],u['username'])).fetchone()
                if current:
                    if current['id']!=u['id']:raise Problem('backup_conflict',409,u['username'])
                else:db.execute('INSERT INTO users(id,username,hash,role,active,revision) VALUES(?,?,?,?,?,?)',(u['id'],u['username'],u['hash'],u['role'],u['active'],u.get('revision',1)))
            # Audit events from the backup are deduplicated by their complete canonical content.
            seen={encode({k:r[k] for k in ('timestamp','user_id','action','kind','record_id','before_value','after_value')}) for r in db.execute('SELECT * FROM audit')}
            for a in document.get('audit',[]):
                item={k:a[k] for k in ('timestamp','user_id','action','kind','record_id','before_value','after_value')}
                if encode(item) not in seen:
                    db.execute('INSERT INTO audit(timestamp,user_id,action,kind,record_id,before_value,after_value) VALUES(?,?,?,?,?,?,?)',tuple(item.values()));seen.add(encode(item))
            self.audit(db,user['id'],'import','backup','',None,{'added':added,'skipped':skipped})
            db.commit()
            return {'added':added,'skipped':skipped}
        except (Invalid,KeyError,ValueError,TypeError,sqlite3.IntegrityError) as e:raise Problem('invalid_backup',400,str(e))
        finally:db.close()
