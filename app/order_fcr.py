"""Order-based feed/gain proxy. Never substitutes for measured consumption FCR."""
from datetime import timedelta
from .domain import day, herd
from .feed import order_scope, order_bin_label
from .feed_receipts import receipts,orders_are_arrivals


def period_headcount(data, batch, start, end):
    """Time-weight beginning-of-day stocks; intraday changes affect the next day.

    Legacy snapshots do not establish every earlier day's stock. Never carry a
    current snapshot backwards across undocumented history to invent an average.
    """
    days = (day(end)-day(start)).days
    result = dict(method='entry_count_proxy', head_count=batch.get('entry_count'),
                  head_days=None, period_days=days, headcount_segments=[],
                  headcount_fallback='period_heads_unknown')
    legacy = batch.get('legacy_group')
    if legacy and start <= legacy['as_of']:
        result['headcount_fallback'] = 'historical_heads_unknown'
        return result
    if not legacy and batch.get('entry_count') is None:
        result['headcount_fallback'] = 'entry_heads_unknown'
        return result
    edges = {start, end}
    if start < batch['entry_date'] < end:
        edges.add(batch['entry_date'])
    events = [m for m in data.get('movements', [])
              if m['batch_id'] == batch['id'] or m.get('target_batch_id') == batch['id']]
    if legacy:
        events += legacy.get('unallocated_events', [])
    for m in events:
        if start <= m['date'] < end:
            edges.add((day(m['date'])+timedelta(days=1)).isoformat())
    ordered = sorted(edges)
    segments = []
    head_days = 0
    for first, last in zip(ordered, ordered[1:]):
        heads = herd(data['batches'], data.get('movements', []), first,
                     [batch['id']], before=True)['remaining']
        if heads is None or heads < 0:
            return result
        head_days += heads * (day(last)-day(first)).days
        segments.append(dict(start=first, end_exclusive=last,
                             end_inclusive=(day(last)-timedelta(days=1)).isoformat(), heads=heads))
    result.update(method='time_weighted_heads', head_count=head_days/days,
                  head_days=head_days, headcount_segments=segments, headcount_fallback=None)
    return result


def order_fcr_estimate(data, batch, first, last):
    result = dict(ratio=None, method='entry_count_proxy', period_start=None,
                  period_end_exclusive=None, period_end_inclusive=None,
                  head_count=batch.get('entry_count'), gain_per_pig=None,
                  estimated_gain_kg=None, order_kg=None, known_order_kg=0,
                  order_count=0, orders=[], reasons=[])
    if not first or not last or first['date'] >= last['date']:
        result['reasons'].append('comparison_required')
        return result
    start, end = first['date'], last['date']
    result.update(period_start=start, period_end_exclusive=end,
                  period_end_inclusive=(day(end)-timedelta(days=1)).isoformat(),
                  gain_per_pig=last['mean']-first['mean'])
    result.update(period_headcount(data, batch, start, end))
    # Half-open, like the actual FCR interval: start morning to end morning.
    for order in sorted((receipts(data) if orders_are_arrivals() else data.get('feed_orders', [])), key=lambda o:(o['date'], o['id'])):
        if not start <= order['date'] < end:
            continue
        scope = order_scope(order, data, {batch['id']})
        if not scope['related']:
            continue
        result['orders'].append(dict(id=order['id'], date=order['date'], kg=scope['kg'],
            bin_total_kg=order['kg'], state=scope['state'], vendor=order.get('vendor',''),
            bin=order_bin_label(order['feed_bin_snapshot']) if order.get('feed_bin_id') else ''))
    result['order_count'] = len(result['orders'])
    result['known_order_kg'] = sum(o['kg'] or 0 for o in result['orders'])
    if not result['orders']:
        result['reasons'].append('no_orders')
    elif any(o['kg'] is None for o in result['orders']):
        result['reasons'].append('unallocated_orders')
    else:
        result['order_kg'] = result['known_order_kg']
    if result['head_count'] is None or result['head_count'] <= 0:
        result['reasons'].append('period_heads_required' if result['method']=='time_weighted_heads' else 'entry_heads_required')
    elif result['gain_per_pig'] <= 0:
        result['reasons'].append('positive_gain_required')
    else:
        result['estimated_gain_kg'] = result['gain_per_pig'] * result['head_count']
    if not result['reasons']:
        result['ratio'] = result['order_kg'] / result['estimated_gain_kg']
    return result
