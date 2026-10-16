"""Real Chromium/HTTP, synthetic data; no customer account or production writes."""
import sys,tempfile,threading,uuid,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from app.review import farm_today
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[];measurements=[]
def passed(s):checks.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011');staff=store.create_user('worker','83000012','staff');store.create_user('reader','83000013','viewer')
 def add(kind,**d):return store.mutate(owner,kind,d,str(uuid.uuid4()))
 barns=[add('barns',name=f'{n}棟') for n in (15,21)];a=add('batches',name='TEST',barn_id=barns[0]['id'],entry_date='2026-01-01',entry_count=100,entry_age_days=71,status='active');b=add('batches',name='TEST',barn_id=barns[1]['id'],entry_date='2026-01-01',entry_count=30,entry_age_days=71,status='active');on=farm_today()
 server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,timezone_id='Asia/Taipei');page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));requests=[]
   page.on('request',lambda r:requests.append((r.method,r.url)))
   def login(name,password):page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(password);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])');page.wait_for_selector('#review-body .review-totals')
   def patrol():page.locator('#review-body [data-key=patrol-list]').evaluate('(e)=>e.open=true')
   page.goto(url);login('owner','83000011');assert page.locator('#daily-entry').is_visible();assert not page.locator('#home-metrics').is_visible();assert not page.locator('#barns').is_visible();assert page.locator('#daily-review').is_visible();page.locator('[data-daily-view=overview]').click();assert page.locator('#barns').is_visible();assert page.locator('#home-metrics').is_visible();assert not page.locator('#daily-review').is_visible();assert not page.locator('#daily-entry').is_visible();page.locator('[data-daily-view=entry]').click();assert '尚未回報' in page.locator('#review-body').inner_text();passed('daily form stays first; unreported days are not described as zero-death patrols')
   f=page.locator('#movement-form');f.locator('[name=barn_id]').select_option(barns[0]['id']);f.locator('[name=type]').select_option('sale')
   for i in range(3):
    f.locator('[name=quantity]').fill(str(i+1));before=len(requests);started=time.monotonic();page.select_option('#language','vi');page.select_option('#language','zh');page.evaluate('async()=>await refresh()');assert f.locator('[name=quantity]').input_value()==str(i+1)
    with page.expect_response(lambda r:'/api/movements' in r.url and r.request.method=='POST') as response:f.locator('button.primary').click()
    assert response.value.status==201;page.wait_for_function('()=>pending===null&&document.querySelector("#movement-form [name=quantity]").value===""');page.wait_for_function('(n)=>data.daily_review.totals.sale===n',arg=sum(range(1,i+2)));measurements.append({'round':i+1,'requests':len(requests)-before,'movement_post_count':sum(m=='POST' and '/api/movements' in u for m,u in requests[before:]),'elapsed_ms':round((time.monotonic()-started)*1000),'selected_batch_preserved':f.locator('[name=batch_id]').input_value()==a['id']})
   assert len(store.snapshot()['movements'])==3;assert all(m['movement_post_count']==1 and m['selected_batch_preserved'] for m in measurements);page.locator('#review-body [data-key=daily-events]').evaluate('(e)=>e.open=true');assert page.locator('.review-event').count()==3;passed('three save/language/sync rounds preserve selected batch, clear only completed quantity, and list each saved event once')
   patrol();assert page.locator('[data-check]').count()==0;page.locator('[data-bulk-check]').click();page.wait_for_selector('#check-dialog[open]');assert '15棟' in page.locator('#check-bulk-scope').inner_text() and '21棟' in page.locator('#check-bulk-scope').inner_text();page.locator('#check-save').click();page.wait_for_function('()=>pending===null&&data.daily_checks.length===2');assert all(r['status']=='no_deaths' for r in store.snapshot()['daily_checks']);passed('one bulk button confirms both reviewed barns with separate durable acknowledgements')
   patrol();page.locator(f'[data-cancel-check="{b["id"]}"]').click();page.locator('#check-reason').fill('重新巡場');page.locator('#check-save').click();page.wait_for_function('(id)=>pending===null&&data.daily_checks.some(r=>r.batch_id===id&&r.status==="cancelled")',arg=b['id'])
   page.route('**/api/daily-checks/bulk',lambda route: (route.fetch(),route.abort('failed')) if route.request.method=='POST' else route.continue_())
   page.locator('[data-bulk-check]').click();page.wait_for_selector('#check-dialog[open]');page.locator('#check-save').click();page.wait_for_function('()=>pending!==null&&!retryPending.busy');assert page.locator('#pending').is_visible();assert len(store.snapshot()['daily_checks'])==2
   page.unroute('**/api/daily-checks/bulk');page.locator('#retry').click();page.wait_for_function('()=>pending===null');assert len(store.snapshot()['daily_checks'])==2;assert next(r for r in store.snapshot()['daily_checks'] if r['batch_id']==b['id'])['revision']==3;passed('bulk write lost response retains pending state; same-key replay creates no duplicates')
   f.locator('[name=type]').select_option('death');f.locator('[name=quantity]').fill('1');f.locator('button.primary').click();page.wait_for_function('()=>pending===null&&data.daily_review.totals.death===1');patrol();assert '已登記死亡' in page.locator('#review-body').inner_text();assert '已補登死亡' in page.locator('#review-body').inner_text();assert next(r for r in store.snapshot()['daily_checks'] if r['batch_id']==a['id'])['status']=='cancelled';passed('later death automatically revokes prior zero-death acknowledgement and updates daily review')
   page.locator('nav [href="#settings"]').click();page.locator('#quality-panel').evaluate('(e)=>e.open=true');page.wait_for_selector('#quality-body .quality-item');assert '入場均重待補' in page.locator('#quality-body').inner_text();page.locator(f'[data-quality-edit="{a["id"]}"]').click();assert page.locator('#batch-editor').is_visible();assert page.locator('#batch-form [name=entry_count]').input_value()=='100';page.locator('#batch-form [data-action=cancelEdit]').click();passed('quality checklist links directly to the existing batch editor without inventing values')
   page.locator('nav [href="#daily"]').click();patrol();
   for width,height in ((320,667),(390,844),(768,1024),(1366,900)):
    page.set_viewport_size({'width':width,'height':height});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),width
   page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(root/'artifacts/daily-review-mobile.png'),full_page=True);passed('320/390/768/1366 width layouts have no horizontal page overflow')
   page.locator('#logout').click();login('reader','83000013');patrol();assert page.locator('[data-check],[data-cancel-check],[data-bulk-check]').count()==0
   result=page.evaluate('''async (b)=>{const r=await fetch('/api/daily-checks/bulk',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':me.csrf,'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({date:'2026-01-03',batch_id:b,status:'no_deaths'})});return r.status}''',a['id']);assert result==403;passed('viewer has no confirmation controls and direct server write is rejected with 403')
   page.locator('#logout').click();login('worker','83000012');patrol();assert page.locator('[data-cancel-check]').count()==0;assert not errors,errors;passed('editor cannot revoke another user confirmation; no uncaught browser errors')
   browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/daily-review-browser-results.json').write_text(json.dumps({'version':VERSION,'mode':'Chromium real HTTP, synthetic local data, viewport simulation; no physical device','checks':checks,'three_round_measurements':measurements},ensure_ascii=False,indent=2));print('Completed',len(checks),'daily review scenarios')
