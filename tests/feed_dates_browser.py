"""Same-day feed dates appear once across HTML/A4/CSV; quantities stay separate."""
import csv,io,json,tempfile,threading,uuid,sys,subprocess,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);checks=[]
def passed(s):checks.append(s);print('PASS '+s,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 s=Store(Path(tmp)/'db');u=s.create_user('owner','83000011')
 def add(kind,**body):return s.mutate(u,kind,body,str(uuid.uuid4()))
 barns=[add('barns',name=f'{n}棟') for n in (20,19,5)]
 lots=[add('batches',barn_id=b['id'],name='OTHER' if i==2 else 'FEED-DATES',entry_date='2026-09-20',entry_count=100,entry_age_days=70,status='active') for i,b in enumerate(barns)]
 for on,kg,index in [('2026-09-18',2000,0),('2026-09-18',1000,1),('2026-09-23',2000,0),('2026-09-24',1500,1),('2026-09-23',2000,1),('2026-09-23',500,0)]:add('feed_orders',date=on,kg=kg,display_unit='ton',vendor='養全',item='大豬料',allocations=[{'batch_id':lots[index]['id'],'kg':kg}])
 shared=add('feed_bins',name='19、5',barn_ids=[barns[i]['id'] for i in (1,2)],vendor='養全',active=True)
 add('feed_orders',date='2026-09-23',kg=1000,display_unit='ton',vendor='養全',item='大豬料',feed_bin_id=shared['id'],target_batch_ids=[lots[i]['id'] for i in (1,2)])
 server=Server(('127.0.0.1',0),s);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':900},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(url);page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])');before=s.export_backup()['records']
   page.evaluate('()=>{const pdf=window.weeklyPdf;window.weeklyPdf=m=>{window.feedModel=m;return pdf(m)};window.feedCalls=[];const draw=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...args){if(String(args[0]).includes("+"))feedCalls.push({args,font:this.font});return draw.apply(this,args)};window.feedBlobs=new Map();const create=URL.createObjectURL;URL.createObjectURL=b=>{const url=create(b);feedBlobs.set(url,b);return url;};}')
   page.locator('#open-daily-weekly-report').click();page.locator('#weekly-cohort').select_option('FEED-DATES|2026-09-20');page.locator('#weekly-barn').select_option('');page.locator('#weekly-from').fill('2026-09-20');page.locator('#weekly-to').fill('2026-09-26')
   def generate():
    page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-a4-preview img');page.locator('#weekly-sheet-body > details').evaluate('(e)=>e.open=true')
   generate();sheet=page.locator('#weekly-sheet-body');lines=sheet.locator('.weekly-feed-entry').all_text_contents();assert lines[:3]==['9/23+2(20)','    +2(19)','    +0.5(20)'],lines;assert lines[3].startswith('    +1(') and page.evaluate('t("sharedFeedPending")') in lines[3],lines;assert lines[4]=='9/24+1.5(19)';assert sum('9/23' in line for line in lines)==1;passed('same-day date printed once; interleaved dates sorted; each order and pending shared-bin marker retained')
   model=page.evaluate('feedModel');cells=[cell for panel in model['pages'] for band in panel for row in band['rows'] if row.get('left') for cell in row['cells'] if cell];assert cells==['\n'.join(lines)];pre=model['preentry']['entries'];assert len(pre)==2 and pre[0].startswith('9/18+') and pre[1].startswith('    +');assert {re.sub(r'^9/18|^\s+','',line) for line in pre}=={'+2(20)','+1(19)'},pre;assert sheet.locator('.weekly-preentry-lines>span').all_text_contents()==model['preentry']['entries'];assert dict(model['totals'])['叫料登記量（噸）']=='已知 6',model['totals'];passed('HTML/PDF share exact notation; pre-entry dates grouped separately and six-ton reliable period total preserved')
   calls=page.evaluate('feedCalls');assert all('monospace' in call['font'] for call in calls);drawn=[x['args'][0] for x in calls];assert drawn[:2]==model['preentry']['entries'];assert drawn[2:]==lines,calls
   image=page.evaluate('async()=>Array.from(new Uint8Array(await feedBlobs.get(document.querySelector("#weekly-a4-preview img").src).arrayBuffer()))')
   with page.expect_download() as download:page.locator('#weekly-print').click()
   path=root/'artifacts/feed-dates-a4.pdf';download.value.save_as(path);assert re.search(r'Pages:\s+1\b',subprocess.check_output(['pdfinfo',str(path)],text=True));assert bytes(image) in path.read_bytes();page.locator('#weekly-a4-preview img').screenshot(path=str(root/'artifacts/feed-dates-a4.png'));passed('date continuation uses aligned monospace columns and PDF embeds the exact one-page A4 preview')
   page.evaluate('()=>{window.print=()=>{window.printedFeedPages=Array.from(document.querySelectorAll("#weekly-print-root img"),img=>img.src);};}')
   page.locator('#weekly-browser-print').click();page.wait_for_function('()=>!!window.printedFeedPages');assert page.evaluate('printedFeedPages')==page.locator('#weekly-a4-preview img').evaluate_all('(xs)=>xs.map(img=>img.src)');page.emulate_media(media='print');printed=root/'artifacts/feed-dates-browser-print.pdf';page.pdf(path=str(printed),prefer_css_page_size=True,display_header_footer=False);printed_info=subprocess.check_output(['pdfinfo',str(printed)],text=True);assert re.search(r'Pages:\s+1\b',printed_info),printed_info;size=re.search(r'Page size:\s+([\d.]+) x ([\d.]+)',printed_info);assert abs(float(size[1])-595.28)<1 and abs(float(size[2])-841.89)<1;page.emulate_media(media='screen');passed('browser print uses the same complete A4 images as preview/PDF, without reflow or a blank extra page')
   with page.expect_download() as download:page.locator('#weekly-csv').click()
   rows=list(csv.reader(io.StringIO(Path(download.value.path()).read_text(encoding='utf-8-sig'))));summary=next(row for row in rows if len(row)>2 and row[0]=='飼料逐筆明細');assert summary[1]=='9/23+2(20)\n    +2(19)\n    +0.5(20)\n9/24+1.5(19)';header=next(i for i,row in enumerate(rows) if len(row)==8 and row[0]=='日期' and row[2]==page.evaluate('t("kg")'));raw=[]
   for row in rows[header+1:]:
    if not row:break
    raw.append(row)
   assert len(raw)==5;assert sum(float(r[2]) for r in raw)==7000;assert sum(r[0]=='2026-09-23' for r in raw)==4;passed('CSV summary suppresses repeated date; raw table keeps every full date, quantity and shared reference')
   for width in (320,390,768):
    page.set_viewport_size({'width':width,'height':900});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');assert sheet.locator('.weekly-feed-entry').evaluate_all('(xs)=>xs.every(e=>e.scrollWidth<=e.clientWidth+1&&getComputedStyle(e).whiteSpace==="pre")')
   page.locator('#weekly-barn').select_option(barns[0]['id']);generate();scoped=sheet.locator('.weekly-feed-entry').all_text_contents();assert scoped==['9/23+2(20)','    +0.5(20)'],scoped;assert s.export_backup()['records']==before;assert not errors,errors;passed('mobile layouts fit, one-barn scope stays correct and no farm data changes')
   page.evaluate('()=>{const original=window.weeklyPdf;window.weeklyPdf=m=>{const row=m.pages[0][0].rows.find(r=>r.left);row.cells[0]=Array.from({length:80},(_,i)=>`9/23+${100+i}(20)`).join(String.fromCharCode(10));return original(m)};}');generate();pages=page.locator('#weekly-a4-preview img').count();assert pages>1;page.evaluate('printedFeedPages=null');page.locator('#weekly-browser-print').click();page.wait_for_function('()=>!!window.printedFeedPages');assert len(page.evaluate('printedFeedPages'))==pages;page.emulate_media(media='print');multi=root/'artifacts/feed-browser-print-continuations.pdf';page.pdf(path=str(multi),prefer_css_page_size=True,display_header_footer=False);info=subprocess.check_output(['pdfinfo',str(multi)],text=True);assert int(re.search(r'Pages:\s+(\d+)',info)[1])==pages,info;page.emulate_media(media='screen');assert s.export_backup()['records']==before;passed('multi-page browser print has the exact preview page count, with no clipped continuation or blank page');browser.close()
 finally:server.shutdown();server.server_close()
print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False))
