"""Real downloads: two paper bands, sparse cells, fixed A4 PDF, no farm writes.
Fixtures mirror the reported 18-week layout, never use customer database data.
"""
import csv,io,json,re,subprocess,sys,tempfile,threading,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(s):checks.append(s);print('PASS',s,flush=True)
def pdf_info(path,one_page=True):
 info=subprocess.check_output(['pdfinfo',str(path)],text=True)
 assert re.search(r'Pages:\s+1\b',info) if one_page else int(re.search(r'Pages:\s+(\d+)',info)[1])>1,info
 size=re.search(r'Page size:\s+([\d.]+) x ([\d.]+)',info)
 assert abs(float(size[1])-595.28)<1 and abs(float(size[2])-841.89)<1,info
 assert path.stat().st_size<4_000_000
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011');store.create_user('reader','83000012','viewer')
 def add(kind,**d):return store.mutate(owner,kind,d,str(uuid.uuid4()))
 barns=[add('barns',name=f'{n}棟',feed_vendor='養全') for n in (12,24)]
 batches=[add('batches',name='SYNTHETIC-18-WEEKS',barn_id=b['id'],entry_date='2026-06-19',entry_age_days=70,entry_count=n,entry_mean_kg=21.9,status='active') for b,n in zip(barns,(500,206))]
 for on,typ,n,b in [('2026-06-26','death',3,0),('2026-07-17','death',3,0),('2026-07-24','death',1,0),('2026-07-24','death',1,1),('2026-07-31','death',1,1),('2026-08-07','death',2,1),('2026-08-14','death',1,0),('2026-09-25','death',1,1),('2026-10-09','death',3,1),('2026-08-07','cull',3,0),('2026-08-21','cull',2,1),('2026-10-13','sale',3,1),('2026-10-16','sale',80,0)]:add('movements',date=on,type=typ,quantity=n,batch_id=batches[b]['id'],**({'outgoing_destination':'嘉義'} if typ=='sale' and n==80 else {}))
 for on,kg,b in [('2026-10-13',4000,1),('2026-10-13',2000,0),('2026-10-15',2000,1)]:add('feed_orders',date=on,kg=kg,display_unit='ton',vendor='養全',item='大豬料',allocations=[{'batch_id':batches[b]['id'],'kg':kg}])
 extra_barns=[add('barns',name=f'{n}棟') for n in (5,6,7)];extra_batches=[add('batches',name='BARN-COLUMNS',barn_id=b['id'],entry_date='2026-09-01',entry_age_days=70,entry_count=100,status='active') for b in extra_barns]
 for b,on in zip(extra_batches,('2026-09-15','2026-09-16')):add('movements',date=on,type='death',quantity=1,batch_id=b['id'])
 before=store.snapshot();server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(user,pw):page.goto(url);page.locator('#login-form [name=username]').fill(user);page.locator('#login-form [name=password]').fill(pw);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   def generate():
    page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-export-actions:not([hidden])');page.wait_for_selector('#weekly-a4-preview img');page.locator('#weekly-sheet-body > details').evaluate('(e)=>e.open=true')
   login('owner','83000011');page.locator('#movement-form details').evaluate('(e)=>e.open=true');page.locator('#movement-form [name=note]').fill('unsaved next entry')
   page.locator('#open-daily-weekly-report').click();page.locator('#weekly-cohort').select_option('SYNTHETIC-18-WEEKS|2026-06-19');page.locator('#weekly-to').fill('2026-10-17');generate();sheet=page.locator('#weekly-sheet-body');tables=sheet.locator('.weekly-table');assert tables.count()==2
   assert tables.nth(0).locator('thead th').count()==tables.nth(1).locator('thead th').count()==13
   assert tables.nth(0).locator('thead th').all_text_contents()[1:]==['第'+str(i)+'週' for i in range(11,23)]
   assert tables.nth(1).locator('thead th').all_text_contents()[1:7]==['第'+str(i)+'週' for i in range(23,29)]
   assert tables.nth(1).locator('thead th').all_text_contents()[7:11]==['第29週','第30週','第31週','第32週'];assert tables.nth(1).locator('thead th').all_text_contents()[11:]==['']*2
   assert set(sheet.locator('.weekly-feed-entry').all_text_contents())=={'10/13+4(24)','     +2(12)','10/15+2(24)'}
   assert sheet.locator('.weekly-feed-entry').evaluate_all('(xs)=>xs.every(e=>e.scrollWidth<=e.clientWidth+1&&getComputedStyle(e).whiteSpace==="pre")');assert all(v not in ('0','0.000','—') for v in sheet.locator('.weekly-table td').all_text_contents())
   assert sheet.locator('.weekly-death td').all_text_contents()[0]=='' and sheet.locator('.weekly-death td').all_text_contents()[1]=='3'
   assert sheet.locator('.weekly-death td').all_text_contents()[5]=='2'
   assert sheet.locator('.weekly-death-barn h3').all_text_contents()==['第12棟','第24棟']
   for barn in ('12棟','24棟'):assert '7/24 死亡1隻' in sheet.locator(f'.weekly-death-barn[data-barn="{barn}"] .weekly-death-entry').all_text_contents()
   assert sheet.locator('.weekly-death-notes').bounding_box()['x'] < sheet.locator('.weekly-shipping-notes').bounding_box()['x']
   assert '嘉義' not in sheet.locator('.weekly-death-notes').inner_text() and '死亡' not in sheet.locator('.weekly-shipping-notes').text_content()
   passed('18-week report has two balanced 12-column bands ending at week 32 and two blanks; unentered cells blank and all three feed notes retained')
   page.evaluate('()=>{const original=window.weeklyPdf;window.realWeeklyPdf=original;window.weeklyPdf=(model)=>{window.lastPdfModel=model;return original(model)}}')
   page.evaluate("()=>{window.feedDrawCalls=[];window.pdfNoteCalls=[];window.pdfAllTextCalls=[];const original=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...args){pdfAllTextCalls.push(args[0]);if(String(args[0]).includes('死亡')||String(args[0]).includes('嘉義'))pdfNoteCalls.push(args);if(String(args[0]).includes('+'))feedDrawCalls.push(args);return original.apply(this,args)}}")
   generate();page.wait_for_selector('#weekly-a4-preview img')
   with page.expect_download() as dl:page.locator('#weekly-print').click()
   output=root/'artifacts/weekly-two-bands-a4.pdf';dl.value.save_as(output);pdf_info(output);model=page.evaluate('lastPdfModel')
   assert all(pair[0] in ('批次','棟舍','進場頭數','棟舍預設廠商','本期間登記料別','週期') for pair in model['basics']);assert len(model['pages'])==1 and len(model['pages'][0])==2
   assert all(len(b['headers'])==12 for b in model['pages'][0]);assert model['pages'][0][1]['headers'][6:10]==['29週','30週','31週','32週'];assert model['pages'][0][1]['rows'][0]['cells'][6:10]==['10/23','10/30','11/6','11/13'];assert all(all(cell=='' for cell in row['cells'][6:10]) for row in model['pages'][0][1]['rows'][1:]);assert '週期預排至32週' in model['legend']
   assert '… CSV' not in page.evaluate('pdfAllTextCalls');calls=page.evaluate('feedDrawCalls');assert {c[0] for c in calls}=={'10/13+4(24)','     +2(12)','10/15+2(24)'};assert len(calls)==3 and all(len(c)==4 and c[3]>0 for c in calls);assert model['shipping_notes']==['10/16 嘉義80'];assert sheet.locator('.weekly-outgoing-row').count()==0;assert '10/16 嘉義80' in sheet.locator('.weekly-shipping-notes').text_content();assert all(r['singleLine'] for p in model['pages'] for b in p for r in b['rows'] if r.get('left'))
   assert len(model['death_notes'])==9 and {'7/24 12棟 死亡1隻','7/24 24棟 死亡1隻'} <= set(model['death_notes'])
   assert [g['title'] for g in model['death_groups']]==['第12棟','第24棟']
   assert all('棟' not in n for g in model['death_groups'] for n in g['notes'])
   note_calls=page.evaluate('pdfNoteCalls');deaths=[c for c in note_calls if re.match(r'^\d+/\d+ 死亡',c[0])];assert all(c[1]<297.64 for c in deaths);assert all(c[1]>=297.64 for c in note_calls if '嘉義' in c[0]);assert len(deaths)==9
   for index,g in enumerate(model['death_groups']):assert all(24+index*136.82<=c[1]<24+(index+1)*136.82 for c in deaths if c[0] in g['notes'] and c[0]!='7/24 死亡1隻')
   assert dict(model['totals'])=={'淘汰數（隻）':'5','死亡數（隻）':'16','叫料登記量（噸）':'8','正常出豬（隻）':'83'}
   assert model['pages'][0][1]['rows'][3]['cells'][4]=='10/13+4(24)\n     +2(12)\n10/15+2(24)'
   assert all(x not in ('0','0.000','—') for b in model['pages'][0] for row in b['rows'] for x in row['cells'])
   passed('single A4: three complete feed entries each drawn once on one line, separate shipment field and original totals')
   with page.expect_download() as dl:page.locator('#weekly-csv').click()
   csvrows=list(csv.reader(io.StringIO(Path(dl.value.path()).read_text(encoding='utf-8-sig'))));deaths=next(r for r in csvrows if r and r[0]=='死亡數（隻）' and len(r)>2);assert deaths[1]=='' and deaths[2]=='3';assert ['叫料登記量（噸）','8'] in csvrows;cycle=next(r for r in csvrows if r and r[0]=='週期');assert cycle[-1]=='第32週';assert len(deaths)==23 and deaths[-4:]==['','','','']
   perweek=next(r for r in csvrows if r and r[0]=='死亡備註');assert '7/24 12棟 死亡1隻' in perweek[6] and '7/24 24棟 死亡1隻' in perweek[6]
   passed('preview/PDF/CSV extend reliable week labels and dates to 32; planned quantities blank and original period totals unchanged')
   for width in (320,390,768,1366):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.evaluate('(v)=>{lang=v;translate()}',language);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');assert page.locator('#weekly-report-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
   page.evaluate('lang="vi";translate()')
   with page.expect_download() as dl:page.locator('#weekly-print').click()
   vi=root/'artifacts/weekly-two-bands-vi-a4.pdf';dl.value.save_as(vi);pdf_info(vi);assert '… CSV' not in page.evaluate('pdfAllTextCalls');passed('Vietnamese PDF is one A4; both languages fit four screen widths')
   page.evaluate('lang="zh";translate()');page.locator('#weekly-close').click();assert page.locator('#movement-form [name=note]').input_value()=='unsaved next entry';assert store.snapshot()==before
   passed('PDF and CSV generation preserve draft and all farm/account data')
   page.locator('#logout').click();page.wait_for_selector('#login-view:not([hidden])');login('reader','83000012');page.locator('nav [href="#stats"]').click();page.locator('#open-weekly-report').click();page.locator('#weekly-cohort').select_option('SYNTHETIC-18-WEEKS|2026-06-19');page.locator('#weekly-to').fill('2026-10-17');generate()
   # Stress only the rendering input: oversized notes must be marked and not paginate Safari's PDF.
   page.evaluate('()=>{window.stressText=[];const draw=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...args){stressText.push(args[0]);return draw.apply(this,args)};const original=window.weeklyPdf;window.realWeeklyPdf=original;window.weeklyPdf=(model)=>{model.death_notes=Array.from({length:30},(_,i)=>"10/9 24棟 死亡1隻");model.death_groups=[{barn:"12棟",title:"第12棟",notes:Array(30).fill("10/9 死亡1隻")},{barn:"24棟",title:"第24棟",notes:[]}];window.stressNotes=model.death_notes.length;for(const p of model.pages)for(const b of p)for(const row of b.rows)if(row.left)row.cells=row.cells.map(()=>Array(40).fill("     +2(12)").join("\\n"));return original(model)}}')
   generate();page.wait_for_selector('#weekly-a4-preview img')
   with page.expect_download() as dl:page.locator('#weekly-print').click()
   stress=root/'artifacts/weekly-two-bands-dense-a4.pdf';dl.value.save_as(stress);pdf_info(stress,one_page=False);assert store.snapshot()==before;assert page.evaluate('stressNotes')==30;stress_draws=page.evaluate('stressText');shown=stress_draws.count('10/9 死亡1隻');omitted=sum(int(re.fullmatch(r'另(\d+)筆，詳CSV',s)[1]) for s in stress_draws if re.fullmatch(r'另(\d+)筆，詳CSV',s));assert shown>6 and shown+omitted==30;assert not errors,errors;assert stress_draws.count('     +2(12)')==960;passed('viewer can download every one of 960 feed lines across A4 continuations; death notes retain an accurate shown/omitted count under their barn')
   page.evaluate('()=>{window.weeklyPdf=window.realWeeklyPdf;}');page.locator('#weekly-cohort').select_option('BARN-COLUMNS|2026-09-01');page.locator('#weekly-barn').select_option('');page.locator('#weekly-to').fill('2026-09-20');generate()
   assert sheet.locator('.weekly-death-barn h3').all_text_contents()==['第5棟','第6棟','第7棟']
   assert sheet.locator('.weekly-death-barn[data-barn="5棟"] .weekly-death-entry').all_text_contents()==['9/15 死亡1隻']
   assert sheet.locator('.weekly-death-barn[data-barn="6棟"] .weekly-death-entry').all_text_contents()==['9/16 死亡1隻']
   assert sheet.locator('.weekly-death-barn[data-barn="7棟"] .weekly-death-entry').count()==0
   assert sheet.locator('.weekly-death-barn[data-barn="5棟"]').bounding_box()['x'] < sheet.locator('.weekly-death-barn[data-barn="6棟"]').bounding_box()['x'] < sheet.locator('.weekly-death-barn[data-barn="7棟"]').bounding_box()['x']
   with page.expect_download() as dl:page.locator('#weekly-print').click()
   columns=root/'artifacts/weekly-barn-columns-a4.pdf';dl.value.save_as(columns);pdf_info(columns);assert store.snapshot()==before
   passed('5/6/7 barn columns preserve each dated death under its own heading; empty barn remains blank and export stays one portrait A4')
   browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/weekly-two-bands-browser.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'local real Chromium / HTTP / PDF downloads; synthetic data; not physical iPhone/Safari/printer'},ensure_ascii=False,indent=2));print('Completed',len(checks),'two-band PDF scenarios')
