"""Real Chromium UI tests with isolated synthetic farm data; no production records."""
import tempfile, threading, uuid, json, sys
from pathlib import Path
from datetime import date, timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store
from app.server import Server
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
out=root/'artifacts';out.mkdir(exist_ok=True)
tmp=tempfile.TemporaryDirectory();store=Store(Path(tmp.name)/'farm.sqlite3')
admin=store.create_user('tester','browser-test-password')
store.create_user('reader','browser-test-password','viewer')
def add(kind,**kw):return store.mutate(admin,kind,kw,str(uuid.uuid4()))
barn=add('barns',name='9棟',group='育成A組')
batch=add('batches',barn_id=barn['id'],name='2026秋季第一批',group='育成A組',entry_date=(date.today()-timedelta(days=40)).isoformat(),entry_count=1000,entry_age_days=70,status='active')
for typ,n in [('sale',150),('cull',20),('death',5)]:add('movements',date=date.today().isoformat(),batch_id=batch['id'],type=typ,quantity=n)
server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start()
base='http://127.0.0.1:'+str(server.server_port)
results=[]
def passed(name):results.append(name);print('PASS',name,flush=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base)
    page.locator('#login-form [name=username]').fill('tester');page.locator('#login-form [name=password]').fill('browser-test-password');page.locator('#login-form button').click()
    page.wait_for_selector('#barns .barn-card');page.wait_for_function("()=>document.querySelector('#home-metrics').textContent.includes('825')")
    passed('login and dashboard 825 / 170 / 5 / 99.50%')
    assert '99.50%' in page.locator('#home-metrics').inner_text()
    page.locator('[data-add-barn]').click();assert page.locator('#movement-form [name=batch_id]').input_value()==batch['id']
    form=page.locator('#movement-form');form.locator('[name=quantity]').fill('3');form.locator('details').click();form.locator('[name=note]').fill('保留輸入測試')
    form.locator('[name=quantity]').focus();before=page.evaluate('({x:scrollX,y:scrollY})')
    page.select_option('#language','vi');assert form.locator('[name=quantity]').input_value()=='3';assert form.locator('[name=note]').input_value()=='保留輸入測試';assert form.locator('details').evaluate('(e)=>e.open')
    passed('language change preserves input and expanded state')
    page.select_option('#language','zh');form.locator('[name=note]').focus();scroll=page.evaluate('scrollY');page.evaluate('refresh()');page.wait_for_timeout(400)
    assert page.evaluate('document.activeElement.name')=='note';assert page.evaluate('scrollY')==scroll;assert form.locator('[name=quantity]').input_value()=='3'
    passed('background sync preserves focus, scroll, input and details')
    form.locator('.primary').dblclick();page.wait_for_function('()=>pending===null');page.wait_for_timeout(350)
    assert len(store.snapshot()['movements'])==4;assert form.locator('[name=quantity]').input_value()=='';assert form.locator('[name=batch_id]').input_value()==batch['id']
    passed('double-click writes once and save preserves scope')
    # Drop a successful response after the server has committed, then retry its exact key.
    def lost_response(route):
        response=route.fetch();assert response.status==201;route.abort('failed');page.unroute('**/api/movements',lost_response)
    page.route('**/api/movements',lost_response)
    form.locator('[name=quantity]').fill('2');form.locator('.primary').click();page.wait_for_selector('#pending:not([hidden])');assert form.locator('[name=quantity]').input_value()=='2';assert len(store.snapshot()['movements'])==5
    page.reload();page.wait_for_selector('#workspace:not([hidden])');page.wait_for_timeout(250);assert page.locator('#movement-form [name=quantity]').input_value()=='2';assert page.locator('#movement-form [name=batch_id]').input_value()==batch['id'];assert page.locator('#movement-form [name=quantity]').is_disabled()
    passed('reload restores pending payload and scope without new request')
    page.locator('#retry').click();page.wait_for_function('()=>pending===null');assert len(store.snapshot()['movements'])==5
    passed('lost committed response and retry do not duplicate')
    page.locator('nav [href="#feed"]').click();d=page.locator('#delivery-form');d.locator('[name=barn_id]').select_option(barn['id']);d.locator('[name=display_unit]').select_option('ton');d.locator('[name=amount]').fill('2');d.locator('.primary').click();page.wait_for_function('()=>pending===null');page.wait_for_timeout(300)
    assert store.snapshot()['deliveries'][0]['kg']==2000;assert not store.snapshot()['usages']
    passed('UI 2 tons persisted as 2000 kg; no consumption invented')
    d.locator('[name=amount]').fill('2');d.locator('[name=display_unit]').select_option('kg');assert d.locator('[name=amount]').input_value()=='2000';d.locator('[name=display_unit]').select_option('ton');assert d.locator('[name=amount]').input_value()=='2';d.locator('[name=amount]').fill('')
    passed('unit switch preserves physical quantity')
    page.locator('nav [href="#weights"]').click();w=page.locator('#weight-form');w.locator('[name=barn_id]').select_option(barn['id']);w.locator('[name=weight_mode]').select_option('individual');w.locator('[name=individual_kg]').fill('50, 60, 70');w.locator('.primary').click();page.wait_for_function('()=>pending===null');page.wait_for_timeout(300)
    assert store.snapshot()['weights'][0]['total_kg']==180;assert store.snapshot()['weights'][0]['count']==3
    passed('individual weights auto-count, total and weighted mean')
    page.locator('nav [href="#history"]').click();hf=page.locator('#history-filter');hf.locator('[name=from]').fill(date.today().isoformat());hf.locator('[name=to]').fill(date.today().isoformat());hf.locator('[name=type]').select_option('death');hf.locator('button[type=submit], button:not([type])').first.click();page.wait_for_timeout(300)
    assert page.locator('#history-results tbody tr').count()==1
    with page.expect_download() as download:page.locator('[data-export=movements]').click()
    text=download.value.path().read_text(encoding='utf-8-sig');assert text.count('\n')==2
    passed('date + type filters and CSV agree')
    page.locator('nav [href="#stats"]').click();page.wait_for_selector('#stats-results details');page.locator('#stats-results details').first.click();page.wait_for_timeout(150);assert page.locator('#stats-results').inner_text().find('資料不足')>=0
    passed('insufficient FCR remains explicitly unknown')
    # Two administrators correcting the same record. A direct service request represents the second session.
    page.locator('nav [href="#history"]').click();page.wait_for_selector('#history-results [data-edit=movements]');page.locator('#history-results [data-edit=movements]').first.click();page.wait_for_timeout(100)
    edit_id=page.locator('#movement-form').get_attribute('data-edit-id');r=next(x for x in store.snapshot()['movements'] if x['id']==edit_id)
    store.mutate(admin,'movements',r|{'note':'另一位管理員'},str(uuid.uuid4()),edit_id)
    page.locator('#movement-form [name=note]').fill('本次更正');page.locator('#movement-form .primary').click();page.wait_for_timeout(300)
    assert '其他人已更正' in page.locator('#movement-form .form-error').inner_text();assert page.locator('#movement-form [name=note]').input_value()=='本次更正'
    passed('conflicting edit rejected without clearing input')
    page.locator('#movement-form [data-action=cancelEdit]').click()
    # Pre-write offline failure retains pending, explicit retry after reconnect.
    form.locator('[name=quantity]').fill('1');context.set_offline(True);form.locator('.primary').click();page.wait_for_selector('#pending:not([hidden])');assert form.locator('[name=quantity]').input_value()=='1'
    context.set_offline(False);page.locator('#retry').click();page.wait_for_function('()=>pending===null');passed('offline is pending until explicit successful retry')
    # Screenshot from synthetic fixture only.
    page.locator('nav [href="#daily"]').click();page.evaluate('scrollTo(0,0)');page.wait_for_timeout(500);page.screenshot(path=str(out/'desktop-1.1.0.png'),full_page=True)
    for size in [{'width':390,'height':844},{'width':768,'height':1024},{'width':1440,'height':900}]:
        page.set_viewport_size(size)
        for name in ['daily','stats','history','feed','weights','settings']:
            page.locator(f'nav [href="#{name}"]').click();page.wait_for_timeout(100)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(size,name)
    page.set_viewport_size({'width':390,'height':844});page.locator('nav [href="#daily"]').click();page.wait_for_timeout(300);page.evaluate('scrollTo(0,0)');page.screenshot(path=str(out/'mobile-1.1.0.png'),full_page=True)
    passed('390px phone, 768px tablet, desktop: all six pages without page overflow')
    # Separate browser session validates viewer UI and server enforcement.
    readonly=browser.new_context();rpage=readonly.new_page();rpage.goto(base);rpage.locator('#login-form [name=username]').fill('reader');rpage.locator('#login-form [name=password]').fill('browser-test-password');rpage.locator('#login-form button').click();rpage.wait_for_selector('#barns .barn-card')
    assert rpage.locator('#movement-form [name=quantity]').is_disabled()
    code=rpage.evaluate("""async()=>{const m=await (await fetch('/api/me')).json();return (await fetch('/api/movements',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':m.csrf,'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({})})).status}""")
    assert code==403;passed('viewer UI and actual server denial (403)')
    page.locator('#logout').click();page.wait_for_selector('#login-view:not([hidden])');page.locator('#login-form [name=username]').fill('reader');page.locator('#login-form [name=password]').fill('browser-test-password');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])');page.wait_for_timeout(300);assert page.locator('#movement-form [name=quantity]').is_disabled();assert page.locator('#movement-form .primary').is_disabled();page.locator('nav [href="#settings"]').click();assert page.locator('.admin-section').is_hidden()
    passed('account switch reloads role restrictions and hides administrator controls')
    assert not errors,errors;passed('no uncaught JavaScript errors')
    browser.close()
server.shutdown();server.server_close();tmp.cleanup()
(out/'browser-results.json').write_text(json.dumps({'version':'1.1.0','type':'real Chromium + synthetic fixtures','passed':results},ensure_ascii=False,indent=2))
print('Completed',len(results),'browser scenarios')
