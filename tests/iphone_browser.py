"""iPhone-size geometry and daily workflow. Engine and OS limits are explicit."""
import argparse,json,sys,tempfile,threading,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright,Error

parser=argparse.ArgumentParser();parser.add_argument('--engine',choices=('chromium','webkit'),default='chromium');parser.add_argument('--baseline-css',type=Path);args=parser.parse_args()
root=Path(__file__).resolve().parents[1];checks=[];measurements={};engine=args.engine
def passed(s):checks.append(s);print('PASS',s,flush=True)
result={'version':VERSION,'engine':engine,'mode':'isolated synthetic farm; iPhone viewport/touch simulation; no physical iPhone','checks':checks,'measurements':measurements,'native_ios_picker_tested':False}
def save_result():
 (root/'artifacts').mkdir(exist_ok=True);(root/f'artifacts/iphone-{engine}-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011');store.create_user('reader','83000012','viewer')
 def add(kind,**body):return store.mutate(owner,kind,body,str(uuid.uuid4()))
 barn=add('barns',name='19棟',group='');batch=add('batches',barn_id=barn['id'],name='JD-115-40.41',entry_date='2026-10-01',entry_count=100,entry_age_days=70,status='active',entry_mean_kg=22.4)
 original=store.export_backup();server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   try:browser=getattr(p,engine).launch(**({'executable_path':'/usr/bin/chromium','args':['--no-sandbox']} if engine=='chromium' else {}))
   except Error:
    result.update(status='blocked',reason='Requested browser engine is not installed or cannot start; no scenarios executed.');save_result();print('BLOCKED',engine,'not available');raise SystemExit(2)
   context=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=3,is_mobile=True,has_touch=True,locale='zh-TW',timezone_id='Asia/Taipei')
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(f'http://127.0.0.1:{server.server_port}')
   def login(name,password):
    page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(password);page.locator('#login-form button').tap();page.wait_for_selector('#workspace:not([hidden])');page.wait_for_selector('#barns .overview-cohort',state='attached')
   login('owner','83000011');f=page.locator('#movement-form');date_input=f.locator('[name=date]')
   def date_geometry():return date_input.evaluate('''e=>{const s=getComputedStyle(e),c=document.createElement('canvas').getContext('2d');c.font=s.fontWeight+' '+s.fontSize+' '+s.fontFamily;const r=e.getBoundingClientRect(),p=e.closest('label').getBoundingClientRect();return {width:r.width,labelWidth:p.width,chineseDateRequired:Math.ceil(c.measureText('2026年10月16日').width+parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)+24),right:r.right,labelRight:p.right};}''')
   if args.baseline_css:
    page.route('**/api/before-iphone.css',lambda route:route.fulfill(status=200,content_type='text/css',body=args.baseline_css.read_text()));old=page.add_style_tag(url=f'http://127.0.0.1:{server.server_port}/api/before-iphone.css');page.locator('link[rel=stylesheet][href*="/style.css"]').evaluate_all('(els)=>els.forEach(e=>e.disabled=true)');measurements['before']=date_geometry();page.locator('link[rel=stylesheet][href*="/style.css"]').evaluate_all('(els)=>els.forEach(e=>e.disabled=false)');old.evaluate('(e)=>e.remove()')
   measurements['after']=date_geometry();d=measurements['after'];assert d['width']>=d['chineseDateRequired'];assert abs(d['width']-d['labelWidth'])<=1
   if 'before' in measurements:assert measurements['before']['width']<measurements['before']['chineseDateRequired'],measurements
   date_box=date_input.bounding_box();type_box=f.locator('[name=type]').bounding_box();assert date_box['y']+date_box['height']<=type_box['y'];passed('localized Chinese date has enough full-row width and cannot overlap movement type')
   f.locator('[name=barn_id]').select_option(barn['id']);f.locator('[name=type]').select_option('death');f.locator('[name=quantity]').fill('2');f.locator('details > summary').tap();f.locator('[name=note]').fill('iPhone 未儲存備註');saved_date=date_input.input_value()
   def choose(size):
    page.locator('#font-control').evaluate('(e)=>e.open=true');page.locator(f'#font-control [data-text-size={size}]').tap();page.locator('#font-control').evaluate('(e)=>e.open=false')
   for i,size in enumerate(('small','large','medium')):
    f.locator('[name=quantity]').focus();page.select_option('#language','vi' if i%2==0 else 'zh');page.evaluate('async()=>await refresh()');choose(size);assert f.locator('[name=quantity]').input_value()=='2';assert f.locator('[name=note]').input_value()=='iPhone 未儲存備註';assert f.locator('[name=batch_id]').input_value()==batch['id'];assert date_input.input_value()==saved_date
   page.select_option('#language','zh');choose('medium');f.locator('details').evaluate('(e)=>e.open=false');passed('three language/font/sync rounds retain date, batch, quantity and note without losing draft')
   page.evaluate('scrollTo(0,0)');page.screenshot(path=str(root/f'artifacts/iphone-{engine}-daily.png'),full_page=True)
   f.locator('button.primary').tap();page.wait_for_function('()=>pending===null&&document.querySelector("#movement-form [name=quantity]").value===""');rows=store.snapshot()['movements'];assert len(rows)==1 and rows[0]['quantity']==2 and rows[0]['note']=='iPhone 未儲存備註';assert f.locator('[name=batch_id]').input_value()==batch['id'];assert date_input.input_value()==saved_date;passed('touch save stores one real HTTP record and retains date/barn/batch')
   cases=0
   for width,height in ((320,667),(375,812),(390,844),(393,852),(430,932),(852,393)):
    page.set_viewport_size({'width':width,'height':height})
    for language in ('zh','vi'):
     page.select_option('#language',language)
     for size in ('small','medium','large'):
      choose(size)
      for tab in ('daily','stats','history','feed','weights','settings'):
       page.evaluate('async tab=>{location.hash=tab;setPage(tab,false);await renderCurrent()}',tab)
       geometry=page.evaluate('''()=>({fits:document.documentElement.scrollWidth<=document.documentElement.clientWidth+2,bad:Array.from(document.querySelectorAll('input:not([type=hidden]),select,textarea')).filter(e=>e.getClientRects().length&&e.closest('label')).flatMap(e=>{const r=e.getBoundingClientRect(),p=e.closest('label').getBoundingClientRect();return r.left<p.left-1||r.right>p.right+1?[e.name||e.id]:[]})})''')
       assert geometry['fits'] and not geometry['bad'],(width,height,language,size,tab,geometry);cases+=1
   passed(f'{cases} phone portrait/landscape page/language/font layouts have no page overflow or controls spilling outside labels')
   page.set_viewport_size({'width':390,'height':844});page.select_option('#language','zh');choose('medium');page.evaluate('async()=>{location.hash="daily";setPage("daily",false);await renderCurrent();for(const [name,value] of Object.entries({"--safe-top":"47px","--safe-bottom":"34px"}))document.documentElement.style.setProperty(name,value);scrollTo(0,0)}')
   assert page.locator('header').evaluate('(e)=>parseFloat(getComputedStyle(e).paddingTop)')>=55
   assert page.locator('nav').evaluate('(e)=>parseFloat(getComputedStyle(e).paddingBottom)')>=39
   page.locator('#font-control').evaluate('(e)=>e.open=true');panel=page.locator('.font-panel').bounding_box();header=page.locator('header').bounding_box();assert panel['y']>=header['y']+header['height'] and panel['x']>=0 and panel['x']+panel['width']<=390;page.locator('#font-control').evaluate('(e)=>e.open=false')
   f.locator('button.primary').evaluate('(e)=>e.scrollIntoView({block:"center"})');page.wait_for_timeout(200);button=f.locator('button.primary').bounding_box();header=page.locator('header').bounding_box();nav=page.locator('nav').bounding_box();assert button['y']>=header['y']+header['height'] and button['y']+button['height']<nav['y'];page.screenshot(path=str(root/f'artifacts/iphone-{engine}-safe-area.png'));passed('simulated 47px top/34px bottom safe areas protect header, size menu and reachable save button')
   page.set_viewport_size({'width':390,'height':430});f.locator('[name=quantity]').focus();f.locator('[name=quantity]').fill('3');assert f.locator('[name=quantity]').input_value()=='3';page.set_viewport_size({'width':390,'height':844});assert f.locator('[name=quantity]').input_value()=='3';page.evaluate('finishForm(document.querySelector("#movement-form"))');passed('short viewport/focus changes keep quantity intact; physical iOS keyboard was not emulated')
   page.locator('#logout').tap();login('reader','83000012');assert f.locator('button.primary').is_disabled();assert store.export_backup()['users']==original['users'];assert not errors;passed('viewer restrictions, existing account hashes and no JavaScript errors retained');browser.close()
   result['status']='passed'
 finally:server.shutdown();server.server_close()
save_result();print('Completed',len(checks),'iPhone scenarios with',engine)
