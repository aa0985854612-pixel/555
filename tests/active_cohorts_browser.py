"""Statistics lists active cohorts; history retains ended and archived sources."""
import base64,copy,json,sys,tempfile,threading,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION,encode
from app.server import Server
from legacy_fixture import workbook_fixture
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1];checks=[]
def passed(message):checks.append(message);print('PASS',message,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011');store.create_user('reader','83000012','viewer')
 def add(kind,**body):return store.mutate(owner,kind,body,str(uuid.uuid4()))
 def batch(number,name,on,status='active'):
  barn=add('barns',name=f'{number}棟')
  return add('batches',barn_id=barn['id'],name=name,entry_date=on,entry_count=100,entry_age_days=71,status=status)
 a=batch(9,'JD-CURRENT','2026-06-12');b=batch(23,'JD-CURRENT','2026-06-12','ended');old=batch(10,'JD-SAME','2025-01-01','ended');new=batch(24,'JD-SAME','2026-10-01')
 add('movements',batch_id=a['id'],date='2026-10-13',type='death',quantity=2);add('movements',batch_id=b['id'],date='2026-10-14',type='death',quantity=3)
 store.import_workbook(owner,{'filename':'synthetic.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'},str(uuid.uuid4()))
 db=store.connect();book=db.execute("SELECT id,data FROM records WHERE kind='workbooks'").fetchone();body=json.loads(book['data']);archive=copy.deepcopy(body['report']['rows'][0]);archive['name']='JD-ARCHIVED';archive['entry_date']='2024-12-01';body['report']['archive_rows']=[archive];db.execute('UPDATE records SET data=? WHERE id=?',(encode(body),book['id']));db.commit();db.close();original=store.export_backup()
 server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(name,pw):
    page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(pw);page.locator('#login-form button').click();page.wait_for_function('()=>data&&data.batches.length===6')
   def options(form,name):return page.locator(f'#{form} [name={name}] option').evaluate_all('(es)=>es.map(e=>e.value).filter(Boolean)')
   page.goto(url);login('owner','83000011');page.locator('nav [href="#stats"]').click();page.wait_for_selector('.period-total');f=page.locator('#stats-filter');f.locator('[name=scope_type]').select_option('cohort')
   assert set(options('stats-filter','cohort'))=={'JD-CURRENT|2026-06-12','JD-SAME|2026-10-01','JD-TEST|2026-09-09'};assert '歷史舊表' not in f.locator('[name=cohort]').inner_text();passed('stats dropdown includes only active cohorts, hides archive and fully ended cohorts, and distinguishes identical names by entry date')
   f.locator('[name=cohort]').select_option('JD-CURRENT|2026-06-12');page.wait_for_function('()=>document.querySelector(".death-hero > strong")?.textContent.trim().startsWith("5 ")');assert all(n in f.locator('[name=cohort] option:checked').text_content() for n in ('9棟','23棟'));assert '23棟：3' in page.locator('.period-barns').inner_text();passed('a partially ended cohort stays selectable with all member barns and all five cumulative deaths')
   f.locator('[name=scope_type]').select_option('barn');assert old['id'] not in options('stats-filter','batch_id');assert b['id'] not in options('stats-filter','batch_id');assert a['id'] in options('stats-filter','batch_id');passed('single-barn statistics dropdown also excludes ended batches')
   page.locator('nav [href="#history"]').click();hf=page.locator('#history-filter');hf.locator('[name=scope_type]').select_option('cohort');assert 'JD-ARCHIVED|2024-12-01' in options('history-filter','cohort');assert 'JD-SAME|2025-01-01' in options('history-filter','cohort');hf.locator('[name=cohort]').select_option('JD-ARCHIVED|2024-12-01');hf.locator('[name=from]').fill('2024-12-01');hf.locator('[name=to]').fill('2026-10-18');hf.locator('[name=type]').select_option('death');hf.locator('button').first.click();page.wait_for_function('()=>document.querySelectorAll("#history-results tbody tr").length===3');q=page.evaluate('query(document.querySelector("#history-filter"))');rows=page.request.get(url+'/api/movements?'+q).json();assert sum(r['quantity'] for r in rows)==4;assert all(r.get('archive') for r in rows);passed('archived and ended batches remain available in history, with archived death details intact')
   page.select_option('#language','vi');assert len(options('stats-filter','cohort'))==3;assert len(options('history-filter','cohort'))==5;page.select_option('#language','zh');page.reload();page.wait_for_function('()=>data&&data.batches.length===6');assert len(options('stats-filter','cohort'))==3;assert 'JD-ARCHIVED|2024-12-01' not in options('stats-filter','cohort');assert page.locator('#stats-filter [name=from]').input_value()=='';assert page.locator('#history-filter [name=cohort]').input_value()=='JD-ARCHIVED|2024-12-01';passed('language changes and reloading with a saved archived filter do not restore old batches to statistics')
   # Exercise normal snapshot refresh after a cohort's last active member ends.
   store.mutate(owner,'batches',a|{'status':'ended'},str(uuid.uuid4()),a['id'])
   page.evaluate('async()=>await refresh({render:false})');assert 'JD-CURRENT|2026-06-12' not in options('stats-filter','cohort');assert 'JD-CURRENT|2026-06-12' in options('history-filter','cohort');passed('ending the last active member removes its cohort on refresh while preserving history')
   page.locator('#logout').click();login('reader','83000012');assert set(options('stats-filter','cohort'))=={'JD-SAME|2026-10-01','JD-TEST|2026-09-09'};assert store.export_backup()['users']==original['users'];now=store.export_backup()['records'];assert [r for r in now if r['id']!=a['id']]==[r for r in original['records'] if r['id']!=a['id']];assert not errors,errors;passed('viewer receives the same active options; queries preserve source records, counts and accounts');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/active-cohorts-browser-results.json').write_text(json.dumps({'version':VERSION,'checks':checks},ensure_ascii=False,indent=2));print('Completed',len(checks),'active cohort browser scenarios')
