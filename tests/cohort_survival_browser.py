"""Real Chromium: whole-batch percentages and inspectable calculation sources."""
import base64,json,sys,tempfile,threading,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from legacy_fixture import workbook_fixture
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(s):checks.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011');store.create_user('reader','83000012','viewer')
 def add(kind,**body):return store.mutate(owner,kind,body,str(uuid.uuid4()))
 store.import_workbook(owner,{'filename':'synthetic.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'},str(uuid.uuid4()))
 source=store.snapshot()['batches'];ended=next(b for b in source if b['legacy_barn']==2);add('movements',batch_id=ended['id'],date='2026-10-15',type='sale',quantity=45);store.mutate(owner,'batches',ended|{'status':'ended'},str(uuid.uuid4()),ended['id'])
 barns=[add('barns',name=f'{n}棟',group='') for n in (3,4,5)]
 a=add('batches',barn_id=barns[0]['id'],name='JD-WEIGHTED',entry_date='2026-01-01',entry_count=100,status='ended');b=add('batches',barn_id=barns[1]['id'],name='JD-WEIGHTED',entry_date='2026-01-01',entry_count=900,status='active');add('batches',barn_id=barns[2]['id'],name='JD-ZERO',entry_date='2026-01-01',entry_count=0,status='active')
 for batch,q in ((a,10),(b,9)):add('movements',batch_id=batch['id'],date='2026-10-15',type='death',quantity=q)
 add('movements',batch_id=a['id'],date='2026-10-15',type='sale',quantity=90)
 movement_count=len(store.snapshot()['movements']);original=store.export_backup();server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(f'http://127.0.0.1:{server.server_port}')
   def login(name,password):
    page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(password);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])');page.wait_for_selector('.cohort-total',state='attached')
   login('owner','83000011');page.locator('[data-daily-view=overview]').click();total=page.locator('[data-cohort-total="JD-TEST|2026-09-09"]');assert total.locator('.cohort-total-head > strong').inner_text().startswith('96.00%');source_card=total.locator('xpath=..');assert source_card.locator('.overview-barn').count()==1;assert source_card.locator('.barn-survival summary').inner_text()=='— ⓘ';total.locator('summary').click();assert total.locator('dd').all_text_contents()==['100 頭','4 頭'];assert '1棟、2棟' in total.inner_text();assert '含已出清' in total.inner_text();passed('whole source cohort shows 96% with 100-entry/4-death basis including sold-out barn; active barn remains unknown')
   weighted=page.locator('[data-cohort-total="JD-WEIGHTED|2026-01-01"]');assert weighted.locator('strong').inner_text().replace(',','.').startswith('98.10%');weighted.locator('summary').click();assert weighted.locator('dd').all_text_contents()==['1,000 頭','19 頭'];assert '3棟、4棟' in weighted.inner_text();assert weighted.locator('xpath=..').locator('.overview-barn').count()==1;passed('unequal 100/900 entry denominators yield 98.10% instead of average percentages; ended barn retained')
   zero=page.locator('[data-cohort-total="JD-ZERO|2026-01-01"]');assert zero.locator('strong').inner_text().startswith('—');zero.locator('summary').click();assert '尚無正的進場分母' in zero.inner_text();passed('zero denominator shows unknown with reason, never 0% or 100%')
   for i in range(3):
    page.evaluate('async()=>await renderHome()');page.select_option('#language','vi' if i%2==0 else 'zh');page.wait_for_function('()=>document.documentElement.lang===(localStorage.getItem("pig-language")==="vi"?"vi":"zh-Hant")');assert total.locator('details').evaluate('(e)=>e.open');assert weighted.locator('details').evaluate('(e)=>e.open');assert weighted.locator('strong').inner_text().replace(',','.').startswith('98.10%')
   page.select_option('#language','zh');assert store.export_backup()['records']==original['records'];passed('three repaint/language rounds preserve expanded explanation and do not write farm data')
   page.locator('[data-daily-view=entry]').click();f=page.locator('#movement-form');f.locator('[name=barn_id]').select_option(barns[1]['id']);f.locator('[name=quantity]').fill('1');f.locator('[name=type]').select_option('death');f.locator('[name=date]').fill('2026-10-16');f.locator('button.primary').click();page.wait_for_function('()=>pending===null');page.wait_for_function('()=>document.querySelector("[data-cohort-total=\\"JD-WEIGHTED|2026-01-01\\"] strong").textContent.startsWith("98.00%")');assert len(store.snapshot()['movements'])==movement_count+1;passed('real HTTP save refreshes cohort total to 98.00% and records death once')
   page.evaluate('async()=>{data.dashboard.as_of="2000-01-01";await renderHome()}');assert weighted.locator('strong').inner_text().startswith('98.00%');assert '2000-01-01' not in weighted.inner_text();assert page.evaluate('data.dashboard.as_of')!='2000-01-01';passed('stale dashboard date uses newly fetched cohort summary rather than yesterday values')
   page.locator('[data-daily-view=overview]').click();cases=0
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.select_option('#language',language)
     for size in ('small','medium','large'):
      page.locator('#font-control').evaluate('(e)=>e.open=true');page.locator(f'#font-control [data-text-size={size}]').click();page.locator('#font-control').evaluate('(e)=>e.open=false');assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+2'),(width,language,size);cases+=1
   passed(f'{cases} phone/tablet/desktop language/font layouts fit with expanded calculation details')
   page.set_viewport_size({'width':390,'height':844});page.select_option('#language','zh');page.locator('#font-control').evaluate('(e)=>e.open=true');page.locator('#font-control [data-text-size=medium]').click();page.locator('#font-control').evaluate('(e)=>e.open=false');page.locator('#barns details').evaluate_all('(els)=>els.forEach(e=>e.open=false)');source_card.scroll_into_view_if_needed();page.screenshot(path=str(root/'artifacts/cohort-survival-mobile.png'));total.locator('summary').click();total.scroll_into_view_if_needed();page.screenshot(path=str(root/'artifacts/cohort-survival-basis-mobile.png'))
   page.locator('nav [href="#settings"]').click();page.locator('.settings-fold:has(#barn-form) > summary').click();assert '非批號' in page.locator('#barn-form').inner_text();assert '組別可留空' in page.locator('.settings-fold:has(#barn-form)').inner_text();passed('barn setup explains optional custom groups separately from batch codes')
   page.locator('#logout').click();login('reader','83000012');assert page.locator('[data-cohort-total="JD-WEIGHTED|2026-01-01"] strong').inner_text().startswith('98.00%');assert not errors;passed('read-only account sees same cohort totals; no uncaught JavaScript errors');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/cohort-survival-browser-results.json').write_text(json.dumps({'version':VERSION,'mode':'real Chromium, isolated synthetic data; no physical phone','passed':checks},ensure_ascii=False,indent=2));print('Completed',len(checks),'cohort survival browser scenarios')
