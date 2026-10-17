"""Read-only quality/daily review. Patrol acknowledgements never alter herd stock."""
from datetime import datetime, timezone, timedelta
from .domain import day, age, herd, Invalid
from .history import source_history, cohort_key


def farm_today():
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


def death_state(data, batch, on, events=None):
    events=events if events is not None else source_history(data,'movements')+data['movements']
    related=[r for r in events if r.get('type')=='death' and not r.get('archive') and
        (r.get('batch_id')==batch['id'] or (not r.get('batch_id') and batch['id'] in r.get('legacy_members',[])))]
    known=sum(r['quantity'] for r in related if r.get('batch_id')==batch['id'] and r.get('date')==on)
    baseline=batch.get('legacy_group',{}).get('as_of','')
    uncertain=any((r.get('date')==on and not r.get('batch_id')) or
        (not r.get('date') and on<=baseline) for r in related)
    return {'known':known,'uncertain':uncertain}


def daily_review(data, on):
    day(on)
    events=list({r['id']:r for r in source_history(data,'movements')+data['movements']}.values())
    dated=[r for r in events if r.get('date')==on]
    checks={(r['batch_id'],r['date']):r for r in data.get('daily_checks',[])}
    barns={b['id']:b['name'] for b in data['barns']}
    rows=[]
    for b in sorted(data['batches'],key=lambda b:(barns[b['barn_id']],b['entry_date'])):
        if b['entry_date']>on:continue
        own=[r for r in dated if r.get('batch_id')==b['id'] or r.get('target_batch_id')==b['id']]
        check=checks.get((b['id'],on))
        if b['status']!='active' and not own and not check:continue
        state=death_state(data,b,on,events)
        status='death_recorded' if state['known'] else 'unresolved' if state['uncertain'] else 'no_deaths' if check and check['status']=='no_deaths' else 'not_reported'
        rows.append({'batch_id':b['id'],'barn_id':b['barn_id'],'barn':barns[b['barn_id']],'batch':b['name'],'cohort':cohort_key(b),
            'status':status,'deaths':state['known'],'check':check,'events':own,
            'can_confirm':b['status']=='active' and on<=farm_today() and on>b.get('legacy_group',{}).get('as_of','') and status=='not_reported',
            'check_superseded':bool(check and ((check['status']=='no_deaths' and (state['known'] or state['uncertain'])) or check.get('note')=='補登死亡後自動撤銷無死亡確認'))})
    return {'date':on,'events':dated,'rows':rows,'unassigned':[r for r in dated if not r.get('batch_id')],
        'totals':{typ:sum(r['quantity'] for r in dated if r['type']==typ) for typ in ('death','sale','cull')},
        'counts':{status:sum(r['status']==status for r in rows) for status in ('no_deaths','death_recorded','not_reported','unresolved')}}


def check_coverage(data, ids, start, end):
    """Count batch-days without expanding long date ranges or inventing zero deaths.

    Historical snapshots have no patrol acknowledgement. Only currently active
    batches after their snapshot baseline are eligible; ended dates are unknown.
    Death records report known deaths, not a completed patrol.
    """
    lo,hi=day(start),min(day(end),day(farm_today()))
    wanted=set(ids);expected=confirmed=death_days=0
    events=source_history(data,'movements')+data['movements']
    for b in data['batches']:
        if b['id'] not in wanted or b['status']!='active':continue
        first=max(lo,day(b['entry_date']))
        if b.get('legacy_group'):first=max(first,day(b['legacy_group']['as_of'])+timedelta(days=1))
        if first>hi:continue
        expected+=(hi-first).days+1
        deaths={r['date'] for r in events if r.get('type')=='death' and r.get('batch_id')==b['id'] and r.get('date') and first.isoformat()<=r['date']<=hi.isoformat()}
        uncertain={r['date'] for r in events if r.get('type')=='death' and not r.get('batch_id') and b['id'] in r.get('legacy_members',[]) and r.get('date') and first.isoformat()<=r['date']<=hi.isoformat()}
        zero={r['date'] for r in data.get('daily_checks',[]) if r['batch_id']==b['id'] and r['status']=='no_deaths' and first.isoformat()<=r['date']<=hi.isoformat()}-deaths-uncertain
        confirmed+=len(zero);death_days+=len(deaths)
    return {'expected_batch_days':expected,'confirmed_zero_batch_days':confirmed,'death_recorded_batch_days':death_days,
        'awaiting_batch_days':expected-confirmed-death_days,'basis':'current_active_batches_after_source_baseline','zero_is_explicit_only':True}


def data_quality(data, on, dashboard=None):
    """Present source gaps without deriving false entry counts or rewriting data."""
    barns={b['id']:b['name'] for b in data['barns']}
    metrics={r['id']:r['herd'] for r in (dashboard or {}).get('batches',[])}
    issues=[]
    for b in data['batches']:
        if b['status']!='active' or b['entry_date']>on:continue
        h=metrics.get(b['id']) or herd(data['batches'],data['movements'],on,[b['id']])
        fields=[]
        if b.get('entry_count') is None:fields.append('missing_entry_count')
        if b.get('entry_mean_kg') is None:fields.append('missing_entry_mean')
        if age(b,on) is None:fields.append('missing_age')
        if h['dead'] is None:fields.append('missing_death_allocation')
        if h['remaining'] is None:fields.append('missing_stock')
        if h.get('denominator') is not None and h['remaining'] is not None and h['remaining']>h['denominator']+max(0,h['adjustment']):fields.append('stock_exceeds_entry')
        if fields:issues.append({'id':'batch:'+b['id'],'kind':'batches','batch_id':b['id'],'barn':barns[b['barn_id']],'name':b['name'],'entry_date':b['entry_date'],'fields':fields,'remaining':h['remaining'],'denominator':h.get('denominator')})
    for kind in ('movements','weights'):
        for r in source_history(data,kind):
            fields=[]
            if not r.get('date'):fields.append('missing_date')
            # Archived cohorts have no active batch ID. An explicit original
            # barn is sufficient; never create a new batch just to clear a flag.
            if not r.get('batch_id') and not (r.get('archive') and r.get('barn_id')):fields.append('missing_barn_allocation')
            if kind=='weights' and r.get('count') is None:fields.append('source_mean_only')
            if fields:issues.append({'id':'source:'+r['id'],'kind':kind,'record_id':r['id'],'fields':fields,'date':r.get('date'),'name':r.get('legacy_batch',''),'source_cell':r.get('source_cell',''),'note':r.get('note',''),'archive':r.get('archive',False)})
    for book in data.get('workbooks',[]):
        for c in book.get('pending_cohorts',[]):
            if c.get('decision')=='keep_app':continue
            issues.append({'id':'conflict:'+book['id']+':'+c['cohort'],'kind':'workbooks','fields':['source_conflict'],'name':c.get('cohort',''),'source_cell':book['filename']})
    for o in data.get('feed_orders',[]):
        if not o['allocations'] and (not o.get('feed_bin_id') or len(o.get('target_batch_ids',[]))!=len(o['feed_bin_snapshot']['barn_ids'])):issues.append({'id':'order:'+o['id'],'kind':'feed_orders','fields':['unassigned_feed'],'date':o['date'],'name':o.get('note',''),'record_id':o['id']})
    return {'as_of':on,'items':issues,'count':len(issues),'active_batches_with_gaps':sum(i['kind']=='batches' for i in issues)}


def bulk_check_preview(data, user, on):
    """Bind one user's all-farm acknowledgement to the reviewed eligible scope."""
    import hashlib
    from .store import encode
    report=daily_review(data,on);eligible=[];skipped=[]
    for row in report['rows']:
        check=row['check']
        own=not check or user['role']=='admin' or check['created_by']==user['id']
        item={k:row[k] for k in ('batch_id','barn_id','barn','batch','status','deaths')}
        if row['can_confirm'] and own:eligible.append(item)
        else:skipped.append(item|{'reason':row['status'] if row['status']!='not_reported' else 'other_owner' if not own else 'outside_check_period'})
    signature=[on,user['id'],user['role'],[{k:r[k] for k in ('batch_id','barn_id','barn','batch','status','deaths','can_confirm','check')} for r in report['rows']]]
    return {'date':on,'eligible':eligible,'skipped':skipped,'preview_token':hashlib.sha256(encode(signature).encode()).hexdigest()}


def save_bulk_checks(store, user, payload, key):
    """One transaction for all eligible barns, including audit and request receipt."""
    import hashlib,uuid
    from .store import Problem,encode,now
    store.require(user)
    if not isinstance(payload,dict) or not isinstance(key,str) or not 16<=len(key)<=128:raise Problem('idempotency_required')
    try:day(payload.get('date'))
    except Invalid:raise Problem('invalid_date')
    fp=hashlib.sha256(encode(['bulk-daily-checks',payload]).encode()).hexdigest();db=store.connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        prior=db.execute('SELECT * FROM requests WHERE user_id=? AND key=?',(user['id'],key)).fetchone()
        if prior:
            if prior['fingerprint']!=fp:raise Problem('idempotency_mismatch',409)
            import json
            return json.loads(prior['result'])
        data=store.snapshot(db,include_source=False);preview=bulk_check_preview(data,user,payload['date'])
        if payload.get('preview_token')!=preview['preview_token']:raise Problem('daily_preview_changed',409)
        confirmed=[]
        for item in preview['eligible']:
            old=next((r for r in data['daily_checks'] if r['batch_id']==item['batch_id'] and r['date']==payload['date']),None)
            others=data|{'daily_checks':[r for r in data['daily_checks'] if not old or r['id']!=old['id']]}
            cleaned=store.validate('daily_checks',{'date':payload['date'],'batch_id':item['batch_id'],'status':'no_deaths','note':''},others,user)
            output=cleaned|{'id':old['id'] if old else str(uuid.uuid4()),'revision':old['revision']+1 if old else 1,
                'created_at':old['created_at'] if old else now(),'created_by':old['created_by'] if old else user['id'],'updated_at':now()}
            db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,data=excluded.data',('daily_checks',output['id'],output['revision'],encode(output)))
            store.audit(db,user['id'],'bulk-zero-update' if old else 'bulk-zero-create','daily_checks',output['id'],old,output)
            data['daily_checks']=others['daily_checks']+[output];confirmed.append(output['id'])
        store.validate_global(data)
        result={'date':payload['date'],'confirmed_count':len(confirmed),'ids':confirmed,'skipped_count':len(preview['skipped'])}
        db.execute('INSERT INTO requests VALUES(?,?,?,?)',(user['id'],key,fp,encode(result)))
        snapshot=store.snapshot(db,include_source=False);sequence=db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0];db.commit()
        return result|{'_snapshot':snapshot,'_sequence':sequence}
    except Invalid as exc:raise Problem(str(exc))
    finally:db.close()
