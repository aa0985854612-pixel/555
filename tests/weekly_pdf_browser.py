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
def pdf_info(path):
 info=subprocess.check_output(['pdfinfo',str(path)],text=True)
 assert re.search(r'Pages:\s+1\b',info),info
 size=re.search(r'Page size:\s+([\d.]+) x ([\d.]+)',info)
 assert abs(float(size[1])-595.28)<1 and abs(float(size[2])-841.89)<1,info
 assert path.stat().st_size<4_000_000
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011');store.create_user('reader','83000012','viewer')
 def add(kind,**d):return store.mutate(owner,kind,d,str(uuid.uuid4()))
 barns=[add('barns',name=f'{n}棟',feed_vendor='養全') for n in (12,24)]
 batches=[add('batches',name='SYNTHETIC-18-WEEKS',barn_id=b['id'],entry_date='2026-06-19',entry_age_days=70,entry_count=n,entry_mean_kg=21.9,status='active') for b,n in zip(barns,(500,206))]
 for on,typ,n,b in [('2026-06-26','death',3,0),('2026-07-17','death',3,0),('2026-07-24','death',2,0),('2026-07-31','death',1,1),('2026-08-07','death',2,1),('2026-08-14','death',1,0),('2026-09-25','death',1,1),('2026-10-09','death',3,1),('2026-08-07','cull',3,0),('2026-08-21','cull',2,1),('2026-10-13','sale',3,1),('2026-10-16','sale',80,0)]:add('movements',date=on,type=typ,quantity=n,batch_id=batches[b]['id'])
 for on,kg,b in [('2026-10-13',4000,1),('2026-10-13',2000,0),('2026-10-15',2000,1)]:add('feed_orders',date=on,kg=kg,display_unit='ton',vendor='養全',item='大豬料',allocations=[{'batch_id':batches[b]['id'],'kg':kg}])
 before=store.snapshot();server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(user,pw):page.goto(url);page.locator('#login-form [name=username]').fill(user);page.locator('#login-form [name=password]').fill(pw);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   def generate():page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-export-actions:not([hidden])')
   login('owner','83000011');page.locator('#movement-form details').evaluate('(e)=>e.open=true');page.locator('#movement-form [name=note]').fill('unsaved next entry')
   page.locator('#open-daily-weekly-report').click();page.locator('#weekly-cohort').select_option('SYNTHETIC-18-WEEKS|2026-06-19');page.locator('#weekly-to').fill('2026-10-17');generate();sheet=page.locator('#weekly-sheet-body');tables=sheet.locator('.weekly-table');assert tables.count()==2
   assert tables.nth(0).locator('thead th').count()==tables.nth(1).locator('thead th').count()==14
   assert tables.nth(0).locator('thead th').all_text_contents()[1:]==['第'+str(i)+'週' for i in range(11,24)]
   assert tables.nth(1).locator('thead th').all_text_contents()[1:6]==['第'+str(i)+'週' for i in range(24,29)]
   assert tables.nth(1).locator('thead th').all_text_contents()[6:9]==['第29週','第30週','第31週'];assert tables.nth(1).locator('thead th').all_text_contents()[9:]==['']*5
   assert set(sheet.locator('.weekly-feed-entry').all_text_contents())=={'10/13+4（24）','10/13+2（12）','10/15+2（24）'}
   assert all(v not in ('0','0.000','—') for v in sheet.locator('.weekly-table td').all_text_contents())
   assert sheet.locator('.weekly-death td').all_text_contents()[0]=='' and sheet.locator('.weekly-death td').all_text_contents()[1]=='3'
   passed('18-week report has two fixed 13-column bands; unentered cells blank and all three feed notes retained')
   page.evaluate('()=>{window.realWeeklyPdf=window.weeklyPdf;window.weeklyPdf=(model)=>{window.lastPdfModel=model;return window.realWeeklyPdf(model)}}')
   with page.expect_download() as dl:page.locator('#weekly-print').click()
   output=root/'artifacts/weekly-two-bands-a4.pdf';dl.value.save_as(output);pdf_info(output);model=page.evaluate('lastPdfModel')
   assert all(pair[0] in ('批次','棟舍','進場頭數','棟舍預設廠商','本期間登記料別','出豬備註') for pair in model['basics']);assert len(model['pages'])==1 and len(model['pages'][0])==2
   assert all(len(b['headers'])==13 for b in model['pages'][0]);assert model['pages'][0][1]['headers'][5:8]==['29週','30週','31週'];assert model['pages'][0][1]['rows'][0]['cells'][5:8]==['10/23','10/30','11/6'];assert all(all(cell=='' for cell in row['cells'][5:8]) for row in model['pages'][0][1]['rows'][1:]);assert '週期預排至31週' in model['legend']
   assert dict(model['totals'])=={'淘汰數（隻）':'5','死亡數（隻）':'16','叫料登記量（噸）':'8','正常出豬（隻）':'83'}
   assert model['pages'][0][1]['rows'][3]['cells'][3]=='10/13+4（24）\n10/13+2（12）\n10/15+2（24）'
   assert all(x not in ('0','0.000','—') for b in model['pages'][0] for row in b['rows'] for x in row['cells'])
   passed('actual downloaded PDF is exactly one portrait A4, with totals 5/16/8/83 and full three-line feed cell')
   with page.expect_download() as dl:page.locator('#weekly-csv').click()
   csvrows=list(csv.reader(io.StringIO(Path(dl.value.path()).read_text(encoding='utf-8-sig'))));deaths=next(r for r in csvrows if r and r[0]=='死亡數（隻）' and len(r)>2);assert deaths[1]=='' and deaths[2]=='3';assert ['叫料登記量（噸）','8'] in csvrows;cycle=next(r for r in csvrows if r and r[0]=='週期');assert cycle[-1]=='第31週';assert len(deaths)==22 and deaths[-3:]==['','','']
   passed('preview/PDF/CSV extend reliable week labels and dates to 31; planned quantities blank and original period totals unchanged')
   for width in (320,390,768,1366):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.evaluate('(v)=>{lang=v;translate()}',language);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');assert page.locator('#weekly-report-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
   page.evaluate('lang="vi";translate()')
   with page.expect_download() as dl:page.locator('#weekly-print').click()
   vi=root/'artifacts/weekly-two-bands-vi-a4.pdf';dl.value.save_as(vi);pdf_info(vi);passed('Vietnamese PDF is one A4; both languages fit four screen widths')
   page.evaluate('lang="zh";translate()');page.locator('#weekly-close').click();assert page.locator('#movement-form [name=note]').input_value()=='unsaved next entry';assert store.snapshot()==before
   passed('PDF and CSV generation preserve draft and all farm/account data')
   page.locator('#logout').click();login('reader','83000012');page.locator('nav [href="#stats"]').click();page.locator('#open-weekly-report').click();page.locator('#weekly-cohort').select_option('SYNTHETIC-18-WEEKS|2026-06-19');page.locator('#weekly-to').fill('2026-10-17');generate()
   # Stress only the rendering input: oversized notes must be marked and not paginate Safari's PDF.
   page.evaluate('()=>{window.realWeeklyPdf=window.weeklyPdf;window.weeklyPdf=(model)=>{for(const p of model.pages)for(const b of p)for(const row of b.rows)if(row.left)row.cells=row.cells.map(()=>Array(40).fill("10/13+2（12）").join("\\n"));return realWeeklyPdf(model)}}')
   with page.expect_download() as dl:page.locator('#weekly-print').click()
   stress=root/'artifacts/weekly-two-bands-dense-a4.pdf';dl.value.save_as(stress);pdf_info(stress);assert store.snapshot()==before;assert not errors,errors;passed('viewer can download; oversized feed cells stay on one A4 with explicit CSV continuation')
   browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/weekly-two-bands-browser.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'local real Chromium / HTTP / PDF downloads; synthetic data; not physical iPhone/Safari/printer'},ensure_ascii=False,indent=2));print('Completed',len(checks),'two-band PDF scenarios')
