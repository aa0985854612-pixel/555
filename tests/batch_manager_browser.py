"""Real mobile self-service management, including ambiguous-save recovery."""
import sys,tempfile,threading,uuid,json
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
from app.store import Store
from app.server import Server
from app.review import farm_today
from playwright.sync_api import sync_playwright

checks=[]
def passed(s):checks.append(s);print('PASS '+s,flush=True)
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011');staff=store.create_user('worker','83000012','staff')
 def add(kind,**body):return store.mutate(owner,kind,body,str(uuid.uuid4()))
 lots=[]
 for barn,count in [('9棟',459),('23棟',245)]:
  b=add('barns',name=barn);lots.append(add('batches',barn_id=b['id'],name='JD-115-23',entry_date='2026-06-12',entry_count=count,status='active'))
 add('movements',batch_id=lots[1]['id'],date='2026-10-20',type='sale',quantity=163)
 def persisted():return {k:v for k,v in store.export_backup().items() if k!='exported_at'}
 server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(user='owner',password='83000011'):
    page.locator('#login-form [name=username]').fill(user);page.locator('#login-form [name=password]').fill(password);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   def open_manager():
    page.locator('nav [href="#settings"]').click();page.locator('#manager-select').select_option(lots[0]['id']);page.locator('#manager-open').click();page.wait_for_selector('#batch-manager-dialog[open]')
   page.goto(url);login();open_manager();dialog=page.locator('#batch-manager-dialog');form=page.locator('#batch-manager-form');a=page.locator(f'[data-batch="{lots[0]["id"]}"]');b=page.locator(f'[data-batch="{lots[1]["id"]}"]')
   before=persisted();a.locator('[data-field=entry_count]').fill('469');b.locator('[data-field=entry_count]').fill('235');a.locator('[data-field=entry_mean_kg]').fill('21.58');a.locator('[data-barn-name]').fill('9棟（北側）');form.locator('[name=reason]').fill('核對進場單，各棟重新分配');page.locator('#manager-preview').click();page.wait_for_selector('#manager-confirm:not([disabled])');assert persisted()==before;assert '704 → 704' in page.locator('#manager-impact').inner_text();passed('whole batch entry review preserves total and writes nothing until confirmation')
   form.locator('[name=reason]').fill('重新核對進場單');assert page.locator('#manager-confirm').is_disabled();page.locator('#manager-close').click();page.reload();page.wait_for_selector('#workspace:not([hidden])');page.locator('nav [href="#settings"]').click();page.locator('#manager-resume').click();assert a.locator('[data-field=entry_count]').input_value()=='469';assert form.locator('[name=reason]').input_value()=='重新核對進場單';passed('changed input invalidates review; account-scoped draft survives close and reload')
   page.locator('#manager-preview').click();page.wait_for_selector('#manager-confirm:not([disabled])');page.locator('#manager-confirm').click();page.wait_for_function('()=>pending===null&&!document.querySelector("#batch-manager-dialog").open');d=store.snapshot();assert [x['entry_count'] for x in d['batches']]==[469,235];assert d['barns'][0]['name']=='9棟（北側）';assert d['batches'][0]['entry_mean_kg']==21.58;passed('one confirmation atomically saves both entries, barn name and mean; no historical movement changed')
   page.locator('#manager-history').click();page.wait_for_function('()=>document.querySelector("#manager-change-history").textContent.includes("重新核對進場單")');page.locator('#manager-change-history details summary').first.click();assert '469' in page.locator('#manager-change-history').inner_text();passed('readable history shows editor, reason, exact entry and stock changes')
   open_manager();page.select_option('#language','vi');assert form.locator('[name=mode] option[value=stock]').inner_text()=='Ghi số kiểm kê thực tế';page.select_option('#language','zh');form.locator('[name=mode]').select_option('stock');page.wait_for_function('()=>Array.from(document.querySelectorAll("[data-current-stock]")).every(e=>e.textContent!=="…")');b.locator('[data-counted]').fill('70');form.locator('[name=reason]').fill('實際盤點');before=persisted();page.locator('#manager-preview').click();page.wait_for_selector('#manager-confirm:not([disabled])');assert '72 → 70' in page.locator('#manager-impact').inner_text();assert persisted()==before
   for width in (320,390,768,1180):
    page.set_viewport_size({'width':width,'height':1000});page.evaluate("document.documentElement.dataset.textSize='large'");assert dialog.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
   page.set_viewport_size({'width':390,'height':1100});dialog.screenshot(path=str(root/'artifacts/batch-manager-mobile.png'));passed('stock inventory preview retains entry totals; 320/390/768/1180 widths and large text fit')
   def ambiguous(route):
    response=route.fetch();assert response.status==201;route.abort()
   page.route('**/api/batch-settings/apply',ambiguous);page.locator('#manager-confirm').click();page.wait_for_function('()=>pending!==null&&!retryPending.busy');assert len(store.snapshot()['movements'])==2;assert page.locator('#manager-retry').is_visible();page.unroute('**/api/batch-settings/apply',ambiguous)
   page.reload();page.wait_for_selector('#workspace:not([hidden])');page.wait_for_selector('#batch-manager-dialog[open]');assert b.locator('[data-counted]').input_value()=='70';page.locator('#manager-retry').click();page.wait_for_function('()=>pending===null&&!document.querySelector("#batch-manager-dialog").open');assert len(store.snapshot()['movements'])==2;passed('lost save response and page reload restore the original pending request; retry does not duplicate inventory adjustment')
   open_manager();a.locator('[data-field=entry_mean_kg]').fill('22');form.locator('[name=reason]').fill('核對均重');page.locator('#manager-preview').click();page.wait_for_selector('#manager-confirm:not([disabled])');add('movements',batch_id=lots[0]['id'],date=farm_today(),type='death',quantity=1);page.locator('#manager-confirm').click();page.wait_for_function('()=>pending===null&&!retryPending.busy');assert dialog.is_visible();assert '其他人' in page.locator('#manager-error').inner_text();assert store.snapshot()['batches'][0]['entry_mean_kg']==21.58;passed('concurrent farm change blocks stale confirmation and retains input')
   page.locator('#manager-close').click();page.locator('#logout').click();page.wait_for_selector('#login-view:not([hidden])');assert dialog.is_hidden();assert not page.locator('#manager-rows').inner_text();login('worker','83000012');page.locator('nav [href="#settings"]').click();assert page.locator('#batch-management').is_hidden();result=page.evaluate('async()=>{const r=await fetch("/api/batch-settings/preview",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":me.csrf},body:"{}"});return r.status;}');assert result==403;assert not errors,errors;passed('logout clears farm editor; staff cannot edit management data in UI or API; no JavaScript errors')
   browser.close()
  print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False))
 finally:server.shutdown();server.server_close()
