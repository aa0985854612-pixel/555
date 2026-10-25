"""Farm policy: use the original order ledger as dated receipts without copies."""
import os
from copy import deepcopy


def orders_are_arrivals():
    return os.environ.get('FEED_ORDERS_ARE_ARRIVALS','').strip().lower() in ('1','true','yes')


def receipts(data):
    originals=data.get('deliveries',[])
    if not orders_are_arrivals():return originals
    result=[];seen=set()
    for source in originals:
        if source['id'] not in seen:result.append(source);seen.add(source['id'])
    for order in data.get('feed_orders',[]):
        if order['id'] in seen:continue
        record=deepcopy(order);seen.add(order['id'])
        record['_receipt_source']='feed_orders'
        if order.get('bin_allocations'):
            record['allocations']=deepcopy(order['bin_allocations'])
        elif order.get('feed_bin_id'):
            snap=order['feed_bin_snapshot'];targets=order.get('target_batch_ids',[])
            record['allocations']=[{'batch_id':targets[0],'kg':order['kg']}] if len(snap['barn_ids'])==1 and len(targets)==1 else []
        result.append(record)
    return result


def stock_warnings(data,after,changes):
    """Warnings for explicitly reviewed receipt writes, including future dates."""
    if not orders_are_arrivals():return []
    from .bin_stock import stock
    from .review import farm_today
    warnings=[];changes=[r for r in changes if r]
    for bid in {r.get('feed_bin_id') for r in changes}:
        bin=next((b for b in data['feed_bins'] if b['id']==bid),None)
        if not bin or not bin.get('inventory_enabled'):continue
        first=min(r['date'] for r in changes if r.get('feed_bin_id')==bid)
        points={max(farm_today(),first)}|{d['date'] for d in receipts(after) if d.get('feed_bin_id')==bid and d['date']>=first}
        for on in points:
            following=stock(after,bin,on)
            if not following['known']:warnings.append('quick_stock_unknown')
            elif following['kg']<0:warnings.append('quick_stock_negative')
            elif following['safe_capacity_kg'] is not None and following['kg']>following['safe_capacity_kg']+1e-7:warnings.append('quick_capacity_exceeded')
    return sorted(set(warnings))
