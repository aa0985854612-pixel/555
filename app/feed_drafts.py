"""Photo transcriptions persist as drafts; only explicit, reviewed confirmation writes feed."""
import copy, hashlib, json, uuid
from .store import Problem, encode, now
from .domain import Invalid, day, number
from .feed import FEED_TYPES, bin_label
from .feed_review import _preview, _apply_preview


def validate_draft(value):
    if not isinstance(value,dict):raise Problem('invalid_feed_draft')
    out={}
    for key,limit,default in [('title',200,'每日飼料登記'),('source',40,'chat_photo')]:
        text=value.get(key,default)
        if not isinstance(text,str) or not text.strip() or len(text)>limit:raise Problem('invalid_feed_draft')
        out[key]=text.strip()
    status=value.get('status','pending')
    if status not in ('pending','confirmed','cancelled'):raise Problem('invalid_feed_draft')
    out['status']=status;sources=value.get('sources',[])
    if not isinstance(sources,list) or len(sources)>20:raise Problem('invalid_feed_draft')
    out['sources']=[]
    for source in sources:
        if not isinstance(source,dict) or set(source)-{'name','sha256'}:raise Problem('invalid_feed_draft')
        name=source.get('name');digest=source.get('sha256','')
        if not isinstance(name,str) or not name.strip() or len(name)>250 or not isinstance(digest,str) or (digest and (len(digest)!=64 or any(ch not in '0123456789abcdef' for ch in digest))):raise Problem('invalid_feed_draft')
        out['sources'].append({'name':name.strip(),'sha256':digest})
    rows=value.get('rows');seen=set();out['rows']=[]
    if not isinstance(rows,list) or not 1<=len(rows)<=100:raise Problem('invalid_feed_draft')
    allowed={'date','kg','display_unit','vendor','item','note','feed_bin_id','target_batch_ids','bin_allocations','allocations'}
    for row in rows:
        if not isinstance(row,dict) or set(row)-{'key','record','bin_label','warning','choice'}:raise Problem('invalid_feed_draft')
        rid=row.get('key');record=row.get('record');choice=row.get('choice','auto')
        try:valid=str(uuid.UUID(rid))==rid
        except (TypeError,ValueError,AttributeError):valid=False
        if not valid or rid in seen or not isinstance(record,dict) or set(record)-allowed:raise Problem('invalid_feed_draft')
        seen.add(rid)
        if choice not in ('auto','create'):
            try:valid=choice.startswith('update:') and str(uuid.UUID(choice[7:]))==choice[7:]
            except (TypeError,ValueError,AttributeError):valid=False
            if not valid:raise Problem('invalid_feed_draft')
        clean={}
        for key,limit in [('date',10),('feed_bin_id',100),('vendor',100),('item',100),('note',2000)]:
            v=record.get(key,'')
            if not isinstance(v,str) or len(v)>limit:raise Problem('invalid_feed_draft')
            clean[key]=v.strip()
        if clean['date']:day(clean['date'])
        kg=record.get('kg');clean['kg']=None if kg is None or kg=='' else number(kg,True)
        clean['display_unit']='ton'
        for key in ('target_batch_ids','bin_allocations','allocations'):
            if key in record:
                v=record[key]
                if not isinstance(v,list) or len(v)>100 or len(encode(v))>16000:raise Problem('invalid_feed_draft')
                if key=='target_batch_ids' and any(not isinstance(x,str) for x in v):raise Problem('invalid_feed_draft')
                if key!='target_batch_ids' and any(not isinstance(x,dict) or set(x)!={'batch_id','kg'} or not isinstance(x['batch_id'],str) or not isinstance(x['kg'],(int,float)) or isinstance(x['kg'],bool) for x in v):raise Problem('invalid_feed_draft')
                clean[key]=copy.deepcopy(v)
        entry={'key':rid,'record':clean,'choice':choice}
        for key,limit in [('bin_label',150),('warning',1000)]:
            text=row.get(key,'')
            if not isinstance(text,str) or len(text)>limit:raise Problem('invalid_feed_draft')
            entry[key]=text.strip()
        out['rows'].append(entry)
    for key in ('confirmed_at','confirmed_by','cancelled_at','cancelled_by'):
        if key in value:
            if not isinstance(value[key],str) or len(value[key])>100:raise Problem('invalid_feed_draft')
            out[key]=value[key]
    if 'confirmed_ids' in value:
        ids=value['confirmed_ids']
        if not isinstance(ids,list) or len(ids)>100 or any(not isinstance(x,str) for x in ids):raise Problem('invalid_feed_draft')
        out['confirmed_ids']=list(ids)
    if status=='confirmed' and (not out.get('confirmed_ids') or not out.get('confirmed_by') or not out.get('confirmed_at')):raise Problem('invalid_feed_draft')
    return out


def _owned(store,user,draft):
    store.require(user)
    if not draft:raise Problem('not_found',404)
    if user['role']!='admin' and draft.get('created_by')!=user['id']:raise Problem('forbidden',403)


def _request(store,user,body,key,action):
    store.require(user)
    if not isinstance(body,dict) or not isinstance(key,str) or not 16<=len(key)<=128:raise Problem('idempotency_required')
    return hashlib.sha256(encode(['feed-draft',action,body]).encode()).hexdigest()


def _prior(db,user,key,fp):
    row=db.execute('SELECT * FROM requests WHERE user_id=? AND key=?',(user['id'],key)).fetchone()
    if row:
        if row['fingerprint']!=fp:raise Problem('idempotency_mismatch',409)
        return json.loads(row['result'])


def _write(db,store,user,draft,previous,result,key,fp,data,action):
    if previous:db.execute('UPDATE records SET revision=?,data=? WHERE id=?',(draft['revision'],encode(draft),draft['id']))
    else:db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,1,?)',('feed_drafts',draft['id'],encode(draft)))
    store.audit(db,user['id'],action,'feed_drafts',draft['id'],previous,draft)
    data['feed_drafts']=[r for r in data.get('feed_drafts',[]) if r['id']!=draft['id']]+[draft]
    db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],key,fp,encode(result)))
    seq=db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0];db.commit()
    return result|{'_snapshot':data,'_sequence':seq}


def save_draft(store,user,body,key,rid=None):
    fp=_request(store,user,body,key,['save',rid]);db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE');prior=_prior(db,user,key,fp)
        if prior:return prior
        data=store.snapshot(db,include_source=False);previous=next((r for r in data.get('feed_drafts',[]) if r['id']==rid),None)
        if rid:
            _owned(store,user,previous)
            if previous['status']!='pending':raise Problem('feed_draft_closed',409)
            if body.get('revision')!=previous['revision']:raise Problem('revision_conflict',409)
        payload=body.get('draft')
        if not isinstance(payload,dict) or payload.get('status','pending')!='pending' or any(k in payload for k in ('confirmed_ids','confirmed_at','confirmed_by','cancelled_at','cancelled_by')):raise Problem('invalid_feed_draft')
        cleaned=validate_draft(payload);stamp=now();draft=cleaned|{'id':rid or str(uuid.uuid4()),'revision':previous['revision']+1 if previous else 1,'created_by':previous['created_by'] if previous else user['id'],'created_at':previous['created_at'] if previous else stamp,'updated_at':stamp}
        return _write(db,store,user,draft,previous,{'id':draft['id'],'revision':draft['revision'],'status':'pending'},key,fp,data,'edit-draft' if previous else 'stage-draft')
    finally:db.close()


def _prepare(store,user,draft,db,data):
    _owned(store,user,draft)
    if draft['status']!='pending':raise Problem('feed_draft_closed',409)
    deleted=[json.loads(r['data']) for r in db.execute("SELECT data FROM records WHERE kind='feed_orders' AND deleted=1")]
    resolved=[]
    for row in draft['rows']:
        entry={'key':row['key'],'errors':[],'matches':[],'request':None,'preview':None,'queue_matches':[]}
        try:
            record=copy.deepcopy(row['record']);bin=next((b for b in data['feed_bins'] if b['id']==record.get('feed_bin_id')),None)
            if not bin and not record.get('feed_bin_id') and row.get('bin_label'):
                candidates=[b for b in data['feed_bins'] if b['active'] and row['bin_label'] in (b['name'],bin_label(b))]
                if len(candidates)==1:bin=candidates[0];record['feed_bin_id']=bin['id']
            if not bin:raise Problem('feed_draft_bin_required')
            day(record.get('date'));number(record.get('kg'),True)
            if record.get('vendor') not in ('養全','新農科'):raise Problem('feed_draft_vendor_required')
            if record.get('item') not in FEED_TYPES:raise Problem('feed_draft_item_required')
            matches=[r for r in data['feed_orders'] if r['date']==record['date'] and (r.get('feed_bin_id')==bin['id'] or (not r.get('feed_bin_id') and {data_batch['barn_id'] for a in r.get('allocations',[]) for data_batch in data['batches'] if data_batch['id']==a['batch_id']}==set(bin['barn_ids'])))]
            entry['matches']=[r|{'can_update':user['role']=='admin' or r.get('created_by')==user['id']} for r in matches]
            choice=row['choice'];selected=None
            if choice.startswith('update:'):selected=next((r for r in matches if r['id']==choice[7:]),None)
            elif choice=='auto' and len(matches)==1:selected=matches[0]
            if choice.startswith('update:') and not selected:raise Problem('revision_conflict',409)
            if choice=='auto' and len(matches)>1:raise Problem('feed_draft_choose_existing')
            if selected:
                if user['role']!='admin' and selected.get('created_by')!=user['id']:raise Problem('feed_draft_admin_required',403)
                if selected.get('feed_bin_id')==bin['id']:
                    for key in ('target_batch_ids','bin_allocations'):
                        if key not in record and key in selected:record[key]=copy.deepcopy(selected[key])
                record['revision']=selected['revision']
                if selected.get('note') and selected['note'] not in record.get('note',''):record['note']=selected['note']+('\n'+record['note'] if record.get('note') else '')
            record['allocations']=[]
            if 'target_batch_ids' not in record:
                record['target_batch_ids']=[]
                for barn_id in bin['barn_ids']:
                    candidates=[b for b in data['batches'] if b['barn_id']==barn_id and b['status']=='active' and b['entry_date']<=record['date']]
                    if len(candidates)==1:record['target_batch_ids'].append(candidates[0]['id'])
            request={'record':record,'rid':selected['id'] if selected else None};preview=_preview(store,user,request,db,data,deleted)
            if preview['voided_matches'] and choice=='auto':raise Problem('feed_draft_choose_existing')
            request.update(decision='update' if selected else 'create',**({'existing_id':selected['id']} if selected else {'new_entry_confirmed':choice=='create'}))
            entry.update(request=request,preview=preview,record=preview['record'],decision=request['decision'])
        except (Invalid,Problem) as error:
            entry['errors'].append(error.code if isinstance(error,Problem) else str(error))
        resolved.append(entry)
    for i,a in enumerate(resolved):
        for j,b in enumerate(resolved[:i]):
            ra,rb=a.get('record'),b.get('record')
            if ra and rb and ra['date']==rb['date'] and ra.get('feed_bin_id')==rb.get('feed_bin_id'):
                a['queue_matches'].append(j);b['queue_matches'].append(i)
                same_update=a['request'].get('existing_id') and a['request'].get('existing_id')==b['request'].get('existing_id')
                if same_update or (a['decision']=='create' and b['decision']=='create' and not all(draft['rows'][n]['choice']=='create' for n in (i,j))):
                    for entry in (a,b):
                        if 'feed_draft_duplicate_row' not in entry['errors']:entry['errors'].append('feed_draft_duplicate_row')
    proof=hashlib.sha256(encode([user['id'],draft,[(r['key'],r['preview']['preview_token'] if r.get('preview') else None,r['request'],r['errors']) for r in resolved]]).encode()).hexdigest()
    return {'id':draft['id'],'revision':draft['revision'],'rows':resolved,'preview_token':proof,'can_confirm':all(not r['errors'] for r in resolved),'count':len(resolved),'total_kg':sum(r['record']['kg'] for r in resolved if r.get('record'))}


def preview_draft(store,user,rid,body):
    store.require(user);db=store.connect()
    try:
        db.execute('BEGIN');data=store.snapshot(db,include_source=False);draft=next((d for d in data.get('feed_drafts',[]) if d['id']==rid),None);_owned(store,user,draft)
        if not isinstance(body,dict) or body.get('revision')!=draft['revision']:raise Problem('revision_conflict',409)
        return _prepare(store,user,draft,db,data)
    finally:db.close()


def finish_draft(store,user,rid,body,key,cancel=False):
    fp=_request(store,user,body,key,['cancel' if cancel else 'confirm',rid]);db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE');prior=_prior(db,user,key,fp)
        if prior:return prior
        data=store.snapshot(db,include_source=False);old=next((r for r in data.get('feed_drafts',[]) if r['id']==rid),None);_owned(store,user,old)
        if old['status']!='pending':raise Problem('feed_draft_closed',409)
        if body.get('revision')!=old['revision']:raise Problem('revision_conflict',409)
        stamp=now();draft=copy.deepcopy(old);draft.update(revision=old['revision']+1,updated_at=stamp)
        outputs=[]
        if cancel:draft.update(status='cancelled',cancelled_at=stamp,cancelled_by=user['id'])
        else:
            if body.get('confirmed') is not True:raise Problem('feed_draft_confirmation_required')
            preview=_prepare(store,user,old,db,data)
            if preview['preview_token']!=body.get('preview_token'):raise Problem('revision_conflict',409)
            if not preview['can_confirm']:raise Problem('feed_draft_incomplete',400,[r['errors'] for r in preview['rows']])
            for row in preview['rows']:
                output,previous=_apply_preview(store,user,row['request'],row['preview'],data)
                if previous:db.execute('UPDATE records SET revision=?,data=? WHERE id=?',(output['revision'],encode(output),output['id']))
                else:db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,1,?)',('feed_orders',output['id'],encode(output)))
                store.audit(db,user['id'],'update' if previous else 'create','feed_orders',output['id'],previous,output);outputs.append(output['id'])
            store.validate_global(data);draft.update(status='confirmed',confirmed_ids=outputs,confirmed_at=stamp,confirmed_by=user['id'])
        result={'id':rid,'revision':draft['revision'],'status':draft['status'],'confirmed_ids':outputs}
        return _write(db,store,user,draft,old,result,key,fp,data,'cancel-draft' if cancel else 'confirm-draft')
    finally:db.close()
