"""Read cached Alice workbook values; preserve formulas/comments, never execute them.

Legacy group totals are authoritative. Barn allocations are labelled estimates;
undated historical movements and weights without sample counts are not invented.
"""
import base64,hashlib,io,math,posixpath,re,xml.etree.ElementTree as ET
from datetime import date,timedelta
from zipfile import ZipFile,BadZipFile
from .domain import Invalid

NS={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
REL='http://schemas.openxmlformats.org/package/2006/relationships'
MAX_FILE=8*1024*1024

def unpack(value):
    if not isinstance(value,str) or len(value)>MAX_FILE*4//3+8:raise Invalid('invalid_workbook')
    try:raw=base64.b64decode(value,validate=True)
    except ValueError:raise Invalid('invalid_workbook')
    if len(raw)>MAX_FILE:raise Invalid('invalid_workbook')
    return raw

def read_workbook(raw):
    try:
        with ZipFile(io.BytesIO(raw)) as z:
            if len(z.infolist())>2000 or sum(f.file_size for f in z.infolist())>64*1024*1024:raise Invalid('invalid_workbook')
            if any(f.flag_bits&1 or f.filename.startswith('/') or '..' in f.filename.split('/') for f in z.infolist()):raise Invalid('invalid_workbook')
            def xml(name):return ET.fromstring(z.read(name))
            def relations(name):return {r.attrib['Id']:r.attrib for r in xml(name)} if name in z.namelist() else {}
            strings=[]
            if 'xl/sharedStrings.xml' in z.namelist():
                strings=[''.join(t.text or '' for t in n.findall('.//x:t',NS)) for n in xml('xl/sharedStrings.xml')]
            workbook=xml('xl/workbook.xml');props=workbook.find('x:workbookPr',NS)
            epoch=date(1904,1,1) if props is not None and props.get('date1904') in ('1','true') else date(1899,12,30)
            links=relations('xl/_rels/workbook.xml.rels');sheets=[]
            for sheet in workbook.findall('x:sheets/x:sheet',NS):
                rel=links[sheet.attrib['{'+NS['r']+'}id']]
                target=rel['Target'];path=posixpath.normpath(posixpath.join('xl',target)) if not target.startswith('/') else target.lstrip('/')
                if not path.startswith('xl/') or rel.get('TargetMode')=='External':raise Invalid('invalid_workbook')
                cells={}
                for c in xml(path).findall('.//x:sheetData/x:row/x:c',NS):
                    typ=c.get('t');v=c.find('x:v',NS);value=v.text if v is not None else None
                    if typ=='s':value=strings[int(value)] if value is not None else None
                    elif typ=='inlineStr':value=''.join(t.text or '' for t in c.findall('.//x:t',NS))
                    elif typ not in ('str','e') and value is not None:
                        try:value=float(value);value=int(value) if value.is_integer() else value
                        except ValueError:raise Invalid('invalid_workbook')
                    formula=c.find('x:f',NS)
                    cells[c.attrib['r']]={'value':value,'formula':formula.text if formula is not None else None}
                rel_path=posixpath.dirname(path)+'/_rels/'+posixpath.basename(path)+'.rels'
                for rel in relations(rel_path).values():
                    if rel.get('Type','').endswith('/comments') and rel.get('TargetMode')!='External':
                        comment_path=posixpath.normpath(posixpath.join(posixpath.dirname(path),rel['Target']))
                        if not comment_path.startswith('xl/'):raise Invalid('invalid_workbook')
                        for c in xml(comment_path).findall('x:commentList/x:comment',NS):
                            cells.setdefault(c.get('ref'),{'value':None,'formula':None})['comment']=''.join(t.text or '' for t in c.findall('.//x:t',NS))
                sheets.append({'name':sheet.get('name'),'cells':cells})
            return sheets,epoch
    except (BadZipFile,KeyError,ValueError,ET.ParseError,IndexError,OverflowError):raise Invalid('invalid_workbook')

def review(raw):
    sheets,epoch=read_workbook(raw)
    current=next((s for s in sheets if s['name'].strip()=='肉豬各周存欄頭數'),None)
    if not current:raise Invalid('unsupported_workbook')
    cells=current['cells']
    def value(ref):return cells.get(ref,{}).get('value')
    if value('R3')!='進場頭數' or value('S3')!='存欄頭數':raise Invalid('unsupported_workbook')
    def iso(v):
        if not isinstance(v,(int,float)) or isinstance(v,bool):raise Invalid('invalid_workbook')
        return (epoch+timedelta(days=int(v))).isoformat()
    def count(ref):
        v=value(ref)
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 or int(v)!=v:raise Invalid('invalid_workbook')
        return int(v)
    as_of=iso(value('B1'));rows=[];issues=[]
    anchors=sorted(int(ref[1:]) for ref in cells if re.fullmatch(r'A\d+',ref) and str(value(ref) or '').startswith('JD-'))
    for r in anchors:
        name=value(f'A{r}');barn_text=value(f'C{r}')
        if not isinstance(barn_text,str):continue
        barns=[int(n) for n in re.findall(r'\d+',barn_text)]
        if not barns or len(barns)!=len(set(barns)):raise Invalid('invalid_workbook')
        birth=iso(value(f'D{r}'));entry=iso(value(f'E{r}'))
        totals={k:count(f'{col}{r}') for k,col in [('entry','R'),('remaining','S'),('sold','T'),('dead','Z'),('culled','AA'),('missing','AB')]}
        if totals['entry']-totals['sold']-totals['dead']-totals['culled']-totals['missing']!=totals['remaining']:raise Invalid('workbook_balance_mismatch')
        comments={ref:c['comment'] for ref,c in cells.items() if 'comment' in c and r<=int(re.search(r'\d+$',ref).group())<r+4}
        # Earlier entry dates in explicit cell comments are authoritative details,
        # while both entry components remain preserved in the original workbook.
        for ref in (f'E{r}',f'R{r}'):
            for line in comments.get(ref,'').splitlines():
                if ('入場日期' in line or '進' in line) and (match:=re.search(r'(\d{1,2})/(\d{1,2})',line)):
                    candidate=date(int(entry[:4]),int(match[1]),int(match[2])).isoformat()
                    if birth<=candidate<entry:entry=candidate
        weights=[];events=[];unresolved=[]
        for rr in range(r,r+4):
            mean=value(f'I{rr}')
            if isinstance(mean,(int,float)) and mean>0 and value(f'H{rr}') is not None:
                weights.append({'date':iso(value(f'H{rr}')),'mean_kg':mean,'sample_count':None,'cell':f'I{rr}','formula':cells[f'I{rr}'].get('formula'),'entry_measurement':rr==r,'age_weeks_hint':value(f'J{rr}')})
            typ={'死亡':'death','賣汰':'cull','售出':'sale'}.get(value(f'AC{rr}'))
            if not typ:continue
            for ref,c in cells.items():
                m=re.fullmatch(r'([A-Z]+)(\d+)',ref)
                if not m or int(m[2])!=rr or len(m[1])>2:continue
                col=0
                for ch in m[1]:col=col*26+ord(ch)-64
                if not 30<=col<=54 or not isinstance(c['value'],(int,float)) or c['value']<=0:continue
                parsed=[]
                for line in c.get('comment','').splitlines():
                    if '不列入' in line or '自行吸收' in line:continue
                    dm=re.match(r'\s*(\d{1,2})/(\d{1,2})\s*(.*)',line)
                    if not dm:continue
                    text=dm[3];verbs={'death':r'死(?:亡)?|市場死亡','cull':r'淘汰|賣汰','sale':r'出(?:豬)?|售'}[typ]
                    quantities=re.findall(r'(?:'+verbs+r')\s*(\d+)\s*(?:頭|隻|棟)',re.split(r'[（(]',text,1)[0])
                    if not quantities:continue
                    q=sum(int(n) for n in quantities);alloc=[]
                    for b,n in re.findall(r'(\d+)棟\s*[＊*]\s*(\d+)',text):alloc.append({'barn':int(b),'quantity':int(n)})
                    if not alloc and (bm:=re.search(r'[（(]\s*(\d+)棟\s*[)）]',text)):alloc=[{'barn':int(bm[1]),'quantity':q}]
                    if alloc:q=sum(a['quantity'] for a in alloc)
                    event_date=date(int(as_of[:4]),int(dm[1]),int(dm[2])).isoformat()
                    parsed.append({'date':event_date,'type':typ,'quantity':q,'allocations':alloc,'cell':ref,'text':line.strip()})
                # A simple sum can resolve shipment counts including market deaths.
                # Preserve the original text and correction evidence; never eval().
                formula=c.get('formula') or ''
                terms=[int(n) for n in formula.split('+')] if re.fullmatch(r'\d+(?:\+\d+)*',formula) else []
                if len(terms)==len(parsed) and sum(terms)==c['value'] and sum(e['quantity'] for e in parsed)!=c['value']:
                    for e,n in zip(parsed,terms):
                        if e['quantity']!=n:e['quantity']=n;e['allocations']=[];e['formula_count_corrected']=True
                if sum(e['quantity'] for e in parsed)!=c['value']:
                    known=sum(e['quantity'] for e in parsed)
                    unresolved.append({'cell':ref,'type':typ,'quantity':c['value'],'unresolved_quantity':c['value']-known if known<=c['value'] else c['value'],'comment':c.get('comment','')})
                    if known<=c['value']:events.extend(parsed)
                else:events.extend(parsed)
        rows.append({'key':str(r),'name':name,'barns':barns,'barn_text':barn_text,'birth_date':birth,'entry_date':entry,'entry_age_days':(date.fromisoformat(entry)-date.fromisoformat(birth)).days,'totals':totals,'weights':weights,'events':events,'unresolved_cells':unresolved,'comments':comments})
    if not rows:raise Invalid('unsupported_workbook')
    all_barns=[b for row in rows for b in row['barns']]
    if len(all_barns)!=len(set(all_barns)):raise Invalid('ambiguous_workbook_barns')
    totals={k:sum(row['totals'][k] for row in rows) for k in ('entry','remaining','sold','dead','culled','missing')}
    for key,col in [('entry','R'),('remaining','S'),('sold','T'),('dead','Z'),('culled','AA'),('missing','AB')]:
        if count(col+'4')!=totals[key]:raise Invalid('workbook_balance_mismatch')
    return {'format':'alice-workbook-review-1','source_sha256':hashlib.sha256(raw).hexdigest(),'as_of':as_of,'sheet':current['name'],'sheets':[s['name'] for s in sheets],'totals':totals,'rows':rows,'archive_rows':archive_review(sheets,epoch),'issues':issues,'historical_sheet_preserved':True}


def archive_review(sheets,epoch):
    """Old sheets are source history only; weekly weights have no invented date."""
    rows=[]
    for sheet in sheets:
        if '肉豬各周存欄頭數(舊)' not in sheet['name'].replace('（','(').replace('）',')'):continue
        cells=sheet['cells']
        def value(ref):return cells.get(ref,{}).get('value')
        def iso(v):return (epoch+timedelta(days=int(v))).isoformat() if isinstance(v,(int,float)) and not isinstance(v,bool) else None
        anchors=sorted(int(ref[1:]) for ref in cells if re.fullmatch(r'A\d+',ref) and str(value(ref) or '').startswith('JD-'))
        for r in anchors:
            entry=iso(value(f'C{r}'));birth=iso(value(f'B{r}'));text=str(value(f'R{r}') or '')
            barns=[int(x) for x in re.findall(r'\d+',text)]
            if not entry or not barns:continue
            weights=[];events=[];unresolved=[]
            for rr in range(r,r+3):
                mean=value(f'G{rr}')
                if isinstance(mean,(int,float)) and mean>0:
                    weights.append({'date':None,'mean_kg':mean,'sample_count':None,'cell':f'G{rr}',
                        'age_weeks_hint':value(f'F{rr}'),'formula':cells[f'G{rr}'].get('formula')})
                typ={'死亡':'death','賣汰':'cull','售出':'sale'}.get(value(f'V{rr}'))
                if not typ:continue
                for ref,cell in cells.items():
                    match=re.fullmatch(r'([A-Z]+)(\d+)',ref)
                    if not match or int(match[2])!=rr:continue
                    column=0
                    for ch in match[1]:column=column*26+ord(ch)-64
                    q=cell.get('value')
                    if column<23 or not isinstance(q,(int,float)) or q<=0 or int(q)!=q:continue
                    parsed=[]
                    for line in cell.get('comment','').splitlines():
                        dm=re.match(r'\s*(\d{1,2})/(\d{1,2})\s*(.*)',line)
                        if not dm:continue
                        verb={'death':r'死(?:亡)?','cull':r'淘汰|賣汰','sale':r'出(?:豬)?|售'}[typ]
                        quantities=re.findall(r'(?:'+verb+r')\s*(\d+)\s*(?:頭|隻)',re.split(r'[（(]',dm[3],1)[0])
                        if not quantities:continue
                        candidates=[]
                        for year in (int(entry[:4]),int(entry[:4])+1):
                            try:d=date(year,int(dm[1]),int(dm[2]))
                            except ValueError:continue
                            if date.fromisoformat(entry)<=d<=date.fromisoformat(entry)+timedelta(days=300):candidates.append(d.isoformat())
                        quantity=sum(map(int,quantities));alloc=[{'barn':int(b),'quantity':int(n)} for b,n in re.findall(r'(\d+)棟\s*[＊*]\s*(\d+)',dm[3])]
                        if not alloc and (bm:=re.search(r'[（(]\s*(\d+)棟\s*[)）]',dm[3])):alloc=[{'barn':int(bm[1]),'quantity':quantity}]
                        parsed.append({'date':candidates[0] if len(candidates)==1 else None,'type':typ,'quantity':quantity,
                            'allocations':alloc,'cell':ref,'text':line.strip(),'year_from_entry_context':True})
                    known=sum(e['quantity'] for e in parsed)
                    if known<=q:events.extend(parsed)
                    if known!=q:unresolved.append({'cell':ref,'type':typ,'quantity':int(q),
                        'unresolved_quantity':int(q)-known if known<q else int(q),'comment':cell.get('comment','') or str(value(match[1]+'3') or '')})
            rows.append({'key':str(r),'name':value(f'A{r}'),'entry_date':entry,'birth_date':birth,
                'barns':barns,'barn_text':text,'sheet':sheet['name'],'weights':weights,'events':events,'unresolved_cells':unresolved,
                'totals':{k:value(f'{c}{r}') for k,c in [('entry','M'),('remaining','N'),('sold','O'),('dead','S'),('culled','T')]}})
    return rows

def allocate(total,weights):
    keys=sorted(weights);denominator=sum(weights.values())
    if total<0 or not keys or denominator<=0:
        if total==0:return {k:0 for k in keys}
        raise Invalid('allocation_required')
    exact={k:total*weights[k]/denominator for k in keys};result={k:math.floor(exact[k]) for k in keys}
    for k in sorted(keys,key=lambda k:(-(exact[k]-result[k]),k))[:total-sum(result.values())]:result[k]+=1
    return result

def parse_counts(text):
    if not isinstance(text,str) or len(text)>10000:raise Invalid('invalid_counts')
    counts={}
    for line in text.splitlines():
        if not line.strip():continue
        m=re.fullmatch(r'\s*(\d+)\s*[/：:,\t ]\s*(\d+)\s*',line)
        if not m or int(m[1]) in counts:raise Invalid('invalid_counts')
        counts[int(m[1])]=int(m[2])
    return counts

def reconcile(report,counts,counts_as_of,closed_barns=()):
    counts_date=date.fromisoformat(counts_as_of);source_date=date.fromisoformat(report['as_of'])
    if not counts_date<=source_date or (source_date-counts_date).days>31:raise Invalid('invalid_counts_date')
    if set(counts)-{b for row in report['rows'] for b in row['barns']}:raise Invalid('invalid_counts')
    result=[];issues=[]
    for row in report['rows']:
        after=[e for e in row['events'] if counts_as_of<e['date']<=report['as_of']]
        previous=dict(row['totals'])
        for e in after:
            previous[{'sale':'sold','cull':'culled','death':'dead'}[e['type']]]-=e['quantity'];previous['remaining']+=e['quantity']
        provided={b:counts[b] for b in row['barns'] if b in counts};missing=[b for b in row['barns'] if b not in provided]
        desired=previous['remaining'];working=dict(provided);row_issues=[]
        if len(missing)==1:working[missing[0]]=max(0,desired-sum(provided.values()))
        elif missing:raise Invalid('allocation_required')
        if not working or (desired and sum(working.values())==0):raise Invalid('allocation_required')
        adjustment=desired-sum(working.values())
        closed=set(row['barns'])&set(closed_barns)
        if adjustment and abs(adjustment)>max(3,desired*.05) and not closed:
            row_issues.append('large_adjustment');before={b:None for b in row['barns']};current=dict(before)
        else:
            before=allocate(desired,working) if adjustment else dict(working)
            current=dict(before)
            for e in after:
                for a in e['allocations']:
                    if a['barn'] in current:current[a['barn']]-=a['quantity']
            # Unknown shipment barns remain unknown in the historical events.
            # Only the labelled provisional stock allocation is reconciled.
            target=row['totals']['remaining']
            if closed:
                for b in closed:current[b]=0
                live={b:q for b,q in current.items() if b not in closed}
                current.update(allocate(target,live))
                if any(before.get(b,0)>0 for b in closed):row_issues.append('closed_barn_historical_date_unknown');before={b:None for b in row['barns']}
            elif sum(current.values())!=target:
                if any(q<0 for q in current.values()):raise Invalid('allocation_required')
                outflow=sum(current.values())-target
                candidates={b:current[b] for b in missing if current[b]>0}
                if candidates and outflow>=0 and sum(candidates.values())>=outflow:
                    kept=allocate(sum(candidates.values())-outflow,candidates);current.update(kept)
                else:current=allocate(target,current)
                row_issues.append('unassigned_outflow_provisional_allocation')
            if any(q<0 for q in current.values()) or sum(current.values())!=target:raise Invalid('allocation_required')
        snapshots={report['as_of']:row['totals']}
        historical_reliable=True
        for cell in row['unresolved_cells']:
            period=re.search(r'(?m)^\s*\d{1,2}/\d{1,2}\s*[-~～]\s*(\d{1,2})/(\d{1,2})',cell['comment'])
            period_end=date(source_date.year,int(period[1]),int(period[2])) if period else None
            if period_end is None or period_end>counts_date:historical_reliable=False
        if counts_as_of!=report['as_of']:
            if historical_reliable:snapshots[counts_as_of]=previous
            else:row_issues.append('historical_events_incomplete');before={b:None for b in row['barns']}
        result.append({'key':row['key'],'snapshots':snapshots,'before':{str(k):v for k,v in before.items()},'current':{str(k):v for k,v in current.items()},'provided':{str(k):v for k,v in provided.items()},'adjustment':adjustment,'issues':row_issues})
        issues.extend({'row':row['key'],'issue':i} for i in row_issues)
    return {'counts_as_of':counts_as_of,'source_as_of':report['as_of'],'rows':result,'issues':issues,'method':'user_estimate_reconciled_to_authoritative_excel'}
