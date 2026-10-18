"""Explicit date corrections retain immutable workbook events and their identities."""
import hashlib,uuid
from .domain import Invalid,day

IDENTITY=('source_row_id','original_date','type','quantity','cohort','source_cell')

def reviews(data):
    return [r for b in data.get('workbooks',[]) for r in (b.get('source_date_reviews',[]) if isinstance(b.get('source_date_reviews',[]),list) else []) if isinstance(r,dict)]


def identity(row):
    return {'source_row_id':row['id'],'original_date':row.get('date'),**{k:row.get(k) for k in ('type','quantity','cohort','source_cell')}}


def apply_dates(row,data):
    review=next((r for r in reviews(data) if r.get('source_row_id')==row['id']),None)
    if not review or identity(row)!={k:review.get(k) for k in IDENTITY}:return [row]
    result=[]
    for i,part in enumerate(review['parts']):
        # Keep the original ID for the first part; subsequent parts have stable IDs.
        item=row|{'id':row['id'] if i==0 else str(uuid.uuid5(uuid.NAMESPACE_URL,'source-date-part:'+row['id']+':'+str(i))),
            'date':part['date'],'quantity':part['quantity'],'note':part['note'],
            'source_original_date':row['date'],'source_original_note':row.get('note',''),'source_original_id':row['id'],'date_review':review}
        if i:
            item['source_anchor']=hashlib.sha256(('source-date-part:'+row.get('source_anchor',row['id'])+':'+str(i)).encode()).hexdigest()
            item['source_event_anchor']=row.get('source_anchor') or row.get('source_event_anchor')
        if part.get('outgoing_destination'):item['outgoing_destination']=part['outgoing_destination']
        result.append(item)
    return result


def validate_reviews(data):
    from .history import source_history
    for book in data.get('workbooks',[]):
        entries=book.get('source_date_reviews',[])
        if not isinstance(entries,list) or any(not isinstance(r,dict) for r in entries):raise Invalid('invalid_source_date_review')
    all_reviews=reviews(data)
    if not all_reviews:return
    raw={r['id']:r for r in source_history(data,include_voided=True,include_matched=True,apply_date_reviews=False)};seen=set()
    roots={b['id']:b.get('base_book_id') or b['id'] for b in data['workbooks']}
    for book in data['workbooks']:
        entries=book.get('source_date_reviews',[])
        if not isinstance(entries,list) or len(entries)>2000:raise Invalid('invalid_source_date_review')
        for review in entries:
            if not isinstance(review,dict) or set(review)!=set(IDENTITY)|{'parts','reason'}:raise Invalid('invalid_source_date_review')
            rid=review.get('source_row_id')
            if not isinstance(rid,str) or rid not in raw or rid in seen:raise Invalid('invalid_source_date_review')
            seen.add(rid);row=raw[rid]
            if roots.get(row['legacy_source'])!=book['id'] or identity(row)!={k:review.get(k) for k in IDENTITY}:raise Invalid('source_date_review_conflict')
            if type(review['quantity']) is not int or review['quantity']<=0 or not row.get('date'):raise Invalid('invalid_source_date_review')
            if not isinstance(review['reason'],str) or not 1<=len(review['reason'].strip())<=500:raise Invalid('invalid_source_date_review')
            parts=review['parts']
            if not isinstance(parts,list) or not 1<=len(parts)<=20:raise Invalid('invalid_source_date_review')
            total=0
            for part in parts:
                if not isinstance(part,dict) or not {'date','quantity','note'}<=set(part) or set(part)-{'date','quantity','note','outgoing_destination'}:raise Invalid('invalid_source_date_review')
                day(part['date'])
                if type(part['quantity']) is not int or part['quantity']<=0:raise Invalid('invalid_source_date_review')
                if row.get('entry_date') and part['date']<row['entry_date']:raise Invalid('before_entry')
                if not isinstance(part['note'],str) or not 1<=len(part['note'].strip())<=2000:raise Invalid('invalid_source_date_review')
                if 'outgoing_destination' in part and (row['type'] not in ('sale','cull') or part['outgoing_destination'] not in ('','新北','南投','嘉義')):raise Invalid('invalid_source_date_review')
                total+=part['quantity']
            if total!=row['quantity']:raise Invalid('source_date_quantity_mismatch')


def adjust_snapshots(data):
    """Move incorporated outflows across dated baselines without moving stock twice."""
    if not reviews(data):return
    from .history import source_history,cohort_key
    raw={r['id']:r for r in source_history(data,include_voided=True,include_matched=True,apply_date_reviews=False)}
    for review in reviews(data):
        row=raw.get(review.get('source_row_id'))
        if not row or row.get('archive') or identity(row)!={k:review.get(k) for k in IDENTITY}:continue
        field={'sale':'sold','death':'dead','cull':'culled'}[row['type']]
        for batch in data['batches']:
            if cohort_key(batch)!=row['cohort'] or not batch.get('legacy_group'):continue
            for on,snapshot in batch['legacy_group']['snapshots'].items():
                delta=sum(p['quantity'] for p in review['parts'] if p['date']<=on)-(row['quantity'] if row['date']<=on else 0)
                snapshot[field]+=delta;snapshot['remaining']-=delta
            for on,values in batch['legacy_values'].items():
                if batch['id']==row.get('batch_id') and values.get(field) is not None:
                    delta=sum(p['quantity'] for p in review['parts'] if p['date']<=on)-(row['quantity'] if row['date']<=on else 0);values[field]+=delta
            for on,heads in batch['legacy_heads'].items():
                delta=sum(p['quantity'] for p in review['parts'] if p['date']<=on)-(row['quantity'] if row['date']<=on else 0)
                if delta and not row.get('batch_id'):batch['legacy_heads'][on]=None
                elif delta and batch['id']==row.get('batch_id') and heads is not None:batch['legacy_heads'][on]-=delta
