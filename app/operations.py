"""Atomic weighing sessions and traceable record/source voids."""
import copy,hashlib,json,uuid
from datetime import datetime,timezone,timedelta
from .store import Problem,encode,now
from .domain import herd,performance,consumption,combined_weights
from .feed_receipts import receipts,orders_are_arrivals


def token(data):
    return hashlib.sha256(encode([orders_are_arrivals(),[(k,[(r['id'],r.get('revision',1)) for r in rows if not r.get('_source_derived')]) for k,rows in data.items()]]).encode()).hexdigest()


def apply_source_voids(data):
    """Adjust only dates already incorporated in legacy snapshots, exactly once."""
    for void in data.get('source_voids',[]):
        row=void['source_record']
        if void['target_kind']!='movements' or row.get('archive') or not row.get('date'):continue
        batch=next((b for b in data['batches'] if b['id']==row.get('batch_id')),None)
        if not batch or row['date']>batch['legacy_group']['as_of']:continue
        field={'sale':'sold','death':'dead','cull':'culled'}[row['type']];q=row['quantity']
        for b in data['batches']:
            if b.get('_cohort_key')!=row['cohort']:continue
            for on,snapshot in b['legacy_group']['snapshots'].items():
                if on>=row['date']:snapshot[field]-=q;snapshot['remaining']+=q
        for on,values in batch['legacy_values'].items():
            if on>=row['date'] and values.get(field) is not None:values[field]-=q
        for on,heads in batch['legacy_heads'].items():
            if on>=row['date'] and heads is not None:batch['legacy_heads'][on]+=q


def void_preview(store,user,data,kind,rid):
    store.require(user,True)
    if kind not in ('movements','feed_orders','deliveries','usages','weights'):raise Problem('void_not_supported')
    from .history import source_history
    row=next((r for r in data[kind] if r['id']==rid),None)
    if not row and kind in ('movements','weights'):row=next((r for r in source_history(data,kind) if r['id']==rid),None)
    if not row:raise Problem('not_found',404)
    source=bool(row.get('legacy_source') or row.get('_source_derived'))
    after=copy.deepcopy(data)
    if source:
        if any(v['source_row_id']==rid for v in data.get('source_voids',[])):raise Problem('already_voided',409)
        if kind=='movements' and not row.get('archive'):
            members=[b for b in data['batches'] if b['id'] in row.get('legacy_members',[])]
            if not row.get('date') or (members and row['date']<=members[0]['legacy_group']['as_of'] and not row.get('batch_id')):raise Problem('source_void_unassigned')
        if kind=='weights' and row.get('entry_measurement'):
            b=next((b for b in data['batches'] if b['id']==row.get('batch_id')),None)
            if b and b.get('entry_mean_kg') is not None and row.get('source_cell','').split('!')[-1] in b.get('entry_mean_source',''):
                raise Problem('source_mean_in_use')
        after['source_voids'].append({'source_row_id':rid,'target_kind':kind,'source_record':copy.deepcopy(row)})
    else:after[kind]=[r for r in after[kind] if r['id']!=rid]
    store.enrich_legacy(after);store.validate_global(after)
    on=max(datetime.now(timezone(timedelta(hours=8))).date().isoformat(),row.get('date') or row.get('end') or '')
    ids=row.get('legacy_members') or [row['batch_id']] if row.get('batch_id') else row.get('legacy_members') or []
    impacts={'as_of':on,'farm_before':herd(data['batches'],data['movements'],on),'farm_after':herd(after['batches'],after['movements'],on)}
    if ids:
        impacts['selected_before']=herd(data['batches'],data['movements'],on,ids);impacts['selected_after']=herd(after['batches'],after['movements'],on,ids)
    if kind=='weights':
        impacts['weighed_before']=combined_weights(data['weights']+[r for r in source_history(data,'weights') if r.get('batch_id')==row.get('batch_id')],row.get('batch_id'))
        impacts['weighed_after']=combined_weights(after['weights']+[r for r in source_history(after,'weights') if r.get('batch_id')==row.get('batch_id')],row.get('batch_id'))
    if kind=='deliveries':impacts['delivery_kg_removed']=row['kg']
    if kind=='feed_orders':impacts['feed_order_kg_removed']=row['kg']
    if kind=='usages':impacts['usage_kg_removed']=consumption(row,receipts(data))
    batch=next((b for b in data['batches'] if b['id']==row.get('batch_id')),None)
    if batch:
        for label,d in [('performance_before',data),('performance_after',after)]:
            b=next(b for b in d['batches'] if b['id']==batch['id'])
            impacts[label]=performance(b,d['batches'],d['movements'],d['weights']+[w for w in source_history(d,'weights') if w.get('batch_id')==b['id']],d['usages'],receipts(d),on)
    return {'record':row,'source':source,'preview_token':token(data),'impact':impacts}


def void_record(store,user,payload,key):
    store.require(user,True)
    if not isinstance(payload,dict) or not isinstance(key,str) or not 16<=len(key)<=128:raise Problem('idempotency_required')
    reason=payload.get('reason');kind=payload.get('kind');rid=payload.get('id')
    if not isinstance(reason,str) or not 1<=len(reason.strip())<=500:raise Problem('void_reason_required')
    fp=hashlib.sha256(encode(['void',payload]).encode()).hexdigest();store.backup_sqlite(label='before-record-void');db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE');prior=db.execute('SELECT * FROM requests WHERE user_id=? AND key=?',(user['id'],key)).fetchone()
        if prior:
            if prior['fingerprint']!=fp:raise Problem('idempotency_mismatch',409)
            return json.loads(prior['result'])
        data=store.snapshot(db,include_source=False);preview=void_preview(store,user,data,kind,rid)
        if payload.get('preview_token')!=preview['preview_token']:raise Problem('revision_conflict',409)
        row=preview['record']
        if preview['source']:
            content={'id':str(uuid.uuid5(uuid.NAMESPACE_URL,'source-void:'+kind+':'+rid)),'revision':1,'target_kind':kind,'source_row_id':rid,'source_record':row,'reason':reason.strip(),'created_at':now(),'created_by':user['id'],'updated_at':now()}
            db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,1,?)',('source_voids',content['id'],encode(content)))
        else:
            if kind=='movements':
                from .history import source_history
                for source in source_history(data,kind,include_matched=True):
                    if rid not in source.get('matched_manual',[]):continue
                    vid=str(uuid.uuid5(uuid.NAMESPACE_URL,'source-void:'+kind+':'+source['id']))
                    if db.execute('SELECT 1 FROM records WHERE id=?',(vid,)).fetchone():continue
                    suppression={'id':vid,'revision':1,'target_kind':kind,'source_row_id':source['id'],'source_record':source,'reason':reason.strip(),'created_by':user['id'],'created_at':now(),'updated_at':now()}
                    db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,1,?)',('source_voids',vid,encode(suppression)))
            content=row|{'revision':row['revision']+1,'updated_at':now(),'void_reason':reason.strip()}
            db.execute('UPDATE records SET deleted=1,revision=?,data=? WHERE id=?',(content['revision'],encode(content),rid))
        store.audit(db,user['id'],'void-source' if preview['source'] else 'void',kind,rid,row,{'reason':reason.strip(),'impact':preview['impact']})
        result={'id':rid,'voided':True};db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],key,fp,encode(result)))
        snapshot=store.snapshot(db,include_source=False);store.validate_global(snapshot);sequence=db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0];db.commit()
        return result|{'_snapshot':snapshot,'_sequence':sequence}
    finally:db.close()


def save_weighing(store,user,payload,key):
    store.require(user)
    if not isinstance(payload,dict) or not isinstance(key,str) or not 16<=len(key)<=128:raise Problem('idempotency_required')
    try:sid=str(uuid.UUID(payload['session_id']))
    except (KeyError,ValueError,TypeError):raise Problem('invalid_weighing')
    pens=payload.get('pens')
    if not isinstance(pens,list) or not 1<=len(pens)<=100 or any(not isinstance(p,dict) for p in pens):raise Problem('invalid_weighing')
    fp=hashlib.sha256(encode(['weighing',payload]).encode()).hexdigest();db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE');prior=db.execute('SELECT * FROM requests WHERE user_id=? AND key=?',(user['id'],key)).fetchone()
        if prior:
            if prior['fingerprint']!=fp:raise Problem('idempotency_mismatch',409)
            return json.loads(prior['result'])
        stored=[json.loads(r['data']) for r in db.execute("SELECT data FROM records WHERE kind='weights'")];existing=[r for r in stored if r.get('session_id')==sid]
        data=store.snapshot(db,include_source=False)
        if existing:
            if any(r.get('session_fingerprint')!=fp or r['created_by']!=user['id'] for r in existing):raise Problem('revision_conflict',409)
            return {'session_id':sid,'ids':[r['id'] for r in existing],'already_saved':True}
        no=1+max([r.get('session_number',0) for r in stored if r['batch_id']==payload.get('batch_id')]+[0]);ids=[]
        for i,pen in enumerate(pens):
            values={k:payload[k] for k in ('date','batch_id','age_days','sampling','note','representative') if k in payload};values.update({k:pen[k] for k in ('pen','section','individual_kg','count','total_kg') if k in pen})
            if values.get('individual_kg'):
                values.pop('count',None);values.pop('total_kg',None)
            cleaned=store.validate('weights',values,data,user)
            output=cleaned|{'id':str(uuid.uuid5(uuid.UUID(sid),str(i))),'revision':1,'session_id':sid,'session_number':no,'session_fingerprint':fp,'created_by':user['id'],'created_at':now(),'updated_at':now()}
            data['weights'].append(output);ids.append(output['id']);db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,1,?)',('weights',output['id'],encode(output)));store.audit(db,user['id'],'create-weighing','weights',output['id'],None,output)
        store.validate_global(data);result={'session_id':sid,'session_number':no,'ids':ids};db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],key,fp,encode(result)));sequence=db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0];db.commit()
        return result|{'_snapshot':data,'_sequence':sequence}
    finally:db.close()
