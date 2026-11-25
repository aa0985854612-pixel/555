"""Exercise vaccine settings, persistence and the real A4 renderer in Chromium."""
import sys
import tempfile
import threading
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.server import Server
from app.store import Store

with tempfile.TemporaryDirectory() as folder:
    store=Store(Path(folder)/'farm.db')
    admin=store.create_user('owner','83000011')
    store.create_user('reader','83000012','viewer')
    def add(kind,**body):
        return store.mutate(admin,kind,body,str(uuid.uuid4()))
    batches=[]
    for barn_name in ('15棟','21棟'):
        barn=add('barns',name=barn_name)
        batches.append(add('batches',barn_id=barn['id'],name='VACCINE-DEMO',
                           entry_date='2026-07-01',entry_count=100,entry_age_days=71,status='active'))
    server=Server(('127.0.0.1',0),store)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url='http://127.0.0.1:'+str(server.server_port)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':390,'height':844})
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url)
            page.locator('#login-form [name=username]').fill('owner')
            page.locator('#login-form [name=password]').fill('83000011')
            page.locator('#login-form button').click()
            page.wait_for_selector('#workspace:not([hidden])')
            page.locator('nav [href="#settings"]').click()
            form=page.locator('#vaccine-form')
            form.locator('#vaccine-batch').select_option(batches[0]['id'])
            form.locator('[name=pr1_done]').check()
            form.locator('button[type=submit]').click()
            assert '請先填寫' in form.locator('.form-error').inner_text()
            assert store.snapshot()['vaccine_plans']==[]
            form.locator('[name=pr1_done]').uncheck()
            form.locator('[name=pr1_date]').fill('2026-08-08')
            form.locator('[name=pr1_bottles]').fill('2')
            form.locator('#vaccine-batch').select_option(batches[1]['id'])
            assert form.locator('[name=pr1_date]').input_value()==''
            form.locator('#vaccine-batch').select_option(batches[0]['id'])
            assert form.locator('[name=pr1_date]').input_value()=='2026-08-08'
            assert form.locator('[name=pr1_bottles]').input_value()=='2'
            form.locator('[name=app1_date]').fill('2026-08-09')
            form.locator('[name=app1_bottles]').fill('3')
            form.locator('[name=app1_done]').check()
            form.locator('[name=pr2_date]').fill('2026-09-08')
            form.locator('[name=pr2_bottles]').fill('4')
            form.locator('[name=pr2_done]').check()
            form.locator('button[type=submit]').click()
            page.wait_for_function("()=>data.vaccine_plans?.length===1 && pending===null")
            plan=store.snapshot()['vaccine_plans'][0]
            assert plan['doses']['pr1']=={'date':'2026-08-08','bottles':2,'done':False}
            assert plan['doses']['app1']=={'date':'2026-08-09','bottles':3,'done':True}
            assert not form.locator('[name=pr1_done]').is_checked()
            assert form.locator('[name=app1_done]').is_checked()
            page.evaluate("""()=>{
                window.vaccineModels=[];window.vaccineDraws=[];window.vaccineTicks=0;
                const pdf=weeklyPdf;
                window.weeklyPdf=async m=>{vaccineModels.push(m);return pdf(m)};
                const fill=CanvasRenderingContext2D.prototype.fillText;
                CanvasRenderingContext2D.prototype.fillText=function(...a){vaccineDraws.push({text:String(a[0]),x:a[1],y:a[2]});return fill.apply(this,a)};
                const stroke=CanvasRenderingContext2D.prototype.stroke;
                CanvasRenderingContext2D.prototype.stroke=function(...a){if(Math.abs(this.lineWidth-1.7)<0.001)vaccineTicks++;return stroke.apply(this,a)};
            }""")
            page.evaluate("(id)=>document.dispatchEvent(new CustomEvent('pigledger:weekly-open',{detail:{batch_id:id}}))",batches[0]['id'])
            page.wait_for_selector('#weekly-a4-preview img')
            assert page.evaluate('vaccineModels.at(-1).vaccinePlans[0].doses.app1.done')
            assert page.evaluate('vaccineTicks')==2, page.evaluate('vaccineTicks')
            drawn=page.evaluate('vaccineDraws')
            assert any(d['text']=='08/08' and 220<d['x']<268 and 1063<d['y']<1089 for d in drawn)
            assert any(d['text']=='08/09' and 268<d['x']<315 and 1063<d['y']<1089 for d in drawn)
            assert any(d['text']=='2' and 220<d['x']<268 and 1089<d['y']<1113 for d in drawn)
            page.locator('#weekly-close').click()
            page.locator('nav [href="#settings"]').click()
            form.locator('[name=pr1_done]').check()
            form.locator('button[type=submit]').click()
            page.wait_for_function("()=>data.vaccine_plans[0].revision===2 && pending===null")
            assert store.snapshot()['vaccine_plans'][0]['doses']['pr1']['done']
            page.evaluate('vaccineTicks=0')
            page.evaluate("(id)=>document.dispatchEvent(new CustomEvent('pigledger:weekly-open',{detail:{batch_id:id}}))",batches[0]['id'])
            page.wait_for_selector('#weekly-a4-preview img')
            assert page.evaluate('vaccineTicks')==3, page.evaluate('vaccineTicks')
            page.evaluate('vaccineTicks=0')
            page.locator('#weekly-barn').select_option('')
            page.wait_for_selector('#weekly-a4-preview img')
            assert len(page.evaluate('vaccineModels.at(-1).vaccineBatchIds'))==2
            assert len(page.evaluate('vaccineModels.at(-1).vaccinePlans'))==1
            assert page.evaluate('vaccineTicks')==0
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
print('PASS vaccine settings save, completion and scoped A4 checks')
