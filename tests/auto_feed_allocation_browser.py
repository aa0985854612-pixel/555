"""Shared-bin registration auto-updates each cohort's paper from one original row."""
import collections,csv,io,json,os,sys,tempfile,threading,uuid,re,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from app.bin_stock import stock
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);checks=[]
def passed(s):checks.append(s);print('PASS '+s,flush=True)
with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':'1','FEED_AUTO_ALLOCATION':'headcount'}):
 s=Store(Path(tmp)/'db');u=s.create_user('owner','83000011')
 def add(kind,**d):return s.mutate(u,kind,d,str(uuid.uuid4()))
 barns={n:add('barns',name=f'{n}棟') for n in (1,2,18)};batches={n:add('batches',name='JD-A' if n in (1,18) else 'JD-B',barn_id=b['id'],entry_date='2026-10-01',entry_age_days=70,entry_count=300 if n==2 else 100,status='active') for n,b in barns.items()}
 bin=add('feed_bins',name='1、2',barn_ids=[barns[n]['id'] for n in (1,2)],vendor='養全',active=True,inventory_enabled=True,capacity_kg=12000,safe_fill_percent=85,inventory_date='2026-10-01',inventory_opening_kg=0)
 one=add('feed_orders',date='2026-10-27',kg=4000,display_unit='ton',feed_bin_id=bin['id'],target_batch_ids=[batches[n]['id'] for n in (1,2)],bin_allocations=[],allocations=[],vendor='養全',item='哺乳二期料')
 add('feed_orders',date='2026-10-27',kg=2000,display_unit='ton',vendor='養全',item='哺乳二期料',allocations=[{'batch_id':batches[18]['id'],'kg':2000}]);before=s.export_backup()['records']
 server=Server(('127.0.0.1',0),s);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(url);page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   page.evaluate('()=>{window.models=[];window.autoDraws=[];const pdf=weeklyPdf;window.weeklyPdf=m=>{models.push(m);return pdf(m)};const draw=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...args){if(String(args[0]).includes("+"))autoDraws.push(args[0]);return draw.apply(this,args)};}')
   def open_report(key):
    page.locator('nav [href="#daily"]').click();page.locator('#open-daily-weekly-report').click();page.locator('#weekly-cohort').select_option(key+'|2026-10-01');page.wait_for_selector('#weekly-a4-preview img')
   def lines():return page.locator('#weekly-sheet-body .weekly-feed-entry').all_text_contents()
   open_report('JD-A');assert sorted(line.strip() for line in lines())==['+2(18)','10/27+1(1)'],lines();assert not page.locator('#weekly-sheet-body .feed-shared-note').count();assert '共用料桶未分攤' not in page.locator('#weekly-sheet-body').inner_text();assert dict(page.evaluate('models.at(-1).totals'))['飼料到料（噸）']=='3';assert '存欄比例自動分攤' in page.evaluate('models.at(-1).legend');passed('existing shared 4-ton order automatically contributes 1 ton to JD-A; its 18-barn 2 tons remain separate; no shared-pending paper line')
   page.evaluate('autoDraws=[]');page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-a4-preview img');assert collections.Counter(page.evaluate('autoDraws'))==collections.Counter(lines())
   with page.expect_download() as d:page.locator('#weekly-print').click()
   pdf=root/'artifacts/auto-feed-allocation-a4.pdf';d.value.save_as(pdf);assert '595.28 x 841.89' in subprocess.check_output(['pdfinfo',str(pdf)],text=True)
   with page.expect_download() as d:page.locator('#weekly-csv').click()
   rows=list(csv.reader(io.StringIO(Path(d.value.path()).read_text(encoding='utf-8-sig'))));assert any(r[:4]==['2026-10-27','1棟','1000','1'] for r in rows);assert not any(r[:4]==['2026-10-27','1棟','4000','4'] for r in rows);passed('screen, PDF drawing and CSV show only the allocated 1 ton on this cohort rather than all 4 tons')
   page.locator('#weekly-cohort').select_option('JD-B|2026-10-01');page.wait_for_selector('#weekly-a4-preview img');assert lines()==['10/27+3(1)'];assert dict(page.evaluate('models.at(-1).totals'))['飼料到料（噸）']=='3';assert s.export_backup()['records']==before;assert stock(s.snapshot(),bin,'2026-10-27')['received_kg']==4000;page.locator('#weekly-close').click();passed('other cohort receives its 3-ton portion; paper generation preserves original IDs and rows; physical bin receives 4 tons once')
   page.locator('nav [href="#feed"]').click();f=page.locator('#feed-order-form');f.locator('[name=date]').fill('2026-10-28');f.locator('[name=feed_bin_id]').select_option(bin['id']);f.locator('[name=item]').select_option('哺乳二期料');f.locator('[name=display_unit]').select_option('ton');f.locator('[name=amount]').fill('2');assert not f.locator('[name=bin_split_confirmed]').is_checked();f.locator('button.primary').click();page.wait_for_selector('#feed-review-dialog[open]');parts=page.locator('#feed-review-body .feed-auto-allocation');assert '存欄比例自動分攤' in parts.inner_text();assert '0.5 噸' in parts.inner_text() and '1.5 噸' in parts.inner_text();passed('normal feed form requires no manual split; confirmation shows automatic 0.5/1.5-ton portions before writing')
   def lose(route):route.fetch();route.abort()
   page.route('**/api/feed-order-apply',lose);page.locator('#feed-review-confirm').click();page.wait_for_selector('#pending:not([hidden])');assert len(s.snapshot()['feed_orders'])==3;page.unroute('**/api/feed-order-apply',lose);page.locator('#retry').click();page.wait_for_function('()=>pending===null');assert len(s.snapshot()['feed_orders'])==3 and not s.snapshot()['deliveries'];new=next(r for r in s.snapshot()['feed_orders'] if r['date']=='2026-10-28');assert new.get('bin_allocations',[])==[];passed('lost response and same-key retry create one original order; no copied arrivals or manual allocation rows')
   open_report('JD-A');assert '10/28+0.5(1)' in lines();assert dict(page.evaluate('models.at(-1).totals'))['飼料到料（噸）']=='3.5'
   updated=s.mutate(u,'feed_orders',new|{'kg':1500,'revision':new['revision']},str(uuid.uuid4()),new['id']);page.evaluate('()=>refresh()');page.wait_for_selector('#weekly-a4-preview img');assert '10/28+0.375(1)' in lines();s.mutate(u,'feed_orders',{'revision':updated['revision']},str(uuid.uuid4()),new['id'],delete=True);page.evaluate('()=>refresh()');page.wait_for_selector('#weekly-a4-preview img');assert len(lines())==2;assert dict(page.evaluate('models.at(-1).totals'))['飼料到料（噸）']=='3';passed('new entry, original quantity correction and deletion automatically refresh each report using net allocated quantities')
   for width in (320,390,768):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.evaluate('(l)=>{lang=l;translate()}',language);page.wait_for_selector('#weekly-a4-preview img');assert page.locator('#weekly-report-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
   page.evaluate('lang="zh";translate()');page.wait_for_selector('#weekly-a4-preview img');page.locator('#weekly-sheet-body > details').evaluate('(e)=>e.open=true');page.locator('#weekly-sheet-body .weekly-feed_orders').first.scroll_into_view_if_needed();page.screenshot(path=str(root/'artifacts/auto-feed-allocation-mobile.png'));assert not errors,errors;passed('Chinese/Vietnamese mobile paper stays within the screen with no browser errors');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/auto-feed-allocation-results.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'isolated synthetic SQLite, real HTTP/Chromium; no production farm writes'},ensure_ascii=False,indent=2));print('Completed',len(checks),'automatic allocation scenarios')
