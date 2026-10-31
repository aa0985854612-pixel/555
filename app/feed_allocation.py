"""Automatic shared-bin attribution, derived from the original dated ledger."""
import os
from decimal import Decimal,ROUND_DOWN
from .domain import herd


def allocation_policy():
    value=os.environ.get('FEED_AUTO_ALLOCATION','').strip().lower()
    return value if value in ('headcount','equal') else ''


def automatic_allocation(record,data):
    """Preserve confirmed portions; never turn a physical receipt into two rows.

    Historical headcount corrections intentionally recalculate unconfirmed
    portions. Explicit manual portions always take precedence. This allocates
    received feed for reports, not measured consumption.
    """
    mode=allocation_policy();snap=record.get('feed_bin_snapshot')
    if not mode or not snap or len(snap['barn_ids'])<2 or record.get('bin_allocations'):return None
    if record.get('allocations'):return None
    batches={b['id']:b for b in data['batches']};explicit=[batches[x] for x in record.get('target_batch_ids',[]) if x in batches]
    selected=[];counts={};head_cache={}
    def heads(b):
        # Pre-entry orders may explicitly identify the upcoming pigs.
        if b['id'] not in head_cache:
            if (b.get('entry_count') is None and not b.get('legacy_group')) or record['date']<b['entry_date']:n=b.get('entry_count')
            else:n=herd(data['batches'],data.get('movements',[]),record['date'],[b['id']])['remaining']
            head_cache[b['id']]=n
        return head_cache[b['id']]
    for barn in snap['barn_ids']:
        candidates=[b for b in explicit if b['barn_id']==barn]
        if not candidates:
            candidates=[b for b in data['batches'] if b['barn_id']==barn and b['entry_date']<=record['date'] and heads(b) is not None and heads(b)>0]
        if len(candidates)!=1:return None
        b=candidates[0];n=heads(b)
        if mode=='headcount' and n is None:return None
        if n is not None and n<0:return None
        selected.append(b);counts[b['id']]=n
    # Equal means divide by the configured barns, independently of headcounts.
    weights=[Decimal(str(counts[b['id']] or 0)) if mode=='headcount' else Decimal(1) for b in selected]
    total_weight=sum(weights)
    if not total_weight:return None
    # Whole-kg inputs split to whole kilograms; the last positive portion keeps the remainder.
    total=Decimal(str(record['kg']));quantum=Decimal(1).scaleb(min(-3 if mode=='equal' else 0,total.normalize().as_tuple().exponent));left=total;rows=[]
    positive=[(b,w) for b,w in zip(selected,weights) if w>0]
    for index,(b,weight) in enumerate(positive):
        amount=left if index==len(positive)-1 else (total*weight/total_weight).quantize(quantum,rounding=ROUND_DOWN)
        left-=amount
        if amount:rows.append({'batch_id':b['id'],'kg':float(amount)})
    return {'basis':'auto_'+mode,'as_of':record['date'],'allocations':rows,'heads':counts,'total_kg':record['kg']}
