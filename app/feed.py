"""Physical feed bins, explicit batch scope, and non-duplicated order attribution."""
import re

FEED_TYPES=('大豬料','仔豬料','哺乳二期料')
YANG_QUAN_BARNS={1,2,3,4,8,9,12,14,18,21,23,24}


def bin_label(bin):
    """Confirmed shorthand only; keep original physical bin IDs and snapshots."""
    return {'1、2':'1','3、4':'3','5、6':'5','16、17':'16'}.get(bin['name'],bin['name'])


def validate_bin_allocations(rows,total,targets,barn_ids,batches):
    from .domain import Invalid,number
    if not isinstance(rows,list) or len(rows)>len(barn_ids):raise Invalid('invalid_allocations')
    result=[];seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'batch_id','kg'}:raise Invalid('invalid_allocations')
        rid=row['batch_id']
        if not isinstance(rid,str) or rid not in targets or rid not in batches or batches[rid]['barn_id'] not in barn_ids:raise Invalid('invalid_allocations')
        barn=batches[rid]['barn_id']
        if barn in seen:raise Invalid('duplicate_allocation')
        seen.add(barn);result.append({'batch_id':rid,'kg':number(row['kg'],True)})
    if result and abs(sum(r['kg'] for r in result)-total)>1e-7:raise Invalid('allocation_total_mismatch')
    return result


def report_order_parts(order,data,selected):
    """Separate confirmed portions so each arrival date retains pre-entry status."""
    rows=order.get('bin_allocations',[])
    if not rows:return [order]
    return [order|{'kg':r['kg'],'bin_total_kg':order['kg'],'bin_allocations':[r],'target_batch_ids':[r['batch_id']]} for r in rows if r['batch_id'] in selected]


def barn_number(name):
    m=re.fullmatch(r'(?:第)?\s*(\d+)\s*棟?',str(name).strip())
    return int(m[1]) if m else None


def initial_bins(barns):
    """User-confirmed 2026-10-17 setup; definitions only, never auto-write on GET."""
    by_number={barn_number(b['name']):b for b in barns};out=[];seen=set()
    for n in sorted(k for k in by_number if k is not None):
        if n in seen:continue
        numbers=next((pair for pair in ((1,2),(3,4),(5,6),(16,17)) if n in pair),None) or (n,)
        if not all(x in by_number for x in numbers):continue
        seen.update(numbers)
        for label in ([f'{n}-1',f'{n}-2'] if n in (11,14,15) else ['、'.join(map(str,numbers))]):
            out.append({'name':label,'barn_ids':[by_number[x]['id'] for x in numbers],
                'vendor':'養全' if all(x in YANG_QUAN_BARNS for x in numbers) else '新農科','active':True,'note':'依使用者確認的廠商及料桶配置（2026-10-17）'})
    return out


def order_scope(order, data, selected=None):
    """A bin total belongs once to its full identified scope, never split by guess."""
    if selected is None:return {'related':True,'kg':order['kg'],'state':'farm_total'}
    chosen=set(selected)
    if order.get('bin_allocations'):
        kg=sum(a['kg'] for a in order['bin_allocations'] if a['batch_id'] in chosen)
        return {'related':bool(kg),'kg':kg,'state':'allocated' if kg else 'unassigned','batch_ids':[a['batch_id'] for a in order['bin_allocations'] if a['batch_id'] in chosen]}
    if not order.get('feed_bin_id'):
        kg=sum(a['kg'] for a in order.get('allocations',[]) if a['batch_id'] in chosen)
        return {'related':bool(kg),'kg':kg,'state':'allocated' if kg else 'unassigned'}
    snap=order['feed_bin_snapshot'];targets=set(order.get('target_batch_ids',[]));batches={b['id']:b for b in data['batches']}
    covered={batches[x]['barn_id'] for x in targets if x in batches}
    chosen_barns={batches[x]['barn_id'] for x in chosen if x in batches}
    related=bool(targets&chosen or (set(snap['barn_ids'])-covered)&chosen_barns)
    complete=covered==set(snap['barn_ids']) and targets<=chosen
    return {'related':related,'kg':order['kg'] if related and complete else None,'state':'bin_total' if related and complete else 'shared_unallocated' if len(snap['barn_ids'])>1 else 'missing_batch'}


def order_detail(order, data, batch_id=None):
    batches={b['id']:b for b in data['batches']};barns={b['id']:b['name'] for b in data['barns']}
    if order.get('feed_bin_id'):
        snap=order['feed_bin_snapshot'];label=bin_label(snap);assigned=order.get('bin_allocations',[])
        return {'id':order['id'],'date':order['date'],'batch_id':assigned[0]['batch_id'] if len(assigned)==1 else None,'barn':'、'.join(barns[batches[a['batch_id']]['barn_id']] for a in assigned) if assigned else '、'.join(snap['barn_names']),
            'bin':label,'bin_label':label,'kg':order['kg'],'vendor':order['vendor'],'item':order['item'],'target_batch_ids':order['target_batch_ids'],'bin_total_kg':order.get('bin_total_kg',order['kg'])}
    a=next(a for a in order['allocations'] if a['batch_id']==batch_id)
    return {'id':order['id'],'date':order['date'],'batch_id':batch_id,'barn':barns[batches[batch_id]['barn_id']],'kg':a['kg'],'vendor':order.get('vendor',''),'item':order.get('item','')}


def report_feed_setup(data, members, orders):
    ids={b['barn_id'] for b in members}
    bins=[b for b in data.get('feed_bins',[]) if b['active'] and set(b['barn_ids'])&ids]
    suppliers=set()
    for barn in data['barns']:
        if barn['id'] not in ids:continue
        if barn.get('feed_vendor'):suppliers.add(barn['feed_vendor'])
        else:suppliers.update(b['vendor'] for b in bins if barn['id'] in b['barn_ids'])
    suppliers=sorted(suppliers)
    return {'configured_vendors':suppliers,'recorded_vendors':sorted({o['vendor'] for o in orders if o.get('vendor')}),
        'recorded_types':sorted({o['item'] for o in orders if o.get('item')}),
        'bins':[{'name':bin_label(b),'vendor':b['vendor'],'barns':[x['name'] for x in data['barns'] if x['id'] in b['barn_ids']]} for b in bins]}


def preentry_order(order,data,selected):
    """Only explicit batch links identify feed ordered before those pigs arrive."""
    chosen=set(selected);ids=set(order.get('target_batch_ids',[])) if order.get('feed_bin_id') else {a['batch_id'] for a in order.get('allocations',[])}
    members=[b for b in data['batches'] if b['id'] in ids&chosen]
    return bool(members) and all(order['date']<b['entry_date'] for b in members)
