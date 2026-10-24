"""Deterministic Chinese/Vietnamese quick entry using the original record kinds."""
import copy,hashlib,json,re,unicodedata,uuid
from datetime import datetime,timedelta,timezone
from .store import Problem,encode,now
from .domain import Invalid,day,number,herd
from .feed import barn_number,bin_label
from .operations import token
from .bin_stock import stock

TYPES={'delivery':'deliveries','order':'feed_orders','death':'movements','cull':'movements','sale':'movements','arrival':'movements'}


def today():return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


def normalized(text):
    text=unicodedata.normalize('NFKC',text).lower().replace('đ','d')
    return ''.join(ch for ch in unicodedata.normalize('NFD',text) if not unicodedata.combining(ch))


def parse(text,on=None,language='zh'):
    if not isinstance(text,str) or not 1<=len(text.strip())<=1000:raise Problem('quick_text_required')
    on=on or today();day(on);work=normalized(text);out={'date':on,'barn_number':None,'type':None,'quantity':None,'unit':None,'notes':[],'errors':[]}
    def extract(pattern):
        nonlocal work
        matches=list(re.finditer(pattern,work,re.I))
        for m in reversed(matches):work=work[:m.start()]+' '*len(m.group())+work[m.end():]
        return matches
    dates=extract(r'(?<!\d)(\d{4})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{1,2})(?!\d)|(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日?|ngay\s+(\d{1,2})\s+thang\s+(\d{1,2})|(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?:\s*/\s*(\d{4}))?(?!\d)|今天|今日|hom nay|昨天|hom qua|明天|ngay mai')
    if len(dates)>1:out['errors'].append('quick_multiple_dates')
    elif dates:
        m=dates[0];s=m.group();year=day(on).year
        try:
            if s in ('今天','今日','hom nay'):value=day(on)
            elif s in ('昨天','hom qua'):value=day(on)-timedelta(days=1)
            elif s in ('明天','ngay mai'):value=day(on)+timedelta(days=1)
            elif m[1]:value=day(f'{int(m[1]):04}-{int(m[2]):02}-{int(m[3]):02}')
            elif m[4]:value=day(f'{year:04}-{int(m[4]):02}-{int(m[5]):02}');out['notes'].append('quick_year_inferred')
            elif m[6]:value=day(f'{year:04}-{int(m[7]):02}-{int(m[6]):02}');out['notes'].append('quick_year_inferred')
            else:
                a,b=int(m[8]),int(m[9]);year=int(m[10]) if m[10] else year
                month,d=(b,a) if language=='vi' else (a,b)
                value=day(f'{year:04}-{month:02}-{d:02}')
                if not m[10]:out['notes'].append('quick_year_inferred')
                if a<=12 and b<=12 and a!=b and language=='vi':out['notes'].append('quick_date_day_month')
            out['date']=value.isoformat()
        except (ValueError,Invalid):out['date']='';out['errors'].append('invalid_date')
    else:out['notes'].append('quick_today_default')
    barns=extract(r'(?<!\d)(?:第\s*)?(\d+)\s*(?:棟|栋)|(?:chuong)\s*(\d+)(?!\d)')
    if len(barns)==1:out['barn_number']=int(barns[0][1] or barns[0][2])
    else:out['errors'].append('quick_multiple_barns' if barns else 'quick_barn_required')
    amounts=extract(r'(?<![\d.,])(-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(噸|吨|公斤|千克|kg\b|tons?\b|tan\b|t\b|隻|只|頭|头|con\b)')
    if len(amounts)!=1:out['errors'].append('quick_multiple_amounts' if amounts else 'quick_amount_required')
    else:
        m=amounts[0];n=float(m[1].replace(',',''));unit=m[2]
        out.update(quantity=n,unit='kg' if unit in ('公斤','千克','kg') else 'ton' if unit in ('噸','吨','ton','tons','tan','t') else 'heads')
        if n<=0:out['errors'].append('invalid_number')
    patterns={'order':r'叫(?:飼|饲)?料|訂(?:購)?(?:飼|饲)?料|订(?:购)?(?:飼|饲)?料|dat\s+(?:mua\s+)?cam', 'delivery':r'到料|入料|飼料到貨|饲料到货|收到(?:飼|饲)?料|nhan\s+cam|nhap\s+cam',
        'death':r'死亡|死掉|死|chet', 'cull':r'淘汰|loai(?:\s+thai)?', 'sale':r'出豬|出猪|出售|賣豬|卖猪|xuat(?:\s+heo)?|ban\s+heo',
        'arrival':r'進豬|进猪|補豬|补猪|入豬|进场|進場|nhap(?:\s+heo)?|them\s+heo'}
    detected=[]
    # Longer feed phrases are removed before generic Vietnamese 'nhap'.
    for kind,pattern in patterns.items():
        if extract(pattern):detected.append(kind)
    extract(r'飼料|饲料|cam|heo|豬|猪')
    if re.search(r'不要|還沒|尚未|沒有|沒|未|取消|\b(?:khong|chua|huy)\b',work):out['errors'].append('quick_negated_statement')
    extract(r'請|请|幫我|帮我|登記|登记|記錄|记录|了|\bda\b')
    if re.search(r'[^\s\d.,，。:：;；()（）+\-/]',work):out['errors'].append('quick_unrecognized_text')
    if len(detected)>1:out['errors'].append('quick_conflicting_types')
    elif detected:out['type']=detected[0]
    elif out['unit'] in ('kg','ton'):out['type']='delivery'
    else:out['errors'].append('quick_type_required')
    if out['type']:
        isfeed=out['type'] in ('order','delivery')
        if out['unit'] and ((out['unit']=='heads')==isfeed):out['errors'].append('quick_unit_mismatch')
        if not isfeed and out['quantity'] is not None and not out['quantity'].is_integer():out['errors'].append('quick_heads_integer')
    if re.search(r'\d',work):out['errors'].append('quick_unrecognized_numbers')
    return out


def validate_source(value):
    if not isinstance(value,dict) or set(value)!={'text','initial_text','operation_id','parser_version','barn_id'}:raise Problem('invalid_quick_source')
    for key in ('text','initial_text'):
        if not isinstance(value[key],str) or not 1<=len(value[key])<=1000:raise Problem('invalid_quick_source')
    for key in ('operation_id','barn_id'):
        try:valid=str(uuid.UUID(value[key]))==value[key]
        except (ValueError,TypeError,AttributeError):valid=False
        if not valid:raise Problem('invalid_quick_source')
    if value['parser_version']!=1:raise Problem('invalid_quick_source')
    return copy.deepcopy(value)


def _owned(store,user,previous):
    store.require(user)
    if not previous or not previous.get('quick_source'):raise Problem('not_found',404)
    if user['role']!='admin' and previous['created_by']!=user['id']:raise Problem('forbidden',403)


def _choices(data,barn,on,order=False):
    return [b for b in data['batches'] if b['barn_id']==barn and (b['entry_date']<=on or order)]


def _prepare(store,user,body,db,data):
    store.require(user)
    if not isinstance(body,dict):raise Problem('invalid_request')
    action=body.get('action','create');kind=body.get('kind');rid=body.get('id');previous=None
    if action not in ('create','update','delete'):raise Problem('invalid_request')
    if action!='create':
        if kind not in set(TYPES.values()) or not isinstance(rid,str):raise Problem('invalid_request')
        previous=next((r for r in data[kind] if r['id']==rid),None);_owned(store,user,previous)
        if body.get('revision')!=previous['revision']:raise Problem('revision_conflict',409)
    if action=='delete':
        source=previous['quick_source'];barn=next(b for b in data['barns'] if b['id']==source['barn_id']);resolved={'date':previous['date'],'type':previous.get('type') if kind=='movements' else 'order' if kind=='feed_orders' else 'delivery','quantity':previous.get('quantity',previous.get('kg')),'unit':'heads' if kind=='movements' else 'kg','notes':[],'errors':[]}
        record=None;bin=next((b for b in data['feed_bins'] if b['id']==previous.get('feed_bin_id')),None);batch=next((b for b in data['batches'] if b['id']==previous.get('batch_id')),None)
        after=copy.deepcopy(data);after[kind]=[r for r in after[kind] if r['id']!=rid]
    else:
        text=body.get('text');resolved=parse(text,language=body.get('language','zh'));c=body.get('corrections',{})
        if not isinstance(c,dict) or set(c)-{'date','barn_id','type','quantity','unit','batch_id','feed_bin_id','item','vendor','outgoing_destination','outgoing_trip','total_weight_kg','note','allocations'}:raise Problem('invalid_request')
        if c:
            for field in ('date','type','quantity','unit'):
                if field in c:resolved[field]=c[field]
            # A deliberate correction replaces parse errors; core fields are still validated below.
            resolved['errors']=[]
        if resolved['errors']:return {'can_confirm':False,'parsed':resolved,'errors':resolved['errors'],'notes':resolved['notes'],'warnings':[],'batch_choices':[],'bin_choices':[]}
        day(resolved['date']);type=resolved['type']
        if type not in TYPES or resolved['unit'] not in ('kg','ton','heads'):raise Problem('quick_type_required')
        feed=type in ('order','delivery')
        if (resolved['unit']=='heads')==feed:raise Problem('quick_unit_mismatch')
        quantity=number(resolved['quantity'],True,not feed)
        if resolved['date']>today() and type!='order':raise Problem('quick_future_actual')
        barn=next((b for b in data['barns'] if b['id']==c.get('barn_id')),None) if c.get('barn_id') else next((b for b in data['barns'] if barn_number(b['name'])==resolved['barn_number']),None)
        if not barn:raise Problem('quick_barn_not_found')
        newkind=TYPES[type]
        if previous and kind!=newkind:raise Problem('quick_type_locked')
        kind=newkind;record={'date':resolved['date'],'note':c.get('note',previous.get('note','') if previous else '')};batch=None;bin=None
        batches=_choices(data,barn['id'],resolved['date'],type=='order');active=[b for b in batches if b['status']=='active']
        prior_targets=([previous['batch_id']] if previous and previous.get('batch_id') else previous.get('target_batch_ids',[]) if previous else [])
        prior_batch=next((b for b in batches if b['id'] in prior_targets),None)
        batch=next((b for b in batches if b['id']==c.get('batch_id')),None) if c.get('batch_id') else prior_batch or (active[0] if len(active)==1 else None)
        bins=[b for b in data['feed_bins'] if (b['active'] or previous and previous.get('feed_bin_id')==b['id']) and barn['id'] in b['barn_ids']] if feed else []
        prior_bin=next((b for b in bins if previous and b['id']==previous.get('feed_bin_id')),None)
        bin=next((b for b in bins if b['id']==c.get('feed_bin_id')),None) if c.get('feed_bin_id') else prior_bin or (bins[0] if len(bins)==1 else None)
        errors=[]
        if not batch:errors.append('quick_batch_required')
        if feed and not bin:errors.append('quick_bin_required')
        if errors:return {'can_confirm':False,'parsed':resolved,'barn':barn,'errors':errors,'notes':resolved['notes'],'warnings':[],'batch_choices':[{'id':b['id'],'name':b['name'],'entry_date':b['entry_date'],'status':b['status']} for b in batches],'bin_choices':[{'id':b['id'],'name':bin_label(b)} for b in bins]}
        if feed:
            kg=quantity*(1000 if resolved['unit']=='ton' else 1)
            targets=[]
            for barnid in bin['barn_ids']:
                eligible=[b for b in _choices(data,barnid,resolved['date'],type=='order') if b['status']=='active']
                if barnid==barn['id']:targets.append(batch['id'])
                elif len(eligible)==1:targets.append(eligible[0]['id'])
            record.update(kg=kg,display_unit=resolved['unit'],vendor=c.get('vendor',previous.get('vendor','') if previous else barn.get('feed_vendor') or bin['vendor']),item=c.get('item',previous.get('item','') if previous else ''),feed_bin_id=bin['id'],target_batch_ids=targets,requested_barn_id=barn['id'],allocations=[{'batch_id':batch['id'],'kg':kg}] if type=='delivery' and len(bin['barn_ids'])==1 else [])
            if type=='delivery':
                if 'allocations' in c:record['allocations']=copy.deepcopy(c['allocations'])
                elif previous and previous.get('feed_bin_id')==bin['id'] and len(bin['barn_ids'])>1:record['allocations']=copy.deepcopy(previous['allocations'])
            if previous and type=='order' and previous.get('bin_allocations'):
                record['bin_allocations']=copy.deepcopy(previous['bin_allocations'])
        else:
            record.update(batch_id=batch['id'],type=type,quantity=quantity)
            for field in ('outgoing_destination','outgoing_trip','total_weight_kg'):
                if previous and field in previous:record[field]=previous[field]
            for field in ('outgoing_destination','outgoing_trip','total_weight_kg'):
                if field in c:record[field]=c[field]
        source=previous['quick_source'] if previous else {'initial_text':text.strip(),'operation_id':str(uuid.uuid4()),'parser_version':1}
        # Operation id is stable from the client, and validated before entering a transaction.
        source=dict(source,text=text.strip(),barn_id=barn['id'])
        if not previous:source['operation_id']=body.get('operation_id','')
        record['quick_source']=validate_source(source)
        after=copy.deepcopy(data)
        if previous:after[kind]=[r for r in after[kind] if r['id']!=rid]
        record=store.validate(kind,record,after,user,previous,quick=True)
        after[kind].append(record|{'id':rid or 'preview','revision':(previous['revision']+1) if previous else 1})
    store.validate_global(after)
    warnings=[];notes=list(resolved['notes']);inventory=None;inventories=[]
    if kind=='feed_orders' and batch and resolved['date']<batch['entry_date']:warnings.append('quick_preentry_order')
    if kind=='deliveries':
        binids={r.get('feed_bin_id') for r in (record,previous) if r}
        for bid in binids:
            candidate=next((b for b in data['feed_bins'] if b['id']==bid),None)
            if not candidate:continue
            current=stock(data,candidate,today());following=stock(after,candidate,today())
            change={'before':current,'after':following};inventories.append(change)
            if inventory is None or bin and candidate['id']==bin['id']:inventory=change
            if candidate.get('inventory_enabled'):
                if resolved['date']<candidate['inventory_date']:notes.append('quick_before_inventory_baseline')
                if not following['known']:warnings.append('quick_stock_unknown')
                elif following['kg']<0:warnings.append('quick_stock_negative')
                checkpoints={today(),resolved['date']}|{d['date'] for d in after['deliveries'] if d.get('feed_bin_id')==bid and resolved['date']<=d['date']<=today()}
                if any((s:=stock(after,candidate,on))['kg'] is not None and s['safe_capacity_kg'] is not None and s['kg']>s['safe_capacity_kg']+1e-7 for on in checkpoints):warnings.append('quick_capacity_exceeded')
            else:
                notes.append('quick_inventory_disabled')
                if record and following['safe_capacity_kg'] is not None and record['kg']>following['safe_capacity_kg']+1e-7:warnings.append('quick_capacity_exceeded')
            if len(candidate['barn_ids'])>1:notes.append('quick_shared_unallocated')
    duplicates=[]
    if action!='delete':
        def identity(r):return [r.get(k) for k in (('date','batch_id','type','quantity') if kind=='movements' else ('date','feed_bin_id','kg'))]
        from .feed_review import _same_scope
        duplicates=[r['id'] for r in data[kind] if r['id']!=rid and (identity(r)==identity(record) if kind=='movements' else r['date']==record['date'] and r['kg']==record['kg'] and _same_scope(r,record,data))]
        if duplicates:warnings.append('quick_possible_duplicate')
    on=max(today(),resolved['date']);impact=None
    if kind=='movements':impact={'before':herd(data['batches'],data['movements'],on,[previous['batch_id'] if action=='delete' else record['batch_id']]),'after':herd(after['batches'],after['movements'],on,[previous['batch_id'] if action=='delete' else record['batch_id']])}
    warnings=sorted(set(warnings));proof=hashlib.sha256(encode([user['id'],body,token(data),record,warnings]).encode()).hexdigest()
    return {'can_confirm':True,'action':action,'kind':kind,'id':rid,'revision':previous['revision'] if previous else None,'record':record,'previous':previous,'parsed':resolved,'barn':{'id':barn['id'],'name':barn['name']},'batch':{'id':batch['id'],'name':batch['name']} if batch else None,'bin':{'id':bin['id'],'name':bin_label(bin)} if bin else None,'notes':sorted(set(notes)),'warnings':warnings,'errors':[],'duplicates':duplicates,'inventory':inventory,'inventories':inventories,'impact':impact,'preview_token':proof}


def preview(store,user,body):
    db=store.connect()
    try:db.execute('BEGIN');return _prepare(store,user,body,db,store.snapshot(db,include_source=False))
    finally:db.close()


def save(store,user,body,key):
    store.require(user)
    if not isinstance(body,dict) or not isinstance(body.get('request'),dict) or not isinstance(key,str) or not 16<=len(key)<=128:raise Problem('idempotency_required')
    if body.get('confirmed') is not True:raise Problem('quick_confirmation_required')
    fp=hashlib.sha256(encode(['quick-save',body]).encode()).hexdigest();db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE');prior=db.execute('SELECT * FROM requests WHERE user_id=? AND key=?',(user['id'],key)).fetchone()
        if prior:
            if prior['fingerprint']!=fp:raise Problem('idempotency_mismatch',409)
            return json.loads(prior['result'])
        data=store.snapshot(db,include_source=False);p=_prepare(store,user,body['request'],db,data)
        if not p['can_confirm']:raise Problem('quick_incomplete')
        if body.get('preview_token')!=p['preview_token']:raise Problem('revision_conflict',409)
        if not set(p['warnings'])<=set(body.get('acknowledged',[])):raise Problem('quick_warning_confirmation_required')
        previous=p['previous'];rid=previous['id'] if previous else str(uuid.uuid4());kind=p['kind'];stamp=now()
        if p['action']=='create':
            op=p['record']['quick_source']['operation_id']
            if db.execute("SELECT id FROM records WHERE json_extract(data,'$.quick_source.operation_id')=? LIMIT 1",(op,)).fetchone():raise Problem('quick_operation_already_saved',409)
        if p['action']=='delete':
            output=previous|{'revision':previous['revision']+1,'updated_at':stamp};db.execute('UPDATE records SET revision=?,deleted=1,data=? WHERE id=?',(output['revision'],encode(output),rid));data[kind]=[r for r in data[kind] if r['id']!=rid]
        else:
            output=p['record']|{'id':rid,'revision':previous['revision']+1 if previous else 1,'created_at':previous['created_at'] if previous else stamp,'created_by':previous['created_by'] if previous else user['id'],'updated_at':stamp}
            if previous:db.execute('UPDATE records SET revision=?,data=? WHERE id=?',(output['revision'],encode(output),rid));data[kind]=[r for r in data[kind] if r['id']!=rid]
            else:db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,1,?)',(kind,rid,encode(output)))
            data[kind].append(output)
            if kind=='movements' and output['type']=='death':
                for check in data['daily_checks']:
                    if check['batch_id']==output['batch_id'] and check['date']==output['date'] and check['status']=='no_deaths':
                        old=dict(check);check.update(status='cancelled',note='補登死亡後自動撤銷無死亡確認',revision=check['revision']+1,updated_at=stamp);db.execute('UPDATE records SET revision=?,data=? WHERE id=?',(check['revision'],encode(check),check['id']));store.audit(db,user['id'],'supersede-zero-check','daily_checks',check['id'],old,check)
        store.validate_global(data);store.audit(db,user['id'],p['action'],kind,rid,previous,output)
        result={'id':rid,'kind':kind,'action':p['action'],'revision':output['revision'],'record':output}
        db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],key,fp,encode(result)));seq=db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0];db.commit()
        return result|{'_snapshot':data,'_sequence':seq}
    finally:db.close()


def history(store,user,query):
    if not user:raise Problem('login_required',401)
    search=normalized(query.get('q',[''])[0]);rows=[];db=store.connect()
    try:
        barns={b['id']:b['name'] for b in store.snapshot(db,include_source=False)['barns']}
        for row in db.execute("SELECT r.kind,r.deleted,r.data,u.username FROM records r LEFT JOIN users u ON u.id=json_extract(r.data,'$.created_by') WHERE json_type(r.data,'$.quick_source')='object' ORDER BY r.rowid DESC"):
            record=json.loads(row['data']);source=record['quick_source'];status='deleted' if row['deleted'] else 'modified' if record['revision']>1 else 'active'
            barn=barns.get(source['barn_id'],'')
            if search and search not in normalized(encode([record.get('date'),barn,record.get('type'),record.get('quantity',record.get('kg')),source['text'],source['initial_text'],row['username']])):continue
            rows.append({'kind':row['kind'],'record':record,'status':status,'creator':row['username'] or record['created_by'],'can_edit':not row['deleted'] and user['role']!='viewer' and (user['role']=='admin' or record['created_by']==user['id'])})
        offset=int(query.get('offset',['0'])[0]);limit=int(query.get('limit',['50'])[0])
        if offset<0 or not 1<=limit<=100:raise Problem('invalid_request')
        return {'rows':rows[offset:offset+limit],'total':len(rows),'offset':offset,'limit':limit}
    finally:db.close()
