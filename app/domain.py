"""Pure herd, sampling and feed calculations. Dates are ISO local farm dates."""
from datetime import date
import math

class Invalid(ValueError):
    pass


def day(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise Invalid('invalid_date')


def number(value, positive=False, integer=False):
    if isinstance(value, bool):
        raise Invalid('invalid_number')
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise Invalid('invalid_number')
    if not math.isfinite(n) or (positive and n <= 0) or (integer and not n.is_integer()):
        raise Invalid('invalid_number')
    return int(n) if integer else n


def age(batch, on):
    n = batch.get('entry_age_days')
    if n is None:
        return None
    value=n + (day(on) - day(batch.get('age_date') or batch['entry_date'])).days
    return value if value>=0 else None


def herd(batches, movements, on, selected=None, before=False):
    ids = set(selected if selected is not None else [b['id'] for b in batches])
    valid = lambda d: d < on if before else d <= on
    # Entry stocks exist at the beginning of the entry day.
    entry = sum(b['entry_count'] for b in batches if b['id'] in ids and b['entry_date'] <= on)
    result = dict(entry=entry, added=0, sold=0, culled=0, dead=0, transfer_in=0, transfer_out=0, adjustment=0)
    for m in movements:
        if not valid(m['date']):
            continue
        included = m['batch_id'] in ids
        target = m.get('target_batch_id') in ids
        q = m['quantity']
        k = m['type']
        if k == 'transfer':
            if included and not target:
                result['transfer_out'] += q
            if target and not included:
                result['transfer_in'] += q
        elif included:
            key = {'sale':'sold', 'cull':'culled', 'death':'dead', 'arrival':'added', 'adjustment':'adjustment'}[k]
            result[key] += q
    result['remaining'] = entry + result['added'] + result['transfer_in'] - result['transfer_out'] + result['adjustment'] - result['sold'] - result['culled'] - result['dead']
    result['outgoing'] = result['sold'] + result['culled']
    result['denominator'] = entry + result['added'] + result['transfer_in']
    result['survival'] = (result['denominator'] - result['dead']) / result['denominator'] * 100 if result['denominator'] else None
    return result


def combined_weights(weights, batch_id=None):
    groups = {}
    for w in weights:
        if batch_id and w['batch_id'] != batch_id:
            continue
        key = w['date']
        g = groups.setdefault(key, dict(date=key, count=0, total_kg=0, representative=True, sources=[]))
        g['count'] += w['count']
        g['total_kg'] += w['total_kg']
        g['representative'] &= bool(w.get('representative'))
        g['sources'].append(w['id'])
    for g in groups.values():
        g['mean'] = g['total_kg'] / g['count']
    return sorted(groups.values(), key=lambda g:g['date'])


def consumption(usage, deliveries):
    if usage['method'] == 'direct':
        return usage['kg']
    delivered = sum(a['kg'] for d in deliveries if usage['start'] <= d['date'] < usage['end'] and (not usage.get('vendor') or d['vendor']==usage['vendor']) and (not usage.get('item') or d['item']==usage['item']) for a in d.get('allocations', []) if a['batch_id'] == usage['batch_id'])
    return usage['opening'] + delivered + usage['transfer_in'] - usage['closing'] - usage['transfer_out'] - usage['loss']


def performance(batch, batches, movements, weights, usages, deliveries, until, start=None, end=None):
    ws = [w for w in combined_weights(weights, batch['id']) if w['date'] <= until]
    if start or end:
        ws = [w for w in ws if (not start or w['date'] >= start) and (not end or w['date'] <= end)]
    result = dict(adg=None, fcr=None, gain=None, feed=None, reasons=[], composition_changed=False, estimated=True)
    if len(ws) < 2:
        if ws:result['last']=ws[-1]
        result['reasons'] = ['two_weights_required']
        return result
    first, last = ws[0], ws[-1]
    days = (day(last['date']) - day(first['date'])).days
    result.update(first=first, last=last, days=days, delta=last['mean']-first['mean'])
    result['adg'] = result['delta'] / days
    changes = [m for m in movements if first['date'] <= m['date'] < last['date'] and (m['batch_id'] == batch['id'] or m.get('target_batch_id') == batch['id'])]
    result['composition_changed'] = bool(changes)
    if any(m['date'] in (first['date'], last['date']) and (m['batch_id']==batch['id'] or m.get('target_batch_id')==batch['id']) for m in movements):
        result['reasons'].append('endpoint_movement_order_unknown')
    if result['delta'] < 0:
        result['reasons'].append('weight_decreased')
    if not first['representative'] or not last['representative']:
        result['reasons'].append('representative_required')
    n0 = herd(batches, movements, first['date'], [batch['id']], before=True)['remaining']
    n1 = herd(batches, movements, last['date'], [batch['id']], before=True)['remaining']
    if n0 <= 0 or n1 < 0:
        result['reasons'].append('invalid_herd')
    gain = last['mean'] * n1 - first['mean'] * n0
    for m in changes:
        if m['type'] == 'adjustment' or m.get('total_weight_kg') is None:
            result['reasons'].append('movement_weight_required')
            continue
        if m['type'] == 'arrival' or (m['type'] == 'transfer' and m.get('target_batch_id') == batch['id']):
            gain -= m['total_weight_kg']
        else:
            gain += m['total_weight_kg']
    active = sorted([u for u in usages if u['batch_id'] == batch['id'] and u['active'] and u['start'] < last['date'] and u['end'] > first['date']], key=lambda u:u['start'])
    cursor, feed = first['date'], 0
    for u in active:
        if u['start'] != cursor or u['end'] > last['date']:
            result['reasons'].append('feed_period_mismatch')
            break
        value = consumption(u, deliveries)
        if value < 0:
            result['reasons'].append('negative_feed')
        feed += value
        cursor = u['end']
    if cursor != last['date']:
        result['reasons'].append('feed_period_mismatch')
    if gain <= 0:
        result['reasons'].append('nonpositive_gain')
    result['reasons'] = list(dict.fromkeys(result['reasons']))
    if not result['reasons']:
        result.update(gain=gain, feed=feed, fcr=feed/gain)
    return result
