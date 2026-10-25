"""The paper reads all saved feed, including future rows, from the original ledger."""
import collections,csv,io,json,os,sys,tempfile,threading,uuid,subprocess,re
from datetime import datetime as RealDatetime,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from app.feed import initial_bins
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);checks=[]
def passed(s):checks.append(s);print('PASS '+s,flush=True)
class Clock(RealDatetime):
 @classmethod
 def now(cls,tz=None):return RealDatetime(2026,10,25,4,tzinfo=timezone.utc).astimezone(tz)
with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':'1'}),patch('app.weekly.datetime',Clock):
 s=Store(Path(tmp)/'db');u=s.create_user('owner','83000011');s.create_user('reader','83000012','viewer')
 def add(kind,**body):return s.mutate(u,kind,body,str(uuid.uuid4()))
 barns={n:add('barns',name=f'{n}棟') for n in (1,2,3,4,5,6,7,8,12,13,14,15,16,17,18,19,20,21,22)}
 group={n:'WHITEBOARD-DEMO' if n in (13,22) else 'GROUP-'+str(next(i for i,g in enumerate(((1,2,3,4),(5,6,7),(8,12,14),(15,16,17),(18,19,20,21))) if n in g)) for n in barns}
 batches={n:add('batches',name=group[n],barn_id=b['id'],entry_date='2026-07-17',entry_count=100,entry_age_days=71,status='active') for n,b in barns.items()}
 bins={b['name']:add('feed_bins',**b) for b in initial_bins(list(barns.values()))}
 old=add('batches',name='OLD-13',barn_id=barns[13]['id'],entry_date='2026-01-01',entry_count=100,status='ended')
 photo=[('養全','10-22',[('8',2),('12',8),('18',2),('21',2)]),('養全','10-27',[('8',4),('12',4),('14-1',8),('1、2',4),('3、4',4),('18',2),('21',2)]),('新農科','10-22',[('20',2),('7',2),('15-1',4),('22',2)]),('新農科','10-24',[('13',4)]),('新農科','10-26',[('5、6',2),('16、17',2),('20',2),('7',2),('13',4),('15-1',6),('19',2),('22',2)])]
 original=[]
 for vendor,on,rows in photo:
  for name,tons in rows:
   bin=bins[name];original.append(add('feed_orders',date='2026-'+on,kg=tons*1000,display_unit='ton',vendor=vendor,item='仔豬料',feed_bin_id=bin['id'],target_batch_ids=[b['id'] for b in batches.values() if b['barn_id'] in bin['barn_ids']]))
 assert len(original)==24 and sum(r['kg'] for r in original)==78000
 before=s.export_backup()['records'];server=Server(('127.0.0.1',0),s);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:(errors.append(str(e)),print('BROWSER ERROR',e,flush=True)));page.on('response',lambda r: print('REPORT ERROR',r.status,r.text(),flush=True) if '/api/weekly-report?' in r.url and r.status!=200 else None)
   page.goto(url);page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   page.evaluate('()=>{window.models=[];window.feedDraws=[];const pdf=weeklyPdf;window.weeklyPdf=m=>{models.push(m);return pdf(m)};const draw=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...args){if(String(args[0]).includes("+"))feedDraws.push(args[0]);return draw.apply(this,args)};}')
   page.locator('nav [href="#stats"]').click();page.locator('#stats-filter [name=from]').fill('2026-10-01');page.locator('#stats-filter [name=to]').fill('2026-10-20');page.locator('#stats-filter [name=barn_id]').select_option(barns[13]['id'],force=True)
   page.locator('#open-weekly-report').click();page.wait_for_selector('#weekly-a4-preview img');assert page.locator('#weekly-report-form input[type=date]').count()==0;assert page.locator('#weekly-barn').input_value()==barns[13]['id'];assert page.locator('#weekly-cohort').input_value()=='WHITEBOARD-DEMO|2026-07-17';assert page.locator('#weekly-report-form label').all_text_contents()[0].startswith('批號')
   labels=page.locator('#weekly-cohort option').all_text_contents();assert all('｜' in label and not re.search(r'2026-\d{2}-\d{2}',label) for label in labels);assert 'WHITEBOARD-DEMO｜13棟、22棟' in labels,labels
   assert page.locator('#weekly-barn option').all_text_contents()==['同批全部棟舍','13棟','22棟']
   def lines():return page.locator('#weekly-sheet-body .weekly-feed-entry').all_text_contents()
   assert lines()==['10/24+4(13)','10/26+4(13)'],lines();assert dict(page.evaluate('models.at(-1).totals'))['飼料到料（噸）']=='8';passed('batch-first selector shows batch and barns without entry dates; only matching barns are offered; old stats end date cannot hide the saved October 24/26 feed')
   page.locator('#weekly-barn').select_option('');page.wait_for_selector('#weekly-a4-preview img');assert len(lines())==4,lines();assert dict(page.evaluate('models.at(-1).totals'))['飼料到料（噸）']=='12'
   full=[]
   for name in set(group.values()):
    result=page.request.get(url+'/api/weekly-report?all_records=1&cohort='+name+'%7C2026-07-17');assert result.status==200
    full.extend(d for w in result.json()['weeks'] for d in w['feed_details'])
   assert len(full)==24 and sum(d['kg'] for d in full)==78000;assert {d['id'] for d in full}=={o['id'] for o in original};assert next(d for d in full if d.get('bin')=='14')['kg']==8000;passed('all 24 synthetic whiteboard records are present once across their proper batches, totaling 78 tons including October 26/27; a two-barn paper prints its own four rows and 12 tons')
   with page.expect_download() as d:page.locator('#weekly-csv').click()
   rows=list(csv.reader(io.StringIO(Path(d.value.path()).read_text(encoding='utf-8-sig'))));header=next(i for i,r in enumerate(rows) if r[:4]==['日期','棟舍','公斤','噸']);raw=[]
   for r in rows[header+1:]:
    if not r:break
    raw.append(r)
   assert len(raw)==4 and sum(float(r[2]) for r in raw)==12000;assert {r[0] for r in raw}=={'2026-10-22','2026-10-24','2026-10-26'}
   page.evaluate('feedDraws=[]');page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-a4-preview img');draws=page.evaluate('feedDraws');assert collections.Counter(draws)==collections.Counter(lines()),(draws,lines())
   with page.expect_download() as d:page.locator('#weekly-print').click()
   pdf=root/'artifacts/weekly-all-records-whiteboard.pdf';d.value.save_as(pdf);info=subprocess.check_output(['pdfinfo',str(pdf)],text=True);assert '595.28 x 841.89' in info;assert re.search(r'Pages:\s+1\b',info);assert '叫料不等於到料' not in page.locator('#weekly-sheet-body').inner_text();passed('HTML, CSV and A4 PDF draw the same four scoped feed lines including future October 26, without duplicate arrivals')
   page.locator('#weekly-barn').select_option(barns[13]['id']);page.wait_for_selector('#weekly-a4-preview img');page.locator('#weekly-cohort').select_option('OLD-13|2026-01-01');page.wait_for_selector('#weekly-a4-preview img');assert not lines();assert page.locator('#weekly-barn option').all_text_contents()==['同批全部棟舍','13棟'];page.locator('#weekly-cohort').select_option('WHITEBOARD-DEMO|2026-07-17');page.wait_for_selector('#weekly-a4-preview img');assert len(lines())==4;assert page.locator('#weekly-barn').input_value()=='';page.locator('#weekly-barn').select_option(barns[13]['id']);page.wait_for_selector('#weekly-a4-preview img');assert len(lines())==2;passed('switching batch resets to all matching barns, excludes unrelated barns and keeps old and current feed separate')
   later=add('feed_orders',date='2026-11-03',kg=1500,display_unit='ton',vendor='新農科',item='大豬料',allocations=[{'batch_id':batches[13]['id'],'kg':1500}]);page.evaluate('()=>refresh()');page.wait_for_selector('#weekly-a4-preview img');assert lines()[-1]=='11/3+1.5(13)';assert dict(page.evaluate('models.at(-1).totals'))['飼料到料（噸）']=='9.5';passed('another device saving a wholly future week automatically refreshes the open paper and PDF; future records are not blanked')
   updated=s.mutate(u,'feed_orders',dict(later,kg=1000,allocations=[{'batch_id':batches[13]['id'],'kg':1000}]),str(uuid.uuid4()),later['id']);page.evaluate('()=>refresh()');page.wait_for_selector('#weekly-a4-preview img');assert lines()[-1]=='11/3+1(13)';assert len(lines())==3
   s.mutate(u,'feed_orders',{'revision':updated['revision']},str(uuid.uuid4()),later['id'],delete=True);page.evaluate('()=>refresh()');page.wait_for_selector('#weekly-a4-preview img');assert lines()==['10/24+4(13)','10/26+4(13)'];assert [r for r in s.export_backup()['records'] if r['id']!=later['id']]==before;passed('editing and deleting the original future order refreshes the paper, with no extra arrivals or accumulated old quantities')
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.evaluate('(l)=>{lang=l;translate()}',language);page.wait_for_selector('#weekly-a4-preview img');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');assert page.locator('#weekly-report-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
   page.set_viewport_size({'width':390,'height':844});page.evaluate('lang="zh";translate()');page.wait_for_selector('#weekly-a4-preview img');page.locator('#weekly-report-dialog').evaluate('(e)=>e.scrollTop=0');page.screenshot(path=str(root/'artifacts/weekly-all-records-mobile.png'));passed('batch-first form and A4 preview fit 320/390/768/1440 screens in Traditional Chinese and Vietnamese')
   page.locator('#weekly-close').click();page.locator('#logout').click();page.locator('#login-form [name=username]').fill('reader');page.locator('#login-form [name=password]').fill('83000012');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])');r=page.request.get(url+'/api/weekly-report?batch_id='+batches[13]['id']+'&all_records=1');assert r.status==200 and r.json()['totals']['feed_orders']==8000;page.locator('#logout').click();page.wait_for_selector('#login-view:not([hidden])');assert page.request.get(url+'/api/weekly-report?batch_id='+batches[13]['id']+'&all_records=1').status==401;assert not errors,errors;passed('viewer can read the complete report, logged-out requests are rejected and no browser errors occur');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/weekly-all-records-results.json').write_text(json.dumps({'version':VERSION,'mode':'real Chromium/HTTP/isolated SQLite and synthetic whiteboard; no production farm writes','checks':checks},ensure_ascii=False,indent=2));print('Completed',len(checks),'complete paper scenarios')
