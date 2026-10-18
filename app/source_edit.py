"""Reversible, audited corrections layered over immutable imported movements."""
import copy,hashlib,json
from datetime import datetime,timezone,timedelta
from .domain import Invalid,day,herd

FIELDS=('date','quantity','batch_id','note','outgoing_destination')

def edits(data):
    return [e for b in data.get('workbooks',[]) for e in b.get('source_movement_edits',[])]


def apply_edit(row,data):
    edit=next((e for e in edits(data) if e['source_row_id']==row['id']),None)
    if not edit:return row
    b=next((b for b in data['batches'] if b['id']==edit['changes']['batch_id']),None)
    return row|edit['changes']|{'barn_id':b['barn_id'] if b else None,'barn_number':b.get('legacy_barn') if b else None,'source_edit':edit}


def base_rows(data):
    from .history import source_history
    return {r['id']:r for r in source_history(data,include_voided=True,include_matched=True,apply_movement_edits=False)}


def validate_edits(data):
    raw=None;seen=set()
    for book in data.get('workbooks',[]):
        items=book.get('source_movement_edits',[])
        if not isinstance(items,list) or len(items)>5000:raise Invalid('invalid_source_edit')
        if items and raw is None:raw=base_rows(data)
        for edit in items:
            if not isinstance(edit,dict) or set(edit)!={'source_row_id','changes','reason'}:raise Invalid('invalid_source_edit')
            rid=edit['source_row_id'];row=raw.get(rid)
            if not row or rid in seen or row.get('archive') or row.get('unresolved') or row.get('matched_manual') or row['type'] not in ('sale','death','cull'):raise Invalid('invalid_source_edit')
            seen.add(rid)
            root=next((b for b in data['workbooks'] if b['id']==row['legacy_source']),None)
            if not root or (root.get('base_book_id') or root['id'])!=book['id']:raise Invalid('invalid_source_edit')
            c=edit['changes']
            if not isinstance(c,dict) or set(c)!=set(FIELDS):raise Invalid('invalid_source_edit')
            day(c['date'])
            if type(c['quantity']) is not int or c['quantity']<=0 or c['quantity']>1000000:raise Invalid('invalid_source_edit')
            b=next((b for b in data['batches'] if b['id']==c['batch_id']),None)
            if c['batch_id'] is not None and (not b or b['id'] not in row['legacy_members']):raise Invalid('source_edit_cohort_locked')
            if c['date']<(b or row)['entry_date']:raise Invalid('before_entry')
            if not isinstance(c['note'],str) or len(c['note'])>2000 or c['outgoing_destination'] not in ('','新北','南投','嘉義') or (row['type']=='death' and c['outgoing_destination']):raise Invalid('invalid_source_edit')
            if not isinstance(edit['reason'],str) or not 1<=len(edit['reason'].strip())<=500:raise Invalid('source_edit_reason_required')


def adjust_snapshots(data):
    if not edits(data):return
    raw=base_rows(data)
    for edit in edits(data):
        old=raw.get(edit['source_row_id'])
        if not old:continue
        new=apply_edit(old,data);field={'sale':'sold','death':'dead','cull':'culled'}[old['type']]
        for b in data['batches']:
            if b['id'] not in old['legacy_members'] or not b.get('legacy_group'):continue
            for on,snapshot in b['legacy_group']['snapshots'].items():
                delta=(new['quantity'] if new['date']<=on else 0)-(old['quantity'] if old.get('date') and old['date']<=on else 0)
                snapshot[field]+=delta;snapshot['remaining']-=delta
                if snapshot[field]<0 or snapshot['remaining']<0:raise Invalid('negative_stock')
            for on,v in b['legacy_values'].items():
                # A newly assigned formerly unknown event cannot establish all other barn totals.
                if new['batch_id'] is None and new['date']<=on:v[field]=None
                elif v.get(field) is not None:
                    v[field]+=(new['quantity'] if new['batch_id']==b['id'] and new['date']<=on else 0)-(old['quantity'] if old['batch_id']==b['id'] and old.get('date') and old['date']<=on else 0)
            for on,heads in b['legacy_heads'].items():
                oldq=old['quantity'] if old.get('date') and old['date']<=on else 0;newq=new['quantity'] if new['date']<=on else 0
                if (oldq and not old['batch_id']) or (newq and not new['batch_id']):
                    if (oldq,newq,old['batch_id'])!=(newq,newq,new['batch_id']):b['legacy_heads'][on]=None
                elif heads is not None:b['legacy_heads'][on]+= (oldq if old['batch_id']==b['id'] else 0)-(newq if new['batch_id']==b['id'] else 0)


def duplicates(data,values,rid=None):
    from .history import source_history
    if values.get('type') not in ('sale','death','cull'):return []
    rows={r['id']:r for r in source_history(data)+data['movements']}
    return [r for r in rows.values() if r['id']!=rid and (values.get('batch_id') is not None or r.get('cohort')==values.get('cohort')) and all(r.get(k)==values.get(k) for k in ('date','batch_id','type','quantity'))]


def duplicate_token(data,values,rid=None):
    rows=duplicates(data,values,rid)
    return hashlib.sha256(json.dumps([values,[(r['id'],r.get('revision',1),[r.get(k) for k in FIELDS]) for r in rows]],sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def preview(store,user,payload,data=None):
    from .store import Problem
    from .operations import token
    store.require(user,True)
    if not isinstance(payload,dict):raise Problem('invalid_source_edit')
    data=data or store.snapshot(include_source=False)
    from .history import source_history
    row=next((r for r in source_history(data) if r['id']==payload.get('id')),None)
    if not row:raise Problem('not_found',404)
    changes={k:payload.get(k,row.get(k,'' if k in ('note','outgoing_destination') else None)) for k in FIELDS}
    edit={'source_row_id':row['id'],'changes':changes,'reason':payload.get('reason','')}
    after=copy.deepcopy(data);owner=next(b for b in after['workbooks'] if b['id']==row['legacy_source']);owner=next(b for b in after['workbooks'] if b['id']==(owner.get('base_book_id') or owner['id']))
    owner['source_movement_edits']=[e for e in owner.get('source_movement_edits',[]) if e['source_row_id']!=row['id']]+[edit]
    validate_edits(after);store.enrich_legacy(after);store.validate_global(after)
    on=max(datetime.now(timezone(timedelta(hours=8))).date().isoformat(),row.get('date') or '',changes['date'])
    before=herd(data['batches'],data['movements'],on);result=herd(after['batches'],after['movements'],on)
    matches=duplicates(after,changes|{'type':row['type'],'cohort':row['cohort']},row['id'])
    return {'record':row,'changes':changes,'owner_id':owner['id'],'edit':edit,'preview_token':token(data),'duplicates':matches,'impact':{'as_of':on,'before':before,'after':result,'barns':[{'id':b['id'],'barn':next(x['name'] for x in data['barns'] if x['id']==b['barn_id']),'before':herd(data['batches'],data['movements'],on,[b['id']])['remaining'],'after':herd(after['batches'],after['movements'],on,[b['id']])['remaining']} for b in data['batches'] if b['id'] in row['legacy_members']]}}


def save(store,user,payload,key):
    from .store import Problem,encode,now
    store.require(user,True)
    if not isinstance(payload,dict) or not isinstance(key,str) or not 16<=len(key)<=128:raise Problem('idempotency_required')
    fp=hashlib.sha256(encode(['source-edit',payload]).encode()).hexdigest();store.backup_sqlite(label='before-source-edit');db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE');prior=db.execute('SELECT * FROM requests WHERE user_id=? AND key=?',(user['id'],key)).fetchone()
        if prior:
            if prior['fingerprint']!=fp:raise Problem('idempotency_mismatch',409)
            return json.loads(prior['result'])
        data=store.snapshot(db,include_source=False);p=preview(store,user,payload,data)
        if p['preview_token']!=payload.get('preview_token'):raise Problem('revision_conflict',409)
        if p['duplicates'] and payload.get('confirm_duplicate') is not True:raise Problem('movement_duplicate',409,p['duplicates'])
        # Do not edit a source event already incorporated in a saved void.
        if any(v['source_row_id']==payload['id'] for v in data.get('source_voids',[])):raise Problem('already_voided',409)
        stored=db.execute('SELECT data FROM records WHERE id=?',(p['owner_id'],)).fetchone();book=json.loads(stored['data']);before=copy.deepcopy(book.get('source_movement_edits',[]))
        book['source_movement_edits']=[e for e in before if e['source_row_id']!=payload['id']]+[p['edit']];book['revision']+=1;book['updated_at']=now()
        db.execute('UPDATE records SET revision=?,data=? WHERE id=?',(book['revision'],encode(book),book['id']))
        store.audit(db,user['id'],'edit-source-movement','workbooks',book['id'],{'record':p['record'],'edits':before},{'record':p['changes'],'reason':payload['reason'],'impact':p['impact'],'edits':book['source_movement_edits']})
        # A source death correction supersedes any zero-death confirmation at its new location.
        if p['record']['type']=='death':
            for check in data.get('daily_checks',[]):
                if check['batch_id']==p['changes']['batch_id'] and check['date']==p['changes']['date'] and check['status']=='no_deaths':
                    old=dict(check);check.update(status='cancelled',note='更正死亡後自動撤銷無死亡確認',revision=check['revision']+1,updated_at=now());db.execute('UPDATE records SET revision=?,data=? WHERE id=?',(check['revision'],encode(check),check['id']));store.audit(db,user['id'],'supersede-zero-check','daily_checks',check['id'],old,check)
        result={'id':payload['id'],'saved':True};db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],key,fp,encode(result)));snapshot=store.snapshot(db,include_source=False);store.validate_global(snapshot);seq=db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0];db.commit()
        return result|{'_snapshot':snapshot,'_sequence':seq}
    finally:db.close()
