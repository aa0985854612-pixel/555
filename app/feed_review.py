"""Review incoming feed quantities against history before an atomic write."""
import copy,hashlib,json,uuid
from .store import Problem,encode,now
from .feed_receipts import orders_are_arrivals,stock_warnings


def _same_scope(a,b,data):
    if a.get('feed_bin_id') and b.get('feed_bin_id'):return a['feed_bin_id']==b['feed_bin_id']
    batches={r['id']:r for r in data['batches']}
    def barns(row):
        if row.get('feed_bin_id'):
            bin=next((x for x in data['feed_bins'] if x['id']==row['feed_bin_id']),None)
            return set(bin['barn_ids']) if bin else set()
        return {batches[x['batch_id']]['barn_id'] for x in row.get('allocations',[]) if x['batch_id'] in batches}
    aa,bb=barns(a),barns(b)
    return aa==bb



def _preview(store,user,body,db,data,deleted_rows=None):
    store.require(user)
    if not isinstance(body,dict) or not isinstance(body.get('record'),dict):raise Problem('invalid_feed_review')
    rid=body.get('rid') or None
    if rid is not None and not isinstance(rid,str):raise Problem('invalid_feed_review')
    previous=next((r for r in data['feed_orders'] if r['id']==rid),None)
    if rid:
        if not previous:raise Problem('not_found',404)
        if user['role']=='staff' and previous.get('created_by')!=user['id']:raise Problem('forbidden',403)
        if body['record'].get('revision')!=previous['revision']:raise Problem('revision_conflict',409)
    incoming=store.validate('feed_orders',body['record'],data,user,previous)
    matches=[r for r in data['feed_orders'] if r['date']==incoming['date'] and _same_scope(incoming,r,data)]
    if previous and not any(r['id']==rid for r in matches):matches.insert(0,previous)
    deleted=deleted_rows if deleted_rows is not None else [json.loads(r['data']) for r in db.execute("SELECT data FROM records WHERE kind='feed_orders' AND deleted=1")]
    deleted=[r for r in deleted if r['date']==incoming['date'] and _same_scope(incoming,r,data)]
    bins={incoming.get('feed_bin_id')}|{r.get('feed_bin_id') for r in matches}
    linked=set(incoming.get('target_batch_ids',[]))|{a['batch_id'] for a in incoming.get('allocations',[])}
    for r in matches:linked.update(r.get('target_batch_ids',[]));linked.update(a['batch_id'] for a in r.get('allocations',[]))
    state=[[(r['id'],r['revision']) for r in matches],[(r['id'],r['revision']) for r in data['feed_bins'] if r['id'] in bins],[(r['id'],r['revision']) for r in data['batches'] if r['id'] in linked]]
    warnings=[]
    if orders_are_arrivals():
        from .operations import token
        state.append(token(data))
        after=copy.deepcopy(data);old=previous or (matches[0] if len(matches)==1 else None)
        after['feed_orders']=[r for r in after['feed_orders'] if not old or r['id']!=old['id']]+[incoming|{'id':'receipt-preview'}]
        warnings=stock_warnings(data,after,[incoming,old])
        if old and not rid:
            added=copy.deepcopy(data);added['feed_orders'].append(incoming|{'id':'receipt-add-preview'})
            if 'quick_capacity_exceeded' in stock_warnings(data,added,[incoming]) and 'quick_capacity_exceeded' not in warnings:
                warnings.append('feed_receipt_possible_capacity')
    from .feed_allocation import automatic_allocation,allocation_policy
    plan=automatic_allocation(incoming,data)
    proof=hashlib.sha256(encode([allocation_policy(),plan,orders_are_arrivals(),user['id'],incoming,rid,state,[(r['id'],r['revision']) for r in deleted]]).encode()).hexdigest()
    return {'automatic_allocation':plan,'receipt_warnings':warnings,'record':incoming,'rid':rid,'preview_token':proof,'matches':[r|{'can_update':user['role']=='admin' or r.get('created_by')==user['id']} for r in matches],
            'voided_matches':[{'id':r['id'],'date':r['date'],'kg':r['kg'],'vendor':r.get('vendor',''),'item':r.get('item','')} for r in deleted]}


def preview_feed_order(store,user,body):
    store.require(user);db=store.connect()
    try:
        db.execute('BEGIN');return _preview(store,user,body,db,store.snapshot(db,include_source=False))
    finally:db.close()


def save_reviewed_feed(store,user,body,key):
    store.require(user)
    if not isinstance(body,dict) or not isinstance(key,str) or not 16<=len(key)<=128:raise Problem('idempotency_required')
    fp=hashlib.sha256(encode(['feed-review',body]).encode()).hexdigest();db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE');prior=db.execute('SELECT * FROM requests WHERE user_id=? AND key=?',(user['id'],key)).fetchone()
        if prior:
            if prior['fingerprint']!=fp:raise Problem('idempotency_mismatch',409)
            return json.loads(prior['result'])
        data=store.snapshot(db,include_source=False);preview=_preview(store,user,body,db,data)
        if body.get('preview_token')!=preview['preview_token']:raise Problem('revision_conflict',409)
        output,previous=_apply_preview(store,user,body,preview,data)
        store.validate_global(data)
        if previous:db.execute('UPDATE records SET revision=?,data=? WHERE id=?',(output['revision'],encode(output),output['id']))
        else:db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,1,?)',('feed_orders',output['id'],encode(output)))
        store.audit(db,user['id'],'update' if previous else 'create','feed_orders',output['id'],previous,output)
        result={'id':output['id'],'revision':output['revision'],'decision':body['decision']};db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],key,fp,encode(result)))
        sequence=db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0];db.commit()
        return result|{'_snapshot':data,'_sequence':sequence}
    finally:db.close()


def _apply_preview(store,user,body,preview,data):
    decision=body.get('decision');previous=None
    if decision=='update':
        previous=next((r for r in preview['matches'] if r['id']==body.get('existing_id')),None)
        if not previous or (preview['rid'] and previous['id']!=preview['rid']):raise Problem('invalid_feed_review')
        if not previous['can_update']:raise Problem('forbidden',403)
        previous={k:v for k,v in previous.items() if k!='can_update'}
        data['feed_orders']=[r for r in data['feed_orders'] if r['id']!=previous['id']]
    elif decision=='create':
        if preview['rid']:raise Problem('invalid_feed_review')
        if (preview['matches'] or preview['voided_matches']) and body.get('new_entry_confirmed') is not True:raise Problem('feed_review_decision_required')
    else:raise Problem('feed_review_decision_required')
    record=copy.deepcopy(body['record'])
    # Keep prior notes when a source transcription corrects only quantities.
    if previous and not preview['rid'] and previous.get('note') and previous['note']!=record.get('note') and previous['note'] not in record.get('note',''):
        record['note']=previous['note']+'\n'+record.get('note','')
    cleaned=store.validate('feed_orders',record,data,user,previous);stamp=now()
    output=cleaned|{'id':previous['id'] if previous else str(uuid.uuid4()),'revision':previous['revision']+1 if previous else 1,
        'created_at':previous.get('created_at',stamp) if previous else stamp,'created_by':previous.get('created_by',user['id']) if previous else user['id'],'updated_at':stamp}
    data['feed_orders'].append(output)
    return output,previous


def _bulk_preview(store,user,body,db,data):
    from .domain import day
    store.require(user)
    if not isinstance(body,dict) or not isinstance(body.get('rows'),list) or not 1<=len(body['rows'])<=50:raise Problem('invalid_feed_bulk')
    day(body.get('date'))
    deleted=[json.loads(r['data']) for r in db.execute("SELECT data FROM records WHERE kind='feed_orders' AND deleted=1")]
    previews=[]
    for row in body['rows']:
        if not isinstance(row,dict) or not isinstance(row.get('record'),dict) or row['record'].get('date')!=body['date']:raise Problem('invalid_feed_bulk')
        previews.append(_preview(store,user,row,db,data,deleted))
    for i,p in enumerate(previews):p['queue_matches']=[j for j,other in enumerate(previews) if j!=i and _same_scope(p['record'],other['record'],data)]
    warnings=[]
    if orders_are_arrivals():
        after=copy.deepcopy(data);changes=[]
        for i,p in enumerate(previews):
            old=next((r for r in p['matches'] if r['id']==p['rid']),None) if p['rid'] else (p['matches'][0] if len(p['matches'])==1 else None)
            after['feed_orders']=[r for r in after['feed_orders'] if not old or r['id']!=old['id']]
            after['feed_orders'].append(p['record']|{'id':'bulk-receipt-preview-'+str(i)});changes.extend([p['record'],old])
        warnings=stock_warnings(data,after,changes)
        if any(p['matches'] and not p['rid'] for p in previews):
            added=copy.deepcopy(data)
            for i,p in enumerate(previews):
                if p['rid']:added['feed_orders']=[r for r in added['feed_orders'] if r['id']!=p['rid']]
                added['feed_orders'].append(p['record']|{'id':'bulk-add-preview-'+str(i)})
            if 'quick_capacity_exceeded' in stock_warnings(data,added,changes) and 'quick_capacity_exceeded' not in warnings:
                warnings.append('feed_receipt_possible_capacity')
    proof=hashlib.sha256(encode([user['id'],body['date'],warnings,[(p['preview_token'],p['queue_matches']) for p in previews]]).encode()).hexdigest()
    return {'receipt_warnings':warnings,'date':body['date'],'rows':previews,'preview_token':proof,'count':len(previews),'total_kg':sum(p['record']['kg'] for p in previews)}


def preview_feed_bulk(store,user,body):
    store.require(user);db=store.connect()
    try:
        db.execute('BEGIN');return _bulk_preview(store,user,body,db,store.snapshot(db,include_source=False))
    finally:db.close()


def save_feed_bulk(store,user,body,key):
    store.require(user)
    if not isinstance(body,dict) or not isinstance(key,str) or not 16<=len(key)<=128:raise Problem('idempotency_required')
    fp=hashlib.sha256(encode(['feed-bulk',body]).encode()).hexdigest();db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE');prior=db.execute('SELECT * FROM requests WHERE user_id=? AND key=?',(user['id'],key)).fetchone()
        if prior:
            if prior['fingerprint']!=fp:raise Problem('idempotency_mismatch',409)
            return json.loads(prior['result'])
        data=store.snapshot(db,include_source=False);p=_bulk_preview(store,user,body,db,data)
        if body.get('preview_token')!=p['preview_token']:raise Problem('revision_conflict',409)
        targets=set();outputs=[]
        for incoming,preview in zip(body['rows'],p['rows']):
            if incoming.get('decision')=='update':
                rid=incoming.get('existing_id')
                if rid in targets:raise Problem('feed_bulk_same_target')
                targets.add(rid)
            if preview['queue_matches'] and incoming.get('decision')=='create' and incoming.get('new_entry_confirmed') is not True:raise Problem('feed_review_decision_required')
            output,previous=_apply_preview(store,user,incoming,preview,data)
            if previous:db.execute('UPDATE records SET revision=?,data=? WHERE id=?',(output['revision'],encode(output),output['id']))
            else:db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,1,?)',('feed_orders',output['id'],encode(output)))
            store.audit(db,user['id'],'update' if previous else 'create','feed_orders',output['id'],previous,output);outputs.append({'id':output['id'],'revision':output['revision'],'decision':incoming['decision']})
        store.validate_global(data)
        result={'ids':[o['id'] for o in outputs],'records':outputs,'count':len(outputs),'draft_id':body.get('draft_id')}
        db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],key,fp,encode(result)));seq=db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0];db.commit()
        return result|{'_snapshot':data,'_sequence':seq}
    finally:db.close()
