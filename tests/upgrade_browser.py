"""Real Chromium, synthetic users and Excel; never changes production credentials."""
import base64,json,sys,tempfile,threading,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from app.accounts import ensure_role_accounts
from legacy_fixture import workbook_fixture
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];results=[]
def passed(name):results.append(name);print('PASS',name,flush=True)
with tempfile.TemporaryDirectory() as folder:
 store=Store(Path(folder)/'test.db');admin=store.create_user('owner','83000011');ensure_role_accounts(store,admin)
 store.create_user('temporary','83000015','viewer',must_change=True)
 store.import_workbook(admin,{'filename':'synthetic.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'},str(uuid.uuid4()))
 server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context(viewport={'width':390,'height':844});page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(name,password):
    page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(password);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   page.goto(base);login('owner','83000011');page.wait_for_selector('#barns .barn-card')
   assert page.evaluate('current')=='daily';assert page.locator('#movement-form').bounding_box()['y']<page.locator('#home-metrics').bounding_box()['y'];passed('daily form appears before metrics after login')
   page.locator('nav [href="#history"]').click();f=page.locator('#history-filter');f.locator('[name=scope_type]').select_option('cohort');key=page.evaluate('data.cohorts.find(c=>!c.archive).key');f.locator('[name=cohort]').select_option(key);barn=store.snapshot()['barns'][1];f.locator('[name=barn_id]').select_option(barn['id']);f.locator('[name=from]').fill('2026-10-14');f.locator('[name=to]').fill('2026-10-14');f.locator('[name=type]').select_option('death');f.locator('button').first.click();page.wait_for_function('()=>document.querySelectorAll("#history-results tbody tr").length===1');assert '2' in page.locator('#history-results tbody').inner_text()
   with page.expect_download() as downloaded:page.locator('[data-export=movements]').click()
   assert downloaded.value.path().read_text(encoding='utf-8-sig').count('\n')==2;passed('cohort + single barn + date + death filter matches CSV')
   f.locator('[name=scope_type]').select_option('all');f.locator('[name=from]').fill('');f.locator('[name=to]').fill('');f.locator('[name=record_kind]').select_option('weights');f.locator('button').first.click();page.wait_for_function('()=>document.querySelector("#history-results").textContent.includes("樣本頭數未知")');assert not page.locator('#history-results [data-edit]').count();passed('source means appear in history without invented counts or edit buttons')
   page.locator('nav [href="#settings"]').click();page.wait_for_selector('.user-row');row=page.locator('.user-row').filter(has=page.locator('input.account-name[value=farmviewer]'));row.locator('[data-setup-user]').click();page.wait_for_selector('.setup-link');link=row.locator('.setup-link').input_value();assert '#activate=' in link
   guest=browser.new_context();recipient=guest.new_page();recipient.goto(link);recipient.wait_for_selector('#activation-form:not([hidden])');assert 'activate' not in recipient.url;assert recipient.locator('#activation-form [name=username]').input_value()=='farmviewer'
   recipient.locator('#activation-form [name=password]').fill('83000018');recipient.locator('#activation-form [name=confirm]').fill('83000018');recipient.locator('#activation-form button').click();recipient.wait_for_selector('#login-form:not([hidden])')
   recipient.locator('#login-form [name=password]').fill('83000018');recipient.locator('#login-form button').click();recipient.wait_for_selector('#barns .barn-card');assert recipient.locator('#movement-form .primary').is_disabled();passed('admin issues private link; recipient sets password and receives viewer access')
   recipient.locator('nav [href="#settings"]').click();own=recipient.locator('#password-form');own.locator('[name=current_password]').fill('83000018');own.locator('[name=new_password]').fill('83000017');own.locator('[name=confirm_password]').fill('83000017');recipient.select_option('#language','vi');assert own.locator('[name=new_password]').input_value()=='83000017';own.locator('button').click();recipient.wait_for_selector('#login-view:not([hidden])');assert recipient.evaluate('async()=>{const r=await fetch("/api/me");return r.status}')==401;passed('viewer changes own password; language retains form; old session expires')
   forced=browser.new_context();q=forced.new_page();q.goto(base);q.locator('#login-form [name=username]').fill('temporary');q.locator('#login-form [name=password]').fill('83000015');q.locator('#login-form button').click();q.wait_for_selector('#password-required:not([hidden])');assert q.locator('nav a:visible').count()==1;assert q.evaluate('async()=>{const r=await fetch("/api/snapshot");return r.status}')==403;passed('temporary password forces change and server blocks other operations')
   assert not errors;assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+2');passed('new controls fit mobile viewport with no JavaScript errors');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/upgrade-browser-results.json').write_text(json.dumps({'version':VERSION,'type':'Chromium synthetic users/workbook; no physical phone','passed':results},ensure_ascii=False,indent=2))
print('Completed',len(results),'upgrade browser scenarios')
