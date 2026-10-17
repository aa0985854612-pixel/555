"""Real Chromium/local HTTP: accepted source gaps stay out of pending UI."""
import sys,json,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from app.server import Server
from app.store import VERSION
from test_quality_completion import QualityCompletionTests
case=QualityCompletionTests('test_scope_count_and_farm_data_are_preserved');case.setUp();server=Server(('127.0.0.1',0),case.store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}';checks=[]
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  def login(name):
   page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill({'owner':'83000011','worker':'83000012','reader':'83000013'}[name]);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
  page.goto(url);login('owner');page.locator('nav [href="#settings"]').click();page.locator('#quality-panel').evaluate('(e)=>e.open=true');page.wait_for_selector('#quality-body .quality-item');before=page.request.get(url+'/api/snapshot').json();history=page.request.get(url+'/api/movements').json();old=before['data_quality']['count'];body=case.target|{'quality_review':case.review}
  result=page.evaluate('''async ({id,body})=>{let r=await fetch('/api/batches/'+id,{method:'PUT',headers:{'Content-Type':'application/json','X-CSRF-Token':me.csrf,'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify(body)});return {status:r.status,body:await r.json()}}''',{'id':case.target['id'],'body':body});assert result['status']==200,result;page.evaluate('async()=>await refresh()');page.wait_for_function('(n)=>Number(document.querySelector("#quality-count").textContent)===n',arg=old-len(case.items));assert page.locator(f'[data-quality-edit="{case.target["id"]}"]').count()==0;checks.append('admin saves completion; pending UI and count immediately exclude selected source gaps')
  for _ in range(3):
   page.select_option('#language','vi');page.select_option('#language','zh');page.evaluate('async()=>await refresh()');page.reload();page.wait_for_selector('#workspace:not([hidden])');page.locator('nav [href="#settings"]').click();page.locator('#quality-panel').evaluate('(e)=>e.open=true');page.wait_for_function('(n)=>Number(document.querySelector("#quality-count").textContent)===n',arg=old-len(case.items));assert page.locator(f'[data-quality-edit="{case.target["id"]}"]').count()==0
  assert page.request.get(url+'/api/movements').json()==history;checks.append('three reload/language/sync rounds retain completion and all historical movements')
  for user in ('reader','worker'):
   page.locator('#logout').click();login(user);r=page.evaluate('''async ({id,body})=>{let r=await fetch('/api/batches/'+id,{method:'PUT',headers:{'Content-Type':'application/json','X-CSRF-Token':me.csrf,'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify(body)});return r.status}''',{'id':case.target['id'],'body':body});assert r==403;page.locator('nav [href="#settings"]').click();page.locator('#quality-panel').evaluate('(e)=>e.open=true');page.wait_for_function('(n)=>Number(document.querySelector("#quality-count").textContent)===n',arg=old-len(case.items))
  assert not errors,errors;checks.append('viewer and editor see the same remaining count; direct batch-completion writes are forbidden');browser.close()
finally:server.shutdown();server.server_close();case.tearDown()
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);(root/'artifacts/quality-completion-browser.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'real Chromium/local HTTP; synthetic data; no physical phone'},ensure_ascii=False,indent=2));print('PASS',len(checks),'quality completion browser checks')
