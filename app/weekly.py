"""Read-only weekly sheets: entry-anchored periods, shared history identities."""
from datetime import datetime,timedelta,timezone
from .domain import day,age,herd,Invalid
from .history import cohort_key,source_history,source_rows

FIELDS={'death':'dead','sale':'sold','cull':'culled'}

def weekly_report(data,query,today=None):
    from .server import selected_ids,filter_rows
    get=lambda k:query.get(k,[''])[0]
    today=today or datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    ids=set(selected_ids(data,query))
    members=[b for b in data['batches'] if b['id'] in ids]
    keys={cohort_key(b) for b in members}
    if not members or len(keys)!=1 or not (get('cohort') or get('batch_id')):raise Invalid('weekly_choose_batch')
    entry=min(b['entry_date'] for b in members);start=max(get('from') or entry,entry);end=get('to') or today
    day(start);day(end)
    if start>end:raise Invalid('invalid_period')
    if (day(end)-day(entry)).days>1092:raise Invalid('weekly_period_too_long')
    key=next(iter(keys));barns={b['id']:b['name'] for b in data['barns']};batches={b['id']:b for b in members}
    sources=[s for s in source_rows(data) if cohort_key(s['row'])==key]
    source_until={s['book']['id']:s['book']['report']['as_of'] for s in sources}
    history=source_history(data)
    relevant=lambda r:r.get('batch_id') in ids or (r.get('cohort')==key and not r.get('archive') and not r.get('batch_id'))
    events=list({r['id']:r for r in history+data['movements'] if relevant(r) and r.get('type') in FIELDS}.values())
    pending=[]
    for s in sources:
        for event in s['row']['events']:
            if event.get('allocations') and sum(a['quantity'] for a in event['allocations'])!=event['quantity']:
                pending.append({'type':event['type'],'date':event.get('date'),'reason':'source_allocation_incomplete','until':s['book']['report']['as_of'],'source_cell':event.get('cell','')})
        for typ,field in FIELDS.items():
            # A source total without dated events cannot be distributed to weeks.
            if sum(e['quantity'] for e in s['row']['events'] if e['type']==typ)!=s['row']['totals'][field] and not any(r.get('unresolved') and r['type']==typ and r.get('legacy_source')==s['book']['id'] for r in events):
                pending.append({'type':typ,'reason':'source_total_without_dates','until':s['book']['report']['as_of'],'source_cell':s['row'].get('sheet',s['book']['report']['sheet'])})
    for r in events:
        if not r.get('date') or (not r.get('batch_id') and not set(r.get('legacy_members',[]))<=ids):
            pending.append({'id':r['id'],'type':r['type'],'date':r.get('date'),'quantity':r['quantity'],'reason':'missing_date' if not r.get('date') else 'missing_barn','until':source_until.get(r.get('legacy_source'),today),'source_cell':r.get('source_cell','')})
    scope={k:v for k,v in query.items() if k in ('cohort','barn_id','batch_id','group')}
    # Shared filtering includes only explicitly allocated orders for this scope.
    orders=filter_rows('feed_orders',data,scope|{'from':[start],'to':[end]})
    unassigned=[o for o in data.get('feed_orders',[]) if start<=o['date']<=end and not o['allocations']]
    pending.extend({'id':o['id'],'type':'feed_orders','date':o['date'],'kg':o['kg'],'reason':'unassigned_order'} for o in unassigned)
    age_values={age(b,entry) for b in members};entry_age=next(iter(age_values)) if len(age_values)==1 else None
    weeks=[];first=(day(start)-day(entry)).days//7;last=(day(end)-day(entry)).days//7
    for index in range(first,last+1):
        anchor=day(entry)+timedelta(days=index*7);lo=max(anchor,day(start));hi=min(anchor+timedelta(days=6),day(end));future=lo>day(today);hi_observed=min(hi,day(today))
        dated=[r for r in events if r.get('date') and lo.isoformat()<=r['date']<=hi_observed.isoformat()]
        selected=[r for r in dated if r.get('batch_id') in ids or set(r.get('legacy_members',[]))<=ids]
        values={typ:sum(r['quantity'] for r in selected if r['type']==typ) for typ in FIELDS}
        missing={p['type'] for p in pending if p['type'] in FIELDS and ((p.get('date') and lo.isoformat()<=p['date']<=hi_observed.isoformat()) or (not p.get('date') and lo.isoformat()<=p['until']))}
        allocated=sum(a['kg'] for o in orders if lo.isoformat()<=o['date']<=hi_observed.isoformat() for a in o['allocations'] if a['batch_id'] in ids)
        feed_details=[{'id':o['id'],'date':o['date'],'batch_id':a['batch_id'],'barn':barns[batches[a['batch_id']]['barn_id']],'kg':a['kg']} for o in sorted(orders,key=lambda o:o['date']) if lo.isoformat()<=o['date']<=hi_observed.isoformat() for a in o['allocations'] if a['batch_id'] in ids]
        unknown_orders=any(lo.isoformat()<=o['date']<=hi_observed.isoformat() for o in unassigned)
        weeks.append({'index':index+1,'age_week':None if entry_age is None else int(entry_age//7)+index+1,'start':lo.isoformat(),'anchor':anchor.isoformat(),'end':hi.isoformat(),'observed_to':hi_observed.isoformat() if not future else None,'future':future,'partial':lo!=anchor or hi!=anchor+timedelta(days=6) or hi>day(today),
            'values':{typ:None if future or typ in missing else n for typ,n in values.items()}|{'feed_orders':None if future or unknown_orders else allocated},'known':values|{'feed_orders':allocated},
            'feed_details':feed_details,'events':[{'id':r['id'],'date':r['date'],'type':r['type'],'quantity':r['quantity'],'barn':barns.get(batches.get(r.get('batch_id'),{}).get('barn_id'),''),'note':r.get('note','') if not r.get('legacy_source') else '', 'source_cell':r.get('source_cell','')} for r in selected]})
    totals={typ:None if not any(not w['future'] for w in weeks) or any(w['values'][typ] is None and not w['future'] for w in weeks) else sum(w['known'][typ] for w in weeks if not w['future']) for typ in (*FIELDS,'feed_orders')}
    known={typ:sum(w['known'][typ] for w in weeks if not w['future']) for typ in (*FIELDS,'feed_orders')}
    until=min(end,today);h=herd(data['batches'],data['movements'],until,ids)
    means={b.get('entry_mean_kg') for b in members};mean=next(iter(means)) if len(means)==1 else None
    return {'cohort':key,'name':members[0]['name'],'entry_date':entry,'entry_age_days':entry_age,'entry_mean_kg':mean,'barns':[barns[b['barn_id']] for b in members],'batch_ids':sorted(ids),'from':start,'to':end,'observed_to':until,'weeks':weeks,'totals':totals,'known_totals':known,'cumulative':h,'pending':pending,'age_mixed':entry_age is None and all(b.get('entry_age_days') is not None for b in members),'barn_ages':[{'barn':barns[b['barn_id']],'age_days':age(b,until),'entry_date':b['entry_date']} for b in members],'week_basis':'entry_date_every_7_days','age_basis':'ordinal_week_entry_age_floor_plus_one','feed_basis':'allocated_manual_orders_kg_not_consumption'}
