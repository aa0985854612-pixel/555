"""Confirmed feed history defaults and the shared A4/PDF header, on real HTTP."""
import csv,io,json,os,sys,tempfile,threading,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);checks=[]
def passed(s):checks.append(s);print('PASS '+s,flush=True)
with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':'1','FEED_AUTO_ALLOCATION':'headcount'}):
 s=Store(Path(tmp)/'db');u=s.create_user('owner','83000011')
 def add(kind,**body):return s.mutate(u,kind,body,str(uuid.uuid4()))
 barns={n:add('barns',name=f'{n}棟') for n in (1,2,8,11,13,19,22)}
 batches={n:add('batches',name='PAIR' if n in (1,2) else 'BATCH-'+str(n),barn_id=b['id'],entry_date='2026-07-17',entry_count=100,entry_age_days=70,status='active') for n,b in barns.items()}
 bins={name:add('feed_bins',name=name,vendor='養全',active=True,barn_ids=[barns[n]['id'] for n in ns]) for name,ns in [('1、2',(1,2)),('8',(8,)),('11-1',(11,)),('11-2',(11,)),('13',(13,)),('22',(22,))]}
 def order(bin,item,date='2026-10-20',**patches):
  b=bins[bin];return add('feed_orders',date=date,kg=2000,display_unit='ton',feed_bin_id=b['id'],target_batch_ids=[x['id'] for x in batches.values() if x['barn_id'] in b['barn_ids']],item=item,**patches)
 order('1、2','仔豬料');order('11-1','哺乳二期料');order('11-2','大豬料','2026-10-21')
 old=order('13','仔豬料');latest=order('13','大豬料','2026-11-01');order('13','哺乳二期料','2026-10-01');order('13','','2026-11-02')
 add('deliveries',date='2026-10-20',kg=1000,display_unit='ton',vendor='養全',item='舊來源料名',allocations=[{'batch_id':batches[19]['id'],'kg':1000}])
 original=s.export_backup();original_count=len(s.snapshot()['feed_orders']);server=Server(('127.0.0.1',0),s);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(pg):
    pg.goto(url);pg.locator('#login-form [name=username]').fill('owner');pg.locator('#login-form [name=password]').fill('83000011');pg.locator('#login-form button').click();pg.wait_for_selector('#workspace:not([hidden])');pg.locator('nav [href="#feed"]').click()
   login(page);f=page.locator('#feed-order-form');item=f.locator('[name=item]')
   def choose(n):f.locator('[name=barn_id]').select_option(barns[n]['id'])
   choose(13);assert item.input_value()=='大豬料';choose(1);assert item.input_value()=='仔豬料';choose(2);assert item.input_value()=='仔豬料';choose(8);assert item.input_value()=='';choose(19);assert item.input_value()=='舊來源料名';passed('barn selection recalls latest dated nonblank confirmed type, shared-bin and legacy records; unknown barn stays blank')
   choose(11);assert item.input_value()=='大豬料';f.locator('[name=feed_bin_id]').select_option(bins['11-1']['id']);assert item.input_value()=='哺乳二期料';f.locator('[name=feed_bin_id]').select_option(bins['11-2']['id']);assert item.input_value()=='大豬料';passed('two physical bins keep separate feed types when selecting their bin')
   choose(13);item.select_option('哺乳二期料');quantity=f.locator('[name=amount]');quantity.fill('');quantity.press('ArrowUp');assert quantity.input_value()=='1';quantity.press('ArrowUp');assert quantity.input_value()=='2';quantity.press('ArrowUp');assert quantity.input_value()=='3';quantity.press('ArrowDown');assert quantity.input_value()=='2';f.locator('[name=amount]').fill('2.000');item.focus();assert f.locator('[name=amount]').input_value()=='2'
   for lang in ('vi','zh'):
    page.select_option('#language',lang);page.evaluate('async()=>await refresh()');assert item.input_value()=='哺乳二期料';assert f.locator('[name=amount]').input_value()=='2'
   f.locator('[name=amount]').fill('1.50');item.focus();assert f.locator('[name=amount]').input_value()=='1.5';passed('manual changes survive sync/language switching; native quantity arrows start at 1 and increment/decrement whole units, integers lose trailing zeros and real fractional tonnes keep precision')
   # A second browser sees only confirmed records, never this unsaved override.
   other=browser.new_page(viewport={'width':768,'height':1024});login(other);of=other.locator('#feed-order-form');of.locator('[name=barn_id]').select_option(barns[13]['id']);assert of.locator('[name=item]').input_value()=='大豬料';assert s.export_backup()['records']==original['records'];passed('new device reads shared database history without using local memory or writing the unsaved choice')
   # Editing must restore the original type rather than today's default.
   page.evaluate('delete document.querySelector("#feed-order-form").dataset.dirty');page.locator(f'[data-edit=feed_orders][data-id="{old["id"]}"]').click();assert item.input_value()=='仔豬料';assert f.locator('[name=amount]').input_value()=='2';f.locator('[data-action=cancelEdit]').click();choose(13);assert item.input_value()=='大豬料';passed('editing an older record preserves its original type and clean integer quantity')
   f.locator('[name=date]').fill('2026-11-03');f.locator('[name=amount]').fill('2.000');item.select_option('哺乳二期料');f.locator('button.primary').click();page.wait_for_selector('#feed-review-dialog[open]');assert '2 噸' in page.locator('#feed-review-body').inner_text();page.locator('#feed-review-confirm').click();page.wait_for_function('()=>pending===null&&document.querySelector("#feed-order-form [name=amount]").value===""');saved=next(r for r in s.snapshot()['feed_orders'] if r['date']=='2026-11-03');assert saved['kg']==2000 and saved['item']=='哺乳二期料'
   other.evaluate('async()=>await refresh()');of.locator('[name=barn_id]').select_option('');of.locator('[name=barn_id]').select_option(barns[13]['id']);assert of.locator('[name=item]').input_value()=='哺乳二期料';other.close();passed('confirmed manual type change is saved once and becomes the next default on another device')
   page.evaluate('()=>{window.models=[];const pdf=weeklyPdf;window.weeklyPdf=m=>{models.push(m);return pdf(m)}}');page.locator('nav [href="#stats"]').click();page.locator('#open-weekly-report').click();page.locator('#weekly-cohort').select_option('BATCH-13|2026-07-17');page.wait_for_function('()=>models.at(-1)?.basics.some(([k,v])=>k==="批次"&&v==="BATCH-13")');page.wait_for_selector('#weekly-a4-preview img')
   header=page.evaluate('models.at(-1).basics');assert dict(header)['料別']=='哺乳二期料';assert '本期間登記料別' not in dict(header);assert not any('仔豬料' in str(row) or '大豬料' in str(row) for row in header);assert page.locator('#weekly-sheet-body .weekly-basics').text_content().count('哺乳二期料')==1
   with page.expect_download() as download:page.locator('#weekly-print').click()
   pdf=Path(download.value.path()).read_bytes();assert pdf.startswith(b'%PDF');passed('A4 preview, browser print model and downloaded PDF use only the latest type in the header, including saved future records')
   assert page.locator('#weekly-csv').count()==0;assert {r['item'] for r in s.snapshot()['feed_orders']} >= {'仔豬料','大豬料','哺乳二期料'};assert len(s.snapshot()['feed_orders'])==original_count+1
   page.locator('#weekly-close').click();page.locator('nav [href="#feed"]').click();choose(13);page.screenshot(path=str(root/'artifacts/feed-memory-mobile.png'));assert s.export_backup()['users']==original['users'];assert not errors,errors;passed('historical feed types remain in original records, while the paper CSV button stays removed; no account changes or JavaScript errors')
   browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/feed-memory-browser-results.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'Chromium/real HTTP/isolated SQLite, simulated mobile; no production writes'},ensure_ascii=False,indent=2));print('Completed',len(checks),'feed memory scenarios')
