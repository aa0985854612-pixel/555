"""Traceable source history and incremental workbook matching; no stock allocation."""
import hashlib
import json
import uuid
from collections import defaultdict


def cohort_key(row):
    return row.get('_cohort_key') or row['name']+'|'+row['entry_date']


def event_keys(row):
    seen=defaultdict(int)
    for event in row.get('events',[]):
        key=(event.get('cell',''),event.get('date'),event['type'])
        ordinal=seen[key];seen[key]+=1
        stable=json.dumps([cohort_key(row),*key,ordinal],ensure_ascii=False)
        yield hashlib.sha256(stable.encode()).hexdigest(),event


def source_rows(data,archives=False):
    """Latest approved row per original cohort; original files remain immutable."""
    books=data.get('workbooks',[])
    for base in books:
        if base.get('base_book_id'):continue
        versions=sorted([b for b in books if b.get('base_book_id')==base['id']],key=lambda b:(b['report']['as_of'],b.get('created_at','')))
        for row in base['report']['rows']:
            current_book,current_row=base,row
            matched={}
            for version in versions:
                matched.update(version.get('matched_events',{}))
                if cohort_key(row) not in version.get('approved_cohorts',[]):continue
                replacement=next((r for r in version['report']['rows'] if cohort_key(r)==cohort_key(row)),None)
                if replacement:current_book,current_row=version,replacement
            yield {'base':base,'base_row':row,'book':current_book,'row':current_row,'matched':matched,'archive':False}
        if archives:
            latest=versions[-1] if versions else base
            for row in latest['report'].get('archive_rows',[]):
                yield {'base':base,'base_row':row,'book':latest,'row':row,'matched':{},'archive':True}


def members_for(data,source):
    return [b for b in data['batches'] if b.get('legacy_source')==source['base']['id'] and b.get('legacy_row')==source['base_row']['key']]


def update_preview(report,data):
    roots=[b for b in data.get('workbooks',[]) if not b.get('base_book_id')]
    root=next((b for b in roots if {cohort_key(r) for r in b['report']['rows']}=={cohort_key(r) for r in report['rows']}),None)
    if not root:return None
    versions=[b for b in data['workbooks'] if b.get('base_book_id')==root['id']]
    latest=max([root,*versions],key=lambda b:b['report']['as_of'])
    old_rows={cohort_key(r):r for r in latest['report']['rows']}
    inherited={k:v for b in versions for k,v in b.get('matched_events',{}).items()}
    changes=[];approved=[];matched=dict(inherited);pending=[]
    for row in report['rows']:
        key=cohort_key(row);base=next(r for r in root['report']['rows'] if cohort_key(r)==key)
        old=old_rows[key];old_events=dict(event_keys(old));new_events=dict(event_keys(row))
        members=[b for b in data['batches'] if b.get('legacy_source')==root['id'] and b.get('legacy_row')==base['key']]
        member_ids={b['id'] for b in members};barn_by_id={b['id']:b['legacy_barn'] for b in members}
        manual=[m for m in data['movements'] if not m.get('_source_derived') and m['batch_id'] in member_ids and root['report']['as_of']<m['date']<=report['as_of']]
        recent=[(eid,e) for eid,e in new_events.items() if e.get('date') and e['date']>root['report']['as_of']]
        row_pending=[]
        if report['as_of']<latest['report']['as_of']:row_pending.append('older_workbook')
        if row['barns']!=base['barns'] or row['totals']['entry']!=base['totals']['entry']:row_pending.append('cohort_structure_changed')
        if any(eid not in new_events or new_events[eid]!=event for eid,event in event_keys(base)):
            row_pending.append('historical_source_changed')
        expected=dict(base['totals'])
        for _,event in recent:
            field={'sale':'sold','death':'dead','cull':'culled'}[event['type']]
            expected[field]+=event['quantity'];expected['remaining']-=event['quantity']
        if any(expected[f]!=row['totals'][f] for f in ('entry','remaining','sold','dead','culled','missing')):row_pending.append('source_totals_unexplained')
        grouped=defaultdict(list)
        for eid,event in recent:grouped[(event['date'],event['type'])].append((eid,event))
        for date_type in set(grouped)|{(m['date'],m['type']) for m in manual}:
            candidates=[m for m in manual if (m['date'],m['type'])==date_type]
            events=grouped.get(date_type,[])
            if not candidates:continue
            if sum(m['quantity'] for m in candidates)!=sum(e['quantity'] for _,e in events):
                row_pending.append('manual_source_conflict');continue
            source_barns=defaultdict(int);manual_barns=defaultdict(int)
            for _,e in events:
                for a in e['allocations']:source_barns[a['barn']]+=a['quantity']
            for m in candidates:manual_barns[barn_by_id[m['batch_id']]]+=m['quantity']
            if any(manual_barns[b]<q for b,q in source_barns.items()):
                row_pending.append('manual_source_conflict');continue
            for eid,_ in events:matched[eid]=[m['id'] for m in candidates]
        change={'cohort':key,'name':row['name'],'added':sum(eid not in old_events for eid in new_events),
                'corrected':sum(eid in old_events and e!=old_events[eid] for eid,e in new_events.items()),
                'unchanged':sum(eid in old_events and e==old_events[eid] for eid,e in new_events.items()),
                'pending':sorted(set(row_pending)),'manual_records':len(manual)}
        changes.append(change)
        if row_pending:pending.append(change)
        else:approved.append(key)
    return {'base_book_id':root['id'],'approved_cohorts':approved,'matched_events':matched,
            'pending_cohorts':pending,'changes':changes,'source_as_of':report['as_of'],
            'added':sum(c['added'] for c in changes if not c['pending']),
            'corrected':sum(c['corrected'] for c in changes if not c['pending']),
            'unchanged':sum(c['unchanged'] for c in changes),
            'matched_manual':len({mid for ids in matched.values() for mid in ids}),
            'preview_token':hashlib.sha256(json.dumps([report['source_sha256'],
                [(b['id'],b['revision']) for b in data['batches']],
                [(m['id'],m['revision']) for m in data['movements']],
                [(b['id'],b['revision']) for b in data['workbooks']]],sort_keys=True).encode()).hexdigest()}


def source_history(data,kind='movements'):
    output=[]
    for source in source_rows(data,archives=True):
        row=source['row'];members=[] if source['archive'] else members_for(data,source)
        common={'revision':1,'legacy_source':source['book']['id'],'legacy_batch':row['name'],
                'cohort':cohort_key(row),'legacy_members':[b['id'] for b in members],
                'archive':source['archive'],'entry_date':row['entry_date']}
        if kind=='movements':
            for eid,event in event_keys(row):
                if eid in source['matched']:continue
                allocations=event['allocations'] or ([{'barn':row['barns'][0],'quantity':event['quantity']}] if len(row['barns'])==1 else [{'barn':None,'quantity':event['quantity']}])
                for allocation in allocations:
                    batch=next((b for b in members if b['legacy_barn']==allocation['barn']),None)
                    barn=next((b for b in data['barns'] if str(b.get('name','')).replace('第','').replace('棟','').strip()==str(allocation['barn'])),None)
                    output.append(common|{'id':str(uuid.uuid5(uuid.NAMESPACE_URL,source['base']['id']+eid+str(allocation['barn']))),
                        'date':event.get('date'),'type':event['type'],'quantity':allocation['quantity'],
                        'batch_id':batch['id'] if batch else None,'barn_id':barn['id'] if barn else None,'barn_number':allocation['barn'],
                        'source_cell':row.get('sheet',source['book']['report']['sheet'])+'!'+event['cell'],
                        'note':event['text'],'event_key':eid,'source_mean':False})
            for cell in row.get('unresolved_cells',[]):
                if cell.get('unresolved_quantity',cell['quantity'])<=0:continue
                output.append(common|{'id':str(uuid.uuid5(uuid.NAMESPACE_URL,source['base']['id']+row.get('sheet','')+cell['cell']+':undated')),
                    'date':None,'type':cell.get('type','unknown'),'quantity':cell.get('unresolved_quantity',cell['quantity']),
                    'batch_id':members[0]['id'] if len(members)==1 else None,'barn_id':next((b['id'] for b in data['barns'] if str(b['name']).replace('第','').replace('棟','').strip()==str(row['barns'][0])),None) if len(row['barns'])==1 else None,'barn_number':row['barns'][0] if len(row['barns'])==1 else None,
                    'source_cell':row.get('sheet',source['book']['report']['sheet'])+'!'+cell['cell'],'note':cell.get('comment',''),'unresolved':True})
        elif kind=='weights':
            for weight in row.get('weights',[]):
                batch=members[0] if len(members)==1 else None
                number=row['barns'][0] if len(row['barns'])==1 else None
                barn=next((b for b in data['barns'] if str(b.get('name','')).replace('第','').replace('棟','').strip()==str(number)),None)
                output.append(common|{'id':str(uuid.uuid5(uuid.NAMESPACE_URL,source['base']['id']+row.get('sheet','')+cohort_key(row)+weight['cell']+':weight')),
                    'date':weight.get('date'),'batch_id':batch['id'] if batch else None,'barn_id':batch['barn_id'] if batch else barn['id'] if barn else None,'barn_number':number,
                    'count':None,'total_kg':None,'individual_kg':[],'mean_kg':weight['mean_kg'],'source_mean':True,
                    'pen':'','sampling':'source_mean','representative':False,'age_days':None,
                    'age_weeks_hint':weight.get('age_weeks_hint'),'source_cell':row.get('sheet',source['book']['report']['sheet'])+'!'+weight['cell'],
                    'note':weight.get('formula') or '', 'entry_measurement':weight.get('entry_measurement',False)})
    return output


def derived_movements(data):
    """Only post-baseline source events enter balances; no invented barn split."""
    output=[]
    histories={r['id']:r for r in source_history(data)}
    for source in source_rows(data):
        members=members_for(data,source)
        for batch in members:batch['legacy_group']['unallocated_events']=[]
        for row in histories.values():
            if row['cohort']!=cohort_key(source['row']) or row.get('archive') or not row.get('date') or row['date']<=source['base']['report']['as_of']:continue
            if row['batch_id']:
                output.append(row|{'_source_derived':True,'created_by':'source-workbook'})
            else:
                for batch in members:batch['legacy_group']['unallocated_events'].append(row)
    return output
