"""Cumulative normal sales in the farm overview, with real HTTP and Chromium."""
import base64,json,sys,tempfile,threading,uuid
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from legacy_fixture import workbook_fixture
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(message):checks.append(message);print('PASS',message,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011');store.create_user('reader','83000012','viewer')
 def add(kind,**body):return store.mutate(owner,kind,body,str(uuid.uuid4()))
 barn=add('barns',name='15棟');second=add('barns',name='21棟')
 a=add('batches',barn_id=barn['id'],name='JD-CURRENT',entry_date='2026-10-09',entry_count=1052,entry_age_days=71,status='active')
 b=add('batches',barn_id=second['id'],name='JD-CURRENT',entry_date='2026-10-09',entry_count=318,entry_age_days=71,status='active')
 large_barn=add('barns',name='7棟');large=add('batches',barn_id=large_barn['id'],name='JD-FOUR-DIGIT',entry_date='2026-10-09',entry_count=2052,entry_age_days=71,status='active');add('movements',batch_id=large['id'],date='2026-10-18',type='sale',quantity=1000)
 old=add('batches',barn_id=barn['id'],name='JD-OLD',entry_date='2025-01-01',entry_count=100,entry_age_days=71,status='ended')
 for batch,on,kind,n in [(a,'2026-10-10','sale',100),(a,'2026-10-18','sale',30),(a,'2026-10-19','sale',2),(a,'2026-10-20','sale',12),(a,'2026-10-18','cull',4),(a,'2026-10-18','death',1),(old,'2025-02-01','sale',99)]:
  add('movements',batch_id=batch['id'],date=on,type=kind,quantity=n)
 store.import_workbook(owner,{'filename':'synthetic.xlsx','base64':base64.b64encode(workbook_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/50\n2/49'},str(uuid.uuid4()))
 original=store.export_backup();server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.clock.install(time=datetime(2026,10,19,6,tzinfo=timezone.utc))
   def login(name,pw):
    page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(pw);page.locator('#login-form button').click();page.wait_for_selector('.overview-sold',state='attached');page.locator('[data-daily-view=overview]').click()
   def row(batch):return page.locator('.overview-barn').filter(has=page.locator(f'[data-add-batch="{batch["id"]}"]'))
   page.goto(url);login('owner','83000011');assert row(a).locator('.overview-sold').inner_text()=='132';assert row(a).locator('.overview-dead').inner_text()=='1';assert row(a).locator('.overview-heads').inner_text()=='915';assert row(b).locator('.overview-sold').inner_text()=='0';assert row(large).locator('.overview-heads').inner_text()=='1,052';assert row(large).locator('.overview-sold').inner_text()=='1,000';assert page.locator('.overview-columns').first.locator('span').all_inner_texts()==['棟舍','存欄','累計死','累計出豬','育成率'];passed('five aligned overview columns show 132 normal sales from entry through today, excluding culls, deaths, future sales and the old batch in the same barn; true zero shows 0')
   source=page.locator('.overview-cohort').filter(has=page.locator('[data-cohort-total="JD-TEST|2026-09-09"]'));assert '—' in source.locator('.overview-sold').all_inner_texts();passed('unknown per-barn imported sale totals remain unknown rather than fabricated zero')
   assert '出豬只計正常出豬' in page.locator('#overview-hint').inner_text();assert store.export_backup()['records']==original['records'];passed('overview explains the normal-sale basis and reading it leaves original records intact')
   cases=0
   for width in (320,375,390,430,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.select_option('#language',language)
     page.wait_for_function('(label)=>document.querySelector(".overview-columns")?.textContent.includes(label)',arg='累計出豬' if language=='zh' else 'Xuất bán lũy kế')
     for size in ('small','medium','large'):
      page.locator('#font-control').evaluate('(e)=>e.open=true');page.locator(f'[data-text-size={size}]').click();page.locator('#font-control').evaluate('(e)=>e.open=false');assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+2'),(width,language,size)
      fit=page.locator('.overview-barn').evaluate_all('(rows)=>rows.every(row=>{const cells=[...row.children];return cells.every((cell,i)=>{const r=cell.getBoundingClientRect();if(r.right>row.getBoundingClientRect().right+1)return false;if(i===0||i===cells.length-1)return true;return cell.scrollWidth<=cell.clientWidth+1})})');assert fit,(width,language,size,'numeric cells overflow')
      assert row(a).locator('.overview-sold').inner_text()=='132';cases+=1
   passed(f'{cases} phone/tablet/desktop, two-language and three-font layouts keep all five columns readable without numeric overflow')
   page.set_viewport_size({'width':390,'height':844});page.select_option('#language','zh');page.locator('#font-control').evaluate('(e)=>e.open=true');page.locator('[data-text-size=medium]').click();page.locator('#font-control').evaluate('(e)=>e.open=false');row(a).scroll_into_view_if_needed();page.screenshot(path=str(root/'artifacts/overview-sales-mobile.png'))
   row(a).locator('.overview-barn-link').click();page.wait_for_selector('#movement-form:visible');f=page.locator('#movement-form');assert f.locator('[name=batch_id]').input_value()==a['id'];f.locator('[name=date]').fill('2026-10-19');f.locator('[name=type]').select_option('sale');f.locator('[name=quantity]').fill('5');f.locator('button.primary').click();page.wait_for_function('()=>pending===null');page.wait_for_function('(id)=>document.querySelector(`[data-add-batch="${id}"]`)?.closest(".overview-barn").querySelector(".overview-sold").textContent==="137"',arg=a['id']);assert row(a).locator('.overview-heads').inner_text()=='910';passed('saving a real normal sale refreshes cumulative sales and stock together, and the barn shortcut still opens the correct batch')
   after=store.export_backup();assert len(after['records'])==len(original['records'])+1;assert all(r in after['records'] for r in original['records']);page.locator('#logout').click();login('reader','83000012');assert row(a).locator('.overview-sold').inner_text()=='137';assert page.locator('#movement-form .primary').is_disabled();assert store.export_backup()['records']==after['records'];assert store.export_backup()['users']==original['users'];assert not errors,errors;passed('viewer sees the same saved totals; existing source records and accounts remain unchanged, with no JavaScript errors');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/overview-sales-browser-results.json').write_text(json.dumps({'version':VERSION,'checks':checks},ensure_ascii=False,indent=2));print('Completed',len(checks),'overview sale browser scenarios')
