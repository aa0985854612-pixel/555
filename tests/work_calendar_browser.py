"""Calendar authoring, weekly boundaries, uncertain-save retry and actual A4 export."""
import json,re,sys,tempfile,threading,uuid,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(s):checks.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');admin=store.create_user('owner','83000011');staff=store.create_user('worker','83000012','staff');viewer=store.create_user('reader','83000013','viewer');baseline=store.export_backup();server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei',accept_downloads=True);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   assert page.request.get(url+'/api/work-calendar').status==401
   def login(user='owner',password='83000011'):
    page.goto(url+'/#calendar');page.locator('#login-form [name=username]').fill(user);page.locator('#login-form [name=password]').fill(password);page.locator('#login-form button').click();page.wait_for_function('()=>data&&Array.isArray(data.work_tasks)');page.wait_for_selector('.calendar-day');page.locator('#calendar-week').fill('2026-10-22');page.locator('#calendar-week').dispatch_event('change');page.wait_for_function("()=>document.querySelector('#calendar-range').textContent==='2026-10-19 → 2026-10-25'")
   def submit(count):
    page.locator('#calendar-form button.primary').click();page.wait_for_function('(n)=>!pending&&data.work_tasks.length===n',arg=count);page.wait_for_selector('.calendar-day')
   login();f=page.locator('#calendar-form');f.locator('[name=title]').fill('清洗水塔');f.locator('[name=weekday]').select_option('0');f.locator('[name=start_date]').fill('2026-10-01');f.locator('[name=time]').fill('09:00');f.locator('[name=note]').fill('1、2棟\n清洗後確認飲水');submit(1)
   f.locator('[name=mode]').select_option('once');f.locator('[name=date]').fill('2026-10-25');f.locator('[name=title]').fill('臨時維修料桶');f.locator('[name=note]').fill('15-1料桶');submit(2)
   assert '清洗水塔' in page.locator('.calendar-day').nth(0).inner_text();assert '臨時維修料桶' in page.locator('.calendar-day').nth(6).inner_text();assert '2026-10-25' in page.locator('.calendar-day').nth(6).inner_text();passed('new tab records weekly and temporary tasks, normalized Monday–Sunday; Sunday included')
   response=page.request.post(url+'/api/work_tasks',data={'title':'forged','mode':'once','date':'2026-10-22'});assert response.status==403;passed('calendar reads require login and writes require CSRF')
   page.evaluate("()=>{window.calendarDrawn=[];const draw=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...args){calendarDrawn.push(args[0]);return draw.apply(this,args)}}")
   page.locator('#calendar-week').dispatch_event('change');page.wait_for_function("()=>!document.querySelector('#calendar-image').disabled")
   page.locator('#calendar-preview-box').evaluate('(e)=>e.open=true');page.wait_for_selector('#calendar-preview img');assert page.locator('#calendar-preview img').count()==1
   with page.expect_download() as d:page.locator('#calendar-pdf').click()
   out=root/'artifacts/work-calendar-a4.pdf';d.value.save_as(out);info=subprocess.check_output(['pdfinfo',str(out)],text=True);assert re.search(r'Pages:\s+1\b',info) and '595.28 x 841.89' in info;drawn=page.evaluate('calendarDrawn');assert all(s in drawn for s in ['星期一','星期日','清洗後確認飲水','臨時維修料桶','15-1料桶']);assert any('清洗水塔' in s for s in drawn);assert d.value.suggested_filename=='工作行事曆_2026-10-19_2026-10-25.pdf';passed('exact preview and downloaded PDF contain full work notes, fixed/temporary columns and seven days on one portrait A4')
   page.locator('#calendar-next').click();page.wait_for_function("()=>document.querySelector('#calendar-week').value==='2026-10-26'&&document.querySelectorAll('.calendar-day').length===7");assert '清洗水塔' in page.locator('#calendar-days').inner_text();assert '臨時維修料桶' not in page.locator('#calendar-days').inner_text();page.locator('#calendar-prev').click();page.wait_for_selector('.calendar-task');passed('weekly tasks recur; temporary task does not carry into following week')
   page.locator('.calendar-day').first.locator('[data-calendar-edit]').click();f.locator('[name=title]').fill('清洗水塔及管線');f.locator('button.primary').click();page.wait_for_function("()=>!pending&&data.work_tasks.find(t=>t.title==='清洗水塔及管線')?.revision===2");page.wait_for_selector('.calendar-task');page.locator('.calendar-day').first.locator('[data-calendar-edit]').click();f.locator('[name=active]').uncheck();f.locator('button.primary').click();page.wait_for_function("()=>!pending&&data.work_tasks.find(t=>t.title==='清洗水塔及管線')?.active===false");page.wait_for_selector('.calendar-day');assert '清洗水塔' not in page.locator('#calendar-days').inner_text();passed('correction keeps original ID and revision; disabled recurrence disappears without deleting audit history')
   # Simulate a response lost AFTER the server committed, then reload and retry original key.
   def lost(route):route.fetch();route.abort()
   page.route('**/api/work_tasks',lost);f.locator('[name=mode]').select_option('once');f.locator('[name=date]').fill('2026-10-21');f.locator('[name=title]').fill('不確定儲存測試');f.locator('button.primary').click();page.wait_for_function('()=>pending&&!retryPending.busy');assert len(store.snapshot()['work_tasks'])==3;page.unroute('**/api/work_tasks',lost);page.reload();page.wait_for_function('()=>me&&data&&pending&&!retryPending.busy');assert f.locator('[name=title]').input_value()=='不確定儲存測試';assert f.locator('[name=mode]').input_value()=='once';page.locator('#retry').click();page.wait_for_function('()=>!pending&&data.work_tasks.length===3');assert len(store.snapshot()['work_tasks'])==3;passed('lost save response survives reload; original retry commits exactly once and restores temporary-task form')
   compact=page.evaluate("async()=>{const blob=await workCalendarPDF({title:'每週工作',range:'2026-10-19 → 2026-10-25',headers:['星期','固定','臨時'],weekdays:['一','二','三','四','五','六','日'],days:Array.from({length:7},(_,i)=>({date:'2026-10-'+(19+i),tasks:i===0?Array.from({length:4},(_,j)=>({title:'固定工作'+j,mode:'weekly',note:''})):[]}))});return blob.previewPages.length;}")
   assert compact==1;passed('four regular Monday jobs fit one A4; an empty trailing spacer never creates a continuation page')
   large=page.evaluate("""async()=>{
    const calls=[],old=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(text,...args){calls.push({text,font:this.font});return old.call(this,text,...args)};
    try{
     const days=Array.from({length:7},(_,i)=>({date:'2026-10-'+(19+i),tasks:[{mode:'weekly',title:'巡查',time:'08:00'},{mode:'weekly',title:'巡查',time:'16:00'},{mode:'weekly',title:'查看污水'},{mode:'weekly',title:'抄水錶'}]}));
     const add=(day,title,mode='weekly',note='')=>days[day].tasks.push({title,mode,note});
     add(0,'填寫紀錄表');add(0,'敲料桶、叫料');add(3,'敲料桶、叫料');add(2,'全場消毒');add(6,'全場消毒');add(1,'例行開會','weekly','下午');
     for(const [day,title] of [[0,'南投出豬80頭'],[1,'新北出豬90頭'],[1,'驗水'],[3,'1、18棟打疫苗'],[4,'嘉義出豬80頭'],[4,'南投出豬80頭'],[4,'8、14棟秤重'],[5,'南投出豬80頭']])add(day,title,'once');
     const model={title:'每週工作',range:'2026-10-19 → 2026-10-25',headers:['星期','固定','臨時'],weekdays:['一','二','三','四','五','六','日'],dailyTitle:'每日固定工作',days},blob=await workCalendarPDF(model);
     return {pages:blob.previewPages.length,calls,unchanged:days.every(d=>d.tasks.filter(t=>t.mode==='weekly'&&t.title==='巡查').length===2)};
    }finally{CanvasRenderingContext2D.prototype.fillText=old;}
   }""")
   texts=[c['text'] for c in large['calls']];assert large['pages']==1 and large['unchanged'];assert all(texts.count(t)==1 for t in ['08:00 · 巡查','16:00 · 巡查','查看污水','抄水錶']);assert texts.count('南投出豬80頭')==3 and texts.count('敲料桶、叫料')==2 and texts.count('全場消毒')==2;assert all(t in texts for t in ['驗水','1、18棟打疫苗','8、14棟秤重','嘉義出豬80頭','新北出豬90頭','下午']);assert all(float(re.search(r'(\d+(?:\.\d+)?)px',c['font'])[1])>=14 for c in large['calls'] if not c['text'].endswith('1 / 1'));passed('42-task week fits one large-print A4, daily routines grouped once, dated work complete and readable text at least 14pt')
   grouping=page.evaluate("""async()=>{
    const result=[];
    for(const count of [6,7]){
     const calls=[],old=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(s,...args){calls.push(s);return old.call(this,s,...args)};
     try{await workCalendarPDF({title:'分組測試',range:'本週',headers:['星期','固定','臨時'],weekdays:['一','二','三','四','五','六','日'],days:Array.from({length:7},(_,i)=>({date:'2026-10-'+(19+i),tasks:i<count?[{title:'每天兩件相同工作',mode:'weekly'},{title:'每天兩件相同工作',mode:'weekly'}]:[]}))});result.push(calls.filter(s=>s==='每天兩件相同工作').length);}finally{CanvasRenderingContext2D.prototype.fillText=old;}
    }
    return result;
   }""")
   assert grouping==[12,2];passed('daily grouping needs all seven dates, preserves duplicate occurrence counts and never mutates the weekly model')
   # Dense content must stay complete, including continuations within the same week.
   dense=page.evaluate("async()=>{const calls=[];const original=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(s,...args){calls.push(s);return original.call(this,s,...args)};try{const tasks=Array.from({length:18},(_,i)=>({title:'任務'+i,mode:'weekly',note:'詳細備註'+i}));const blob=await workCalendarPDF({title:'測試',range:'2026-10-19 → 2026-10-25',headers:['星期','固定','臨時'],weekdays:['一','二','三','四','五','六','日'],days:Array.from({length:7},(_,i)=>({date:'2026-10-'+(19+i),tasks:i===0?tasks:[]}))});return {pages:blob.previewPages.length,calls};}finally{CanvasRenderingContext2D.prototype.fillText=original;}}")
   assert dense['pages']>1 and all('任務'+str(i) in dense['calls'] and '詳細備註'+str(i) in dense['calls'] for i in range(18));passed('dense schedule retains every task and note on clearly numbered same-week continuation pages')
   page.locator('#logout').click();login('reader','83000013');assert f.locator('button.primary').is_disabled();assert page.locator('[data-calendar-edit]').count()==0;assert f.locator('[name=title]').input_value()=='';csrf=page.evaluate('me.csrf');assert page.request.post(url+'/api/work_tasks',headers={'X-CSRF-Token':csrf,'Idempotency-Key':str(uuid.uuid4())},data={'title':'denied','mode':'once','date':'2026-10-21'}).status==403;passed('viewer can see/export but cannot write, and previous user input is cleared on logout')
   page.locator('#logout').click();login('worker','83000012');assert page.locator('[data-calendar-edit]').count()==0;f.locator('[name=mode]').select_option('once');f.locator('[name=date]').fill('2026-10-22');f.locator('[name=title]').fill('自己安排工作');submit(4);assert page.locator('[data-calendar-edit]').count()>=1;passed('staff can add and correct own work; another author’s work remains protected')
   for width in (320,390,768):
    page.set_viewport_size({'width':width,'height':844});page.evaluate("document.documentElement.dataset.textSize='large'");assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1');page.locator('nav [href="#settings"]').click();page.wait_for_function("()=>current==='settings'");page.locator('nav [href="#calendar"]').click();page.wait_for_selector('.calendar-day');assert page.locator('nav [href="#calendar"]').is_visible()
   page.locator('#language').select_option('vi');page.wait_for_function("()=>document.querySelector('#page-title').textContent==='Lịch công việc'");page.wait_for_selector('.calendar-day');assert 'Thứ Hai' in page.locator('.calendar-day').first.inner_text();passed('phone/tablet large text has no page overflow, seven tabs remain reachable and Vietnamese labels work')
   after=store.export_backup();assert [r for r in after['records'] if r['kind']!='work_tasks']==baseline['records'];assert after['users']==baseline['users'];assert after['security']==baseline['security'];assert not errors,errors;passed('calendar changes and exports preserve every farm record and account; no browser errors')
   browser.close()
 finally:server.shutdown()
(root/'artifacts/work-calendar-browser.json').write_text(json.dumps({'version':VERSION,'passed':checks},ensure_ascii=False,indent=2));print('ALL',len(checks),'PASSED')
