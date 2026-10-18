"""Automatic batch entry-to-today statistics, real Chromium and isolated HTTP."""
import json,sys,tempfile,threading,uuid
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1];checks=[]
def passed(message):checks.append(message);print('PASS',message,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011');store.create_user('reader','83000012','viewer')
 def add(kind,**body):return store.mutate(owner,kind,body,str(uuid.uuid4()))
 def batch(number,name,on,status='active'):
  barn=add('barns',name=f'{number}棟')
  return add('batches',barn_id=barn['id'],name=name,entry_date=on,entry_count=100,entry_age_days=71,status=status)
 a=batch(11,'JD-OLD','2026-05-22');b=batch(21,'JD-OLD','2026-05-22','ended');c=batch(15,'JD-NEW','2026-10-09')
 for row,on,n in [(a,'2026-05-22',2),(a,'2026-10-13',4),(b,'2026-10-14',3),(a,'2026-10-18',1),(a,'2026-10-19',7),(c,'2026-10-10',2)]:
  add('movements',batch_id=row['id'],date=on,type='death',quantity=n)
 add('movements',batch_id=a['id'],date='2026-10-18',type='sale',quantity=5)
 original=store.export_backup();server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.clock.install(time=datetime(2026,10,18,8,tzinfo=timezone.utc))
   def login(user,pw):
    page.locator('#login-form [name=username]').fill(user);page.locator('#login-form [name=password]').fill(pw);page.locator('#login-form button').click();page.wait_for_function('()=>data&&data.batches.length===3');page.locator('nav [href="#stats"]').click();page.wait_for_selector('.period-total')
   def shown(start,end,total):
    page.wait_for_function('(x)=>document.querySelector(".death-range")?.textContent===x[0]+" → "+x[1]&&document.querySelector(".death-hero > strong")?.textContent.trim().startsWith(x[2]+" ")',arg=[start,end,total])
   page.goto(url);login('owner','83000011');f=page.locator('#stats-filter')
   f.locator('[name=from]').fill('2026-10-18');f.locator('[name=to]').fill('2026-10-18');f.locator('[name=scope_type]').select_option('cohort');f.locator('[name=cohort]').select_option('JD-OLD|2026-05-22')
   shown('2026-05-22','2026-10-18',10)
   assert f.locator('[name=from]').input_value()=='2026-05-22';assert f.locator('[name=to]').input_value()=='2026-10-18';assert page.locator('.death-label').inner_text()=='批次累計死亡（進場日起）'
   assert '21棟：3' in page.locator('.period-barns').inner_text();passed('selecting a cohort replaces stale one-day filters, auto-queries entry through today, includes entry/today and ended barns, excludes sale/future deaths')
   page.locator('.period-total').click();page.wait_for_function('()=>current==="history"');hf=page.locator('#history-filter');assert hf.locator('[name=from]').input_value()=='2026-05-22';assert hf.locator('[name=to]').input_value()=='2026-10-18';q=page.evaluate('query(document.querySelector("#history-filter"))');rows=page.request.get(url+'/api/movements?'+q).json();assert sum(r['quantity'] for r in rows)==10;passed('cumulative total drill-down carries exactly the displayed dates and cohort into history')
   page.locator('nav [href="#stats"]').click();page.wait_for_selector('.period-total');f.locator('[name=from]').fill('2026-10-13');f.locator('[name=to]').fill('2026-10-14');f.locator('button').first.click();shown('2026-10-13','2026-10-14',7);assert page.locator('.death-label').inner_text()=='肉豬週期死亡統計';passed('manual date query remains a custom interval with the matching label and count')
   f.locator('[name=cohort]').select_option('JD-NEW|2026-10-09');shown('2026-10-09','2026-10-18',2);assert f.locator('[name=from]').input_value()=='2026-10-09';passed('switching cohorts refreshes both dates and count without pressing query')
   f.locator('[name=scope_type]').select_option('barn');f.locator('[name=barn_id]').select_option(a['barn_id']);f.locator('[name=batch_id]').select_option(a['id']);shown('2026-05-22','2026-10-18',7);passed('single-barn batch selection also automatically uses its entry-to-today range')
   page.select_option('#language','vi');shown('2026-05-22','2026-10-18',7);assert 'Lũy kế' in page.locator('.death-label').inner_text();assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+2');page.select_option('#language','zh')
   page.reload();page.wait_for_function('()=>data&&data.batches.length===3');page.locator('nav [href="#stats"]').click();shown('2026-05-22','2026-10-18',7);passed('saved filters survive reload; cumulative title translates and mobile layout fits')
   page.locator('#logout').click();login('reader','83000012');f.locator('[name=scope_type]').select_option('cohort');f.locator('[name=cohort]').select_option('JD-OLD|2026-05-22');shown('2026-05-22','2026-10-18',10);assert store.export_backup()['records']==original['records'];assert store.export_backup()['users']==original['users'];assert not errors,errors;passed('viewer can use automatic totals, with all original farm data and account hashes preserved');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/cumulative-deaths-browser-results.json').write_text(json.dumps({'version':VERSION,'checks':checks},ensure_ascii=False,indent=2));print('Completed',len(checks),'cumulative death browser scenarios')
