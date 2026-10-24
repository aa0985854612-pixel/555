"""Derived physical-bin book stock; orders never become arrivals or consumption."""
from datetime import date,timedelta
from .domain import consumption,day


def delivery_scope(record,data,selected=None):
    from .feed import order_scope
    if record.get('allocations'):
        ids=None if selected is None else set(selected)
        kg=sum(a['kg'] for a in record['allocations'] if ids is None or a['batch_id'] in ids)
        return {'related':ids is None or any(a['batch_id'] in ids for a in record['allocations']),'kg':kg,'state':'allocated'}
    return order_scope(record,data,selected)


def usage_bin(usage,data):
    if usage.get('feed_bin_id'):return usage['feed_bin_id']
    batch=next((b for b in data['batches'] if b['id']==usage['batch_id']),None)
    bins=[b for b in data['feed_bins'] if b['active'] and batch and batch['barn_id'] in b['barn_ids']]
    return bins[0]['id'] if len(bins)==1 else None


def stock(data,bin,on):
    day(on);enabled=bin.get('inventory_enabled',False);cap=bin.get('capacity_kg');percent=bin.get('safe_fill_percent',85)
    result={'feed_bin_id':bin['id'],'name':bin['name'],'enabled':enabled,'as_of':on,
        'capacity_kg':cap,'safe_fill_percent':percent,'safe_capacity_kg':cap*percent/100 if cap else None,
        'baseline_date':bin.get('inventory_date'),'opening_kg':bin.get('inventory_opening_kg'),
        'received_kg':0,'consumed_kg':0,'kg':None,'known':False,'reasons':[]}
    if not enabled:result['reasons']=['inventory_not_enabled'];return result
    start=bin['inventory_date']
    if on<start:result['reasons']=['inventory_before_baseline'];return result
    result['received_kg']=sum(d['kg'] for d in data['deliveries'] if d.get('feed_bin_id')==bin['id'] and start<=d['date']<=on)
    until=(day(on)+timedelta(days=1)).isoformat();batches={b['id']:b for b in data['batches']}
    if any(not d.get('feed_bin_id') and start<=d['date']<=on and (not d['allocations'] or any(batches.get(a['batch_id'],{}).get('barn_id') in bin['barn_ids'] for a in d['allocations'])) for d in data['deliveries']):
        result['reasons'].append('inventory_delivery_bin_unknown')
    for u in data['usages']:
        if not u['active'] or u['end']<=start or u['start']>=until:continue
        batch=batches.get(u['batch_id'])
        if not batch or batch['barn_id'] not in bin['barn_ids']:continue
        target=usage_bin(u,data)
        if target and target!=bin['id']:continue
        if not target:result['reasons'].append('inventory_usage_bin_unknown');continue
        if u['start']<start or u['end']>until:result['reasons'].append('inventory_usage_spans_date');continue
        if u['method']=='inventory' and any(d.get('feed_bin_id')==bin['id'] and not d['allocations'] and u['start']<=d['date']<u['end'] for d in data['deliveries']):
            result['reasons'].append('inventory_shared_usage_unknown');continue
        kg=consumption(u,data['deliveries'])
        if kg is None:result['reasons'].append('inventory_shared_usage_unknown');continue
        if kg<0:result['reasons'].append('inventory_negative_usage');continue
        result['consumed_kg']+=kg
    result['reasons']=sorted(set(result['reasons']));result['known']=not result['reasons']
    if result['known']:result['kg']=bin['inventory_opening_kg']+result['received_kg']-result['consumed_kg']
    return result
