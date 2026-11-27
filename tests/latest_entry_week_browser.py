"""The displayed A4 grid uses the final arrival's date and weight."""
import sys,tempfile,threading,uuid
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store
from app.server import Server
with tempfile.TemporaryDirectory() as folder:
 store=Store(Path(folder)/'farm.db');admin=store.create_user('owner','83000011')
 def add(kind,**data):return store.mutate(admin,kind,data,str(uuid.uuid4()))
 barn=add('barns',name='15棟')
 lots=[{'date':'2026-10-09','count':70,'mean_kg':19},{'date':'2026-10-16','count':30,'mean_kg':22}]
 batch=add('batches',barn_id=barn['id'],name='TWO-ARRIVALS',entry_date='2026-10-09',entry_count=100,entry_age_days=64,entry_mean_kg=19,status='active',report_entry_lots=lots)
 for day,kg in [('2026-10-07',1000),('2026-10-12',2000),('2026-10-16',3000)]:
  add('feed_orders',date=day,kg=kg,display_unit='ton',vendor='',allocations=[{'batch_id':batch['id'],'kg':kg}])
 before=store.snapshot()
 server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
   page.goto('http://127.0.0.1:'+str(server.server_port));page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   page.evaluate('''()=>{window.models=[];const pdf=weeklyPdf;window.weeklyPdf=async model=>{models.push(model);return pdf(model)}}''')
   page.evaluate("id=>document.dispatchEvent(new CustomEvent('pigledger:weekly-open',{detail:{batch_id:id}}))",batch['id']);page.wait_for_selector('#weekly-a4-preview img')
   model=page.evaluate('models.at(-1)');band=next(b for b in model['pages'][0] if b.get('firstWeek')==4);column=band['headers'].index('11週');previous=band['headers'].index('10週')
   assert band['rows'][0]['cells'][column]=='10/16' and band['rows'][0]['cells'][previous]=='',band
   assert band['rows'][3]['cells'][previous]=='',band
   assert band['rows'][3]['cells'][column].split('\n')==['10/7+1(15)','10/12+2(15)','10/16+3(15)'],band['rows'][3]['cells'][column]
   assert [entry['date'] for entry in model['headerEntries']]==['2026-10-09','2026-10-16']
   assert [entry['mean'] for entry in model['headerEntries']]==[19,22]
   assert any(pair[1]=='71 天' for pair in model['basics'])
   assert store.snapshot()['batches']==before['batches'] and store.snapshot()['feed_orders']==before['feed_orders'] and not errors,errors
   browser.close()
 finally:server.shutdown();server.server_close()
print('PASS final arrival weight determines A4 start week and date; both arrival records remain intact')
