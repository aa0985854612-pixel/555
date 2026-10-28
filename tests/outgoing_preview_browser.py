"""Shipment preview reads real dated stock without writing farm data until Save."""
import sys,tempfile,threading,uuid,json,time
from datetime import timedelta,date
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store
from app.server import Server
from app.review import farm_today
from app.cloud_store import read_document
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);passed=[]
def check(name):passed.append(name);print('PASS '+name,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'preview.db');owner=store.create_user('owner','83000011');today=farm_today();entry=(date.fromisoformat(today)-timedelta(days=40)).isoformat();yesterday=(date.fromisoformat(today)-timedelta(days=1)).isoformat()
 def add(kind,**values):return store.mutate(owner,kind,values,str(uuid.uuid4()))
 def farm_state():
  db=store.connect()
  try:return read_document(db)
  finally:db.close()
 b23=add('barns',name='23棟');b24=add('barns',name='24棟')
 lot23=add('batches',name='JD-115-23',barn_id=b23['id'],entry_date=entry,entry_count=100,status='active')
 lot24=add('batches',name='JD-115-24',barn_id=b24['id'],entry_date=entry,entry_count=200,status='active')
 add('movements',date=today,batch_id=lot23['id'],type='sale',quantity=18)
 first=add('movements',date=today,batch_id=lot24['id'],type='sale',quantity=20,outgoing_destination='南投')
 add('movements',date=today,batch_id=lot24['id'],type='sale',quantity=19)
 add('movements',date=today,batch_id=lot24['id'],type='death',quantity=2)
 server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx=browser.new_context(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(url);page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])');f=page.locator('#movement-form');box=page.locator('#outgoing-preview');destination=f.locator('[name=outgoing_destination]');assert not f.locator('details').evaluate('(e)=>e.open');assert destination.is_visible();assert destination.locator('..').inner_text().startswith('出豬地點');assert destination.evaluate('(e)=>e.closest("label").parentElement===e.form.querySelector(":scope > .grid")');assert destination.evaluate('(e)=>!!(e.closest("label").compareDocumentPosition(e.form.querySelector(".scope"))&Node.DOCUMENT_POSITION_FOLLOWING)');f.screenshot(path=str(root/'artifacts/outgoing-destination-main-mobile.png'));check('destination is visible above barn/batch in the main form while optional details stay closed')
   def choose(lot,barn,when=today):
    f.locator('[name=date]').fill(when);f.locator('[name=type]').select_option('sale');f.locator('[name=barn_id]').select_option(barn['id']);f.locator('[name=batch_id]').select_option(lot['id'])
   def value(key,number):page.wait_for_function('([k,n])=>document.querySelector(`[data-shipment="${k}"]`)?.textContent.trim().startsWith(n)',arg=[key,str(number)])
   before=farm_state();choose(lot24,b24);f.locator('[name=outgoing_destination]').select_option('新北');f.locator('[name=quantity]').fill('80');value('shipmentBefore',159);value('shipmentQuantity',80);value('shipmentAfter',79);assert '24棟' in box.inner_text() and 'JD-115-24' in box.inner_text() and '新北' in box.inner_text();assert farm_state()==before;check('24 barn: 159 → 80 → 79; batch and destination shown; preview writes no records, audit or requests')
   for width in (320,390,768,1180):
    page.set_viewport_size({'width':width,'height':1000});page.evaluate("document.documentElement.dataset.textSize='large'");assert box.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1');assert box.locator('[data-shipment=shipmentAfter]').is_visible()
   page.set_viewport_size({'width':390,'height':1000});box.screenshot(path=str(root/'artifacts/outgoing-preview-mobile.png'));check('large numbers fit 320/390/768/1180 widths and large text; mobile screenshot saved')
   f.locator('[name=quantity]').fill('160');value('shipmentAfter',-1);assert not f.locator('[name=quantity]').evaluate('(e)=>e.checkValidity()');assert '超過存欄' in box.inner_text();assert farm_state()==before
   f.locator('[name=type]').select_option('death');assert box.is_hidden() and destination.is_hidden();assert f.locator('[name=quantity]').evaluate('(e)=>e.validity.customError===false');f.locator('[name=type]').select_option('cull');assert destination.is_visible() and destination.input_value()=='新北';value('shipmentAfter',-1)
   for quantity in ('','0','1.5','-1'):
    f.locator('[name=quantity]').fill(quantity);assert box.is_hidden();assert not f.locator('[name=quantity]').evaluate('(e)=>e.validity.customError')
   f.locator('[name=quantity]').fill('80');choose(lot23,b23);value('shipmentBefore',82);value('shipmentAfter',2);check('over-stock preview flags invalid quantity; death hides it; culls preview too; invalid or blank quantities hide the empty preview; switching barns recalculates')
   page.evaluate('(id)=>edit("movements",id)',first['id']);assert destination.is_visible() and destination.input_value()=='南投';f.locator('[name=quantity]').fill('30');value('shipmentBefore',179);value('shipmentAfter',149);assert '先還原' in box.inner_text()
   f.locator('[name=date]').fill(yesterday);value('shipmentBefore',200);value('shipmentAfter',170);f.locator('[name=date]').fill((date.fromisoformat(entry)-timedelta(days=1)).isoformat());page.wait_for_function('()=>document.querySelector("#outgoing-preview").textContent.includes("早於進場日")');value('shipmentBefore','—');value('shipmentAfter','—');f.locator('[data-action=cancelEdit]').click();check('editing adds back the old shipment once; earlier dates exclude later events; pre-entry dates do not invent stock; cancel clears edit context')
   choose(lot24,b24);f.locator('[name=quantity]').fill('80');value('shipmentAfter',79);page.select_option('#language','vi');page.wait_for_function('()=>document.querySelector("#outgoing-preview h3").textContent.includes("Tồn đàn")');value('shipmentAfter',79);page.select_option('#language','zh');check('Chinese/Vietnamese changes preserve the exact preview and unsaved input')
   held=[]
   def hold(route):
    q=parse_qs(urlsplit(route.request.url).query)
    if q.get('batch_id'):
     response=route.fetch();held.append((route,response))
    else:route.continue_()
   page.route('**/api/statistics?**',hold);choose(lot23,b23,yesterday);page.wait_for_timeout(250);assert len(held)==1;choose(lot24,b24,yesterday);page.wait_for_timeout(250);assert len(held)==2
   held[1][0].fulfill(response=held[1][1]);value('shipmentBefore',200);held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(100);value('shipmentBefore',200);assert '24棟' in box.inner_text();page.unroute('**/api/statistics?**',hold);check('out-of-order stock responses cannot replace the selected barn with the previous barn stock')
   def unknown(route):
    q=parse_qs(urlsplit(route.request.url).query)
    if q.get('batch_id'):route.fulfill(json={'as_of':q['to'][0],'ids':q['batch_id'],'cumulative':{'remaining':None}})
    else:route.continue_()
   page.route('**/api/statistics?**',unknown);choose(lot23,b23);page.wait_for_function('()=>document.querySelector("#outgoing-preview").textContent.includes("資料不足")');value('shipmentBefore','—');value('shipmentAfter','—');page.unroute('**/api/statistics?**',unknown)
   def abort(route):
    if parse_qs(urlsplit(route.request.url).query).get('batch_id'):route.abort()
    else:route.continue_()
   page.route('**/api/statistics?**',abort);choose(lot24,b24);page.wait_for_selector('[data-shipment-retry]');value('shipmentBefore','—');value('shipmentAfter','—');page.unroute('**/api/statistics?**',abort);page.locator('[data-shipment-retry]').click();value('shipmentBefore',159);value('shipmentAfter',79);check('unknown stock and network failures show no invented zeros; retry obtains live stock')
   assert farm_state()==before;destination.select_option('嘉義');f.locator('button.primary').click();page.wait_for_function('()=>pending===null&&document.querySelector("#movement-form [name=quantity]").value===""');page.wait_for_function('(id)=>data.dashboard.batches.find(b=>b.id===id).herd.remaining===79',arg=lot24['id']);assert box.is_hidden();new=store.snapshot()['movements'];assert len(new)==5 and new[-1]['quantity']==80 and new[-1]['outgoing_destination']=='嘉義';check('Save keeps the existing validated write flow and writes exactly once; stock refreshes to 79 and the cleared form hides its preview')
   page.locator('#logout').click();page.wait_for_selector('#login-view:not([hidden])');assert box.is_hidden() and not box.inner_text();assert not errors,errors;check('logout removes stock preview; no JavaScript runtime errors')
   browser.close()
  print(json.dumps({'passed':len(passed),'checks':passed},ensure_ascii=False))
 finally:server.shutdown();server.server_close()
