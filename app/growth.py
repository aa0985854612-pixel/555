"""Sample-based daily growth and live-weight projections, never weighing records."""
from .domain import combined_weights, day, herd
from .history import source_history
from .review import farm_today
from .order_fcr import order_fcr_estimate


def estimate_growth(batch, weights, movements, on):
    day(on)
    points = [w for w in combined_weights(weights, batch['id']) if w['date'] <= on]
    result = dict(as_of=on, method=None, first=None, last=points[-1] if points else None,
                  weighing_dates=len(points), interval_days=None, gain_kg=None, adg_kg=None,
                  days_since_last=None, estimated_mean_kg=None, composition_changed=False,
                  reasons=[])
    if not points:
        result['reasons'].append('no_weighing')
        return result
    last = points[-1]
    result['days_since_last'] = (day(on) - day(last['date'])).days
    if len(points) >= 2:
        first = points[-2]
        result['method'] = 'two_weighings'
    else:
        measured = batch.get('entry_mean_date') or batch['entry_date']
        if batch.get('entry_mean_kg') is None:
            result['reasons'].append('entry_mean_required')
            return result
        if measured >= last['date']:
            result['reasons'].append('different_dates_required')
            return result
        first = dict(date=measured, mean=batch['entry_mean_kg'], source='entry_mean')
        result['method'] = 'entry_and_weighing'
    days = (day(last['date']) - day(first['date'])).days
    gain = last['mean'] - first['mean']
    rate = gain / days
    result.update(first=first, interval_days=days, gain_kg=gain, adg_kg=rate)
    result['composition_changed'] = any(
        first['date'] <= m['date'] <= on and
        (m['batch_id'] == batch['id'] or m.get('target_batch_id') == batch['id'])
        for m in movements)
    if gain < 0:
        result['reasons'].append('weight_decreased')
    else:
        result['estimated_mean_kg'] = last['mean'] + rate * result['days_since_last']
    return result


def growth_estimates(data, on=None):
    on = on or farm_today()
    weights = list({w['id']: w for w in source_history(data, 'weights') + data['weights']
                    if not w.get('archive')}.values())
    movements = list({m['id']: m for m in source_history(data, 'movements') + data['movements']
                      if not m.get('archive')}.values())
    results = []
    for b in data['batches']:
        if b['status'] != 'active' or b['entry_date'] > on:
            continue
        if herd(data['batches'], data['movements'], on, [b['id']])['remaining'] == 0:
            continue
        growth = estimate_growth(b, weights, movements, on)
        results.append(dict(batch_id=b['id'], barn_id=b['barn_id'], growth=growth,
                            order_estimate=order_fcr_estimate(data, b, growth['first'], growth['last'])))
    return dict(as_of=on, batches=results)
