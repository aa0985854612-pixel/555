"""Audited whole-event barn assignments; source identity and totals stay intact."""
import uuid
from .domain import Invalid

FIELDS=('source_row_id','date','type','quantity','cohort','source_cell')

def identity(row):
    return {key:row['id'] if key=='source_row_id' else row.get(key) for key in FIELDS}


def apply_assignment(row,data):
    if row.get('archive') or row.get('batch_id'):return row
    expected=identity(row)
    for batch in data['batches']:
        for review in batch.get('source_assignments',[]):
            if {key:review.get(key) for key in FIELDS}!=expected:continue
            if batch['id'] not in row.get('legacy_members',[]):continue
            return row|{'batch_id':batch['id'],'barn_id':batch['barn_id'],'barn_number':batch['legacy_barn'],
                'assignment_review':review,'note':row.get('note','')+'｜人工核對：'+review['reason']}
    return row


def reviewed_events(book,row,data):
    """Only enrich the baseline's per-barn totals, without rewriting its stock."""
    from .history import event_keys,cohort_key
    members=[b['id'] for b in data['batches'] if b.get('legacy_source')==book['id'] and b.get('legacy_row')==row['key']]
    events=[]
    for key,event in event_keys(row):
        if event.get('allocations'):events.append(event);continue
        record={'id':str(uuid.uuid5(uuid.NAMESPACE_URL,book['id']+key+'None')),'date':event.get('date'),
            'type':event['type'],'quantity':event['quantity'],'cohort':cohort_key(row),
            'source_cell':row.get('sheet',book['report']['sheet'])+'!'+event['cell'],'legacy_members':members}
        assigned=apply_assignment(record,data)
        events.append(event|{'allocations':[{'barn':assigned['barn_number'],'quantity':event['quantity']}]} if assigned.get('batch_id') else event)
    return events


def validate_assignments(reviews,batch,data):
    from .history import source_history
    if not isinstance(reviews,list) or len(reviews)>1000:raise Invalid('invalid_source_assignment')
    # Strip reviews to validate against the immutable, unassigned source event.
    rawdata=data|{'batches':[dict(b,source_assignments=[]) for b in data['batches']]}
    if not any(b['id']==batch.get('id') for b in rawdata['batches']):rawdata['batches'].append(batch|{'source_assignments':[]})
    raw={r['id']:r for r in source_history(rawdata,include_voided=True,include_matched=True)}
    seen=set()
    for review in reviews:
        if not isinstance(review,dict) or set(review)!=set(FIELDS)|{'reason'}:raise Invalid('invalid_source_assignment')
        if not isinstance(review.get('source_row_id'),str) or type(review.get('quantity')) is not int or review['quantity']<=0:raise Invalid('invalid_source_assignment')
        row=raw.get(review.get('source_row_id'))
        if not row or row.get('archive') or row.get('batch_id') or not row.get('date') or row.get('unresolved'):raise Invalid('invalid_source_assignment')
        if batch.get('id') not in row.get('legacy_members',[]):raise Invalid('invalid_source_assignment')
        if {key:review.get(key) for key in FIELDS}!=identity(row):raise Invalid('source_assignment_conflict')
        if not isinstance(review['reason'],str) or not 1<=len(review['reason'].strip())<=500:raise Invalid('invalid_source_assignment')
        if row['id'] in seen:raise Invalid('duplicate_source_assignment')
        seen.add(row['id'])
        for other in data['batches']:
            if other['id']!=batch.get('id') and any(x.get('source_row_id')==row['id'] for x in other.get('source_assignments',[])):raise Invalid('duplicate_source_assignment')


def rebuild_confirmed_stock(data):
    """Replace provisional splits only when every member and all outflows agree."""
    groups={}
    for batch in data['batches']:
        if batch.get('legacy_group'):groups.setdefault(batch['legacy_group']['id'],[]).append(batch)
    for members in groups.values():
        marked=[b for b in members if b.get('stock_basis')]
        if not marked:continue
        pending=len(marked)!=len(members);planned={}
        for on,snapshot in members[0]['legacy_group']['snapshots'].items():
            values=[b['legacy_values'].get(on,{}) for b in members]
            if any(any(v.get(k) is None for k in ('entry','sold','dead','culled')) for v in values):pending=True;break
            heads=[v['entry']-v['sold']-v['dead']-v['culled'] for v in values]
            if snapshot.get('missing',0) or sum(v['entry'] for v in values)!=snapshot['entry'] or min(heads)<0 or sum(heads)!=snapshot['remaining']:pending=True;break
            planned[on]=heads
        if pending:
            for b in marked:b['legacy_stock_pending']=True
            continue
        for i,b in enumerate(members):
            b['legacy_stock_pending']=False
            for on in b['legacy_heads']:
                if on in planned:b['legacy_heads'][on]=planned[on][i]
