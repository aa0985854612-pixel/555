"""Mixed entry dates retain truthful ages and share the ordinary A4 grid."""
import csv,io,json,re,subprocess,sys,tempfile,threading,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(s):checks.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as temp:
 s=Store(Path(temp)/'db');u=s.create_user('owner','83000011');s.create_user('reader','83000012','viewer')
 def add(kind,**d):return s.mutate(u,kind,d,str(uuid.uuid4()))
 barns={n:add('barns',name=f'{n}棟',feed_vendor='新農科') for n in (15,21,12,24)}
 first=add('batches',name='MIXED',barn_id=barns[15]['id'],entry_date='2026-10-09',entry_count=1052,entry_age_days=71,entry_mean_kg=21.36,status='active')
 second=add('batches',name='MIXED',barn_id=barns[21]['id'],same_batch_as=first['id'],entry_date='2026-10-16',entry_count=318,entry_age_days=71,entry_mean_kg=21.58,status='active')
 for n in (12,24):add('batches',name='ORDINARY',barn_id=barns[n]['id'],entry_date='2026-06-19',entry_count=100,entry_age_days=70,status='active')
 bins={label:add('feed_bins',name=label,barn_ids=[barns[n]['id']],vendor='新農科',active=True) for label,n in [('15-1',15),('15-2',15),('21',21)]}
 for on,kg,label,b in [('2026-10-08',8000,'15-1',first),('2026-10-10',2000,'15-2',first),('2026-10-16',1000,'21',second)]:add('feed_orders',date=on,kg=kg,display_unit='ton',vendor='新農科',item='哺乳二期料',feed_bin_id=bins[label]['id'],target_batch_ids=[b['id']])
 for on,b in [('2026-10-16',first),('2026-10-17',second)]:add('movements',date=on,type='death',quantity=1,batch_id=b['id'])
 before=s.snapshot();server=Server(('127.0.0.1',0),s);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(name,pw):page.goto(url);page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(pw);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   def generate():page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-export-actions:not([hidden])')
   login('owner','83000011');page.locator('#movement-form details').evaluate('(e)=>e.open=true');page.locator('#movement-form [name=note]').fill('next daily draft');page.locator('#open-daily-weekly-report').click();page.locator('#weekly-cohort').select_option('ORDINARY|2026-06-19');page.locator('#weekly-to').fill('2026-10-18');generate();sheet=page.locator('#weekly-sheet-body');ordinary=sheet.locator('.weekly-table').evaluate_all('(xs)=>xs.map(x=>({columns:x.querySelectorAll("thead th").length,width:x.getBoundingClientRect().width}))')
   page.evaluate('()=>{window.originalPdf=window.weeklyPdf;window.weeklyPdf=m=>{window.lastModel=m;return originalPdf(m)};window.drawn=[];const old=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...a){drawn.push(a[0]);return old.apply(this,a)}}')
   page.locator('#weekly-cohort').select_option('MIXED|2026-10-09');page.locator('#weekly-to').fill('2026-10-18');generate();mixed=sheet.locator('.weekly-table').evaluate_all('(xs)=>xs.map(x=>({columns:x.querySelectorAll("thead th").length,width:x.getBoundingClientRect().width}))');assert ordinary==mixed and [x['columns'] for x in mixed]==[13,13]
   assert sheet.locator('.weekly-table thead th').first.inner_text()=='15棟週次';assert sheet.locator('.weekly-table').first.locator('thead th').all_text_contents()[1:]==[f'第{i}週' for i in range(11,23)];assert sheet.locator('.weekly-table').nth(1).locator('thead th').all_text_contents()[1:]==[f'第{i}週' for i in range(23,33)]+['',''];assert '本表週次依15棟' in sheet.inner_text()
   facts=sheet.locator('.weekly-entry-facts').inner_text();assert all(v in facts for v in ['2026-10-09','2026-10-16','1,052','318','21.36','21.58']);assert sheet.locator('.weekly-entry-facts tbody tr').nth(1).inner_text().count('71')==1
   passed('mixed 15/21 cohort now has the ordinary two equal 12-column bands to week 32 plus two blanks, with explicit 15-barn reference and original entry facts')
   with page.expect_download() as dl:page.locator('#weekly-print').click()
   pdf=root/'artifacts/weekly-mixed-15-21-a4.pdf';dl.value.save_as(pdf);info=subprocess.check_output(['pdfinfo',str(pdf)],text=True);assert re.search(r'Pages:\s+1\b',info) and '595.28 x 841.89' in info;model=page.evaluate('lastModel');assert model['cycle']=='15棟週次';assert [len(b['headers']) for b in model['pages'][0]]==[12,12];assert model['entries'][1][1:4]==['2026-10-16','318','71 天'];assert model['preentry']['summary']=='8 噸';assert dict(model['totals'])['叫料登記量（噸）']=='3';assert page.evaluate('drawn').count('10/8+8（15-1）')==1;assert '… CSV' not in page.evaluate('drawn');assert model['pages'][0][1]['headers'][-2:]==['',''];assert '15棟' in model['legend']
   with page.expect_download() as dl:page.locator('#weekly-csv').click()
   rows=list(csv.reader(io.StringIO(Path(dl.value.path()).read_text(encoding='utf-8-sig'))));cycle=next(r for r in rows if r and r[0]=='15棟週次');assert cycle[1]=='第11週' and cycle[-1]=='第32週';assert ['叫料登記量（噸）','3'] in rows;assert any(r and r[0]=='進場前叫料' and '8 噸' in r for r in rows)
   passed('actual downloaded PDF is one portrait A4; preview/PDF/CSV use the named reference, pre-entry 8 tonnes appears once and period feed stays 3 tonnes')
   for n,on in [(15,'2026-10-09'),(21,'2026-10-16')]:
    page.locator('#weekly-barn').select_option(barns[n]['id']);generate();assert sheet.locator('.weekly-table thead th').first.inner_text()=='週期';assert sheet.locator('.weekly-table').first.locator('thead th').nth(1).inner_text()=='第11週';assert sheet.locator('.weekly-starts td').first.inner_text()==('10/9' if n==15 else '10/16');assert sheet.locator('.weekly-entry-facts tbody tr').count()==1
   passed('single 15 and single 21 retain their own entry dates and true week 11; the cohort reference is never applied to the single later barn')
   page.locator('#weekly-barn').select_option('');page.locator('#weekly-from').fill('2026-10-16');generate();assert sheet.locator('.weekly-table').first.locator('thead th').nth(1).inner_text()=='第12週';assert sheet.locator('.weekly-preentry').count()==0;page.locator('#weekly-from').fill('2026-10-09');generate();cases=0
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.evaluate('(v)=>{lang=v;translate()}',language)
     for size in ('small','medium','large'):
      page.evaluate('(v)=>document.documentElement.dataset.textSize=v',size);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');assert page.locator('#weekly-report-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1');cases+=1
   page.evaluate('lang="vi";translate();drawn=[]')
   with page.expect_download() as dl:page.locator('#weekly-print').click()
   vi=root/'artifacts/weekly-mixed-15-21-vi-a4.pdf';dl.value.save_as(vi);assert re.search(r'Pages:\s+1\b',subprocess.check_output(['pdfinfo',str(vi)],text=True));assert '… CSV' not in page.evaluate('drawn')
   passed(f'partial intervals keep the reference date; {cases} language/font/phone/tablet/desktop layouts fit and Vietnamese PDF also stays one A4')
   page.evaluate('lang="zh";translate()');page.locator('#weekly-close').click();assert page.locator('#movement-form [name=note]').input_value()=='next daily draft';assert s.snapshot()==before;assert not errors,errors;browser.close();passed('reporting preserves all farm data, accounts and the next daily draft; no browser errors')
 finally:server.shutdown();server.server_close()
(root/'artifacts/weekly-reference-browser-results.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'local real Chromium/HTTP/PDF with synthetic data; not physical iPhone/Safari/printer'},ensure_ascii=False,indent=2));print('Completed',len(checks),'weekly reference scenarios')
