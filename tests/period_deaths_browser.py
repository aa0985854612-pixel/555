"""Compact period deaths: real Chromium/HTTP, isolated synthetic 24-barn farm."""
import csv,io,json,sys,tempfile,threading,uuid
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[];measurements={}
def passed(s):checks.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011');store.create_user('reader','83000012','viewer')
 def add(kind,**body):return store.mutate(owner,kind,body,str(uuid.uuid4()))
 groups=[[11,21],[9,23],[12,24],[13,22],[8,14],[5,6,7],[19,20],[2,3,4],[1,18],[10,16,17],[15]];weeks=[26,23,22,18,16,13,12,9,8,7,6];quantities=[4,1,0,1,1,1,0,0,0,0,0];batches=[];keys=[]
 for i,(numbers,week,count) in enumerate(zip(groups,weeks,quantities)):
  members=[];on=str(date(2026,10,15)-timedelta(days=week*7-35));keys.append(f'JD-DEMO-{30-i}|{on}')
  for j,n in enumerate(numbers):
   barn=add('barns',name=f'{n}棟',group='A' if j==0 else 'B');b=add('batches',barn_id=barn['id'],name=f'JD-DEMO-{30-i}',entry_date=on,entry_count=100,entry_age_days=35,status='ended' if n==21 else 'active');members.append(b)
  if count:add('movements',batch_id=members[0]['id'],date='2026-10-15',type='death',quantity=count)
  batches.append(members)
 add('movements',batch_id=batches[0][1]['id'],date='2026-10-14',type='death',quantity=3)
 add('movements',batch_id=batches[0][0]['id'],date='2026-10-15',type='sale',quantity=1)
 original=store.export_backup();server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(user,pw):
    page.locator('#login-form [name=username]').fill(user);page.locator('#login-form [name=password]').fill(pw);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   def submit():
    with page.expect_response(lambda r:'/api/statistics?' in r.url and r.request.method=='GET') as response:page.locator('#stats-filter button').first.click()
    s=response.value.json();page.wait_for_function('(s)=>document.querySelector(".death-range")?.textContent===s.death_summary.from+" → "+s.death_summary.to',arg=s);return s
   def stats():page.locator('nav [href="#stats"]').click();page.wait_for_selector('.period-total')
   page.goto(url);login('owner','83000011');stats();f=page.locator('#stats-filter');f.locator('[name=from]').fill('2026-10-15');f.locator('[name=to]').fill('2026-10-15');s=submit();page.wait_for_function('()=>document.querySelector(".death-hero strong").textContent.includes("8")')
   assert page.locator('.period-item').count()==5;assert page.locator('.period-item:visible').count()==5;assert page.locator('.period-item .period-age').all_inner_texts()==[str(w)+'W' for w,n in zip(weeks,quantities) if n];assert page.locator('.period-count.is-zero:visible').count()==0
   top=page.locator('.period-item').first;assert '11、21棟' in top.locator('.period-row-title').inner_text();assert '11棟：4' in top.inner_text() and '21棟：0' not in top.locator('.period-barns').inner_text();assert top.locator('.period-count').inner_text().startswith('4');assert 'JD-DEMO-30' in top.locator('.period-batch').inner_text();assert len(s['death_groups'])==11;passed('only five positive-death rows: total still 8, zero groups and barn subtotals hidden, cohort membership and age order retained')
   # A changed, unsubmitted date must not change the drill-down of old results.
   f.locator('[name=from]').fill('2026-10-14');top.locator('.period-count').click();page.wait_for_function('()=>current==="history"');hf=page.locator('#history-filter');assert hf.locator('[name=from]').input_value()=='2026-10-15';assert hf.locator('[name=to]').input_value()=='2026-10-15';assert hf.locator('[name=cohort]').input_value()==keys[0];assert hf.locator('[name=type]').input_value()=='death';page.wait_for_function('()=>document.querySelectorAll("#history-results tbody tr").length===1')
   q=page.evaluate('query(document.querySelector("#history-filter"))');r=page.request.get(url+'/api/export?kind=movements&'+q);csvrows=list(csv.DictReader(io.StringIO(r.text().lstrip('\ufeff'))));assert sum(int(r['quantity']) for r in csvrows)==4;assert {r['date'] for r in csvrows}=={'2026-10-15'};passed('tap period total preserves displayed dates despite unsent changes; history and CSV match exact death count')
   stats();f.locator('[name=scope_type]').select_option('all');f.locator('[name=from]').fill('2026-10-14');f.locator('[name=to]').fill('2026-10-15');submit();page.wait_for_function('()=>document.querySelector(".death-hero strong").textContent.includes("11")');top=page.locator('.period-item').first;assert top.locator('.period-age').inner_text()=='26W';top.locator('.period-barns button').nth(1).click();page.wait_for_function('()=>current==="history"');assert hf.locator('[name=barn_id]').input_value()==batches[0][1]['barn_id'];assert hf.locator('[name=batch_id]').input_value()==batches[0][1]['id'];page.wait_for_function('()=>document.querySelectorAll("#history-results tbody tr").length===1');q=page.evaluate('query(document.querySelector("#history-filter"))');rows=page.request.get(url+'/api/movements?'+q).json();assert len(rows)==1 and rows[0]['quantity']==3;passed('date range includes both boundary days; per-barn drill-down keeps cohort, barn and exact batch including ended barn')
   stats();f.locator('[name=scope_type]').select_option('group');f.locator('[name=group]').select_option('B');s=submit();assert s['death_summary']['total']==3;assert s['death_groups'][0]['period_deaths']==3;page.wait_for_function('()=>document.querySelector(".death-hero strong").textContent.includes("3")');page.locator('.period-item').first.locator('.period-row').click();page.wait_for_function('()=>current==="history"');assert hf.locator('[name=group]').input_value()=='B';q=page.evaluate('query(document.querySelector("#history-filter"))');rows=page.request.get(url+'/api/movements?'+q).json();assert sum(r['quantity'] for r in rows)==3;passed('group restriction stays attached when opening the cohort; another group cannot inflate history')
   stats();f.locator('[name=scope_type]').select_option('all');f.locator('[name=from]').fill('2026-10-15');f.locator('[name=to]').fill('2026-10-15');submit()
   f.locator('[name=from]').fill('2026-10-16');f.locator('[name=to]').fill('2026-10-16');submit();page.wait_for_selector('.period-empty');assert page.locator('.period-item').count()==0;assert page.locator('.period-empty').inner_text()=='查詢期間沒有死亡紀錄';assert page.locator('.death-hero > strong').inner_text().startswith('0');page.select_option('#language','vi');page.wait_for_function('()=>document.querySelector(".period-empty")?.textContent==="Không có bản ghi heo chết trong kỳ"');page.select_option('#language','zh');passed('confirmed zero-death period has explicit bilingual empty state and zero total without hiding or deleting data')
   f.locator('[name=from]').fill('2026-10-15');f.locator('[name=to]').fill('2026-10-15');submit();page.wait_for_selector('.period-item')
   cases=0
   for width in (320,375,390,430,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.select_option('#language',language);page.wait_for_selector('.period-item')
     for size in ('small','medium','large'):
      page.locator('#font-control').evaluate('(e)=>e.open=true');page.locator(f'#font-control [data-text-size={size}]').click();page.locator('#font-control').evaluate('(e)=>e.open=false');assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+2'),(width,language,size)
      assert page.locator('.period-item:visible').count()==5
      for box in page.locator('.period-count').all():
       b=box.bounding_box();assert b['x']>=0 and b['x']+b['width']<=width+1
      assert page.locator('.period-row').first.bounding_box()['height']>=44;cases+=1
   passed(f'{cases} mobile/tablet/desktop, two-language and three-font layouts fit with zero rows hidden and touch targets')
   page.set_viewport_size({'width':390,'height':844});page.select_option('#language','zh');page.locator('#font-control').evaluate('(e)=>e.open=true');page.locator('#font-control [data-text-size=medium]').click();page.locator('#font-control').evaluate('(e)=>e.open=false');page.wait_for_selector('.period-item');page.locator('.period-deaths').scroll_into_view_if_needed();page.evaluate('scrollTo(0,document.querySelector(".period-deaths").getBoundingClientRect().top+scrollY-document.querySelector("header").offsetHeight-8)');measurements['row_height_px']=round(page.locator('.period-item').first.bounding_box()['height']);measurements['list_height_px']=round(page.locator('.period-list').bounding_box()['height']);page.screenshot(path=str(root/'artifacts/period-deaths-mobile.png'));page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path=str(root/'artifacts/period-deaths-desktop.png'),full_page=True)
   # Explicit API simulation exercises unknown rendering; numbers are not written.
   page.evaluate('async()=>{const s=await api("/api/statistics?from=2026-10-15&to=2026-10-15");s.death_summary.total=null;s.death_groups[0].period_deaths=null;s.death_groups[0].barns[0].period_deaths=null;s.death_groups[0].barns[0].barn_id=null;s.death_groups[0].barns[0].name="未建檔棟舍";document.querySelector("#stats-results").innerHTML=statHTML(s)}');assert page.locator('.death-hero > strong').inner_text().startswith('—');assert page.locator('.period-item').first.locator('.period-count').inner_text().startswith('—');assert '資料不足' in page.locator('.period-item').first.inner_text();assert '未建檔棟舍' in page.locator('.period-item').first.locator('.period-barns > span').inner_text();assert page.locator('.period-item').first.locator('.period-barns button').count()==0;passed('simulated incomplete source displays unknown and known subtotal instead of false zero')
   page.locator('#logout').click();login('reader','83000012');stats();f.locator('[name=scope_type]').select_option('all');f.locator('[name=from]').fill('2026-10-15');f.locator('[name=to]').fill('2026-10-15');submit();page.wait_for_function('()=>document.querySelector(".death-hero strong").textContent.includes("8")');assert page.locator('.period-item:visible').count()==5;assert store.export_backup()['records']==original['records'];assert store.export_backup()['users']==original['users'];assert not errors;passed('viewer can query and drill down; all existing records and password hashes unchanged; no JavaScript errors');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/period-deaths-browser-results.json').write_text(json.dumps({'version':VERSION,'mode':'real Chromium/HTTP, isolated synthetic farm; viewport/touch simulation, not physical iPhone/Safari','checks':checks,'measurements':measurements},ensure_ascii=False,indent=2));print('Completed',len(checks),'period browser scenarios')
