"""Plain-language calendar, grouped routines, correct facts and original editable records."""
import copy,json,sys,tempfile,threading,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(s):checks.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');admin=store.create_user('owner','83000011')
 def add(title,weekday=0,time='',note='',date=None):return store.mutate(admin,'work_tasks',dict(title=title,mode='once' if date else 'weekly',weekday=weekday,start_date='2026-10-19',time=time,note=note,**({'date':date} if date else {})),str(uuid.uuid4()))
 water=None
 for day in range(7):
  add('巡豬',day,'08:00');w=add('查看污水',day,'08:00');add('巡豬',day,'16:00')
  if day==0:water=w
 for day in (0,3):add('敲料桶、叫料',day)
 for day in (2,6):add('全場消毒',day)
 add('填寫肉豬紀錄表');add('例行開會',1,note='下午')
 for date,title in [('2026-10-19','南投出豬80頭'),('2026-10-20','新北出豬90頭'),('2026-10-20','驗水'),('2026-10-22','1、18棟打疫苗'),('2026-10-23','嘉義出豬80頭'),('2026-10-23','南投出豬80頭'),('2026-10-23','8、14棟秤重'),('2026-10-24','南投出豬80頭')]:add(title,date=date)
 before=store.export_backup();server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url+'/#calendar');page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_function('()=>data&&data.work_tasks.length===35');page.locator('#calendar-week').fill('2026-10-22');page.locator('#calendar-week').dispatch_event('change');page.wait_for_function("()=>document.querySelectorAll('.calendar-routine-card').length===2&&!document.querySelector('#calendar-image').disabled")
   routine=page.locator('#calendar-routine');assert routine.is_visible();assert routine.locator('h3').all_text_contents()==['上午 8:00','下午 4:00'];assert routine.locator('.calendar-task strong').all_text_contents()==['巡視豬隻','檢查污水','巡視豬隻'];assert '巡視豬隻' not in page.locator('#calendar-days').inner_text();assert page.locator('.calendar-day').count()==7;passed('daily work appears once in clear morning/afternoon cards; seven dated rows contain only their additional fixed or temporary work')
   days=page.locator('.calendar-day');assert '10/19' in days.nth(0).inner_text() and '星期一' in days.nth(0).inner_text();assert '出豬：南投 80 頭' in days.nth(0).inner_text();assert '出豬：新北 90 頭' in days.nth(1).inner_text() and '水質檢驗' in days.nth(1).inner_text();assert days.nth(1).locator('.calendar-task-time').inner_text()=='下午';assert '施打疫苗（1、18棟）' in days.nth(3).inner_text();assert all(t in days.nth(4).inner_text() for t in ['出豬：嘉義 80 頭','出豬：南投 80 頭','豬隻秤重（8、14棟）']);passed('plain-language labels preserve every shipment destination/count, vaccine/weight barn, date and the unspecified afternoon meeting time')
   page.locator('[data-calendar-manage]').click();assert page.locator('#calendar-manage').evaluate('(e)=>e.open');page.locator('[data-calendar-edit="'+water['id']+'"]').click();assert page.locator('#calendar-form [name=title]').input_value()=='查看污水' and page.locator('#calendar-form [name=time]').input_value()=='08:00';page.locator('#calendar-form [data-action=cancelEdit]').click();passed('grouped routines still lead to original editable day records; presentation wording never replaces saved input')
   facts=page.evaluate("""()=>{
    const rows=[{title:'南投出豬080頭',time:'',note:'備註保留'},{title:'1、18棟暫停打疫苗',note:'下午，等電話'},{title:'特殊工作（取消）',time:'23:15',note:'別改這段'},{title:'8、14棟秤重',date:'2026-10-23',quantity:80},{title:'例行開會',note:'下午'}],before=JSON.stringify(rows);
    return {labels:rows.map(row=>calendarPresentation.task(row)),same:before===JSON.stringify(rows),times:['00:05','08:00','12:30','16:15','23:50','25:00'].map(t=>calendarPresentation.time(t)),vi:calendarPresentation.task(rows[0],'vi')};
   }""")
   assert facts['same'];assert facts['labels'][0]=={'title':'出豬：南投 080 頭','timeLabel':'','note':'備註保留'};assert facts['labels'][1]['title']=='1、18棟暫停打疫苗' and facts['labels'][1]['note']=='下午，等電話';assert facts['labels'][2]['title']=='特殊工作（取消）' and facts['labels'][2]['note']=='別改這段';assert facts['labels'][4]['timeLabel']=='下午';assert facts['times']==['凌晨 12:05','上午 8:00','中午 12:30','下午 4:15','晚上 11:50','25:00'];assert facts['vi']['title']=='南投出豬080頭';passed('only exact known phrases are rewritten; free text, cancellation wording, notes, leading zeroes, source objects and unconfigured times stay intact')
   for width in (320,390,768,1180):
    page.set_viewport_size({'width':width,'height':900});page.evaluate("document.documentElement.dataset.textSize='large'");assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1');assert routine.is_visible();assert page.locator('#calendar-image').is_enabled()
   page.set_viewport_size({'width':390,'height':844});page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(root/'artifacts/calendar-clear-phone.png'),full_page=True);passed('new time cards and date columns fit 320/390/768/1180px with large text and reachable image export')
   with page.expect_download() as dl:page.locator('#calendar-pdf').click()
   dl.value.save_as(root/'artifacts/calendar-clear-design.pdf');assert page.locator('#calendar-preview img').count()==1;page.locator('#language').select_option('vi');page.wait_for_function("()=>document.querySelectorAll('.calendar-routine-card').length===2&&!document.querySelector('#calendar-image').disabled");assert page.locator('.calendar-routine-card h3').all_text_contents()==['08:00','16:00'];after=store.export_backup();assert after['records']==before['records'] and after['audit']==before['audit'] and after['requests']==before['requests'] and after['users']==before['users'];assert not errors,errors;passed('reworded A4 still exports as one page, Vietnamese time labels work, and no records, accounts or history are changed')
   browser.close()
 finally:server.shutdown()
(root/'artifacts/calendar-presentation-browser.json').write_text(json.dumps({'version':VERSION,'passed':checks},ensure_ascii=False,indent=2));print('ALL',len(checks),'PASSED')
