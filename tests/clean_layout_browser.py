"""Isolated browser verification for retired UI and original receipt corrections."""
import os,json,sys,tempfile,threading,uuid
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from app.store import Store,VERSION
from app.server import Server
from app.quick_record import preview,save
from app.review import farm_today
from app.bin_stock import stock
from playwright.sync_api import sync_playwright
checks=[]
def passed(s):checks.append(s);print('PASS '+s,flush=True)
with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':'1'}):
 store=Store(Path(tmp)/'db');u=store.create_user('owner','83000011');store.create_user('reader','83000012','viewer')
 def add(kind,**d):return store.mutate(u,kind,d,str(uuid.uuid4()))
 barn=add('barns',name='13棟');batch=add('batches',name='TEST',barn_id=barn['id'],entry_date='2026-01-01',entry_count=100,status='active');bin=add('feed_bins',name='13',barn_ids=[barn['id']],vendor='新農科',active=True,inventory_enabled=True,capacity_kg=10000,safe_fill_percent=85,inventory_date='2026-01-01',inventory_opening_kg=0);task=add('work_tasks',mode='once',date=farm_today(),title='保留的既有工作',time='',note='',active=True)
 with patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':''}):
  req={'text':'13棟到料2噸','operation_id':str(uuid.uuid4())};p=preview(store,u,req);out=save(store,u,{'request':req,'confirmed':True,'preview_token':p['preview_token'],'acknowledged':p['warnings']},str(uuid.uuid4()))
 row=out['record'];before=store.export_backup()['records'];server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)));requests=[];page.on('request',lambda r:requests.append(r.url))
   def login(name,password):
    page.goto(url);page.fill('#login-form [name=username]',name);page.fill('#login-form [name=password]',password);page.click('#login-form button');page.wait_for_selector('#workspace:not([hidden])');page.wait_for_selector('#review-body .review-totals')
   login('owner','83000011');assert page.locator('#quick-entry,#quick-form,#page-calendar').count()==0;assert page.locator('nav a').count()==6;assert page.locator('nav [href="#calendar"]').count()==0;assert not any(any(n in x for n in ('quick-record.js','quick-record.css','work-calendar.js','work-calendar-pdf.js','calendar-presentation.js')) for x in requests);assert store.export_backup()['records']==before;passed('smart quick-entry and calendar DOM/resources removed; six navigation destinations; existing records unchanged')
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for lang in ('zh','vi'):
     page.select_option('#language',lang)
     for tab in ('daily','feed','history','weights','settings'):
      page.click(f'nav [href="#{tab}"]');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'),(width,lang,tab)
     if width<=390:assert page.locator('nav').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
   page.select_option('#language','zh');page.set_viewport_size({'width':390,'height':844});page.click('nav [href="#daily"]');page.evaluate('scrollTo(0,0)');page.screenshot(path=str(root/'artifacts/clean-home-mobile.png'),full_page=True);passed('mobile/tablet/desktop and Chinese/Vietnamese layouts fit, all six mobile tabs visible without horizontal scroll')
   page.click('nav [href="#history"]');page.select_option('#history-filter [name=record_kind]','deliveries');page.locator('#history-filter button[type=submit],#history-filter button:not([type])').first.click();page.wait_for_selector(f'[data-edit="deliveries"][data-id="{row["id"]}"]');page.click(f'[data-edit="deliveries"][data-id="{row["id"]}"]');f=page.locator('#delivery-form');page.wait_for_selector('#delivery-form:visible');f.locator('[name=amount]').fill('1.5');f.locator('button.primary').click();page.wait_for_selector('#receipt-edit-dialog[open]');assert '1.5' in page.locator('#receipt-edit-body').inner_text();assert not page.locator('#quick-entry').count();page.click('#receipt-edit-confirm');page.wait_for_function('()=>pending===null&&!document.querySelector("#receipt-edit-dialog").open');assert store.snapshot()['deliveries'][0]['kg']==1500 and store.snapshot()['deliveries'][0]['display_unit']=='ton';assert stock(store.snapshot(),bin,farm_today())['kg']==1500;passed('existing shortcut-created delivery remains editable through original history/form with stock preview, no retired quick-entry screen')
   page.click('nav [href="#history"]');page.wait_for_selector(f'[data-edit="deliveries"][data-id="{row["id"]}"]');page.click(f'[data-edit="deliveries"][data-id="{row["id"]}"]');f.locator('[name=amount]').fill('1.25');f.locator('button.primary').click();page.wait_for_selector('#receipt-edit-dialog[open]')
   def lost(route):route.fetch();route.abort('failed')
   page.route('**/api/quick-records/save',lost);page.click('#receipt-edit-confirm');page.wait_for_function('()=>pending!==null&&!retryPending.busy');assert page.locator('#receipt-edit-retry').is_visible();page.unroute('**/api/quick-records/save');page.click('#receipt-edit-retry');page.wait_for_function('()=>pending===null&&!document.querySelector("#receipt-edit-dialog").open');assert len(store.snapshot()['deliveries'])==1 and store.snapshot()['deliveries'][0]['kg']==1250;passed('lost correction response has an accessible in-dialog same-key retry, updates once and preserves original row ID')
   page.click('nav [href="#history"]');page.wait_for_selector(f'[data-edit="deliveries"][data-id="{row["id"]}"]');page.click(f'[data-edit="deliveries"][data-id="{row["id"]}"]');f.locator('[name=amount]').fill('9');f.locator('button.primary').click();page.wait_for_selector('#receipt-edit-dialog[open]');assert page.locator('#receipt-edit-confirm').is_disabled();page.locator('[data-receipt-warning=quick_capacity_exceeded]').check();assert page.locator('#receipt-edit-confirm').is_enabled();page.click('#receipt-edit-close');assert store.snapshot()['deliveries'][0]['kg']==1250;passed('manual correction retains capacity acknowledgement and cancellation does not change quantity')
   page.evaluate('()=>{location.hash="calendar";setPage("calendar")}');assert page.evaluate('current')=='daily';assert page.locator('#daily-entry').is_visible();assert store.snapshot()['work_tasks'][0]['id']==task['id']
   page.evaluate('''(on)=>{window.oldCalendarRequest={path:'/api/work_tasks',method:'POST',body:{mode:'once',date:on,title:'舊待重試工作',time:'',note:'',active:true},key:crypto.randomUUID(),user:me.id,formId:'calendar-form'};pending=structuredClone(oldCalendarRequest);persistPending();}''',farm_today());page.click('#retry');page.wait_for_function('()=>pending===null');assert len(store.snapshot()['work_tasks'])==2;page.evaluate('()=>{pending=structuredClone(oldCalendarRequest);persistPending();}');page.click('#retry');page.wait_for_function('()=>pending===null');assert len(store.snapshot()['work_tasks'])==2;passed('old calendar link falls back to daily; stored tasks and old missing-form pending retries remain safe and idempotent')
   page.click('#logout');page.wait_for_selector('#login-view:not([hidden])');login('reader','83000012');assert page.locator('#movement-form button.primary').is_disabled();assert page.locator('#quick-entry,#page-calendar').count()==0;assert not errors,errors;passed('read-only access and logout remain usable with no browser errors')
   browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/clean-layout-browser-results.json').write_text(json.dumps({'version':VERSION,'checks':checks},ensure_ascii=False,indent=2));print('Completed',len(checks),'clean layout scenarios')
