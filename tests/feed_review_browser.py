"""Real browser/HTTP review and pre-entry report, with a local reference image."""
import csv,io,json,re,subprocess,sys,tempfile,threading,uuid
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from app.domain import herd
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(msg):checks.append(msg);print('PASS',msg,flush=True)
with tempfile.TemporaryDirectory() as temp:
 store=Store(Path(temp)/'db');admin=store.create_user('owner','83000011');store.create_user('reader','83000012','viewer')
 def add(kind,**d):return store.mutate(admin,kind,d,str(uuid.uuid4()))
 barn=add('barns',name='15棟',feed_vendor='新農科');batch=add('batches',name='JD-PREENTRY',barn_id=barn['id'],entry_date='2026-10-09',entry_count=1052,status='active',entry_age_days=71)
 bin=add('feed_bins',name='15-1',barn_ids=[barn['id']],vendor='新農科',active=True);otherbin=add('feed_bins',name='15-2',barn_ids=[barn['id']],vendor='新農科',active=True)
 body=dict(date='2026-10-08',kg=4000,display_unit='ton',vendor='新農科',item='哺乳二期料',feed_bin_id=bin['id'],target_batch_ids=[batch['id']],note='original medication note');old=add('feed_orders',**body)
 original_users=store.export_backup()['users'];original_herd=herd(store.snapshot()['batches'],[], '2026-10-18');photo=Path(temp)/'source-photo.png';Image.new('RGB',(50,50),'pink').save(photo)
 server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));bodies=[];page.on('request',lambda r:bodies.append(r.post_data or '') if '/api/' in r.url else None)
   def login(name,pw):page.goto(url);page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(pw);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   login('owner','83000011');page.locator('nav [href="#feed"]').click();f=page.locator('#feed-order-form');f.locator('[name=date]').fill('2026-10-08');f.locator('[name=feed_bin_id]').select_option(bin['id']);f.locator('[name=item]').select_option('哺乳二期料');f.locator('[name=display_unit]').select_option('ton');f.locator('[name=amount]').fill('8');f.locator('details').evaluate('(e)=>e.open=true');page.locator('[data-feed-barn]').select_option(batch['id']);f.locator('[name=note]').fill('transcribed photo medicine');page.locator('#feed-source-photo').set_input_files(photo);f.locator('.primary').click();page.wait_for_selector('#feed-review-dialog[open]')
   assert '4 噸 → 8 噸' in page.locator('#feed-review-body').inner_text();assert page.locator('.feed-reference-photo').evaluate('(e)=>e.complete&&e.naturalWidth===50');page.locator('#feed-review-confirm').click();assert page.locator('#feed-review-error').inner_text();assert len(store.snapshot()['feed_orders'])==1
   page.locator(f'#feed-review-options input[value="{old["id"]}"]').check();page.select_option('#language','vi');page.select_option('#language','zh');assert page.locator('#feed-review-options input:checked').input_value()==old['id'];page.locator('#feed-review-confirm').click();page.wait_for_function('()=>pending===null&&document.querySelector("#feed-order-form [name=amount]").value===""');r=store.snapshot()['feed_orders'][0];assert r['id']==old['id'] and r['revision']==2 and r['kg']==8000;assert all(x in r['note'] for x in ('original medication note','transcribed photo medicine','source-photo.png'));assert all('data:image' not in b and len(b)<5000 for b in bodies)
   passed('local photo stays in tab; original 4 vs incoming 8 tonnes requires explicit decision, preserves choice across languages and updates one record with notes and audit')
   card=page.locator('#feed-order-results .feed-order-record');assert card.locator('.order-quantity').inner_text()=='8 噸';assert card.locator('.feed-order-main strong').inner_text()=='料桶 15-1';assert card.locator('.feed-preentry-tag').inner_text()=='進場前叫料';assert not card.locator('details').evaluate('(e)=>e.open');assert card.locator('.order-note').is_hidden();card.locator('summary').click();page.evaluate('async()=>await refresh()');assert card.locator('details').evaluate('(e)=>e.open');assert card.locator('.order-note').is_visible()
   passed('compact card shows bucket, feed type, vendor and integer amount; medication/source/batches fold and retain open state during sync')
   f.locator('[name=amount]').fill('9');f.locator('.primary').click();page.wait_for_selector('#feed-review-dialog[open]');page.locator(f'#feed-review-options input[value="{old["id"]}"]').check();current=store.snapshot()['feed_orders'][0];store.mutate(admin,'feed_orders',body|{'kg':8000,'note':'concurrent manual note','revision':current['revision']},str(uuid.uuid4()),old['id']);page.locator('#feed-review-confirm').click();page.wait_for_function('()=>pending===null&&document.querySelector("#feed-order-form .form-error").textContent!==""');assert f.locator('[name=amount]').input_value()=='9';assert store.snapshot()['feed_orders'][0]['note']=='concurrent manual note'
   f.locator('[name=amount]').fill('8');f.locator('.primary').click();page.wait_for_selector('#feed-review-dialog[open]');page.locator(f'#feed-review-options input[value="{old["id"]}"]').check();page.locator('#feed-review-confirm').click();page.wait_for_function('()=>pending===null&&document.querySelector("#feed-order-form [name=amount]").value===""');assert len(store.snapshot()['feed_orders'])==1
   passed('concurrent manual correction invalidates stale preview, retains draft and requires a fresh comparison instead of overwriting')
   add('feed_orders',**(body|{'date':'2026-10-10','kg':2000,'feed_bin_id':otherbin['id'],'note':''}));page.evaluate('async()=>await refresh()');page.locator('nav [href="#stats"]').click();page.locator('#open-weekly-report').click();page.locator('#weekly-cohort').select_option('JD-PREENTRY|2026-10-09');page.locator('#weekly-to').fill('2026-10-18');page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-export-actions:not([hidden])');page.wait_for_selector('#weekly-a4-preview img');page.locator('#weekly-sheet-body > details').evaluate('(e)=>e.open=true');sheet=page.locator('#weekly-sheet-body');assert '10/8+8（15-1）' in sheet.locator('.weekly-preentry').inner_text();assert '10/8' not in ' '.join(sheet.locator('.weekly-feed-entry').all_text_contents());assert '10/10+2（15-2）' in sheet.inner_text()
   page.evaluate('()=>{window.pdfDraws=[];const draw=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...a){pdfDraws.push(a[0]);return draw.apply(this,a)}}')
   page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-a4-preview img')
   with page.expect_download() as dl:page.locator('#weekly-print').click()
   pdf=root/'artifacts/feed-preentry-a4.pdf';dl.value.save_as(pdf);info=subprocess.check_output(['pdfinfo',str(pdf)],text=True);assert re.search(r'Pages:\s+1\b',info);assert '595.28 x 841.89' in info;assert page.evaluate('pdfDraws').count('10/8+8（15-1）')==1;assert page.evaluate('pdfDraws').count('10/10+2（15-2）')==1
   with page.expect_download() as dl:page.locator('#weekly-csv').click()
   rows=list(csv.reader(io.StringIO(Path(dl.value.path()).read_text(encoding='utf-8-sig'))));assert any(r and r[0]=='進場前叫料' and '8 噸' in r for r in rows);assert any(r[:2]==['2026-10-08','15-1'] and '8' in r for r in rows);assert ['叫料登記量（噸）','2'] in rows
   passed('pre-entry 8 tonnes keeps 10/8 in its own preview/CSV/A4 section; period feed remains 2 tonnes on 10/10, both drawn once and PDF is one portrait A4')
   page.locator('#weekly-close').click();page.locator('nav [href="#feed"]').click();f.locator('[name=amount]').fill('8');f.locator('.primary').click();page.wait_for_selector('#feed-review-dialog[open]');cases=0
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.select_option('#language',language)
     for size in ('small','medium','large'):
      page.evaluate('(s)=>document.documentElement.dataset.textSize=s',size);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');assert page.locator('#feed-review-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1');cases+=1
   page.locator('#feed-review-close').click();page.select_option('#language','zh');page.set_viewport_size({'width':390,'height':844});page.evaluate('document.documentElement.dataset.textSize="medium"');f.locator('details').evaluate('(e)=>e.open=false');page.screenshot(path=str(root/'artifacts/feed-review-mobile.png'),full_page=True)
   passed(f'{cases} language/font/phone/tablet/desktop review layouts fit; cancelling leaves the typed quantity unchanged')
   page.locator('#logout').click();login('reader','83000012');page.locator('nav [href="#feed"]').click();assert f.locator('.primary').is_disabled();assert page.evaluate('async()=>{const headers={"Content-Type":"application/json","X-CSRF-Token":me.csrf,"Idempotency-Key":crypto.randomUUID()};const a=await fetch("/api/feed-order-preview",{method:"POST",headers,body:JSON.stringify({record:{}})});const b=await fetch("/api/feed-order-apply",{method:"POST",headers,body:JSON.stringify({record:{},decision:"create"})});return [a.status,b.status]}')==[403,403];assert store.export_backup()['users']==original_users;assert herd(store.snapshot()['batches'],[], '2026-10-18')==original_herd;assert not errors,errors;assert not store.snapshot()['usages'];browser.close()
   passed('viewer remains read-only; all account hashes, stock and consumption rules unchanged; no page errors')
 finally:server.shutdown();server.server_close()
(root/'artifacts/feed-review-browser-results.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'local real Chromium/HTTP/SQLite and PDF download; synthetic records; not physical iPhone/Safari/printer'},ensure_ascii=False,indent=2));print('Completed',len(checks),'feed review scenarios')
