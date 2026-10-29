import sqlite3, json, uuid, hashlib, secrets, hmac, os, re
from pathlib import Path
from datetime import datetime, timezone
from .domain import Invalid, day, number, herd, consumption, age
from .notification_schema import PUSH_SCHEMA

VERSION='2.0.66'
SCHEMA_VERSION=4
KINDS=('barns','batches','movements','feed_orders','deliveries','usages','weights','workbooks','source_voids','daily_checks','feed_bins','work_tasks','feed_drafts')
SCHEMA='''
CREATE TABLE IF NOT EXISTS records(kind TEXT NOT NULL, id TEXT PRIMARY KEY, revision INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS records_kind ON records(kind,deleted);
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','staff','viewer')), active INTEGER NOT NULL DEFAULT 1, revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS requests(user_id TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(user_id,key));
CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, user_id TEXT NOT NULL, action TEXT NOT NULL, kind TEXT NOT NULL, record_id TEXT NOT NULL, before_value TEXT, after_value TEXT);
CREATE TABLE IF NOT EXISTS account_security(user_id TEXT PRIMARY KEY REFERENCES users(id),must_change INTEGER NOT NULL DEFAULT 0,setup_hash TEXT,setup_expires REAL);
'''+PUSH_SCHEMA

class Problem(Exception):
    def __init__(self, code, status=400, details=None):
        self.code, self.status, self.details = code, status, details


def validate_password(value):
    # Keep strings intact: leading zeroes are part of the password.
    if not isinstance(value,str) or re.fullmatch(r'[0-9]{4,8}',value) is None:
        raise Problem('invalid_password_policy')
    return value


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
        if version > SCHEMA_VERSION:
            db.close()
            raise RuntimeError('Database schema is newer than this application')
        if existed and version < SCHEMA_VERSION:
            self.backup_sqlite(db, 'before-migration')
        db.executescript(SCHEMA)
        if 'revision' not in {r['name'] for r in db.execute('PRAGMA table_info(users)')}:
            db.execute('ALTER TABLE users ADD COLUMN revision INTEGER NOT NULL DEFAULT 1')
        db.execute('PRAGMA user_version='+str(SCHEMA_VERSION));db.commit()
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

    def snapshot(self, db=None, include_source=True):
        owned=db is None
        db=db or self.connect()
        data={k:[] for k in KINDS}
        column='data' if include_source else "CASE WHEN kind='workbooks' THEN json_remove(data,'$.base64') ELSE data END AS data"
        for r in db.execute('SELECT kind,id,revision,'+column+' FROM records WHERE deleted=0 ORDER BY rowid'):
            if r['kind'] not in data: raise RuntimeError('Unknown entity in database')
            data[r['kind']].append(json.loads(r['data']) | {'id':r['id'],'revision':r['revision']})
        self.enrich_legacy(data)
        if owned: db.close()
        return data

    def enrich_legacy(self,data):
        books={book['id']:book for book in data['workbooks']}
        for b in data['batches']:
            if not b.get('legacy_source'):b.pop('_cohort_key',None)
        for b in data['batches']:
            if not b.get('legacy_source'):continue
            book=books.get(b['legacy_source'])
            if not book:continue
            row=next((r for r in book['report']['rows'] if r['key']==b['legacy_row']),None)
            plan=next((p for p in book['plan']['rows'] if p['key']==b['legacy_row']),None)
            if not row or not plan:continue
            b['_cohort_key']=row['name']+'|'+row['entry_date']
            members=[x['id'] for x in data['batches'] if x.get('legacy_source')==book['id'] and x.get('legacy_row')==row['key']]
            b['legacy_group']={'id':book['id']+':'+row['key'],'members':members,'expected_members':len(row['barns']),'snapshots':json.loads(encode(plan['snapshots'])),'as_of':book['report']['as_of']}
            b['legacy_heads']={book['report']['as_of']:plan['current'].get(str(b['legacy_barn']),plan['current'].get(b['legacy_barn']))}
            if book['plan']['counts_as_of']!=book['report']['as_of']:
                b['legacy_heads'][book['plan']['counts_as_of']]=plan['before'].get(str(b['legacy_barn']),plan['before'].get(b['legacy_barn']))
            # A single-barn entry correction changes the original entry stock,
            # not an arrival/adjustment event. Rebuild from immutable source on
            # every read so repeated enrichment/import cannot apply it twice.
            if len(row['barns'])==1 and b.get('entry_count') is not None:
                delta=b['entry_count']-row['totals']['entry']
                b['legacy_entry_original']=row['totals']['entry']
                for snapshot in b['legacy_group']['snapshots'].values():
                    snapshot['entry']+=delta;snapshot['remaining']+=delta
                b['legacy_heads']={on:heads+delta if heads is not None else None for on,heads in b['legacy_heads'].items()}
            b['legacy_values']={}
            from .source_assignment import reviewed_events
            value_events=reviewed_events(book,row,data) if any(x.get('source_assignments') for x in data['batches']) else row['events']
            for snapshot_date in plan['snapshots']:
                values={'entry':b['entry_count']}
                for field,typ in [('sold','sale'),('culled','cull'),('dead','death')]:
                    all_events=[e for e in value_events if e['type']==typ]
                    dated=[e for e in all_events if e['date']<=snapshot_date]
                    complete=sum(e['quantity'] for e in all_events)==row['totals'][field] and all(sum(a['quantity'] for a in e['allocations'])==e['quantity'] for e in dated)
                    values[field]=sum(a['quantity'] for e in dated for a in e['allocations'] if a['barn']==b['legacy_barn']) if complete else None
                b['legacy_values'][snapshot_date]=values
        # Explicit grouping is separate from physical entry dates and transfers.
        batches={b['id']:b for b in data['batches']}
        def resolve(b,seen):
            if b['id'] in seen:raise Invalid('cohort_link_cycle')
            target=b.get('same_batch_as')
            if not target:return b.get('_cohort_key') or b['name']+'|'+b['entry_date']
            if b.get('legacy_source'):raise Invalid('legacy_source_conflict')
            if target not in batches:raise Invalid('referenced_record')
            key=resolve(batches[target],seen|{b['id']});b['_cohort_key']=key;return key
        for b in data['batches']:resolve(b,set())
        from .source_dates import adjust_snapshots
        adjust_snapshots(data)
        from .source_edit import adjust_snapshots as adjust_edits
        adjust_edits(data)
        from .source_assignment import rebuild_confirmed_stock
        rebuild_confirmed_stock(data)
        from .operations import apply_source_voids
        apply_source_voids(data)
        from .history import derived_movements
        data['movements']=[m for m in data['movements'] if not m.get('_source_derived')]+derived_movements(data)

    def create_user(self, username, password, role='admin', actor='bootstrap', must_change=False):
        if role not in ('admin','staff','viewer') or not isinstance(username,str) or not 1<=len(username.strip())<=80:
            raise Problem('invalid_user')
        validate_password(password)
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            uid=str(uuid.uuid4())
            db.execute('INSERT INTO users(id,username,hash,role) VALUES(?,?,?,?)',(uid,username.strip(),password_hash(password),role))
            if must_change:db.execute('INSERT INTO account_security(user_id,must_change) VALUES(?,1)',(uid,))
            self.audit(db,actor,'create','users',uid,None,{'username':username.strip(),'role':role})
            db.commit()
            return {'id':uid,'username':username.strip(),'role':role,'active':True}
        except sqlite3.IntegrityError:
            raise Problem('username_exists',409)
        finally: db.close()

    def create_initial_admin(self, username, password):
        # First-run creation is atomic. Never reset or replace an existing account.
        if not isinstance(username,str) or not 1<=len(username.strip())<=80:raise Problem('invalid_user')
        validate_password(password)
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

    def validate(self, kind, d, data, user, previous=None, *, quick=False):
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
            if kind=='movements' and d.get('type') in ('sale','death','cull','transfer') and herd(data['batches'],data['movements'],d[datekey],[b['id']])['remaining'] is None:raise Invalid('heads_unknown')
            return b
        original_id=d.get('id')
        d={k:v for k,v in d.items() if k not in ('id','revision','created_at','created_by','updated_at','deleted')}
        allowed={
            'barns':{'name','group','feed_vendor'},
            'feed_drafts':{'title','source','sources','rows','status','confirmed_ids','confirmed_at','confirmed_by','cancelled_at','cancelled_by'},
            'work_tasks':{'title','mode','weekday','date','start_date','end_date','time','note','active'},
            'batches':{'barn_id','name','group','entry_date','entry_date_override','entry_count','entry_age_days','age_date','status','cohort_id','same_batch_as','legacy_source','legacy_row','legacy_barn','note','entry_mean_kg','entry_mean_date','entry_mean_source','entry_mean_note','entry_count_source','entry_count_reason','source_assignments','stock_basis','quality_review','weekly_start_date','report_entry_lots','report_entry_lots_source'},
            'movements':{'date','batch_id','type','quantity','note','target_batch_id','total_weight_kg','outgoing_destination','outgoing_trip','quick_source'},
            'feed_orders':{'date','kg','display_unit','vendor','item','note','allocations','feed_bin_id','feed_bin_snapshot','target_batch_ids','bin_allocations','requested_barn_id','quick_source'},
            'feed_bins':{'name','barn_ids','vendor','active','note','capacity_kg','safe_fill_percent','inventory_enabled','inventory_date','inventory_opening_kg'},
            'deliveries':{'date','kg','display_unit','vendor','item','note','allocations','feed_bin_id','feed_bin_snapshot','target_batch_ids','requested_barn_id','quick_source'},
            'usages':{'start','end','batch_id','method','kg','opening','closing','transfer_in','transfer_out','loss','note','active','vendor','item','feed_bin_id'},
            'weights':{'date','batch_id','age_days','pen','count','total_kg','individual_kg','sampling','note','representative','section','session_id','session_number','session_fingerprint'},
            'daily_checks':{'date','batch_id','status','note'},
            'source_voids':{'target_kind','source_row_id','source_record','reason'},
            'workbooks':{'filename','base64','counts_text','counts_as_of','closed_barns','source_url','sha256','report','plan','review_decisions','source_date_reviews','source_movement_edits'},
        }[kind]
        d={k:v for k,v in d.items() if k in allowed}
        if kind in ('deliveries','feed_orders','movements'):
            source=d.get('quick_source') or (previous or {}).get('quick_source')
            if source:
                if not quick and (not previous or source!=previous.get('quick_source')):raise Problem('invalid_quick_source')
                from .quick_record import validate_source
                source=validate_source(source)
                if not quick and previous:
                    if kind=='movements':source['barn_id']=lookup('batches',d.get('batch_id'))['barn_id']
                    elif kind=='feed_orders' and d.get('feed_bin_id'):
                        bin=lookup('feed_bins',d['feed_bin_id']);requested=d.get('requested_barn_id') or previous.get('requested_barn_id') or source['barn_id']
                        if requested not in bin['barn_ids']:
                            if len(bin['barn_ids'])!=1:raise Problem('quick_review_required',409)
                            requested=bin['barn_ids'][0]
                        source['barn_id']=requested;d['requested_barn_id']=requested
                d['quick_source']=source
        if kind=='feed_drafts':
            from .feed_drafts import validate_draft
            d=validate_draft(d)
        elif kind=='work_tasks':
            from .work_calendar import validate_task
            d=validate_task(d)
        elif kind=='barns':
            text('name',True); text('group')
            if 'feed_vendor' in d and d['feed_vendor'] not in ('','養全','新農科'):raise Invalid('invalid_vendor')
            if any(x['name']==d['name'] for x in data['barns']): raise Invalid('duplicate_barn')
        elif kind=='feed_bins':
            text('name',True);text('note')
            if d.get('vendor') not in ('養全','新農科'):raise Invalid('invalid_vendor')
            ids=d.get('barn_ids')
            if not isinstance(ids,list) or not ids or len(ids)>100 or any(not isinstance(x,str) for x in ids) or len(ids)!=len(set(ids)):raise Invalid('invalid_feed_bin')
            for rid in ids:lookup('barns',rid)
            if previous and previous['barn_ids']!=ids and any(u.get('feed_bin_id')==previous['id'] or not u.get('feed_bin_id') and lookup('batches',u['batch_id'])['barn_id'] in previous['barn_ids'] for u in data.get('usages',[])):raise Invalid('feed_bin_members_locked')
            if not isinstance(d.get('active',True),bool):raise Invalid('invalid_status')
            d['active']=d.get('active',True)
            if any(b['name']==d['name'] for b in data.get('feed_bins',[])):raise Invalid('duplicate_feed_bin')
            for field in ('capacity_kg','safe_fill_percent','inventory_enabled','inventory_date','inventory_opening_kg'):
                if field not in d and previous and field in previous:d[field]=previous[field]
            if 'capacity_kg' in d:
                d['capacity_kg']=None if d['capacity_kg'] in ('',None) else number(d['capacity_kg'],True)
            if 'safe_fill_percent' in d:
                qty('safe_fill_percent',True)
                if d['safe_fill_percent']>100:raise Invalid('invalid_bin_inventory')
            if 'inventory_enabled' in d and type(d['inventory_enabled']) is not bool:raise Invalid('invalid_bin_inventory')
            if d.get('inventory_enabled'):
                day(d.get('inventory_date'));qty('inventory_opening_kg')
                if not d.get('capacity_kg') or d['inventory_opening_kg']<0:raise Invalid('invalid_bin_inventory')
            elif 'inventory_date' in d and d['inventory_date']:day(d['inventory_date'])
            if 'inventory_opening_kg' in d and d['inventory_opening_kg'] is not None:
                qty('inventory_opening_kg')
                if d['inventory_opening_kg']<0:raise Invalid('invalid_bin_inventory')
        elif kind=='batches':
            lookup('barns',d.get('barn_id'));text('name',True);text('group')
            day(d.get('entry_date'))
            d['same_batch_as']=d.get('same_batch_as') or None
            if d['same_batch_as']:
                if d.get('legacy_source'):raise Invalid('legacy_source_conflict')
                target=lookup('batches',d['same_batch_as'])
                if target['barn_id']==d['barn_id']:raise Invalid('cohort_link_same_barn')
                if d['entry_date']<target['entry_date']:raise Invalid('cohort_link_earlier_entry')
            if d.get('legacy_source'):
                book=lookup('workbooks',d['legacy_source'])
                source=next((r for r in book['report']['rows'] if r['key']==d.get('legacy_row')),None)
                if not source or d.get('legacy_barn') not in source['barns']:raise Invalid('missing_reference')
                if len(source['barns'])==1 or d.get('entry_count') is not None:
                    qty('entry_count',False,True)
                    if d['entry_count']<0 or (len(source['barns'])>1 and d['entry_count']>source['totals']['entry']):raise Invalid('legacy_entry_unknown')
                    if len(source['barns'])>1 and not str(d.get('entry_count_source','')).strip():raise Invalid('entry_source_required')
                override=d.get('entry_date_override')
                if override is not None:
                    if not isinstance(override,dict) or set(override)!={'original_date','date','reason'} or override['original_date']!=source['entry_date'] or override['date']!=d['entry_date'] or not isinstance(override['reason'],str) or not 1<=len(override['reason'].strip())<=500:raise Invalid('legacy_source_conflict')
                    if day(override['date'])<day(override['original_date']):raise Invalid('legacy_source_conflict')
                    if not previous or override!=previous.get('entry_date_override'):self.require(user,True)
                if d['entry_date']!=source['entry_date'] and not override:raise Invalid('legacy_source_conflict')
                text('note')
            else:
                if d.get('entry_date_override') is not None:raise Invalid('legacy_source_conflict')
                qty('entry_count',False,True)
                if d['entry_count']<0: raise Invalid('invalid_number')
            if 'stock_basis' in d:
                basis=d['stock_basis']
                if not d.get('legacy_source') or not isinstance(basis,dict) or set(basis)!={'mode','reason'} or basis.get('mode')!='entry_minus_source_outflows' or not isinstance(basis.get('reason'),str) or not 1<=len(basis['reason'].strip())<=500:raise Invalid('invalid_stock_basis')
            if 'source_assignments' in d:
                from .source_assignment import validate_assignments
                validate_assignments(d['source_assignments'],d|{'id':previous['id'] if previous else original_id},data|{'batches':data['batches']+([previous] if previous else [])})
            text('entry_count_reason')
            if d.get('entry_age_days') is not None:
                qty('entry_age_days')
                if d['entry_age_days']<0: raise Invalid('invalid_number')
            else: d['entry_age_days']=None
            d['age_date']=d.get('age_date') or d['entry_date'];day(d['age_date'])
            if d.get('entry_mean_kg') is not None:
                qty('entry_mean_kg',True)
                d['entry_mean_date']=d.get('entry_mean_date') or d['entry_date'];day(d['entry_mean_date'])
                if d['entry_mean_date']<d['entry_date']:raise Invalid('before_entry')
            else:d['entry_mean_kg']=None;d['entry_mean_date']=None
            text('entry_mean_source');text('entry_mean_note');text('entry_count_source')
            if 'weekly_start_date' in d:
                d['weekly_start_date']=d.get('weekly_start_date') or ''
                if d['weekly_start_date']:
                    day(d['weekly_start_date'])
                    if d['weekly_start_date']<d['entry_date']:raise Invalid('before_entry')
            if 'report_entry_lots' in d or 'report_entry_lots_source' in d:
                lots=d.get('report_entry_lots',[])
                if not isinstance(lots,list) or len(lots)>12:raise Invalid('invalid_report_entry_lots')
                dates=set()
                for lot in lots:
                    if not isinstance(lot,dict) or set(lot)!={'date','count','mean_kg'}:raise Invalid('invalid_report_entry_lots')
                    day(lot['date'])
                    if lot['date']<d['entry_date'] or (lot['date'] in dates and not d.get('entry_date_override')):raise Invalid('invalid_report_entry_lots')
                    dates.add(lot['date']);lot['count']=number(lot['count'],True,True)
                    if lot['mean_kg'] is not None:lot['mean_kg']=number(lot['mean_kg'],True)
                if lots and (sum(lot['count'] for lot in lots)!=d['entry_count'] or min(dates)!=d['entry_date']):raise Invalid('report_entry_total_mismatch')
                text('report_entry_lots_source')
                if lots and not d['report_entry_lots_source']:raise Invalid('entry_source_required')
                d['report_entry_lots']=sorted(lots,key=lambda lot:lot['date'])
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
            if 'quality_review' in d:
                from .review import validate_quality_review
                validate_quality_review(d['quality_review'],d,data,previous)
        elif kind=='daily_checks':
            from .review import farm_today, death_state
            day(d.get('date'));b=batch();text('note')
            if d['date']>farm_today():raise Invalid('future_daily_check')
            if d.get('status') not in ('no_deaths','cancelled'):raise Invalid('invalid_status')
            if d['status']=='cancelled' and not d['note']:raise Invalid('check_reason_required')
            if d['status']=='no_deaths':
                if b.get('legacy_group') and d['date']<=b['legacy_group']['as_of']:raise Invalid('check_legacy_period')
                state=death_state(data,b,d['date'])
                if state['known'] or state['uncertain']:raise Invalid('daily_death_conflict')
            if any(r['batch_id']==d['batch_id'] and r['date']==d['date'] for r in data.get('daily_checks',[])):raise Problem('daily_check_exists',409)
        elif kind=='movements':
            day(d.get('date'));b=batch();text('note')
            k=d.get('type')
            if k not in ('sale','death','cull','arrival','transfer','adjustment'): raise Invalid('invalid_type')
            if 'outgoing_destination' in d:
                destination=d['outgoing_destination']
                if not isinstance(destination,str) or destination not in ('','新北','南投','嘉義'):raise Invalid('invalid_outgoing_destination')
                if destination and k not in ('sale','cull'):raise Invalid('outgoing_destination_type')
                if k not in ('sale','cull'):d.pop('outgoing_destination')
            if 'outgoing_trip' in d:
                trip=d['outgoing_trip']
                if not isinstance(trip,str) or len(trip)>80 or any(ord(c)<32 or ord(c)==127 for c in trip):raise Invalid('invalid_outgoing_trip')
                trip=trip.strip()
                if trip and k not in ('sale','cull'):raise Invalid('outgoing_trip_type')
                if k in ('sale','cull'):d['outgoing_trip']=trip
                else:d.pop('outgoing_trip')
            qty('quantity',k!='adjustment',True)
            if not d['quantity']: raise Invalid('invalid_number')
            if k=='adjustment': self.require(user,True)
            if d.get('total_weight_kg') is not None: qty('total_weight_kg',True)
            if k=='transfer':
                target=batch('target_batch_id')
                from .history import cohort_key
                linked=(b.get('same_batch_as') or target.get('same_batch_as')) and cohort_key(b)==cohort_key(target)
                if b['id']==target['id'] or ((b.get('cohort_id') or b['id'])!=(target.get('cohort_id') or target['id']) and not linked): raise Invalid('transfer_cohort_mismatch')
            else: d.pop('target_batch_id',None)
        elif kind in ('deliveries','feed_orders'):
            day(d.get('date'));qty('kg',True);text('item');text('note')
            if d.get('display_unit') not in ('kg','ton'):raise Invalid('invalid_unit')
            if kind=='deliveries' and not d.get('feed_bin_id') and previous and previous.get('feed_bin_id'):
                for field in ('feed_bin_id','feed_bin_snapshot','target_batch_ids','requested_barn_id'):
                    if field not in d and field in previous:d[field]=previous[field]
            if kind=='deliveries' and d.get('feed_bin_id'):
                bin=lookup('feed_bins',d['feed_bin_id'])
                if not bin['active'] and not (previous and previous.get('feed_bin_id')==bin['id']):raise Invalid('feed_bin_inactive')
                d['feed_bin_snapshot']=({'id':bin['id'],'name':bin['name'],'barn_ids':list(bin['barn_ids']),'barn_names':[lookup('barns',rid)['name'] for rid in bin['barn_ids']]})
                if previous and previous.get('feed_bin_id')==bin['id']:d['feed_bin_snapshot']=previous['feed_bin_snapshot']
                snap=d['feed_bin_snapshot']
                if not isinstance(snap,dict) or set(snap)!={'id','name','barn_ids','barn_names'} or snap['id']!=bin['id'] or snap['barn_ids']!=bin['barn_ids'] or not isinstance(snap['name'],str) or not snap['name'].strip() or len(snap['name'])>2000 or not isinstance(snap['barn_names'],list) or len(snap['barn_names'])!=len(bin['barn_ids']) or any(not isinstance(x,str) or len(x)>2000 for x in snap['barn_names']):raise Invalid('invalid_feed_bin')
                targets=d.get('target_batch_ids',[])
                if not isinstance(targets,list) or len(targets)!=len(set(targets)):raise Invalid('invalid_allocations')
                target_barns=set()
                for rid in targets:
                    b=lookup('batches',rid)
                    if b['barn_id'] not in bin['barn_ids'] or b['entry_date']>d['date'] or b['barn_id'] in target_barns:raise Invalid('invalid_allocations')
                    target_barns.add(b['barn_id'])
                d['target_batch_ids']=targets
                for a in d.get('allocations',[]):
                    if not isinstance(a,dict) or lookup('batches',a.get('batch_id'))['barn_id'] not in bin['barn_ids']:raise Invalid('invalid_allocations')
            if kind in ('feed_orders','deliveries') and d.get('requested_barn_id'):
                lookup('barns',d['requested_barn_id'])
                if not d.get('feed_bin_id') or d['requested_barn_id'] not in lookup('feed_bins',d['feed_bin_id'])['barn_ids']:raise Invalid('invalid_feed_bin')
            if kind=='feed_orders' and d.get('feed_bin_id'):
                from .feed import FEED_TYPES
                bin=lookup('feed_bins',d['feed_bin_id'])
                if not bin['active'] and not (previous and previous.get('feed_bin_id')==bin['id']):raise Invalid('feed_bin_inactive')
                if d['item'] and d['item'] not in FEED_TYPES:raise Invalid('invalid_feed_type')
                d['vendor']=d.get('vendor',bin['vendor'])
                if d.get('allocations'):raise Invalid('bin_allocation_conflict')
                if previous and previous.get('feed_bin_id')==bin['id']:
                    d['feed_bin_snapshot']=previous['feed_bin_snapshot']
                else:
                    d['feed_bin_snapshot']={'id':bin['id'],'name':bin['name'],'barn_ids':list(bin['barn_ids']),'barn_names':[lookup('barns',rid)['name'] for rid in bin['barn_ids']]}
                snap=d['feed_bin_snapshot']
                if not isinstance(snap,dict) or set(snap)!={'id','name','barn_ids','barn_names'} or snap['id']!=bin['id'] or snap['barn_ids']!=bin['barn_ids'] or not isinstance(snap['name'],str) or not snap['name'].strip() or len(snap['name'])>2000 or not isinstance(snap['barn_names'],list) or len(snap['barn_names'])!=len(bin['barn_ids']) or any(not isinstance(x,str) or len(x)>2000 for x in snap['barn_names']):raise Invalid('invalid_feed_bin')
                targets=d.get('target_batch_ids',[])
                if not isinstance(targets,list) or any(not isinstance(x,str) for x in targets) or len(targets)!=len(set(targets)):raise Invalid('invalid_allocations')
                seen_barns=set()
                for rid in targets:
                    b=lookup('batches',rid)
                    if b['barn_id'] not in d['feed_bin_snapshot']['barn_ids'] or b['barn_id'] in seen_barns:raise Invalid('invalid_allocations')
                    if b['status']=='ended' and user['role']!='admin':raise Problem('batch_ended',403)
                    seen_barns.add(b['barn_id'])
                d['target_batch_ids']=targets
                from .feed import validate_bin_allocations
                rows=d.get('bin_allocations',previous.get('bin_allocations',[]) if previous and previous.get('feed_bin_id')==bin['id'] else [])
                if rows or 'bin_allocations' in d:
                    d['bin_allocations']=validate_bin_allocations(rows,d['kg'],targets,snap['barn_ids'],{b['id']:b for b in data['batches']})
            elif kind=='feed_orders':
                for key in ('feed_bin_id','feed_bin_snapshot','target_batch_ids','bin_allocations'):d.pop(key,None)
            if d.get('vendor') not in ('','養全','新農科'):raise Invalid('invalid_vendor')
            allocations=d.get('allocations',[])
            if not isinstance(allocations,list) or len(allocations)>(1 if kind=='feed_orders' else 500):raise Invalid('invalid_allocations')
            seen=set()
            for a in allocations:
                if not isinstance(a,dict):raise Invalid('invalid_allocations')
                b=lookup('batches',a.get('batch_id'))
                if kind=='deliveries' and b['entry_date']>d['date']:raise Invalid('before_entry')
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
            if not d.get('feed_bin_id') and previous and previous.get('feed_bin_id'):d['feed_bin_id']=previous['feed_bin_id']
            if d.get('feed_bin_id'):
                bin=lookup('feed_bins',d['feed_bin_id']);b=lookup('batches',d['batch_id'])
                if b['barn_id'] not in bin['barn_ids']:raise Invalid('invalid_feed_bin')
            if d.get('method')=='direct':
                if qty('kg')<0:raise Invalid('invalid_number')
            elif d.get('method')=='inventory':
                for k in ('opening','closing','transfer_in','transfer_out','loss'):
                    if qty(k,default=0)<0:raise Invalid('invalid_number')
                d.pop('kg',None)
            else:raise Invalid('invalid_method')
            overlap=[u['id'] for u in data['usages'] if d['active'] and u['active'] and u['batch_id']==d['batch_id'] and u['start']<d['end'] and u['end']>d['start']]
            if overlap:raise Problem('overlapping_usage',409,overlap)
        elif kind=='source_voids':
            if user['role']!='admin' or d.get('target_kind') not in ('weights','movements') or not isinstance(d.get('source_record'),dict) or d['source_record'].get('id')!=d.get('source_row_id') or not isinstance(d.get('reason'),str) or not d['reason'].strip():raise Invalid('invalid_backup')
        elif kind=='weights':
            text('section')
            if d['section'] not in ('','head','middle','tail'):raise Invalid('invalid_weighing')
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
            from .history import update_preview
            text('filename',True);text('source_url')
            raw=unpack(d.get('base64'));report=review(raw)
            update=update_preview(report,data)
            if update:
                decisions=d.get('review_decisions',{})
                if not isinstance(decisions,dict) or any(key not in {r['cohort'] for r in update['pending_cohorts']} or value!='keep_app' for key,value in decisions.items()):raise Invalid('invalid_workbook')
                for row in update['pending_cohorts']:row['decision']=decisions.get(row['cohort'])
                original=next(b for b in data['workbooks'] if b['id']==update['base_book_id'])
                d.update(sha256=report['source_sha256'],report=report,plan=original['plan'],
                    base_book_id=update['base_book_id'],approved_cohorts=update['approved_cohorts'],
                    matched_events=update['matched_events'],pending_cohorts=update['pending_cohorts'],update_summary=update)
                return d
            closed=d.get('closed_barns',[])
            if not isinstance(closed,list) or any(isinstance(n,bool) or not isinstance(n,int) for n in closed):raise Invalid('invalid_counts')
            plan=reconcile(report,parse_counts(d.get('counts_text')),d.get('counts_as_of'),closed)
            if any(x['issue']=='large_adjustment' for x in plan['issues']):raise Invalid('large_allocation_adjustment')
            d.update(sha256=report['source_sha256'],report=report,plan=plan,closed_barns=closed)
        return d

    def validate_global(self, data):
        data={kind:[dict(r) for r in rows] for kind,rows in data.items()}
        from .source_dates import validate_reviews
        validate_reviews(data)
        from .source_edit import validate_edits
        validate_edits(data)
        self.enrich_legacy(data)
        bid={b['id']:b for b in data['batches']}
        barns={b['id'] for b in data['barns']}
        for b in data['batches']:
            if b['barn_id'] not in barns:raise Invalid('referenced_record')
        check_slots=set()
        for check in data.get('daily_checks',[]):
            slot=(check['batch_id'],check['date'])
            if slot in check_slots:raise Invalid('daily_check_exists')
            check_slots.add(slot)
            if check['batch_id'] not in bid:raise Invalid('referenced_record')
            if check['date']<bid[check['batch_id']]['entry_date']:raise Invalid('before_entry')
        for kind in ('movements','weights','usages'):
            for r in data[kind]:
                if r['batch_id'] not in bid:raise Invalid('referenced_record')
                dates=[r['start']] if kind=='usages' else [r['date']]
                if any(d<bid[r['batch_id']]['entry_date'] for d in dates):raise Invalid('before_entry')
                if r.get('target_batch_id'):
                    if r['target_batch_id'] not in bid:raise Invalid('referenced_record')
                    if r['date']<bid[r['target_batch_id']]['entry_date']:raise Invalid('before_entry')
                    source,target=bid[r['batch_id']],bid[r['target_batch_id']]
                    from .history import cohort_key
                    linked=(source.get('same_batch_as') or target.get('same_batch_as')) and cohort_key(source)==cohort_key(target)
                    if (source.get('cohort_id') or source['id'])!=(target.get('cohort_id') or target['id']) and not linked:raise Invalid('transfer_cohort_mismatch')
        for kind in ('deliveries','feed_orders'):
            for d in data.get(kind,[]):
                for a in d['allocations']:
                    if a['batch_id'] not in bid:raise Invalid('referenced_record')
                    if kind=='deliveries' and d['date']<bid[a['batch_id']]['entry_date']:raise Invalid('before_entry')
        for kind in ('deliveries','feed_orders','movements'):
            for record in data[kind]:
                source=record.get('quick_source')
                if not source:continue
                if source['barn_id'] not in barns:raise Invalid('referenced_record')
                if kind=='movements' and bid[record['batch_id']]['barn_id']!=source['barn_id']:raise Invalid('invalid_quick_source')
                if record.get('feed_bin_snapshot') and source['barn_id'] not in record['feed_bin_snapshot']['barn_ids']:raise Invalid('invalid_quick_source')
        bins={b['id']:b for b in data.get('feed_bins',[])}
        for bin in bins.values():
            if not set(bin['barn_ids'])<=barns:raise Invalid('referenced_record')
        for o in data.get('feed_orders',[])+data.get('deliveries',[]):
            if not o.get('feed_bin_id'):continue
            bin=bins.get(o['feed_bin_id'])
            if not bin:raise Invalid('referenced_record')
            snap=o['feed_bin_snapshot']
            if bin['barn_ids']!=snap['barn_ids']:raise Invalid('feed_bin_members_locked')
            if not set(o.get('target_batch_ids',[]))<=bid.keys():raise Invalid('referenced_record')
            if any(bid[x]['barn_id'] not in snap['barn_ids'] for x in o.get('target_batch_ids',[])):raise Invalid('referenced_record')
            from .feed import validate_bin_allocations
            validate_bin_allocations(o.get('bin_allocations',[]),o['kg'],o.get('target_batch_ids',[]),snap['barn_ids'],bid)
            if o.get('requested_barn_id') and o['requested_barn_id'] not in snap['barn_ids']:raise Invalid('referenced_record')
        for u in data.get('usages',[]):
            if u.get('feed_bin_id') and (u['feed_bin_id'] not in bins or bid[u['batch_id']]['barn_id'] not in bins[u['feed_bin_id']]['barn_ids']):raise Invalid('referenced_record')
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
                balance=None if balance is None or changes[date] is None else balance+changes[date]
                if balance is not None and balance<0:raise Invalid('insufficient_heads')
        for book in data['workbooks']:
            if book.get('base_book_id'):continue
            for row in book['report']['rows']:
                members=[b for b in data['batches'] if b.get('legacy_source')==book['id'] and b.get('legacy_row')==row['key']]
                if len(members)!=len(row['barns']) or {b['legacy_barn'] for b in members}!=set(row['barns']):raise Invalid('legacy_source_conflict')
                if len(members)>1 and all(b['entry_count'] is not None for b in members) and sum(b['entry_count'] for b in members)!=row['totals']['entry']:raise Invalid('legacy_entry_total_mismatch')
                if len(members)==1:
                    member=members[0];number(member['entry_count'],False,True)
                    if member['entry_count']<0:raise Invalid('invalid_number')
                    if member['entry_count']!=row['totals']['entry'] and not member.get('entry_count_reason','').strip():raise Invalid('entry_count_reason_required')
                    if any(s['remaining']<0 or s['entry']<s['dead'] for s in member['legacy_group']['snapshots'].values()):raise Invalid('insufficient_heads')
        from .history import source_history
        known={r['id']:r for kind in ('movements','weights') for r in source_history(data,kind,include_voided=True,include_matched=True)}
        for void in data.get('source_voids',[]):
            row=void['source_record'];original=known.get(void['source_row_id']) or next((r for r in known.values() if row.get('source_anchor') and r.get('source_anchor')==row['source_anchor']),None)
            if not original or any(row.get(k)!=original.get(k) for k in ('cohort','archive')) or (original and row.get('source_cell','').split('!')[-1]!=original.get('source_cell','').split('!')[-1]):raise Invalid('invalid_backup')
            if void['target_kind']=='movements':
                number(row.get('quantity'),True,True)
                batch=next((b for b in data['batches'] if b['id']==row.get('batch_id')),None)
                if batch and row.get('date') and row['date']<=batch['legacy_group']['as_of'] and any(row.get(k)!=original.get(k) for k in ('date','type','quantity','batch_id')):raise Invalid('invalid_backup')
                if not row.get('archive') and not row.get('date'):raise Invalid('source_void_unassigned')
        active_by_batch={}
        for u in data['usages']:
            if u['active']:active_by_batch.setdefault(u['batch_id'],[]).append(u)
        for rows in active_by_batch.values():
            rows.sort(key=lambda u:u['start'])
            if any(a['end']>b['start'] for a,b in zip(rows,rows[1:])):raise Invalid('overlapping_usage')

    def mutate(self, user, kind, payload, request_key, rid=None, delete=False, return_snapshot=False):
        self.require(user,admin=kind in ('barns','batches','workbooks','feed_bins') or delete)
        if kind not in KINDS:raise Problem('unknown_kind',404)
        if kind=='feed_drafts':raise Problem('feed_draft_review_required',403)
        if kind=='deliveries' and isinstance(payload,dict) and payload.get('feed_bin_id'):raise Problem('quick_review_required',409)
        if kind in ('workbooks','source_voids'):raise Problem('legacy_source_readonly',403)
        if not isinstance(payload,dict) or not isinstance(request_key,str) or not 16<=len(request_key)<=128:raise Problem('idempotency_required')
        fingerprint=hashlib.sha256(encode([kind,rid,delete,payload]).encode()).hexdigest()
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT * FROM requests WHERE user_id=? AND key=?',(user['id'],request_key)).fetchone()
            if prior:
                if prior['fingerprint']!=fingerprint:raise Problem('idempotency_mismatch',409)
                return json.loads(prior['result'])
            data=self.snapshot(db,include_source=False)
            previous=None
            if rid:
                previous=next((r for r in data[kind] if r['id']==rid),None)
                if not previous:raise Problem('not_found',404)
                if kind in ('movements','weights') and (previous.get('legacy_source') or previous.get('_source_derived')):raise Problem('legacy_source_readonly',403)
                if user['role']=='staff' and previous.get('created_by')!=user['id']:raise Problem('forbidden',403)
                if kind=='deliveries' and previous.get('quick_source'):raise Problem('quick_review_required',409)
                if payload.get('revision')!=previous['revision']:raise Problem('revision_conflict',409,previous)
                data[kind]=[r for r in data[kind] if r['id']!=rid]
            if kind=='daily_checks' and previous and any(payload.get(k)!=previous[k] for k in ('date','batch_id')):raise Problem('daily_check_identity_locked')
            if kind=='daily_checks' and delete:raise Problem('daily_check_cancel_required')
            rid=rid or str(uuid.uuid4())
            if delete:
                output={'id':rid,'deleted':True,'revision':previous['revision']+1}
                tombstone=previous|{'revision':output['revision'],'updated_at':now()}
                db.execute('UPDATE records SET deleted=1,revision=revision+1,data=? WHERE id=?',(encode(tombstone),rid))
            else:
                if kind=='barns' and previous and 'feed_vendor' not in payload and 'feed_vendor' in previous:
                    payload=payload|{'feed_vendor':previous['feed_vendor']}
                if kind=='batches' and previous:
                    payload={k:previous[k] for k in ('source_assignments','stock_basis','quality_review') if k not in payload and k in previous}|payload
                if kind=='movements' and previous and 'outgoing_destination' not in payload and payload.get('type') in ('sale','cull') and 'outgoing_destination' in previous:
                    payload=payload|{'outgoing_destination':previous['outgoing_destination']}
                if kind=='movements' and previous and 'outgoing_trip' not in payload and payload.get('type') in ('sale','cull') and 'outgoing_trip' in previous:
                    payload=payload|{'outgoing_trip':previous['outgoing_trip']}
                if kind=='batches' and previous and 'same_batch_as' not in payload:
                    payload=payload|{'same_batch_as':previous.get('same_batch_as')}
                if kind=='batches' and previous:
                    payload={k:previous[k] for k in ('weekly_start_date','report_entry_lots','report_entry_lots_source','entry_date_override') if k in previous and k not in payload}|payload
                if kind=='batches' and previous and previous.get('legacy_source'):
                    if any(payload.get(k)!=previous.get(k) for k in ('legacy_source','legacy_row','legacy_barn','barn_id')):raise Problem('legacy_source_conflict')
                    if payload.get('entry_date')!=previous.get('entry_date') and not payload.get('entry_date_override'):raise Problem('legacy_source_conflict')
                if kind=='feed_orders' and previous and 'feed_bin_id' not in payload:
                    payload={k:previous[k] for k in ('feed_bin_id','target_batch_ids') if k in previous}|payload
                duplicate_confirmation=payload.get('duplicate_confirmation') if kind=='movements' else None
                if kind=='movements':payload={k:v for k,v in payload.items() if k!='duplicate_confirmation'}
                cleaned=self.validate(kind,payload,data,user,previous)
                if kind=='movements':
                    from .source_edit import duplicates,duplicate_token
                    if duplicates(data,cleaned,rid) and duplicate_confirmation!=duplicate_token(data,cleaned,rid):raise Problem('movement_duplicate',409,duplicates(data,cleaned,rid))
                if kind=='batches' and previous and previous.get('legacy_group',{}).get('expected_members')==1:
                    if cleaned['entry_count']!=previous['entry_count']:
                        if not cleaned.get('entry_count_reason'):raise Problem('entry_count_reason_required')
                    else:cleaned['entry_count_reason']=previous.get('entry_count_reason','')
                if kind=='weights':
                    for field in ('session_id','session_number','session_fingerprint'):
                        cleaned.pop(field,None)
                        if previous and field in previous:cleaned[field]=previous[field]
                output=cleaned|{'id':rid,'revision':previous['revision']+1 if previous else 1,'created_at':previous.get('created_at',now()) if previous else now(),'created_by':previous.get('created_by',user['id']) if previous else user['id'],'updated_at':now()}
                data[kind].append(output)
                db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,data=excluded.data',(kind,rid,output['revision'],encode(output)))
            self.validate_global(data)
            if kind=='movements' and not delete and output.get('type')=='death':
                for check in data.get('daily_checks',[]):
                    if check['batch_id']==output['batch_id'] and check['date']==output['date'] and check['status']=='no_deaths':
                        old=dict(check);check.update(status='cancelled',note='補登死亡後自動撤銷無死亡確認',revision=check['revision']+1,updated_at=now())
                        db.execute('UPDATE records SET revision=?,data=? WHERE id=?',(check['revision'],encode(check),check['id']))
                        self.audit(db,user['id'],'supersede-zero-check','daily_checks',check['id'],old,check)
            if return_snapshot:self.enrich_legacy(data)
            self.audit(db,user['id'],'delete' if delete else 'update' if previous else 'create',kind,rid,previous,output)
            db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],request_key,fingerprint,encode(output)))
            sequence=db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0] if return_snapshot else None
            db.commit()
            return output|{'_snapshot':data,'_sequence':sequence} if return_snapshot else output
        except Invalid as e:raise Problem(str(e))
        finally:db.close()

    def import_workbook(self,user,payload,request_key):
        self.require(user,True)
        if not isinstance(payload,dict) or not isinstance(request_key,str) or not 16<=len(request_key)<=128:raise Problem('idempotency_required')
        cleaned=self.validate('workbooks',dict(payload),self.snapshot(include_source=False),user)
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
            data=self.snapshot(db,include_source=False)
            if cleaned.get('base_book_id'):
                from .history import update_preview
                current=update_preview(cleaned['report'],data)
                if payload.get('preview_token') and payload['preview_token']!=current['preview_token']:raise Problem('revision_conflict',409)
                for row in current['pending_cohorts']:row['decision']=cleaned.get('review_decisions',{}).get(row['cohort'])
                cleaned.update(approved_cohorts=current['approved_cohorts'],matched_events=current['matched_events'],
                    pending_cohorts=current['pending_cohorts'],update_summary=current)
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
                for row in ([] if cleaned.get('base_book_id') else cleaned['report']['rows']):
                    plan=next(p for p in cleaned['plan']['rows'] if p['key']==row['key']);cohort_id=None
                    for barn_number in row['barns']:
                        linked={b['barn_id'] for b in data['batches'] if b.get('legacy_barn')==barn_number}
                        barn=next((b for b in data['barns'] if b['id'] in linked),None) if len(linked)==1 else None
                        barn=barn or next((b for b in data['barns'] if re_barn_number(b['name'])==barn_number),None)
                        if not barn:
                            barn=insert('barns',{'name':str(barn_number)+'棟','group':''});barns_added+=1
                        if any(b['barn_id']==barn['id'] and b['name']==row['name'] for b in data['batches']):raise Problem('legacy_source_conflict',409)
                        head=plan['current'].get(str(barn_number),plan['current'].get(barn_number))
                        batch={'barn_id':barn['id'],'name':row['name'],'group':row['name'],'entry_date':row['entry_date'],'entry_count':row['totals']['entry'] if len(row['barns'])==1 else None,'entry_age_days':row['entry_age_days'],'age_date':row['entry_date'],'status':'ended' if head==0 else 'active','cohort_id':cohort_id,'legacy_source':book_id,'legacy_row':row['key'],'legacy_barn':barn_number,'note':''}
                        measured=next((w for w in row['weights'] if w.get('date')==row['entry_date']),None)
                        if len(row['barns'])==1 and measured:
                            batch.update(entry_mean_kg=measured['mean_kg'],entry_mean_date=measured['date'],entry_mean_source=cleaned['filename']+' '+cleaned['report']['sheet']+'!'+measured['cell'])
                        created=insert('batches',self.validate('batches',batch,data,user));cohort_id=cohort_id or created['id'];batches_added+=1
                means_added=0
                root_id=cleaned.get('base_book_id') or book_id
                for source in cleaned['report']['rows']:
                    if len(source['barns'])!=1:continue
                    measured=next((w for w in source['weights'] if w.get('date')==source['entry_date']),None)
                    batch=next((b for b in data['batches'] if b.get('legacy_source')==root_id and b.get('legacy_barn')==source['barns'][0]),None)
                    if not measured or not batch:continue
                    stored=db.execute('SELECT data FROM records WHERE id=?',(batch['id'],)).fetchone()
                    original=json.loads(stored['data'])
                    if 'entry_mean_kg' in original:continue
                    updated=original|{'entry_mean_kg':measured['mean_kg'],'entry_mean_date':measured['date'],
                        'entry_mean_source':cleaned['filename']+' '+cleaned['report']['sheet']+'!'+measured['cell'],
                        'entry_mean_note':'','revision':original['revision']+1,'updated_at':now()}
                    db.execute('UPDATE records SET data=?,revision=? WHERE id=?',(encode(updated),updated['revision'],updated['id']))
                    self.audit(db,user['id'],'fill-entry-mean','batches',updated['id'],original,updated);means_added+=1
                self.validate_global(self.snapshot(db))
                result={'book_id':book_id,'already_imported':False,'barns_added':barns_added,'batches_added':batches_added,
                    'entry_means_added':means_added,'update_summary':cleaned.get('update_summary')}
            db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],request_key,fingerprint,encode(result)));db.commit();return result
        finally:db.close()

    def export_backup(self):
        self.backup_sqlite(label='export')
        db=self.connect()
        try:
            db.execute('BEGIN')
            return {'format':'pigledger-backup','schema':SCHEMA_VERSION,'version':VERSION,'exported_at':now(),'records':[dict(r) for r in db.execute('SELECT * FROM records')],'users':[dict(r) for r in db.execute('SELECT * FROM users')],'audit':[dict(r) for r in db.execute('SELECT * FROM audit ORDER BY seq')],'security':[dict(r) for r in db.execute('SELECT * FROM account_security')],'requests':[dict(r) for r in db.execute('SELECT * FROM requests')]}
        finally:db.close()

    def import_backup(self, user, document):
        self.require(user,True)
        if not isinstance(document,dict) or document.get('format')!='pigledger-backup' or document.get('schema') not in (1,2,3,4):raise Problem('invalid_backup')
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
                    if kind=='workbooks':
                        from .legacy import unpack,review,history_report
                        checked=review(unpack(r.get('base64')))
                        if checked['source_sha256']!=r.get('sha256'):raise Problem('invalid_backup')
                        def subset(old,new):
                            if isinstance(old,dict):return isinstance(new,dict) and all(k in new and subset(v,new[k]) for k,v in old.items())
                            if isinstance(old,list):return isinstance(new,list) and len(old)==len(new) and all(subset(a,b) for a,b in zip(old,new))
                            return old==new
                        if not subset(history_report(r['report']),history_report(checked)):raise Problem('invalid_backup')
                        continue
                    others={k:[x for x in rows if not (k==kind and x['id']==r['id'])] for k,rows in data.items()}
                    cleaned=self.validate(kind,r,others,user,r if kind in ('feed_orders','deliveries','movements','batches') else None)
                    if any((r.get(k, '') if k in ('vendor','item','entry_mean_source','entry_mean_note','entry_count_source','section') else r.get(k))!=v for k,v in cleaned.items()):raise Problem('invalid_backup')
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
            for security in document.get('security',[]):
                uid=security.get('user_id')
                if str(uuid.UUID(uid))!=uid or security.get('must_change') not in (0,1):raise Problem('invalid_backup')
                if not db.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():raise Problem('invalid_backup')
                if not db.execute('SELECT 1 FROM account_security WHERE user_id=?',(uid,)).fetchone():
                    db.execute('INSERT INTO account_security(user_id,must_change) VALUES(?,?)',(uid,security['must_change']))
            for request in document.get('requests',[]):
                uid=request.get('user_id');key=request.get('key');fp=request.get('fingerprint')
                if not isinstance(key,str) or not 16<=len(key)<=128 or not isinstance(fp,str) or len(fp)!=64 or any(c not in '0123456789abcdef' for c in fp):raise Problem('invalid_backup')
                if not isinstance(json.loads(request['result']),dict) or not db.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():raise Problem('invalid_backup')
                prior=db.execute('SELECT fingerprint,result FROM requests WHERE user_id=? AND key=?',(uid,key)).fetchone()
                if prior:
                    if prior['fingerprint']!=fp or prior['result']!=request['result']:raise Problem('backup_conflict',409)
                else:db.execute('INSERT INTO requests VALUES(?,?,?,?)',(uid,key,fp,request['result']))
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
