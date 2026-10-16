"""Actual Chromium: device-local size settings, hierarchy, drafts and responsive layout."""
import json,sys,tempfile,threading,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];results=[];measurements={}
def passed(s):results.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as folder:
 store=Store(Path(folder)/'db');admin=store.create_user('owner','83000011')
 def add(kind,**d):return store.mutate(admin,kind,d,str(uuid.uuid4()))
 barn=add('barns',name='19棟',group='A');batch=add('batches',barn_id=barn['id'],name='JD-SAMPLE',entry_date='2026-01-01',entry_count=100,entry_age_days=70,status='active')
 add('movements',date='2026-10-15',batch_id=batch['id'],type='death',quantity=2)
 server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');page=context.new_page();errors=[];writes=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:writes.append(r.url) if r.method in ('POST','PUT','DELETE') else None)
   def choose(size):
    if not page.locator('#font-control').evaluate('(e)=>e.open'):page.locator('#font-control summary').click()
    page.locator(f'#font-control [data-text-size={size}]').click();assert page.locator(f'#font-control [data-text-size={size}]').get_attribute('aria-pressed')=='true'
    box=page.locator('.font-panel').bounding_box();assert box['x']>=0 and box['x']+box['width']<=page.viewport_size['width']+1
   page.goto(base);page.wait_for_function('()=>document.querySelector(".cover-art").naturalWidth>0');assert page.title()=='嘉得肉豬紀錄';assert page.locator('#login-view h1').inner_text()=='嘉得肉豬紀錄';assert page.locator('.cover-art').evaluate('(e)=>e.naturalWidth')==1536
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900});assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+2'),width
   page.set_viewport_size({'width':390,'height':844});assert page.locator('#login-form button').bounding_box()['y']+page.locator('#login-form button').bounding_box()['height']<=844;page.screenshot(path=str(root/'artifacts/jiade-login-mobile.png'),full_page=True);page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path=str(root/'artifacts/jiade-login-desktop.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});passed('Jia De title and illustration render; login button visible on mobile; four cover layouts fit')
   assert page.locator('html').get_attribute('data-text-size')=='medium';choose('large');page.reload();assert page.locator('html').get_attribute('data-text-size')=='large';assert page.locator('#login-form input').first.evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)')==20;passed('size control available before login, persists after reload, and scales inputs')
   page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])');f=page.locator('#movement-form');f.locator('[name=barn_id]').select_option(barn['id']);f.locator('[name=quantity]').fill('7');f.locator('details').evaluate('(e)=>e.open=true');f.locator('[name=note]').fill('尚未儲存的備註');count=len(writes)
   for size,pixels in [('small',16),('medium',17),('large',20)]:
    choose(size);assert f.locator('[name=quantity]').input_value()=='7';assert f.locator('[name=note]').input_value()=='尚未儲存的備註';assert f.locator('details').evaluate('(e)=>e.open');assert f.locator('[name=batch_id]').input_value()==batch['id'];assert f.locator('[name=quantity]').evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)')==pixels
   assert len(writes)==count;passed('small/medium/large preserve form values, scope and expanded details without farm writes')
   page.keyboard.press('Escape');assert not page.locator('#font-control').evaluate('(e)=>e.open');assert page.locator('#font-control summary').evaluate('(e)=>e===document.activeElement');passed('keyboard Escape closes size menu and restores control focus')
   for i in range(3):
    page.select_option('#language','vi' if i%2==0 else 'zh');page.evaluate('async()=>await refresh()');choose(['small','medium','large'][i]);assert f.locator('[name=quantity]').input_value()=='7';assert f.locator('[name=note]').input_value()=='尚未儲存的備註';assert f.locator('details').evaluate('(e)=>e.open')
   page.select_option('#language','vi');assert page.locator('#font-control summary').get_attribute('aria-label')=='Cỡ chữ';assert page.locator('#font-control [data-text-size=large]').inner_text()=='Lớn';page.select_option('#language','zh');passed('three sync/language/size rounds retain drafts; labels translate to Vietnamese')
   page.evaluate('finishForm(document.querySelector("#movement-form"))');page.locator('nav [href="#stats"]').click();sf=page.locator('#stats-filter');sf.locator('[name=from]').fill('2026-10-15');sf.locator('[name=to]').fill('2026-10-15');sf.locator('button').first.click();page.wait_for_selector('.death-hero');page.wait_for_function('()=>document.querySelector(".death-hero strong").textContent.includes("2")')
   for size in ('small','medium','large'):
    choose(size);measurements[size]=page.evaluate('()=>({body:parseFloat(getComputedStyle(document.body).fontSize),title:parseFloat(getComputedStyle(document.querySelector("#page-title")).fontSize),death:parseFloat(getComputedStyle(document.querySelector(".death-hero>strong")).fontSize),metadata:parseFloat(getComputedStyle(document.querySelector(".death-range")).fontSize)})');m=measurements[size];assert m['death']>m['title']>m['body']>m['metadata'];assert sf.locator('[name=from]').input_value()=='2026-10-15';assert sf.locator('[name=to]').input_value()=='2026-10-15'
   assert measurements['large']['death']>measurements['small']['death'];passed('death/title/body/metadata have distinct hierarchy at all three sizes; filters retained')
   cases=0
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.select_option('#language',language)
     for size in ('small','medium','large'):
      choose(size);page.locator('#font-control summary').click()
      for tab in ('daily','stats','history','feed','weights','settings'):
       page.evaluate('async(tab)=>{location.hash=tab;setPage(tab,false);await renderCurrent()}',tab);assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+2'),(width,language,size,tab);cases+=1
   passed(f'{cases} page/size/language/viewport layouts without horizontal page overflow')
   page.set_viewport_size({'width':390,'height':844});page.select_option('#language','zh');choose('medium');page.locator('#font-control summary').click();page.evaluate('async()=>{location.hash="daily";setPage("daily",false);await renderCurrent();scrollTo(0,0)}');page.screenshot(path=str(root/'artifacts/appearance-daily-mobile.png'),full_page=True)
   page.locator('[href="#stats"]').click();page.wait_for_selector('.death-hero');page.evaluate('scrollTo(0,0)');page.screenshot(path=str(root/'artifacts/appearance-stats-mobile.png'),full_page=True);page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path=str(root/'artifacts/appearance-stats-desktop.png'),full_page=True)
   other=page.context.new_page();other.goto(base);assert other.locator('html').get_attribute('data-text-size')=='medium';other.evaluate('localStorage.setItem("pig-text-size","large")');page.wait_for_function('()=>document.documentElement.dataset.textSize==="large"');other.close();passed('same-browser tabs synchronize the local font preference')
   assert not errors;passed('no uncaught JavaScript errors');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/appearance-browser-results.json').write_text(json.dumps({'version':VERSION,'mode':'real Chromium, synthetic farm; simulated viewports, no physical phone','passed':results,'hierarchy_px':measurements},ensure_ascii=False,indent=2));print('Completed',len(results),'appearance browser scenarios')
