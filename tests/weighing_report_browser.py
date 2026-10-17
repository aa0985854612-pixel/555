"""Real Chromium + isolated SQLite: per-job print/PDF/CSV, never production writes."""
import csv,io,json,sys,tempfile,threading,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from app.operations import save_weighing
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(s):checks.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as folder:
 store=Store(Path(folder)/'farm.db');owner=store.create_user('owner','83000011');store.create_user('reader','83000012','viewer')
 def add(kind,**d):return store.mutate(owner,kind,d,str(uuid.uuid4()))
 barns=[add('barns',name=str(n)+'棟',group='') for n in (19,20)]
 batches=[add('batches',name='JD-REPORT',barn_id=b['id'],entry_date='2026-08-28',entry_count=350,entry_age_days=71,status='active',entry_mean_kg=21.7,entry_mean_date='2026-08-28') for b in barns]
 pens=[{'section':section,'pen':pen,'individual_kg':[40+3*i+n for n in range(6)]} for i,(section,pen) in enumerate([('head','1A'),('middle','1B'),('middle','4B'),('middle','4A'),('middle','7B'),('tail','7A')])]
 first=save_weighing(store,owner,{'session_id':str(uuid.uuid4()),'date':'2026-10-15','batch_id':batches[0]['id'],'age_days':112,'sampling':'synthetic sample','note':'RAW_SOURCE_SHA_DO_NOT_PRINT '+('long import source note '*80),'representative':False,'pens':pens},str(uuid.uuid4()))
 other=save_weighing(store,owner,{'session_id':str(uuid.uuid4()),'date':'2026-10-15','batch_id':batches[1]['id'],'age_days':112,'pens':[{'pen':'2A','individual_kg':[108,97.5,95.11,100]}]},str(uuid.uuid4()))
 original_users=store.export_backup()['users'];server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(name,password):
    page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(password);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   def report(key):
    page.locator(f'[data-print-weighing="{key}"]').click();page.wait_for_selector('#weighing-report-dialog[open]')
   def print_ready():
    page.locator('#print-weighing-report').evaluate('(b)=>{window.print=()=>{};b.click()}');page.emulate_media(media='print')
   page.goto(url);login('owner','83000011');page.locator('nav [href="#weights"]').click();page.wait_for_selector('[data-print-weighing]');report(first['session_id']);body=page.locator('#weighing-report-body')
   assert body.locator('tbody tr').count()==6;assert body.locator('.report-weights b').count()==36
   assert body.locator('.report-result > div > strong').inner_text().startswith('50 ') and '1,800' == body.locator('.report-result p b').nth(1).inner_text()
   assert '350' in body.locator('.report-basics').inner_text() and '21.7 kg' in body.locator('.report-basics').inner_text() and '16 週' in body.inner_text();assert '20棟' not in body.inner_text() and 'RAW_SOURCE_SHA' not in body.inner_text()
   passed('one saved job: 19 barn, six pens, all 36 weights, basic metadata, exact weighted mean 50 without padded decimals; unrelated barn and long source notes excluded')
   with page.expect_download() as download:page.locator('#csv-weighing-report').click()
   dl=download.value;rows=list(csv.reader(io.StringIO(Path(dl.path()).read_text(encoding='utf-8-sig'))));header=next(i for i,r in enumerate(rows) if r and r[0]=='區段（選填）');sample=rows[header+1:header+7]
   assert len(sample)==6 and sample[0][1]=='1A' and [float(v) for v in sample[0][2:8]]==pens[0]['individual_kg'];assert sum(float(r[-3]) for r in sample)==36 and sum(float(r[-2]) for r in sample)==1800;assert any(r and r[0]=='本次總平均' and abs(float(r[1])-1800/36)<1e-8 for r in rows);assert '2026-10-15' in dl.suggested_filename and '19棟' in dl.suggested_filename
   passed('downloaded UTF-8 CSV opens as a table with basic metadata, six separate weight columns and full-precision weighted totals')
   print_ready();assert page.locator('#workspace').is_hidden() and page.locator('#weighing-report-dialog').is_hidden();assert page.locator('#weighing-print-root tbody tr').count()==6
   for size in ('small','medium','large'):
    page.evaluate('(s)=>document.documentElement.dataset.textSize=s',size);assert page.locator('#weighing-print-root .report-heading h1').evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)')>=26
   pdf=root/'artifacts/weighing-report-synthetic.pdf';page.pdf(path=str(pdf),prefer_css_page_size=True,print_background=True);page.screenshot(path=str(root/'artifacts/weighing-report-print.png'),full_page=True)
   page.emulate_media(media='screen');page.evaluate('window.dispatchEvent(new Event("afterprint"))');assert page.title()=='嘉得肉豬紀錄';page.locator('#close-weighing-report').click();passed('independent A4 PDF/print contains only the report, readable fixed print typography and restored page title')
   # A save outside the current history filter still offers its exact saved report.
   wf=page.locator('#weight-filter');wf.locator('[name=from]').fill('2026-10-14');wf.locator('[name=to]').fill('2026-10-14');wf.locator('button').first.click();page.wait_for_function('()=>!document.querySelector("[data-print-weighing]")')
   f=page.locator('#weighing-form');f.locator('[name=barn_id]').select_option(barns[0]['id']);f.locator('[name=date]').fill('2026-10-16');f.locator('[name=age_weeks]').fill('16');pn=page.locator('#weighing-pens .weighing-pen');pn.first.locator('[data-pen-field=pen]').fill('1A');pn.first.locator('.pig-weights input').nth(0).fill('50');pn.first.locator('.pig-weights input').nth(1).fill('50');page.locator('#add-weighing-pen').click();pn.nth(1).locator('[data-pen-field=pen]').fill('4B');pn.nth(1).locator('[data-pen-field=mode]').select_option('total');pn.nth(1).locator('[data-pen-field=count]').fill('4');pn.nth(1).locator('[data-pen-field=total_kg]').fill('240')
   page.route('**/api/weighings',lambda route:route.abort('failed'));f.locator('[type=submit]').click();page.wait_for_selector('#pending:not([hidden])');assert page.locator('#weighing-saved-export').is_hidden();assert len(store.snapshot()['weights'])==7;page.unroute('**/api/weighings');page.locator('#retry').click();page.wait_for_function('()=>pending===null');page.wait_for_selector('#weighing-saved-export:not([hidden])');page.locator('[data-open-weighing-report]').click();assert body.locator('tbody tr').count()==2 and '56.67' in body.locator('.report-result').inner_text();assert body.locator('.report-weights b').count()==2 and '未逐隻秤重' in body.inner_text();assert f.locator('[name=date]').input_value()=='2026-10-16' and f.locator('[name=batch_id]').input_value()==batches[0]['id'];page.locator('#close-weighing-report').click()
   passed('failed save shows no success/export; retry offers actual saved job even outside history filters, preserves scope and weights 2+4 samples correctly')
   # A second job on the same date must remain a distinct export.
   pn=page.locator('#weighing-pens .weighing-pen');pn.first.locator('[data-pen-field=pen]').fill('=1+1');pn.first.locator('.pig-weights input').nth(0).fill('80');f.locator('[type=submit]').click();page.wait_for_function('()=>pending===null');page.wait_for_function('()=>document.querySelector("#weighing-saved-export").textContent.includes("80 kg")');page.locator('[data-open-weighing-report]').click();assert body.locator('tbody tr').count()==1 and body.locator('.report-result > div > strong').inner_text().startswith('80 ')
   with page.expect_download() as download:page.locator('#csv-weighing-report').click()
   content=Path(download.value.path()).read_text(encoding='utf-8-sig');assert "'=1+1" in content;assert '340' not in content
   passed('same-date jobs remain separate; text in CSV is quoted and spreadsheet formulas neutralized')
   cases=0
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.evaluate('(v)=>{lang=v;translate()}',language)
     for size in ('small','medium','large'):
      page.evaluate('(s)=>document.documentElement.dataset.textSize=s',size);assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+2');assert page.locator('#weighing-report-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1'),(width,language,size);cases+=1
   page.set_viewport_size({'width':390,'height':844});page.evaluate('lang="zh";translate();document.documentElement.dataset.textSize="medium"');page.screenshot(path=str(root/'artifacts/weighing-report-mobile.png'));page.locator('#close-weighing-report').click();passed(f'{cases} phone/tablet/desktop, language and font layouts; only the sample table scrolls horizontally on small screens')
   f.locator('details').evaluate('(e)=>e.open=true')
   for _ in range(3):
    f.locator('[name=note]').fill('unsaved next weighing');page.evaluate('async()=>await refresh()');page.select_option('#language','vi');page.select_option('#language','zh');assert f.locator('[name=note]').input_value()=='unsaved next weighing';page.locator('[data-open-weighing-report]').click();page.locator('#close-weighing-report').click();assert f.locator('[name=note]').input_value()=='unsaved next weighing'
   passed('three sync/language/export rounds retain the next unsaved weighing draft')
   page.locator('#logout').click();login('reader','83000012');page.locator('nav [href="#weights"]').click();assert page.locator('#weighing-saved-export').is_hidden();wf.locator('[name=from]').fill('2026-10-15');wf.locator('[name=to]').fill('2026-10-16');wf.locator('button').first.click();page.wait_for_selector('[data-print-weighing]');report(other['session_id']);assert '20棟' in body.inner_text() and body.locator('tbody tr').count()==1 and body.locator('.report-result > div > strong').inner_text().startswith('100.15 ');assert f.locator('[type=submit]').is_disabled();assert not errors,errors;assert store.export_backup()['users']==original_users;page.locator('#close-weighing-report').click();passed('viewer can export saved reports, cannot write, sees no prior user receipt; account hashes retained, no JavaScript errors')
   report(other['session_id'])
   assert body.locator('.report-weights b').all_text_contents()==['108','97.5','95.11','100']
   assert body.locator('.report-pen-mean').inner_text()=='100.15'
   assert body.locator('.report-result p b').nth(1).inner_text()=='400.61'
   page.select_option('#language','vi');assert body.locator('.report-weights b').all_text_contents()==['108','97,5','95,11','100'];page.select_option('#language','zh')
   with page.expect_download() as download:page.locator('#csv-weighing-report').click()
   decimals=list(csv.reader(io.StringIO(Path(download.value.path()).read_text(encoding='utf-8-sig'))))
   assert any(r and r[0]=='本次總平均' and abs(float(r[1])-100.1525)<1e-9 for r in decimals)
   print_ready();pdf=root/'artifacts/weighing-report-decimals.pdf';page.pdf(path=str(pdf),prefer_css_page_size=True,print_background=True)
   import subprocess
   printed=subprocess.check_output(['pdftotext','-layout',str(pdf),'-']).decode()
   assert '97.5' in printed and '95.11' in printed and '108.00' not in printed and '100.00' not in printed
   assert store.snapshot()['weights'][6]['individual_kg']==[108,97.5,95.11,100]
   page.emulate_media(media='screen');page.evaluate('window.dispatchEvent(new Event("afterprint"))');page.locator('#close-weighing-report').click()
   passed('integer and fractional weights trim only trailing zeros in Chinese/Vietnamese preview and actual PDF; CSV and stored numbers retain full precision')
   browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/weighing-report-browser-results.json').write_text(json.dumps({'version':VERSION,'mode':'real Chromium/HTTP/SQLite; synthetic data and mobile viewports, not Safari or physical phones','checks':checks},ensure_ascii=False,indent=2));print('Completed',len(checks),'weighing report scenarios')
