"""Real Chromium/HTTP: visible FCR uses unchanged server results and honest gaps."""
import json,sys,tempfile,threading,uuid
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
 def batch(name,first='2026-01-02',last='2026-01-12',feed=2500,representative=True,weighted=True):
  barn=add('barns',name=name+'棟');b=add('batches',barn_id=barn['id'],name=name,entry_date='2026-01-01',entry_count=100,entry_age_days=70,status='active')
  if weighted:
   for on,mean in ((first,50),(last,60)):add('weights',batch_id=b['id'],date=on,count=10,total_kg=mean*10,representative=representative)
   add('usages',batch_id=b['id'],start=first,end=last,method='direct',kg=feed,active=True)
  return b
 a=batch('A');b=batch('B',first='2026-01-03',last='2026-01-13',feed=3000);c=batch('C',weighted=False);d=batch('D');z=batch('ZERO',feed=0)
 add('feed_orders',date='2026-01-05',kg=10000,display_unit='kg',vendor='',item='',allocations=[{'batch_id':c['id'],'kg':10000}]);add('movements',batch_id=d['id'],date='2026-01-05',type='sale',quantity=5);add('movements',batch_id=d['id'],date='2026-01-06',type='death',quantity=1)
 before=store.export_backup();server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True);errors=[];page.on('pageerror',lambda e:errors.append(str(e)));requests=[];page.on('request',lambda r:requests.append((r.method,r.url)))
   def login(name,pw):page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(pw);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])');page.locator('nav [href="#stats"]').click();page.wait_for_selector('.fcr-overview')
   page.goto(url);login('owner','83000011');f=page.locator('#stats-filter');f.locator('[name=from]').fill('2026-01-01');f.locator('[name=to]').fill('2026-01-31')
   def query(target=None):
    if target:
     f.locator('[name=scope_type]').select_option('barn');f.locator('[name=barn_id]').select_option(target['barn_id']);f.locator('[name=batch_id]').select_option(target['id'])
    else:f.locator('[name=scope_type]').select_option('all')
    with page.expect_response(lambda r:'/api/statistics?' in r.url and r.request.method=='GET') as response:f.locator('button').first.click()
    s=response.value.json();page.wait_for_function('(name)=>document.querySelector(".fcr-scope")?.textContent.includes(name)',arg=target['name'] if target else '全場');return s
   s=query(a);page.wait_for_function('()=>document.querySelector(".fcr-value strong").textContent==="2.50"');card=page.locator('.fcr-overview');assert card.is_visible();assert card.locator('xpath=ancestor::details').count()==0;assert s['aggregate_fcr']==2.5;assert '2026-01-02 → 2026-01-12' in card.inner_text();assert not card.locator('.fcr-missing').count();assert card.bounding_box()['y']>=page.locator('.period-total').bounding_box()['y']+page.locator('.period-total').bounding_box()['height'];assert card.bounding_box()['y']<page.locator('.period-list').bounding_box()['y'];passed('valid FCR 2.50 is an independent visible card directly below death total, with actual weighing dates')
   s=query(c);page.wait_for_selector('.fcr-missing');assert s['aggregate_fcr'] is None;assert card.locator('.fcr-value strong').inner_text()=='—';assert '兩個不同日期' in card.inner_text() and '完整實際耗料' in card.inner_text();assert '10000' not in card.inner_text();passed('10,000 kg ordered feed produces no fabricated FCR; missing weights and actual consumption are stated')
   s=query(d);assert s['aggregate_fcr'] is None;assert '異動缺少活體總重量' in card.inner_text();assert page.locator('.period-total > strong').inner_text().startswith('1');page.locator('.period-count').first.click();page.wait_for_function('()=>current==="history"');page.wait_for_selector('#history-results tbody tr');assert '1' in page.locator('#history-results').inner_text();page.locator('nav [href="#stats"]').click();page.wait_for_selector('.fcr-overview');passed('missing sale/death weights are shown clearly and death drill-down still works')
   s=query();page.wait_for_function('()=>document.querySelector(".fcr-scope").textContent==="全場"');assert s['aggregate_fcr'] is None and s['fcr_period_mismatch'];assert '比較日期不同' in card.inner_text();passed('all-farm query does not merge incompatible periods or omit incomplete batches')
   s=query(z);page.wait_for_function('()=>document.querySelector(".fcr-value strong").textContent==="0.00"');assert s['aggregate_fcr']==0;assert not card.locator('.fcr-missing').count();passed('confirmed zero actual consumption remains valid 0.00 rather than being treated as missing')
   query(c);page.wait_for_selector('.fcr-missing');cases=0
   for width in (320,390,768,1366):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.select_option('#language',language);page.wait_for_selector('.fcr-missing')
     for size in ('small','medium','large'):
      page.locator('#font-control').evaluate('(e)=>e.open=true');page.locator(f'#font-control [data-text-size={size}]').click();page.locator('#font-control').evaluate('(e)=>e.open=false');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'),(width,language,size);assert card.is_visible();assert card.locator('.fcr-missing li').count()>=2;cases+=1
   page.set_viewport_size({'width':390,'height':844});page.select_option('#language','zh');page.locator('#font-control').evaluate('(e)=>e.open=true');page.locator('[data-text-size=medium]').click();page.locator('#font-control').evaluate('(e)=>e.open=false');card.scroll_into_view_if_needed();page.screenshot(path=str(root/'artifacts/fcr-overview-mobile.png'));passed(f'{cases} viewport/language/font combinations fit; FCR and missing-data text remain readable')
   query(a);page.wait_for_function('()=>document.querySelector(".fcr-value strong").textContent==="2.50"');n=len(requests);page.evaluate('async()=>await refresh()');assert not any('/api/statistics?' in u for m,u in requests[n:]);page.locator('[data-key=other-statistics]').evaluate('(e)=>e.open=true');assert '估計FCR' not in page.locator('[data-key=feed-performance] > summary').inner_text();page.locator('#logout').click();login('reader','83000012');query(a);page.wait_for_function('()=>document.querySelector(".fcr-value strong").textContent==="2.50"');assert store.export_backup()['records']==before['records'];assert store.export_backup()['users']==before['users'];assert not errors,errors;passed('viewer sees the same result; no extra calculation requests, duplicate aggregate summary, farm writes or browser errors');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/fcr-overview-browser.json').write_text(json.dumps({'version':VERSION,'mode':'real Chromium/local HTTP, synthetic farm, viewport simulation; not physical phone/Safari','checks':checks},ensure_ascii=False,indent=2));print('PASS',len(checks),'FCR overview browser scenarios')
