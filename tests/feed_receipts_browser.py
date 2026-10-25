"""Browser acceptance for the farm's single order/receipt entry policy."""
import json,os,sys,tempfile,threading,uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from app.review import farm_today
from app.domain import day
from app.bin_stock import stock
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(text):checks.append(text);print('PASS '+text,flush=True)
with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':'1'}):
 s=Store(Path(tmp)/'db');owner=s.create_user('owner','83000011');s.create_user('reader','83000012','viewer')
 def add(kind,**d):return s.mutate(owner,kind,d,str(uuid.uuid4()))
 barn=add('barns',name='13棟');batch=add('batches',name='TEST',barn_id=barn['id'],entry_date='2026-01-01',entry_count=100,status='active');bin=add('feed_bins',name='13',barn_ids=[barn['id']],vendor='新農科',active=True,capacity_kg=10000,safe_fill_percent=85,inventory_enabled=True,inventory_date='2026-10-01',inventory_opening_kg=0)
 today=farm_today();tomorrow=(day(today)+timedelta(days=1)).isoformat();yesterday=(day(today)-timedelta(days=1)).isoformat()
 original=add('feed_orders',date=today,kg=2000,display_unit='ton',vendor='新農科',item='仔豬料',note='',feed_bin_id=bin['id'],target_batch_ids=[batch['id']])
 server=Server(('127.0.0.1',0),s);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 def inventory(on=today):return stock(s.snapshot(),bin,on)['kg']
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(pg,name,password):
    pg.goto(url);pg.fill('#login-form [name=username]',name);pg.fill('#login-form [name=password]',password);pg.click('#login-form button');pg.wait_for_selector('#workspace:not([hidden])');pg.wait_for_function('()=>data?.feed_orders_are_arrivals===true')
   def recognize(text):
    page.fill('#quick-input',text);page.press('#quick-input','Enter');page.wait_for_selector('#quick-preview:not([hidden])');page.wait_for_function('()=>!document.querySelector("#quick-recognize").disabled')
   def confirm():
    page.click('#quick-confirm');page.wait_for_function('()=>pending===null&&document.querySelector("#quick-success").textContent!==""')
   login(page,'owner','83000011');assert inventory()==2000;page.click('nav [href="#feed"]');page.wait_for_selector('.feed-order-record');assert '飼料到料紀錄' in page.locator('#page-feed').inner_text();assert page.locator('#delivery-results').locator('..').is_hidden();assert len(s.snapshot()['feed_orders'])==1 and not s.snapshot()['deliveries'];passed('existing order appears as received feed, stock reads original row, and duplicate arrival card is hidden')
   page.click('nav [href="#daily"]');recognize('13棟到料1.5噸');assert '只登記一次' in page.locator('#quick-result-body').inner_text();confirm();assert inventory()==3500;assert len(s.snapshot()['feed_orders'])==2 and not s.snapshot()['deliveries'];passed('arrival phrase saves one canonical order/receipt and immediately adds exactly 1.5 tons')
   recent=next(r for r in s.snapshot()['feed_orders'] if r.get('quick_source'));page.locator('#quick-history>summary').click();page.wait_for_selector(f'[data-quick-edit="{recent["id"]}"]');page.click(f'[data-quick-edit="{recent["id"]}"]');page.wait_for_selector('#quick-preview:not([hidden])');page.click('#quick-modify');page.fill('#quick-corrections [name=amount]','1');page.click('#quick-corrections button[type=submit]');page.wait_for_selector('#quick-preview:not([hidden])');confirm();assert inventory()==3000;page.wait_for_selector(f'[data-quick-delete="{recent["id"]}"]');page.click(f'[data-quick-delete="{recent["id"]}"]');page.wait_for_selector('#quick-preview:not([hidden])');confirm();assert inventory()==2000;passed('editing 1.5 to 1 ton and deleting change stock by the net original quantity')
   recognize(f'{tomorrow} 13棟叫料2噸');confirm();assert inventory()==2000 and inventory(tomorrow)==4000;page.click('nav [href="#feed"]');page.wait_for_selector('.feed-order-record .feed-preentry-tag');assert '預定到料' in page.locator('#feed-order-results').inner_text();passed('future dated receipt stays out of current stock and enters on its recorded date')
   page.click('nav [href="#feed"]');f=page.locator('#feed-order-form');f.locator('[name=date]').fill(yesterday);f.locator('[name=barn_id]').select_option(barn['id']);f.locator('[name=feed_bin_id]').select_option(bin['id']);f.locator('[name=amount]').fill('0.5');f.locator('button.primary').click();page.wait_for_selector('#feed-review-dialog[open]');page.click('#feed-review-confirm');page.wait_for_function('()=>pending===null&&!document.querySelector("#feed-review-dialog").open');assert inventory()==2500 and not s.snapshot()['deliveries'];passed('original feed form still reviews and saves one received quantity without another arrival entry')
   result=page.evaluate('''async()=>{const r=await fetch('/api/deliveries',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':me.csrf,'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({})});return {status:r.status,body:await r.json()}}''');assert result['status']==409 and result['body']['error']=='feed_receipt_use_order';passed('old direct arrival create is rejected with the one-entry instruction')
   page.click('nav [href="#daily"]');recognize('13棟叫料9噸');assert page.locator('[data-quick-warning=quick_capacity_exceeded]').is_visible();assert page.locator('#quick-confirm').is_disabled();page.fill('#quick-input','');passed('capacity warning still gates unified receipt confirmation')
   second=browser.new_page(timezone_id='Asia/Taipei');login(second,'reader','83000012');page.click('nav [href="#daily"]');recognize('13棟叫料0.25噸');confirm();second.wait_for_function('()=>data.feed_receipts.some(r=>r.kg===250)',timeout=22000);assert second.locator('#quick-input').is_disabled();passed('second device receives the canonical receipt and read-only controls remain locked')
   page.select_option('#language','vi');page.click('nav [href="#feed"]');page.wait_for_function('()=>document.querySelector("#page-feed").textContent.includes("Lịch sử nhận cám")');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');assert not errors,errors;passed('Vietnamese mobile labels describe the same single received-feed workflow without browser errors')
   browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/feed-receipts-browser-results.json').write_text(json.dumps({'version':VERSION,'checks':checks},ensure_ascii=False,indent=2));print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False))
