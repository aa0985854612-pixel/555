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
    entry = sum(b['entry_count'] for b in batches if b['id'] in ids and b['entry_date'] <= on and not b.get('legacy_group'))
    result = dict(entry=entry, added=0, sold=0, culled=0, dead=0, transfer_in=0, transfer_out=0, adjustment=0)
    baseline_remaining=0;unknown_remaining=False;unknown_fields=set();seen=set();legacy=False;unallocated_out=0
    for b in batches:
        if b['id'] not in ids or b['entry_date']>on or not b.get('legacy_group'):continue
        legacy=True;group=b['legacy_group'];key=group['id']
        if key in seen:continue
        seen.add(key)
        members=[x for x in batches if x['id'] in group['members'] and x['id'] in ids]
        effective=group['as_of'] if (on>group['as_of'] or (on==group['as_of'] and not before)) else on
        if before and effective==on:effective=None
        snapshot=group['snapshots'].get(effective)
        complete=len(group['members'])==group['expected_members'] and set(group['members'])<=ids
        if complete and snapshot:
            for k in ('entry','sold','culled','dead'):result[k]+=snapshot[k]
            baseline_remaining+=snapshot['remaining']
        else:
            for member in members:
                stock=member['legacy_heads'].get(effective)
                if stock is None:unknown_remaining=True
                else:baseline_remaining+=stock
                known=member.get('legacy_values',{}).get(effective,{})
                for field in ('entry','sold','culled','dead'):
                    if known.get(field) is None:unknown_fields.add(field)
                    else:result[field]+=known[field]
        for event in group.get('unallocated_events',[]):
            if not valid(event['date']):continue
            field={'sale':'sold','cull':'culled','death':'dead'}[event['type']]
            if complete:
                result[field]+=event['quantity'];unallocated_out+=event['quantity']
            else:
                unknown_remaining=True;unknown_fields.add(field)
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
    # Legacy exits are already reflected in baseline stock. Only new operational
    # movements enter the balance a second time; original group totals stay exact.
    operational=[m for m in movements if valid(m['date'])]
    out_delta=sum(m['quantity'] for m in operational if m['batch_id'] in ids and m['type'] in ('sale','cull','death'))
    result['remaining'] = None if unknown_remaining else entry+baseline_remaining+result['added']+result['transfer_in']-result['transfer_out']+result['adjustment']-out_delta-unallocated_out
    if not legacy:
        result['remaining']=entry+result['added']+result['transfer_in']-result['transfer_out']+result['adjustment']-result['sold']-result['culled']-result['dead']
    for field in unknown_fields:result[field]=None
    result['legacy_source']=legacy;result['historical_unknown']=unknown_remaining or bool(unknown_fields)
    result['outgoing'] = result['sold'] + result['culled'] if result['sold'] is not None and result['culled'] is not None else None
    result['denominator'] = result['entry']+result['added']+result['transfer_in'] if result['entry'] is not None else None
    result['survival'] = (result['denominator'] - result['dead']) / result['denominator'] * 100 if result['denominator'] and result['dead'] is not None else None
    return result


def combined_weights(weights, batch_id=None):
    groups = {}
    for w in weights:
        if not w.get('date'):continue
        if batch_id and w['batch_id'] != batch_id:
            continue
        key = w['date']
        g = groups.setdefault(key, dict(date=key, count=0, total_kg=0, representative=True, sources=[]))
        if not w.get('count') or w.get('total_kg') is None:
            if w.get('mean_kg') is not None:g.setdefault('source_means',[]).append(w)
            continue
        g['count'] += w['count']
        g['total_kg'] += w['total_kg']
        g['representative'] &= bool(w.get('representative'))
        g['sources'].append(w['id'])
    results=[]
    for g in groups.values():
        if g['count']:g['mean']=g['total_kg']/g['count'];g['source']='weighted_sample'
        elif len(g.get('source_means',[]))==1:
            source=g['source_means'][0]
            g.update(count=None,total_kg=None,mean=source['mean_kg'],representative=False,sources=[source['id']],source='source_mean')
        else:continue
        results.append(g)
    return sorted(results, key=lambda g:g['date'])


def consumption(usage, deliveries):
    if usage['method'] == 'direct':
        return usage['kg']
    delivered = sum(a['kg'] for d in deliveries if usage['start'] <= d['date'] < usage['end'] and (not usage.get('vendor') or d['vendor']==usage['vendor']) and (not usage.get('item') or d['item']==usage['item']) for a in d.get('allocations', []) if a['batch_id'] == usage['batch_id'])
    return usage['opening'] + delivered + usage['transfer_in'] - usage['closing'] - usage['transfer_out'] - usage['loss']


def performance(batch, batches, movements, weights, usages, deliveries, until, start=None, end=None):
    ws = [w for w in combined_weights(weights, batch['id']) if w['date'] <= until]
    if batch.get('entry_mean_kg') is not None:
        measured=batch.get('entry_mean_date') or batch['entry_date']
        if measured<=until and not any(w['date']==measured for w in ws):
            ws.append({'date':measured,'mean':batch['entry_mean_kg'],'count':None,'total_kg':None,
                'representative':False,'sources':['entry:'+batch['id']],'source':'entry_mean',
                'source_note':batch.get('entry_mean_source','')})
            ws.sort(key=lambda w:w['date'])
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
    if n0 is None or n1 is None:
        result['reasons'].append('legacy_history_unknown');return result
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
