"""Review and atomically save a whole cohort's entry data or counted stock."""
import copy
import hashlib
import json
import uuid
from .domain import Invalid, day, herd, number
from .history import cohort_key
from .operations import token
from .review import farm_today
from .store import Problem, encode, now

ENTRY_FIELDS = {'entry_date', 'entry_count', 'entry_mean_kg', 'entry_mean_date',
                'entry_age_days', 'age_date', 'status', 'weekly_start_date',
                'report_entry_lots', 'report_entry_lots_source', 'note'}


def _prepare(store, user, body, data):
    store.require(user, True)
    if not isinstance(body, dict) or body.get('mode') not in ('entry', 'stock'):
        raise Problem('invalid_batch_settings')
    if set(body) - {'mode', 'batch_id', 'reason', 'rows', 'date', 'name', 'preserve_entry_total', 'preview_token'}:
        raise Problem('invalid_batch_settings')
    reason = body.get('reason')
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
        raise Problem('batch_settings_reason_required')
    anchor = next((b for b in data['batches'] if b['id'] == body.get('batch_id')), None)
    if not anchor:
        raise Problem('not_found', 404)
    members = [b for b in data['batches'] if cohort_key(b) == cohort_key(anchor)]
    rows = body.get('rows')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100 or any(not isinstance(r, dict) for r in rows):
        raise Problem('invalid_batch_settings')
    ids = [r.get('id') for r in rows]
    if any(not isinstance(rid, str) for rid in ids) or len(set(ids)) != len(ids) or set(ids) != {b['id'] for b in members}:
        raise Problem('batch_settings_members_changed', 409)
    originals = {b['id']: b for b in members}
    for row in rows:
        if type(row.get('revision')) is not int or row['revision'] != originals[row['id']]['revision']:
            raise Problem('revision_conflict', 409)
    after = copy.deepcopy(data)
    writes = []
    barns = {b['id']: b for b in data['barns']}
    on = farm_today()
    if body['mode'] == 'entry':
        if not isinstance(body.get('name'), str) or not body['name'].strip() or len(body['name']) > 80:
            raise Problem('invalid_text')
        if not isinstance(body.get('preserve_entry_total', True), bool):
            raise Problem('invalid_batch_settings')
        candidates = {}
        renamed = {}
        count_changed = False
        for row in rows:
            if set(row) != {'id', 'revision', 'barn_revision', 'barn_name', 'fields'} or not isinstance(row['fields'], dict) or set(row['fields']) - ENTRY_FIELDS:
                raise Problem('invalid_batch_settings')
            previous = originals[row['id']]
            barn = barns[previous['barn_id']]
            if type(row['barn_revision']) is not int or row['barn_revision'] != barn['revision']:
                raise Problem('revision_conflict', 409)
            if not isinstance(row['barn_name'], str) or not 1 <= len(row['barn_name'].strip()) <= 80:
                raise Problem('invalid_text')
            if barn['id'] in renamed and renamed[barn['id']] != row['barn_name'].strip():
                raise Problem('invalid_batch_settings')
            renamed[barn['id']] = row['barn_name'].strip()
            candidate = copy.deepcopy(previous) | copy.deepcopy(row['fields']) | {'name': body['name'].strip()}
            day(candidate.get('entry_date'))
            if candidate.get('entry_count') is not None:
                candidate['entry_count'] = number(candidate['entry_count'], False, True)
                if candidate['entry_count'] < 0:
                    raise Problem('invalid_number')
            if candidate['entry_count'] != previous['entry_count']:
                count_changed = True
                candidate['entry_count_reason'] = reason.strip()
                candidate['entry_count_source'] = reason.strip()
            if candidate['entry_date'] != previous['entry_date'] and previous.get('legacy_source'):
                book = next(b for b in data['workbooks'] if b['id'] == previous['legacy_source'])
                source = next(r for r in book['report']['rows'] if r['key'] == previous['legacy_row'])
                if candidate['entry_date'] < source['entry_date']:
                    raise Problem('batch_settings_legacy_date')
                candidate['entry_date_override'] = None if candidate['entry_date'] == source['entry_date'] else {
                    'original_date': source['entry_date'], 'date': candidate['entry_date'], 'reason': reason.strip()}
            candidates[previous['id']] = candidate
        if count_changed and body.get('preserve_entry_total', True):
            old_counts = [b['entry_count'] for b in members]
            new_counts = [b['entry_count'] for b in candidates.values()]
            if all(x is not None for x in old_counts) and (any(x is None for x in new_counts) or sum(old_counts) != sum(new_counts)):
                raise Problem('batch_settings_total_mismatch')
        # A corrected source split must rebuild from confirmed per-barn exits,
        # rather than silently leave the source's old provisional stock split.
        if count_changed and anchor.get('legacy_group', {}).get('expected_members', 0) > 1:
            for candidate in candidates.values():
                candidate['stock_basis'] = {'mode': 'entry_minus_source_outflows', 'reason': reason.strip()}
        for rid, name in renamed.items():
            old = barns[rid]
            if name == old['name']:
                continue
            context = after | {'barns': [b for b in after['barns'] if b['id'] != rid]}
            cleaned = store.validate('barns', old | {'name': name}, context, user, old)
            new = cleaned | _metadata(old, user)
            after['barns'] = [new if b['id'] == rid else b for b in after['barns']]
            writes.append(('barns', old, new))
        after['batches'] = [candidates.get(b['id'], b) for b in after['batches']]
        for rid, candidate in candidates.items():
            old = originals[rid]
            context = after | {'batches': [b for b in after['batches'] if b['id'] != rid]}
            cleaned = store.validate('batches', candidate, context, user, old)
            old_cleaned = store.validate('batches', copy.deepcopy(old), data | {'batches': [b for b in data['batches'] if b['id'] != rid]}, user, old)
            if any(cleaned.get(k) != old_cleaned.get(k) for k in ('entry_mean_kg', 'entry_mean_date')):
                cleaned['entry_mean_source'] = reason.strip()
            changed = any(value != old_cleaned.get(k, [] if isinstance(value, list) else '' if isinstance(value, str) else None)
                          for k, value in cleaned.items())
            if changed:
                new = cleaned | _metadata(old, user)
                writes.append(('batches', old, copy.deepcopy(new)))
            else:
                new = old
            after['batches'] = [new if b['id'] == rid else b for b in after['batches']]
        store.enrich_legacy(after)
        store.validate_global(after)
        if count_changed and any(b.get('legacy_stock_pending') for b in after['batches'] if b['id'] in ids):
            raise Problem('batch_settings_source_pending')
    else:
        on = body.get('date')
        day(on)
        if on > farm_today():
            raise Problem('batch_settings_future_stock')
        for row in rows:
            if set(row) != {'id', 'revision', 'remaining'}:
                raise Problem('invalid_batch_settings')
            target = row['remaining']
            if target is None:
                continue  # Unknown/unfilled barns are never treated as zero.
            target = number(target, False, True)
            if target < 0:
                raise Problem('invalid_number')
            old = originals[row['id']]
            current = herd(data['batches'], data['movements'], on, [old['id']])['remaining']
            if current is None:
                raise Problem('heads_unknown')
            if target == current:
                continue
            cleaned = store.validate('movements', {'batch_id': old['id'], 'date': on,
                'type': 'adjustment', 'quantity': target - current, 'note': reason.strip()}, after, user)
            # A later, legitimate recount may have identical inputs. Only the
            # request key deduplicates retries; each new save needs a new ID.
            rid = str(uuid.uuid4())
            new = cleaned | {'id': rid, 'revision': 1, 'created_by': user['id'], 'created_at': now(), 'updated_at': now()}
            after['movements'].append(new)
            writes.append(('movements', None, new))
        store.enrich_legacy(after)
        store.validate_global(after)
    if not writes:
        raise Problem('batch_settings_no_changes')
    before_h = herd(data['batches'], data['movements'], on, ids)
    after_h = herd(after['batches'], after['movements'], on, ids)
    proof_body = {k: v for k, v in body.items() if k != 'preview_token'}
    proof = hashlib.sha256(encode([user['id'], proof_body, token(data)]).encode()).hexdigest()
    preview = {'mode': body['mode'], 'as_of': on, 'preview_token': proof,
        'before': before_h, 'after': after_h, 'rows': []}
    for old in members:
        new = next(b for b in after['batches'] if b['id'] == old['id'])
        new_barn = next(b for b in after['barns'] if b['id'] == old['barn_id'])
        fields = [{'field': k, 'before': old.get(k), 'after': new.get(k)}
                  for k in sorted(ENTRY_FIELDS | {'name'}) if old.get(k) != new.get(k)]
        preview['rows'].append({'id': old['id'], 'barn': barns[old['barn_id']]['name'],
            'barn_after': new_barn['name'], 'fields': fields,
            'before': herd(data['batches'], data['movements'], on, [old['id']])['remaining'],
            'after': herd(after['batches'], after['movements'], on, [old['id']])['remaining']})
    return preview, after, writes


def _metadata(old, user):
    return {'id': old['id'], 'revision': old['revision'] + 1,
            'created_by': old.get('created_by', user['id']), 'created_at': old.get('created_at', now()), 'updated_at': now()}


def preview(store, user, body):
    store.require(user, True)
    db = store.connect()
    try:
        db.execute('BEGIN')
        result, _, _ = _prepare(store, user, body, store.snapshot(db, include_source=False))
        return result
    except Invalid as e:
        raise Problem(str(e)) from None
    finally:
        db.close()


def save(store, user, body, key):
    store.require(user, True)
    if not isinstance(body, dict) or not isinstance(key, str) or not 16 <= len(key) <= 128:
        raise Problem('idempotency_required')
    fingerprint = hashlib.sha256(encode(['batch-settings', body]).encode()).hexdigest()
    db = store.connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        prior = db.execute('SELECT * FROM requests WHERE user_id=? AND key=?', (user['id'], key)).fetchone()
        if prior:
            if prior['fingerprint'] != fingerprint:
                raise Problem('idempotency_mismatch', 409)
            return json.loads(prior['result'])
        p, after, writes = _prepare(store, user, body, store.snapshot(db, include_source=False))
        if body.get('preview_token') != p['preview_token']:
            raise Problem('revision_conflict', 409)
        for kind, previous, new in writes:
            db.execute('INSERT INTO records(kind,id,revision,data) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,data=excluded.data',
                       (kind, new['id'], new['revision'], encode(new)))
            store.audit(db, user['id'], 'batch-settings', kind, new['id'], previous,
                        {'record': new, 'reason': body['reason'].strip(), 'impact': p})
        result = {'saved': True, 'changed': len(writes), 'batch_id': body['batch_id']}
        db.execute('INSERT INTO requests VALUES(?,?,?,?)', (user['id'], key, fingerprint, encode(result)))
        seq = db.execute('SELECT COALESCE(MAX(seq),0) FROM audit').fetchone()[0]
        db.commit()
        return result | {'_snapshot': after, '_sequence': seq}
    except Invalid as e:
        raise Problem(str(e)) from None
    finally:
        db.close()
