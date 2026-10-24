"""Quick movements must visibly update the daily report, including backdated edits."""
import json,sys,tempfile,threading,uuid
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from app.review import farm_today
from app.domain import day
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(text):checks.append(text);print('PASS '+text,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011')
 def add(kind,**body):return store.mutate(owner,kind,body,str(uuid.uuid4()))
 barn=add('barns',name='13棟');batch=add('batches',name='TEST-13',barn_id=barn['id'],entry_date='2026-01-01',entry_count=100,entry_age_days=70,status='active');bin=add('feed_bins',name='13',barn_ids=[barn['id']],vendor='新農科',active=True)
 on=farm_today();yesterday=(day(on)-timedelta(days=1)).isoformat();older=(day(on)-timedelta(days=2)).isoformat()
 server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(url);page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_selector('#review-body .review-totals')
   def recognize(text):
    page.locator('#quick-input').fill(text);page.locator('#quick-input').press('Enter');page.wait_for_selector('#quick-preview:not([hidden])');page.wait_for_function('()=>!document.querySelector("#quick-recognize").disabled')
   def confirm():
    page.locator('#quick-confirm').click();page.wait_for_function('()=>pending===null&&document.querySelector("#quick-success").textContent!==""')
   def totals(death,sale=0,cull=0):
    page.wait_for_function('(values)=>JSON.stringify(Array.from(document.querySelectorAll("#review-body .review-totals strong"),e=>Number(e.textContent.replace(/,/g,""))))===JSON.stringify(values)',arg=[death,sale,cull],timeout=5000)
   # The old implementation leaves the report on today when saving yesterday.
   f=page.locator('#movement-form');f.locator('[name=quantity]').fill('17')
   recognize(f'{yesterday} 13棟死3隻');confirm();page.wait_for_function('(d)=>document.querySelector("#review-date").value===d',arg=yesterday,timeout=5000);totals(3);assert page.locator('[data-key=daily-events]').evaluate('(e)=>e.open');assert '死亡 3' in page.locator('.review-event').inner_text();assert f.locator('[name=quantity]').input_value()=='17';assert len(store.snapshot()['movements'])==1;passed('backdated quick death switches review date, displays 3 heads and opens saved event without altering manual-form draft or duplicating data')
   # Today must also switch back after browsing the past.
   recognize('13棟出豬4隻');confirm();page.wait_for_function('(d)=>document.querySelector("#review-date").value===d',arg=on);totals(0,4);assert '4' in page.locator('.review-event').inner_text();recognize('13棟淘汰2隻');confirm();totals(0,4,2);passed('today sale/cull return report to today and update visible totals immediately')
   # Quick history edits move the event to its corrected date and refresh both days.
   page.locator('#quick-history>summary').click();death=next(r for r in store.snapshot()['movements'] if r['type']=='death');page.wait_for_selector(f'[data-quick-edit="{death["id"]}"]');page.locator(f'[data-quick-edit="{death["id"]}"]').click();page.wait_for_selector('#quick-preview:not([hidden])');page.locator('#quick-modify').click();page.locator('#quick-corrections [name=date]').fill(older);page.locator('#quick-corrections [name=amount]').fill('2');page.locator('#quick-corrections button[type=submit]').click();page.wait_for_selector('#quick-preview:not([hidden])');confirm();page.wait_for_function('(d)=>document.querySelector("#review-date").value===d',arg=older);totals(2);page.locator('#review-date').fill(yesterday);page.locator('#review-date').dispatch_event('change');totals(0);passed('history edit changes quantity/date with corrected-day display and removes count from original day')
   page.wait_for_selector(f'[data-quick-delete="{death["id"]}"]');page.locator(f'[data-quick-delete="{death["id"]}"]').click();page.wait_for_selector('#quick-preview:not([hidden])');confirm();page.wait_for_function('(d)=>document.querySelector("#review-date").value===d',arg=older);totals(0);assert page.locator('.review-event').count()==0;passed('history delete displays affected day and removes saved count from report')
   # Feed is not a head count, and must not redirect daily review to its date.
   page.locator('#review-date').fill(on);page.locator('#review-date').dispatch_event('change');totals(0,4,2);recognize(f'{older} 13棟叫料2噸');confirm();assert page.locator('#review-date').input_value()==on;totals(0,4,2);passed('feed orders remain feed records and do not change selected head-count report date')
   # Editing-preview/failed request cannot turn into a reported count.
   recognize('13棟死1隻');assert len(store.snapshot()['movements'])==2;totals(0,4,2);page.route('**/api/quick-records/save',lambda route:route.fulfill(status=409,content_type='application/json',body='{"error":"revision_conflict"}'));page.locator('#quick-confirm').click();page.wait_for_function('()=>pending===null&&document.querySelector("#quick-errors").textContent!==""');totals(0,4,2);assert len(store.snapshot()['movements'])==2;page.unroute('**/api/quick-records/save');passed('preview and failed save never change reported counts')
   recognize(f'{yesterday} 13棟出豬1隻')
   def lost(route):route.fetch();route.abort('failed')
   page.route('**/api/quick-records/save',lost);page.locator('#quick-confirm').click();page.wait_for_function('()=>pending!==null&&!retryPending.busy');assert len(store.snapshot()['movements'])==3;totals(0,4,2)
   page.unroute('**/api/quick-records/save');page.reload();page.wait_for_selector('#workspace:not([hidden])');page.locator('#retry').click();page.wait_for_function('()=>pending===null&&document.querySelector("#quick-success").textContent!==""');page.wait_for_function('(d)=>document.querySelector("#review-date").value===d',arg=yesterday);totals(0,1);assert page.locator('[data-key=daily-events]').evaluate('(e)=>e.open');assert len(store.snapshot()['movements'])==3;passed('lost response then reload and same-key retry shows backdated saved count once')
   page.locator('#quick-input').fill('');page.select_option('#language','vi');assert 'Đối chiếu' in page.locator('#daily-review').inner_text();assert not errors,errors;assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1');passed('Vietnamese mobile layout and browser error checks pass')
   browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/quick-daily-sync-results.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'isolated synthetic HTTP/Chromium'},ensure_ascii=False,indent=2))
print('Completed',len(checks),'quick daily sync scenarios')
