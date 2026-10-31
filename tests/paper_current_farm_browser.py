"""Real mobile workflow for the six paper, equal-feed and live-overview requests."""
import copy,json,os,sys,tempfile,threading,uuid,subprocess,re
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION,Problem
from app.source_edit import duplicate_token
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);checks=[]
def passed(s):checks.append(s);print('PASS '+s,flush=True)
with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':'1','FEED_AUTO_ALLOCATION':'equal'}):
 s=Store(Path(tmp)/'db');u=s.create_user('owner','83000011');s.create_user('reader','83000012','viewer')
 def add(kind,**body):
  try:return s.mutate(u,kind,body,str(uuid.uuid4()))
  except Problem as error:
   if kind!='movements' or error.args[0]!='movement_duplicate':raise
   data=s.snapshot();clean=s.validate(kind,body,data,u);return s.mutate(u,kind,body|{'duplicate_confirmation':duplicate_token(data,clean)},str(uuid.uuid4()))
 barns={n:add('barns',name=f'{n}棟') for n in (1,2,9,12)}
 first=add('batches',name='PAPER',barn_id=barns[1]['id'],entry_date='2026-07-17',entry_count=1000,entry_age_days=70,status='active')
 batches={1:first,2:add('batches',name='PAPER',barn_id=barns[2]['id'],entry_date='2026-07-17',entry_count=300,entry_age_days=70,status='active',same_batch_as=first['id'])}
 for n in (9,12):batches[n]=add('batches',name='OLD-'+str(n),barn_id=barns[n]['id'],entry_date='2026-06-01',entry_count=100,entry_age_days=70,status='active')
 for date,q,place in [('2026-10-13',3,'南投'),('2026-10-14',50,'新北'),('2026-10-15',60,'新北'),('2026-10-16',80,'嘉義'),('2026-10-23',39,'嘉義'),('2026-10-23',39,'南投'),('2026-10-26',70,'南投'),('2026-10-27',59,'南投'),('2026-10-30',38,'嘉義')]:add('movements',date=date,type='sale',batch_id=first['id'],quantity=q,outgoing_destination=place)
 add('movements',date='2026-10-30',type='sale',batch_id=batches[2]['id'],quantity=1,outgoing_destination='嘉義');add('movements',date='2026-10-30',type='sale',batch_id=batches[9]['id'],quantity=100,outgoing_destination='嘉義')
 for n in (1,2):
  for i in (10,18,28):add('movements',date=f'2026-10-{i}',type='death',batch_id=batches[n]['id'],quantity=1)
 ended=s.mutate(u,'batches',batches[12]|{'status':'ended'},str(uuid.uuid4()),batches[12]['id'])
 bin=add('feed_bins',name='1、2',barn_ids=[barns[n]['id'] for n in (1,2)],vendor='養全',active=True)
 order=add('feed_orders',date='2026-10-26',kg=2000,display_unit='ton',item='大豬料',feed_bin_id=bin['id'],target_batch_ids=[batches[n]['id'] for n in (1,2)])
 original=s.export_backup();server=Server(('127.0.0.1',0),s);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(name='owner',password='83000011'):
    page.goto(url);page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(password);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   login();page.locator('[data-daily-view=overview]').click();page.wait_for_selector('#cleared-records');live=page.evaluate('data.dashboard.current_farm');all_sold=page.evaluate('data.dashboard.cumulative.sold');assert all_sold-live['herd']['sold']==100;assert set(live['ids'])=={batches[1]['id'],batches[2]['id']};assert page.locator('#barns .overview-barn').count()==2;assert page.locator('#home-metrics').inner_text().count(str(live['herd']['sold']))==1;passed('live overview excludes cleared barn9 and ended barn12 while lifetime sales remain exactly100 higher')
   page.locator('#cleared-records>summary').click();assert page.locator('.cleared-record').count()==2;page.locator(f'[data-cleared-history="{batches[9]["id"]}"]').click();page.wait_for_selector('#page-history:not([hidden])');page.wait_for_selector('#history-results tbody tr');assert page.locator('#history-filter [name=batch_id]').input_value()==batches[9]['id'];assert page.locator('#history-filter [name=from]').input_value()=='';assert '100' in page.locator('#history-results').inner_text();passed('cleared-record history shortcut opens the exact old batch with no stale date limits')
   page.locator('nav [href="#daily"]').click();page.locator('[data-daily-view=overview]').click();page.locator('#cleared-records').evaluate('(e)=>e.open=true');page.locator(f'[data-cleared-report="{batches[12]["id"]}"]').click();page.wait_for_selector('#weekly-a4-preview img');assert page.locator('#weekly-cohort option:checked').inner_text().startswith('OLD-12');assert page.locator('#weekly-csv').count()==0;assert 'CSV' not in page.locator('#weekly-report-dialog').text_content();page.locator('#weekly-close').click();passed('ended batch remains available for A4 reporting and the paper dialog has no CSV button or CSV guidance')
   page.evaluate('()=>{window.models=[];window.draws=[];let n=0;const ids=new WeakMap();const pdf=weeklyPdf;window.weeklyPdf=m=>{models.push(m);return pdf(m)};const draw=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...a){if(!ids.has(this.canvas))ids.set(this.canvas,n++);draws.push({text:String(a[0]),x:a[1],y:a[2],page:ids.get(this.canvas)});return draw.apply(this,a)}}')
   page.locator('nav [href="#stats"]').click();page.locator('#open-weekly-report').click();page.locator('#weekly-cohort').select_option('PAPER|2026-07-17');page.wait_for_selector('#weekly-a4-preview img');model=page.evaluate('models.at(-1)');sale_rows=[r for pp in model['pages'] for band in pp for r in band['rows'] if r['label']=='售出數'];assert any('50、60' in v for r in sale_rows for v in r['cells']);assert '10/30 嘉義39' in model['shipping_notes'];assert not any('嘉義38' in v for v in model['shipping_notes']);passed('weekly sale cells list each shipment amount; two barns on the same truck remain one Chiayi39 entry')
   draws=page.evaluate('draws');shipping=model['shipping_notes'];points=[next(d for d in draws if d['text']==v) for v in shipping];assert points[0]['x']==points[1]['x'] and points[0]['y']<points[1]['y'];assert all(points[i]['y']<points[i+1]['y'] for i in range(len(points)-1));assert all(p['x']==points[0]['x'] for p in points);assert not any('CSV' in d['text'] for d in draws)
   with page.expect_download() as dl:page.locator('#weekly-print').click()
   output=root/'artifacts/paper-current-farm-a4.pdf';dl.value.save_as(output);assert '595.28 x 841.89' in subprocess.check_output(['pdfinfo',str(output)],text=True);page.locator('#weekly-a4-preview img').first.screenshot(path=str(root/'artifacts/paper-current-farm-a4.png'));passed('shipment notes run chronologically down one column when they fit, on the actual portrait A4 PDF')
   page.locator('#weekly-barn').select_option(barns[1]['id']);page.wait_for_selector('#weekly-a4-preview img');one=page.request.get(url+'/api/weekly-report?all_records=1&batch_id='+first['id']).json();two=page.request.get(url+'/api/weekly-report?all_records=1&batch_id='+batches[2]['id']).json();assert one['totals']['feed_orders']==two['totals']['feed_orders']==1000;assert len(s.snapshot()['feed_orders'])==1 and s.snapshot()['feed_orders'][0]['kg']==2000;passed('shared two-ton receipt is one original row and each barn report receives exactly one ton despite different headcounts')
   # Real PDF overflow: fill down before the right-hand column, then continue pages.
   extra=copy.deepcopy(model);extra['shipping_notes']=[f'10/{i} 嘉義{i}' for i in range(1,121)];extra['death_groups']=[{'title':'第1棟','notes':[f'9/{i} 死亡1隻' for i in range(1,101)]}]
   result=page.evaluate('''async m=>{draws=[];const pdf=await weeklyPdf(m);return {draws,pages:pdf.previewPages.length}}''',extra);assert result['pages']>1;draws=result['draws']
   for expected in extra['shipping_notes']+extra['death_groups'][0]['notes']:assert sum(d['text']==expected for d in draws)==1,(expected,draws)
   a=next(d for d in draws if d['text']==extra['shipping_notes'][0]);next_col=next(d for d in draws if d['text'] in extra['shipping_notes'] and d['page']==a['page'] and d['x']>a['x']+10);previous=[d for d in draws if d['text'] in extra['shipping_notes'] and d['page']==a['page'] and d['x']==a['x']];assert len(previous)>1 and previous[-1]['y']>next_col['y'];assert not any('CSV' in d['text'] or '另有' in d['text'] for d in draws);passed('120 shipment entries and100 deaths fill columns downward then right and continue across pages without loss or CSV truncation')
   many=copy.deepcopy(model);many['death_groups']=[];many['death_notes']=[];many['shipping_notes']=[];band=copy.deepcopy(many['pages'][0][0]);band['rows']=[band['rows'][0],next(r for r in band['rows'] if r['label']=='售出數')];values='、'.join(str(i) for i in range(100,220));band['rows'][1]['cells']=[values]+['']*(len(band['headers'])-1);many['pages']=[[band]]
   result=page.evaluate('''async m=>{draws=[];const pdf=await weeklyPdf(m);return {draws,pages:pdf.previewPages.length}}''',many);center=24+58+(595.28-48-58)/len(band['headers'])/2;printed=''.join(d['text'] for d in result['draws'] if abs(d['x']-center)<.01 and re.fullmatch('[0-9、]+',d['text']));assert printed==values,(printed,values);passed('120 individual sale values remain complete in the weekly sale cell instead of being summed or cropped')
   page.locator('#weekly-close').click();page.locator('nav [href="#daily"]').click();page.locator('[data-daily-view=overview]').click()
   for width in (320,390,768):
    page.set_viewport_size({'width':width,'height':900})
    for lang in ('zh','vi'):
     page.select_option('#language',lang);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
   page.select_option('#language','zh');page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(root/'artifacts/current-farm-mobile.png'),full_page=True);assert s.export_backup()['records']==original['records'] and s.export_backup()['users']==original['users'];passed('both languages fit mobile/tablet widths and the reporting changes do not modify farm records or accounts')
   page.locator('#logout').click();page.wait_for_selector('#login-view:not([hidden])');login('reader','83000012');page.locator('[data-daily-view=overview]').click();page.locator('#cleared-records').evaluate('(e)=>e.open=true');page.locator(f'[data-cleared-report="{batches[9]["id"]}"]').click();page.wait_for_selector('#weekly-a4-preview img');assert page.locator('#weekly-barn').input_value()==barns[9]['id'];assert not errors,errors;passed('read-only accounts can find cleared records and print their A4 without write permission or browser errors');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/paper-current-farm-browser.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'real Chromium HTTP, isolated synthetic SQLite; no production farm writes'},ensure_ascii=False,indent=2));print('Completed',len(checks),'paper/current-farm scenarios')
