"""Read-only weekly sheets: entry-anchored periods, shared history identities."""
from datetime import datetime,timedelta,timezone
from .domain import day,age,herd,Invalid
from .history import cohort_key,source_history,source_rows

FIELDS={'death':'dead','sale':'sold','cull':'culled'}

def report_orders(data):
    """Read the existing single receipt ledger; never copy rows into storage."""
    from .feed_receipts import orders_are_arrivals,receipts
    if not orders_are_arrivals():return data.get('feed_orders',[])
    orders={o['id']:o for o in data.get('feed_orders',[])}
    result=[]
    for receipt in receipts(data):
        if receipt['id'] in orders:
            result.append(orders[receipt['id']]);continue
        row=receipt|{'vendor':receipt.get('vendor',''),'item':receipt.get('item','')}
        if row.get('feed_bin_id'):
            row=row|{'bin_allocations':row.get('allocations',[]),'target_batch_ids':row.get('target_batch_ids') or [a['batch_id'] for a in row.get('allocations',[])]}
        result.append(row)
    return result

def weekly_report(data,query,today=None):
    from .server import selected_ids,filter_rows
    get=lambda k:query.get(k,[''])[0]
    today=today or datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    ids=set(selected_ids(data,query))
    members=[b for b in data['batches'] if b['id'] in ids]
    keys={cohort_key(b) for b in members}
    if not members or len(keys)!=1 or not (get('cohort') or get('batch_id')):raise Invalid('weekly_choose_batch')
    entry=min(b['entry_date'] for b in members)
    all_records=get('all_records')=='1'
    default_start=entry if all_records else min(b.get('weekly_start_date') or b['entry_date'] for b in members)
    start=entry if all_records else max(get('from') or default_start,entry)
    end=max(today,entry) if all_records else get('to') or today
    day(start);day(end)
    if start>end:raise Invalid('invalid_period')
    if not all_records and (day(end)-day(entry)).days>1092:raise Invalid('weekly_period_too_long')
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
    from .feed import order_scope,order_detail,report_feed_setup,preentry_order,report_order_parts
    ledger=report_orders(data)
    feed_data=data|{'feed_orders':ledger}
    feed_query=scope if all_records else scope|{'to':[min(end,today)]}
    candidates=[part for order in filter_rows('feed_orders',feed_data,feed_query) for part in report_order_parts(order,data,ids)]
    if all_records:
        # Paper is the complete saved ledger, including dated future entries.
        # Stock and survival below retain their separate as-of-today cutoff.
        end=max([today,entry]+[r['date'] for r in events+candidates if r.get('date')]+list(source_until.values()))
    preentry=[]
    for o in candidates:
        if not preentry_order(o,data,ids):continue
        linked=set(o.get('target_batch_ids',[])) if o.get('feed_bin_id') else {a['batch_id'] for a in o.get('allocations',[])}
        arrivals=[b['entry_date'] for b in members if b['id'] in linked]
        if arrivals and (entry if all_records else get('from') or entry)<=min(arrivals):preentry.append(o)
    orders=[o for o in candidates if start<=o['date']<=end and not preentry_order(o,data,ids)]
    pre_details=[];pre_shared=[]
    for o in sorted(preentry,key=lambda r:(r['date'],r['id'])):
        if o.get('feed_bin_id'):
            (pre_details if order_scope(o,data,ids)['kg'] is not None else pre_shared).append(order_detail(o,data))
        else:
            pre_details.extend(order_detail(o,data,a['batch_id']) for a in o['allocations'] if a['batch_id'] in ids)
    pre_known=sum(d['kg'] for d in pre_details)
    preentry_feed={'details':pre_details,'shared_details':pre_shared,'known_kg':pre_known,'total_kg':None if pre_shared else pre_known,'count':len({r['id'] for r in preentry}),'basis':'before_explicit_batch_entry_not_in_period_totals'}
    unassigned=[o for o in ledger if start<=o['date']<=end and not o['allocations'] and not o.get('feed_bin_id')]
    bin_pending=[o for o in orders if o.get('feed_bin_id') and order_scope(o,data,ids)['kg'] is None]
    pending.extend({'id':o['id'],'type':'feed_orders','date':o['date'],'kg':o['kg'],'bin':o['feed_bin_snapshot']['name'],'reason':'shared_bin_unallocated' if len(o['feed_bin_snapshot']['barn_ids'])>1 else 'bin_batch_unknown'} for o in bin_pending)
    pending.extend({'id':o['id'],'type':'feed_orders','date':o['date'],'kg':o['kg'],'reason':'unassigned_order'} for o in unassigned)
    age_values={age(b,entry) for b in members};entry_age=next(iter(age_values)) if len(age_values)==1 else None
    # A named earliest-entry barn supplies grid labels, never a fake cohort age.
    week_reference=None
    if entry_age is None:
        from .feed import barn_number
        candidates=[b for b in members if b['entry_date']==entry and age(b,entry) is not None]
        if candidates:
            ref=min(candidates,key=lambda b:(barn_number(barns[b['barn_id']]) or 10**9,barns[b['barn_id']],b['id']))
            ref_age=age(ref,entry)
            week_reference={'batch_id':ref['id'],'barn':barns[ref['barn_id']],'entry_date':entry,'age_days':ref_age,'start_week':int(ref_age//7)+1,'basis':'named_earliest_entry_barn_only'}
    weeks=[];first=(day(start)-day(entry)).days//7;last=(day(end)-day(entry)).days//7
    for index in range(first,last+1):
        anchor=day(entry)+timedelta(days=index*7);lo=max(anchor,day(start));hi=min(anchor+timedelta(days=6),day(end));future=lo>day(today);hi_observed=min(hi,day(today))
        recorded_to=hi if all_records else hi_observed
        dated=[r for r in events if r.get('date') and lo.isoformat()<=r['date']<=recorded_to.isoformat()]
        selected=[r for r in dated if r.get('batch_id') in ids or set(r.get('legacy_members',[]))<=ids]
        values={typ:sum(r['quantity'] for r in selected if r['type']==typ) for typ in FIELDS}
        missing={p['type'] for p in pending if p['type'] in FIELDS and ((p.get('date') and lo.isoformat()<=p['date']<=recorded_to.isoformat()) or (not p.get('date') and lo.isoformat()<=p['until']))}
        period_orders=[o for o in orders if lo.isoformat()<=o['date']<=recorded_to.isoformat()]
        allocated=sum((order_scope(o,data,ids)['kg'] or 0) if o.get('feed_bin_id') else sum(a['kg'] for a in o['allocations'] if a['batch_id'] in ids) for o in period_orders)
        feed_details=[];feed_shared_details=[]
        for o in sorted(period_orders,key=lambda o:o['date']):
            if o.get('feed_bin_id'):
                target=feed_details if order_scope(o,data,ids)['kg'] is not None else feed_shared_details
                target.append(order_detail(o,data))
            else:
                for a in o['allocations']:
                    if a['batch_id'] in ids:feed_details.append(order_detail(o,data,a['batch_id']))
        unknown_orders=bool(feed_shared_details) or any(lo.isoformat()<=o['date']<=recorded_to.isoformat() for o in unassigned)
        weeks.append({'index':index+1,'age_week':None if entry_age is None else int(entry_age//7)+index+1,'start':lo.isoformat(),'anchor':anchor.isoformat(),'end':hi.isoformat(),'observed_to':hi_observed.isoformat() if not future else None,'future':future,'partial':lo!=anchor or hi!=anchor+timedelta(days=6) or hi>day(today),
            'has_records':bool(selected or period_orders),'missing_types':sorted(missing|({'feed_orders'} if unknown_orders else set())),
            'values':{typ:None if typ in missing or (future and (not all_records or not any(r['type']==typ for r in selected))) else n for typ,n in values.items()}|{'feed_orders':None if unknown_orders or (future and (not all_records or not period_orders)) else allocated},'known':values|{'feed_orders':allocated},
            'feed_details':feed_details,'feed_shared_details':feed_shared_details,'events':[{'id':r['id'],'date':r['date'],'type':r['type'],'quantity':r['quantity'],'barn':barns.get(batches.get(r.get('batch_id'),{}).get('barn_id'),''),'note':r.get('note','') if not r.get('legacy_source') else '', 'source_cell':r.get('source_cell',''),'outgoing_destination':r.get('outgoing_destination',''),'outgoing_trip':r.get('outgoing_trip','')} for r in selected]})
    counted=[w for w in weeks if not w['future'] or (all_records and w['has_records'])]
    totals={typ:None if not counted or any(w['values'][typ] is None and (not w['future'] or typ in w['missing_types']) for w in counted) else sum(w['known'][typ] for w in counted) for typ in (*FIELDS,'feed_orders')}
    known={typ:sum(w['known'][typ] for w in counted) for typ in (*FIELDS,'feed_orders')}
    until=min(end,today);h=herd(data['batches'],data['movements'],until,ids)
    means={b.get('entry_mean_kg') for b in members};mean=next(iter(means)) if len(means)==1 else None
    from .review import check_coverage
    coverage=check_coverage(data,ids,start,end)
    destinations=sorted({e['outgoing_destination'] for w in weeks for e in w['events'] if e['type'] in ('sale','cull') and e['outgoing_destination']})
    # Keep each barn's actual entry facts; linked cohorts can enter on different
    # dates and source-only combined counts must never become per-barn counts.
    entry_details=[{'batch_id':b['id'],'barn':barns[b['barn_id']],'date':b['entry_date'],
        'count':herd(data['batches'],data['movements'],until,[b['id']])['entry'] if b.get('legacy_group') else b['entry_count'],
        'age_days':age(b,b['entry_date']),'mean_kg':b.get('entry_mean_kg'),'mean_date':b.get('entry_mean_date')} for b in members]
    entry_details=[detail for b,original in zip(members,entry_details) for detail in ([original|{'date':lot['date'],'count':lot['count'],'mean_kg':lot['mean_kg'],'mean_date':lot['date'] if lot['mean_kg'] is not None else None,'age_days':original['age_days'] if index==0 and lot['date']==b['entry_date'] else None} for index,lot in enumerate(b.get('report_entry_lots',[]))] or [original])]
    means={d['mean_kg'] for d in entry_details};mean=next(iter(means)) if len(means)==1 else None
    from .feed_receipts import orders_are_arrivals
    return {'all_records':all_records,'feed_orders_are_arrivals':orders_are_arrivals(),'week_reference':week_reference,'preentry_feed':preentry_feed,'entry_details':entry_details,'outgoing_destinations':destinations,'feed_setup':report_feed_setup(data,members,orders+preentry),'death_check_coverage':coverage,'cohort':key,'name':members[0]['name'],'entry_date':entry,'entry_age_days':entry_age,'entry_mean_kg':mean,'barns':[barns[b['barn_id']] for b in members],'batch_ids':sorted(ids),'from':start,'to':end,'observed_to':until,'weeks':weeks,'totals':totals,'known_totals':known,'cumulative':h,'pending':pending,'age_mixed':entry_age is None and all(b.get('entry_age_days') is not None for b in members),'barn_ages':[{'barn':barns[b['barn_id']],'age_days':age(b,until),'entry_date':b['entry_date']} for b in members],'week_basis':'entry_date_every_7_days','age_basis':'ordinal_week_entry_age_floor_plus_one','feed_basis':'allocated_manual_orders_kg_not_consumption'}
