"""Real Chromium, 24 synthetic barns: grouping, safe edits and mobile overview."""
import base64,json,sys,tempfile,threading,uuid
from datetime import date,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from legacy_fixture import workbook_fixture
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1];results=[];measurements={}
def passed(s):results.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');admin=store.create_user('owner','83000011');reader=store.create_user('reader','83000012','viewer');store.create_user('temporary','83000013','staff',must_change=True)
 def add(kind,**d):return store.mutate(admin,kind,d,str(uuid.uuid4()))
 number=3;members=[]
 for i,count in enumerate((3,2,3,2,3,2,2,2,2,1)):
  for j in range(count):
   barn=add('barns',name=f'{number}棟',group='A');number+=1
   b=add('batches',barn_id=barn['id'],name=f'JD-SAMPLE-{39-i}',entry_date=str(date(2026,10,2)-timedelta(days=7*i)),entry_count=200+j,entry_age_days=70,status='active',entry_mean_kg=22.4+i)
   members.append(b)
 add('movements',batch_id=members[0]['id'],date='2026-10-15',type='death',quantity=2)
 old=add('batches',barn_id=members[3]['barn_id'],name=members[0]['name'],entry_date='2025-01-01',entry_count=10,status='ended')
 store.import_workbook(admin,{'filename':'synthetic.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'},str(uuid.uuid4()))
 original=store.export_backup();server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];writes=[]
   page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:writes.append(r.url) if r.method in ('POST','PUT','DELETE') else None)
   page.goto(f'http://127.0.0.1:{server.server_port}')
   def login(name,password):
    page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(password);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   login('owner','83000011');page.wait_for_selector('#barns .overview-barn');assert page.locator('#barns .overview-barn').count()==24
   assert page.locator('#daily-entry').is_visible();assert page.locator('#movement-form').bounding_box()['y']<page.locator('#home-metrics').bounding_box()['y']
   f=page.locator('#movement-form');f.locator('[name=quantity]').fill('7');page.locator('[data-daily-view=overview]').click();assert page.locator('#daily-entry').is_hidden();assert f.locator('[name=quantity]').input_value()=='7';page.wait_for_timeout(400)
   measurements['overview_metrics_top_px']=round(page.locator('#home-metrics').bounding_box()['y']);assert measurements['overview_metrics_top_px']<260
   first=page.locator(f'[data-add-batch="{members[0]["id"]}"]');assert page.locator('.overview-barn').filter(has=first).locator('.overview-dead').inner_text()=='2';assert '99.00%' in page.locator('.overview-barn').filter(has=first).inner_text();first.click();assert page.locator('#daily-entry').is_visible();assert f.locator('[name=batch_id]').input_value()==members[0]['id'];assert f.locator('[name=quantity]').input_value()=='7';page.evaluate('finishForm(document.querySelector("#movement-form"))');passed('24-barn overview is one tap away; exact death/survival and correct barn/batch shortcut preserve quantity')
   page.locator('[href="#settings"]').click();page.wait_for_selector('.cohort-setting');assert page.locator('.cohort-setting').count()==12;assert page.locator('.cohort-setting:visible').count()==11
   target=page.locator('.cohort-setting').filter(has=page.locator(f'[data-member="{members[0]["id"]}"]'));assert target.locator('.member-row').count()==3
   assert len(set(page.locator('.cohort-setting').evaluate_all('(els)=>els.map(e=>e.dataset.cohortKey)')))==12;assert page.locator('#batch-workspace').bounding_box()['y']<240
   measurements['grouped_list_height_px']=round(page.locator('#batch-settings').bounding_box()['height'])
   measurements['old_table']=page.evaluate('''()=>{const h=document.createElement('div');h.className='card';h.style.cssText='position:absolute;left:-5000px;width:'+document.querySelector('#batch-workspace').offsetWidth+'px';h.innerHTML=table(['barn','batch','entryDate','entry','entryMean','entryMeanDate','status','edit'],data.batches.filter(b=>b.status==='active').map(b=>'<tr><td>'+data.barns.find(x=>x.id===b.barn_id).name+'</td><td>'+b.name+'</td><td>'+b.entry_date+'</td><td>'+fmt(b.entry_count,0)+'</td><td>'+fmt(b.entry_mean_kg)+'</td><td>'+(b.entry_mean_date||'—')+'</td><td>'+t(b.status)+'</td><td>'+recordActions('batches',b)+'</td></tr>'));document.body.append(h);const oldTable=h.querySelector('table'),r={height:Math.round(oldTable.offsetHeight),width:oldTable.offsetWidth,available:h.querySelector('.table-wrap').clientWidth};h.remove();return r;}''')
   assert measurements['grouped_list_height_px']<measurements['old_table']['height'];assert measurements['old_table']['width']>measurements['old_table']['available'];passed('same batch grouped across three barns; same name with older date stays separate; active/ended filter works')
   page.locator('#batch-search').fill('4棟');assert page.locator('.cohort-setting:visible').count()>=1;assert target.is_visible();page.locator('#batch-search').fill('no-such-batch');assert page.locator('#batch-no-match').is_visible();page.locator('#batch-search').fill('JD-SAMPLE-39');assert page.locator('.cohort-setting:visible').count()==1;page.locator('#batch-status').select_option('');assert page.locator('.cohort-setting:visible').count()==2;page.locator('#batch-status').select_option('active');page.locator('#batch-search').fill('')
   assert store.export_backup()['records']==original['records'];passed('batch/barn search and status switches perform no writes or record merging')
   target.locator(':scope > summary').click();target.locator(f'[data-edit="batches"][data-id="{members[0]["id"]}"]').click();bf=page.locator('#batch-form');assert bf.locator('[name=name]').is_hidden();assert bf.locator('[name=barn_id]').is_hidden();assert bf.locator('[name=entry_date]').is_visible();assert page.locator('#batch-editor').locator('xpath=..').get_attribute('data-cohort-key')==members[0]['name']+'|'+members[0]['entry_date'];bf.locator('[name=entry_mean_kg]').fill('23.75')
   for i in range(3):
    bf.locator('[name=entry_mean_kg]').focus();page.evaluate('async()=>await refresh()');page.select_option('#language','vi' if i%2==0 else 'zh');page.wait_for_function('()=>document.activeElement?.name==="entry_mean_kg"');assert bf.locator('[name=entry_mean_kg]').input_value()=='23.75';assert bf.get_attribute('data-edit-id')==members[0]['id']
   page.select_option('#language','zh');target.locator(f'[data-edit="batches"][data-id="{members[1]["id"]}"]').click();assert bf.get_attribute('data-edit-id')==members[0]['id'];assert '先儲存' in bf.locator('.form-error').inner_text();passed('inline editor keeps focus and draft in three language/sync rounds; switching barn cannot discard edits')
   bf.locator('button.primary').click();page.wait_for_function('()=>pending===null&&!document.querySelector("#batch-form").dataset.editId');updated=store.snapshot()['batches'];assert next(b for b in updated if b['id']==members[0]['id'])['entry_mean_kg']==23.75;assert next(b for b in updated if b['id']==members[1]['id'])['entry_mean_kg']==22.4
   target.locator(f'[data-edit="batches"][data-id="{members[1]["id"]}"]').click();bf.locator('[name=entry_count]').fill('250');bf.locator('[data-action=cancelEdit]').click();assert next(b for b in store.snapshot()['batches'] if b['id']==members[1]['id'])['entry_count']==201;passed('real server saves only selected barn; cancel leaves other barn count unchanged')
   page.locator('#new-batch').click();assert bf.is_visible();bf.locator('[name=name]').fill('unsaved-new');page.locator('#new-batch').click();assert bf.locator('[name=name]').input_value()=='unsaved-new';bf.locator('[data-action=cancelEdit]').click();assert len(store.snapshot()['batches'])==25;page.locator('#new-batch').click();assert bf.locator('[name=entry_mean_kg]').input_value()=='';assert bf.locator('[name=cohort_id]').input_value()=='';bf.locator('[name=barn_id]').select_option(members[0]['barn_id']);bf.locator('[name=name]').fill('JD-NEW');bf.locator('[name=entry_count]').fill('10');bf.locator('button.primary').click();page.wait_for_function('()=>pending===null&&!document.querySelector("#batch-form").dataset.editId&&document.querySelector("#batch-editor").hidden');assert len(store.snapshot()['batches'])==26;created=next(b for b in store.snapshot()['batches'] if b['name']=='JD-NEW');assert created['entry_count']==10 and created['entry_mean_kg'] is None;passed('new batch starts clean, repeated click retains draft, cancel is safe, and real server creates only one record')
   page.locator('nav [href="#daily"]').click();page.locator('[data-daily-view=overview]').click();unknown=page.locator('.overview-barn:has(.barn-survival details)').first;assert unknown.locator('.barn-survival summary').inner_text()=='— ⓘ';unknown.locator('summary').click();assert '可靠單棟' in unknown.inner_text();passed('source denominator remains unknown and missing reason is accessible, never an invented zero')
   cases=0
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.select_option('#language',language)
     for size in ('small','medium','large'):
      page.locator('#font-control').evaluate('(e)=>e.open=true');page.locator(f'[data-text-size={size}]').click();page.locator('#font-control').evaluate('(e)=>e.open=false')
      for tab in ('daily','stats','settings'):
       page.evaluate('async(tab)=>{location.hash=tab;setPage(tab,false);await renderCurrent()}',tab);assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+2'),(width,language,size,tab);cases+=1
       if tab=='settings':assert page.locator('#batch-settings .table-wrap').count()==0
   passed(f'{cases} realistic farm viewport/language/font combinations fit without horizontal page overflow')
   page.set_viewport_size({'width':390,'height':844});page.select_option('#language','zh');page.locator('#font-control').evaluate('(e)=>e.open=true');page.locator('[data-text-size=medium]').click();page.locator('#font-control').evaluate('(e)=>e.open=false');page.locator('[href="#settings"]').click();page.evaluate('scrollTo(0,0)');page.screenshot(path=str(root/'artifacts/compact-settings-mobile.png'),full_page=True)
   target.locator(':scope > summary').evaluate('(e)=>e.parentElement.open=true');target.locator(f'[data-edit="batches"][data-id="{members[0]["id"]}"]').click();page.locator('#batch-editor').scroll_into_view_if_needed();page.screenshot(path=str(root/'artifacts/compact-edit-mobile.png'));bf.locator('[data-action=cancelEdit]').click();page.locator('nav [href="#daily"]').click();page.locator('[data-daily-view=overview]').click();page.wait_for_timeout(400);page.screenshot(path=str(root/'artifacts/compact-overview-mobile.png'),full_page=True)
   page.locator('#logout').click();login('reader','83000012');page.locator('[href="#settings"]').click();assert page.locator('#batch-workspace').is_hidden();assert not page.locator('[data-edit=batches]:visible').count();page.locator('#password-card > summary').click();assert page.locator('#password-form').is_visible();assert page.evaluate('async()=>{const r=await fetch("/api/batches/x",{method:"PUT",headers:{"Content-Type":"application/json","X-CSRF-Token":me.csrf},body:"{}"});return r.status}')==403;passed('viewer cannot use batch management or server writes; own password remains accessible')
   page.locator('#logout').click();login('temporary','83000013');assert page.locator('#password-form').is_visible();assert page.locator('#batch-workspace').is_hidden();assert page.locator('nav a:visible').count()==1;assert store.export_backup()['users']==original['users'];assert not errors;passed('forced first password change remains usable; existing hashes retained; no uncaught JavaScript errors')
   browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/compact-browser-results.json').write_text(json.dumps({'version':VERSION,'mode':'real Chromium; isolated synthetic 24-barn farm, 25 batch records; no physical phone','passed':results,'measurements':measurements},ensure_ascii=False,indent=2));print('Completed',len(results),'compact browser scenarios')
