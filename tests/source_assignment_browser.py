"""Real Chromium + local HTTP, synthetic source assignment and CSV."""
import sys,json,threading,csv,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.server import Server
from app.store import VERSION
from playwright.sync_api import sync_playwright
from test_source_assignment import SourceAssignmentTests
case=SourceAssignmentTests('test_assignment_preserves_source_id_and_farm_totals');case.setUp();server=Server(('127.0.0.1',0),case.store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}';checks=[]
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url);page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
  body=case.target|{'source_assignments':[case.review]};response=page.evaluate('async ({id,body})=>{let r=await fetch("/api/batches/"+id,{method:"PUT",headers:{"Content-Type":"application/json","X-CSRF-Token":me.csrf,"Idempotency-Key":crypto.randomUUID()},body:JSON.stringify(body)});return {status:r.status,body:await r.json()}}',{'id':case.target['id'],'body':body});assert response['status']==200,response;page.evaluate('async()=>await refresh()');checks.append('admin HTTP assignment is saved and refreshed')
  query='batch_id='+case.target['id']+'&from=2026-10-11&to=2026-10-11&type=death';rows=page.request.get(url+'/api/movements?'+query).json();assert len(rows)==1 and rows[0]['id']==case.record['id'] and rows[0]['quantity']==1;exported=list(csv.DictReader(io.StringIO(page.request.get(url+'/api/export?kind=movements&'+query).text().lstrip('\ufeff'))));assert len(exported)==1 and exported[0]['barn']=='1棟' and exported[0]['quantity']=='1';checks.append('real history query and CSV have one original event assigned to barn 1')
  page.locator('nav [href="#history"]').click();hf=page.locator('#history-filter');hf.locator('[name=from]').fill('2026-10-11');hf.locator('[name=to]').fill('2026-10-11');hf.locator('button').first.click();page.wait_for_selector('#history-results tbody tr');assert page.locator('#history-results tbody tr').count()==1;assert '1棟' in page.locator('#history-results').inner_text();page.reload();page.wait_for_selector('#workspace:not([hidden])');stored=page.request.get(url+'/api/movements?'+query).json();assert len(stored)==1 and stored[0]['id']==case.record['id'];assert not errors,errors;checks.append('mobile history displays barn and reload does not duplicate the event');browser.close()
finally:server.shutdown();server.server_close();case.tearDown()
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);(root/'artifacts/source-assignment-browser.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'real Chromium/local HTTP/synthetic farm; not physical phone'},ensure_ascii=False,indent=2));print('PASS',len(checks),'source assignment browser checks')
