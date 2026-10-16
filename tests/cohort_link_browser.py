"""Real browser grouping of separately dated arrivals; no production data."""
import sys,tempfile,threading,uuid,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(s):checks.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');admin=store.create_user('owner','83000011');store.create_user('reader','83000012','viewer')
 def add(kind,**d):return store.mutate(admin,kind,d,str(uuid.uuid4()))
 barns=[add('barns',name=f'{n}棟',group='') for n in (15,21)];first=add('batches',name='DEMO-LINK',barn_id=barns[0]['id'],entry_date='2026-10-09',entry_count=100,entry_age_days=71,status='active');second=add('batches',name='DEMO、LINK',barn_id=barns[1]['id'],entry_date='2026-10-16',entry_count=30,entry_age_days=71,status='active');old=add('batches',name='OLD-LINK',barn_id=barns[1]['id'],entry_date='2026-05-01',entry_count=0,status='ended');original=store.export_backup()['users']
 server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(name,password):page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(password);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   page.goto(url);login('owner','83000011');page.locator('nav [href="#settings"]').click();page.wait_for_selector('.cohort-setting');page.locator(f'[data-member="{second["id"]}"]').evaluate('(e)=>e.closest("details").open=true');page.locator(f'[data-edit=batches][data-id="{second["id"]}"]').click();f=page.locator('#batch-form');f.locator('[name=same_batch_as]').select_option(first['id']);assert f.locator('[name=name]').input_value()=='DEMO-LINK';assert f.locator('[name=entry_date]').input_value()=='2026-10-16';assert f.locator('[name=entry_count]').input_value()=='30'
   for _ in range(3):
    page.evaluate('async()=>await refresh()');page.select_option('#language','vi');page.select_option('#language','zh');assert f.locator('[name=same_batch_as]').input_value()==first['id'];assert f.locator('[name=entry_count]').input_value()=='30'
   passed('select existing same batch while preserving later entry date and count through three sync/language rounds')
   with page.expect_response(lambda r:'/api/batches/'+second['id'] in r.url and r.request.method=='PUT') as response:f.locator('.primary').click()
   assert response.value.status==200;page.wait_for_function('()=>pending===null');page.wait_for_function('(id)=>data.batches.find(b=>b.id===id)?.same_batch_as!==null',arg=second['id']);page.wait_for_timeout(150);members=page.locator('.cohort-setting').filter(has=page.locator(f'[data-member="{second["id"]}"]'));assert members.locator('.member-row').count()==2;assert '15棟' in members.locator('summary').first.inner_text() and '21棟' in members.locator('summary').first.inner_text();saved=store.snapshot();assert next(b for b in saved['batches'] if b['id']==second['id'])['entry_date']=='2026-10-16';assert next(b for b in saved['batches'] if b['id']==old['id'])['status']=='ended';passed('saved grouping puts both barns together, keeps old ended batch and original physical arrivals')
   page.locator('nav [href="#daily"]').click();page.locator('[data-daily-view=overview]').click();page.wait_for_selector('.overview-cohort');card=page.locator('.overview-cohort').filter(has_text='DEMO-LINK');assert card.locator('.overview-barn').count()==2;assert '100.00%' in card.inner_text();page.locator('[data-daily-view=entry]').click();page.locator('#movement-form [name=barn_id]').select_option(barns[1]['id']);page.locator('#movement-form [name=batch_id]').select_option(second['id']);page.locator('#open-daily-weekly-report').click();assert page.locator('#weekly-cohort').input_value()=='DEMO-LINK|2026-10-09';page.locator('#weekly-barn').select_option('');page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-export-actions:not([hidden])');assert '15棟、21棟' in page.locator('#weekly-sheet-body').inner_text();assert '週齡依棟舍' in page.locator('#weekly-sheet-body').inner_text();page.locator('#weekly-close').click();passed('overview survival and weekly export share the linked cohort, showing per-barn ages instead of a false shared age')
   page.locator('#logout').click();login('reader','83000012');page.locator('nav [href="#daily"]').click();page.locator('[data-daily-view=overview]').click();assert page.locator('.overview-cohort').filter(has_text='DEMO-LINK').locator('.overview-barn').count()==2;assert store.export_backup()['users']==original;assert not errors,errors;passed('viewer sees the same shared group without account changes or uncaught errors');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/cohort-link-browser-results.json').write_text(json.dumps({'version':VERSION,'mode':'real Chromium/HTTP/isolated SQLite; synthetic data, mobile viewport, not physical phone','checks':checks},ensure_ascii=False,indent=2));print('Completed',len(checks),'cohort link scenarios')
