"""Split barn reports, two entry rows and matching single-A4 PDF/CSV."""
import json,re,sys,tempfile,threading,uuid,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(s):checks.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011')
 def add(kind,**body):return store.mutate(owner,kind,body,str(uuid.uuid4()))
 barn=add('barns',name='15棟');other=add('barns',name='21棟');lots=[{'date':'2026-10-09','count':702,'mean_kg':21.36},{'date':'2026-10-16','count':350,'mean_kg':None}]
 a=add('batches',barn_id=barn['id'],name='JD-115-40.41',entry_date='2026-10-09',entry_count=1052,entry_age_days=71,status='active',weekly_start_date='2026-10-16',report_entry_lots=lots,report_entry_lots_source='synthetic confirmed entry dates and total')
 b=add('batches',barn_id=other['id'],name='JD-115-41',entry_date='2026-10-16',entry_count=318,entry_age_days=71,entry_mean_kg=21.58,status='active',weekly_start_date='2026-10-16')
 add('movements',batch_id=b['id'],date='2026-10-18',type='death',quantity=1);original=store.export_backup();server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url);page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_function('()=>data&&data.batches.length===2');page.wait_for_selector('.overview-cohort',state='attached');assert page.locator('.overview-cohort').count()==2
   page.evaluate('()=>{window.entryModels=[];const pdf=window.weeklyPdf;window.weeklyPdf=model=>{entryModels.push(model);return pdf(model)}}');page.locator('#open-daily-weekly-report').click()
   for name,entry,count in [('JD-115-40.41','2026-10-09',2),('JD-115-41','2026-10-16',1)]:
    page.locator('#weekly-cohort').select_option(name+'|'+entry);assert page.locator('#weekly-from').input_value()=='2026-10-16';page.locator('#weekly-to').fill('2026-10-19');page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-a4-preview img');model=page.evaluate('entryModels.at(-1)');assert len(model['entries'])==count;assert all(r[0]==('15棟' if count==2 else '21棟') for r in model['entries']);assert model['pages'][0][0]['rows'][0]['cells'][0]=='10/16'
    if count==2:assert [r[1] for r in model['entries']]==['2026-10-09','2026-10-16'];assert [r[2] for r in model['entries']]==['702','350'];assert model['entries'][0][4]=='21.36 kg';assert model['entries'][1][4]==''
    else:assert model['entries'][0][2]=='318';assert model['entries'][0][4]=='21.58 kg'
    with page.expect_download() as download:page.locator('#weekly-print').click()
    target=root/'artifacts'/('entry-lots-'+str(count)+'.pdf');download.value.save_as(target);info=subprocess.check_output(['pdfinfo',str(target)],text=True);assert re.search(r'Pages:\s+1\b',info);assert '595.28 x 841.89' in info
   passed('two independent barn reports default to 10/16; 15 has two actual entry rows, 21 has one, unknown weight is blank; both downloads are one portrait A4')
   with page.expect_download() as download:page.locator('#weekly-csv').click()
   csv=download.value.path().read_text(encoding='utf-8-sig');assert 'JD-115-41' in csv and '318' in csv and '21.58' in csv;assert '1052' not in csv;passed('CSV uses the same independent batch and actual entry details')
   page.locator('#weekly-close').click();page.locator('nav [href="#settings"]').click();card=page.locator('.cohort-setting').filter(has=page.locator(f'[data-member="{a["id"]}"]'));card.locator('summary').first.click();card.locator(f'[data-member="{a["id"]}"] [data-edit]').click();f=page.locator('#batch-form');f.locator('details').first.evaluate('(e)=>e.open=true');assert f.locator('[name=weekly_start_date]').input_value()=='2026-10-16';assert f.locator('.report-entry-lot').count()==2
   f.locator('[data-lot=mean_kg]').nth(1).fill('22.5');assert store.export_backup()['records']==original['records'];f.locator('button.primary').click();page.wait_for_function('()=>pending===null');page.wait_for_function('(id)=>data.batches.find(b=>b.id===id)?.report_entry_lots?.[1]?.mean_kg===22.5',arg=a['id']);saved=store.snapshot();assert next(x for x in saved['batches'] if x['id']==a['id'])['entry_count']==1052;assert next(x for x in saved['batches'] if x['id']==b['id'])['entry_count']==318;passed('entry details can be edited and saved in batch settings without adding pigs or changing the other barn')
   assert not errors,errors;assert store.export_backup()['users']==original['users'];browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/report-entry-lots-browser-results.json').write_text(json.dumps({'version':VERSION,'checks':checks},ensure_ascii=False,indent=2));print('Completed',len(checks),'entry report browser scenarios')
