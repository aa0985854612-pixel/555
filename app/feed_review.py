"""Review incoming feed quantities against history before an atomic write."""
import copy,hashlib,json,uuid
from .store import Problem,encode,now


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



def _preview(store,user,body,db,data):
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
    deleted=[json.loads(r['data']) for r in db.execute("SELECT data FROM records WHERE kind='feed_orders' AND deleted=1")]
    deleted=[r for r in deleted if r['date']==incoming['date'] and _same_scope(incoming,r,data)]
    bins={incoming.get('feed_bin_id')}|{r.get('feed_bin_id') for r in matches}
    linked=set(incoming.get('target_batch_ids',[]))|{a['batch_id'] for a in incoming.get('allocations',[])}
    for r in matches:linked.update(r.get('target_batch_ids',[]));linked.update(a['batch_id'] for a in r.get('allocations',[]))
    state=[[(r['id'],r['revision']) for r in matches],[(r['id'],r['revision']) for r in data['feed_bins'] if r['id'] in bins],[(r['id'],r['revision']) for r in data['batches'] if r['id'] in linked]]
    proof=hashlib.sha256(encode([user['id'],incoming,rid,state,[(r['id'],r['revision']) for r in deleted]]).encode()).hexdigest()
    return {'record':incoming,'rid':rid,'preview_token':proof,'matches':[r|{'can_update':user['role']=='admin' or r.get('created_by')==user['id']} for r in matches],
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
        data['feed_orders'].append(output);store.validate_global(data)
        if previous:db.execute('UPDATE records SET revision=?,data=? WHERE id=?',(output['revision'],encode(output),output['id']))
        else:db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,1,?)',('feed_orders',output['id'],encode(output)))
        store.audit(db,user['id'],'update' if previous else 'create','feed_orders',output['id'],previous,output)
        result={'id':output['id'],'revision':output['revision'],'decision':decision};db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],key,fp,encode(result)))
        sequence=db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0];db.commit()
        return result|{'_snapshot':data,'_sequence':sequence}
    finally:db.close()
