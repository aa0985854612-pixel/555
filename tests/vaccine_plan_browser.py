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
    other_barn=add('barns',name='23棟')
    add('batches',barn_id=other_barn['id'],name='OTHER',entry_date='2026-07-01',
        entry_count=100,entry_age_days=71,status='active')
    mismatch_barn=add('barns',name='38棟')
    mismatch=add('batches',barn_id=mismatch_barn['id'],name='MISMATCH',entry_date='2026-07-01',entry_count=100,status='active')
    old_doses={key:{'date':'','bottles':None,'done':False} for key in ('pr1','app1','pr2','app2')}
    old_doses['pr1']={'date':'2026-08-01','bottles':2,'done':True}
    old_doses['app1']={'date':'2026-08-02','bottles':3,'done':True}
    add('vaccine_plans',batch_id=mismatch['id'],scope='cohort',doses=old_doses)
    archived_barn=add('barns',name='39棟')
    add('batches',barn_id=archived_barn['id'],name='ARCHIVED',
        entry_date='2026-07-01',entry_count=100,status='ended')
    mixed=[]
    for number,status in ((40,'active'),(41,'ended')):
        barn=add('barns',name=f'{number}棟')
        mixed.append(add('batches',barn_id=barn['id'],name='MIXED',
                         entry_date='2026-07-01',entry_count=100,status=status))
    legacy=[]
    for index in (30,31):
        barn=add('barns',name=f'{index}棟')
        legacy.append(add('batches',barn_id=barn['id'],name='LEGACY',
                          entry_date='2026-07-01',entry_count=100,entry_age_days=71,status='active'))
    for batch,date in zip(legacy,('2026-08-01','2026-08-02')):
        doses={key:{'date':'','bottles':None,'done':False} for key in ('pr1','app1','pr2','app2')}
        doses['pr1']={'date':date,'bottles':1,'done':True}
        add('vaccine_plans',batch_id=batch['id'],doses=doses)
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
            options=form.locator('#vaccine-batch option').all_text_contents()
            assert options.count('VACCINE-DEMO｜15棟、21棟')==1,options
            assert not any('ARCHIVED' in option for option in options),options
            assert 'MIXED｜40棟' in options,options
            assert not any('41棟' in option for option in options),options
            form.locator('#vaccine-batch').select_option('LEGACY|2026-07-01')
            assert '各棟原有資料不同' in form.locator('.form-error').inner_text()
            assert form.locator('[name=dose1_date]').input_value()==''
            assert '2026-08-01' in form.locator('#vaccine-previous').text_content()
            assert '2026-08-02' in form.locator('#vaccine-previous').text_content()
            form.locator('#vaccine-batch').select_option('MISMATCH|2026-07-01')
            assert '原有 PR、APP 資料不同' in form.locator('.form-error').inner_text()
            assert '2026-08-01' in form.locator('#vaccine-previous').text_content() and '2026-08-02' in form.locator('#vaccine-previous').text_content()
            form.locator('[name=dose2_date]').fill('2026-09-01')
            form.locator('button[type=submit]').click()
            page.wait_for_function("()=>data.vaccine_plans.some(p=>p.scope==='cohort'&&p.revision===2) && pending===null")
            preserved=next(p for p in store.snapshot()['vaccine_plans'] if p['batch_id']==mismatch['id'])
            assert preserved['doses']['pr1']==old_doses['pr1'] and preserved['doses']['app1']==old_doses['app1']
            assert preserved['doses']['pr2']==preserved['doses']['app2']
            form.locator('#vaccine-batch').select_option('VACCINE-DEMO|2026-07-01')
            form.locator('[name=dose1_done]').check()
            form.locator('button[type=submit]').click()
            assert '請先填寫' in form.locator('.form-error').inner_text()
            assert len(store.snapshot()['vaccine_plans'])==3
            form.locator('[name=dose1_done]').uncheck()
            form.locator('[name=dose1_date]').fill('2026-08-08')
            form.locator('[name=dose1_bottles]').fill('2')
            form.locator('#vaccine-batch').select_option('OTHER|2026-07-01')
            assert form.locator('[name=dose1_date]').input_value()==''
            form.locator('#vaccine-batch').select_option('VACCINE-DEMO|2026-07-01')
            assert form.locator('[name=dose1_date]').input_value()=='2026-08-08'
            assert form.locator('[name=dose1_bottles]').input_value()=='2'
            form.locator('[name=dose2_date]').fill('2026-09-08')
            form.locator('[name=dose2_bottles]').fill('4')
            form.locator('[name=dose2_done]').check()
            form.locator('button[type=submit]').click()
            page.wait_for_function("()=>data.vaccine_plans?.length===4 && pending===null")
            plan=next(item for item in store.snapshot()['vaccine_plans'] if item.get('scope')=='cohort' and item['batch_id'] in [b['id'] for b in batches])
            assert plan['scope']=='cohort'
            assert plan['doses']['pr1']=={'date':'2026-08-08','bottles':2,'done':False}
            assert plan['doses']['app1']==plan['doses']['pr1']
            assert not form.locator('[name=dose1_done]').is_checked()
            page.evaluate("""()=>{
                window.vaccineModels=[];window.vaccineDraws=[];window.vaccineTicks=0;window.vaccineTickPositions=[];
                const pdf=weeklyPdf;
                window.weeklyPdf=async m=>{vaccineModels.push(m);return pdf(m)};
                const fill=CanvasRenderingContext2D.prototype.fillText;
                CanvasRenderingContext2D.prototype.fillText=function(...a){vaccineDraws.push({text:String(a[0]),x:a[1],y:a[2]});return fill.apply(this,a)};
                const move=CanvasRenderingContext2D.prototype.moveTo;
                CanvasRenderingContext2D.prototype.moveTo=function(x,y){if(Math.abs(this.lineWidth-1.7)<0.001)vaccineTickPositions.push({x,y,color:this.strokeStyle});return move.call(this,x,y)};
                const stroke=CanvasRenderingContext2D.prototype.stroke;
                CanvasRenderingContext2D.prototype.stroke=function(...a){if(Math.abs(this.lineWidth-1.7)<0.001)vaccineTicks++;return stroke.apply(this,a)};
            }""")
            page.evaluate("(id)=>document.dispatchEvent(new CustomEvent('pigledger:weekly-open',{detail:{batch_id:id}}))",batches[0]['id'])
            page.wait_for_selector('#weekly-a4-preview img')
            assert page.evaluate('vaccineModels.at(-1).vaccinePlans[0].doses.app2.done')
            assert page.evaluate('vaccineTicks')==2, page.evaluate('vaccineTicks')
            positions=page.evaluate('vaccineTickPositions')
            assert len(positions)==2 and positions[0]['x'] != positions[1]['x'] and all(315<d['x']<363 and d['color']=='#b42332' for d in positions),positions
            drawn=page.evaluate('vaccineDraws')
            assert any(d['text']=='08/08' and 220<d['x']<268 and 1063<d['y']<1089 for d in drawn)
            assert any(d['text']=='08/08' and 268<d['x']<315 and 1063<d['y']<1089 for d in drawn)
            assert any(d['text']=='2' and 220<d['x']<268 and 1089<d['y']<1113 for d in drawn)
            page.locator('#weekly-close').click()
            page.locator('nav [href="#settings"]').click()
            form.locator('[name=dose1_done]').check()
            form.locator('button[type=submit]').click()
            page.wait_for_function("()=>data.vaccine_plans.some(p=>p.scope==='cohort'&&p.revision===2&&p.doses.pr1.date==='2026-08-08') && pending===null")
            saved=next(item for item in store.snapshot()['vaccine_plans'] if item.get('scope')=='cohort' and item['batch_id'] in [b['id'] for b in batches])
            assert saved['doses']['pr1']['done'] and saved['doses']['pr1']==saved['doses']['app1']
            page.evaluate('vaccineTicks=0')
            page.evaluate("(id)=>document.dispatchEvent(new CustomEvent('pigledger:weekly-open',{detail:{batch_id:id}}))",batches[0]['id'])
            page.wait_for_selector('#weekly-a4-preview img')
            assert page.evaluate('vaccineTicks')==4, page.evaluate('vaccineTicks')
            page.evaluate('vaccineTicks=0')
            page.locator('#weekly-barn').select_option('')
            page.wait_for_selector('#weekly-a4-preview img')
            assert len(page.evaluate('vaccineModels.at(-1).vaccineBatchIds'))==2
            assert len(page.evaluate('vaccineModels.at(-1).vaccinePlans'))==1
            assert page.evaluate('vaccineTicks')==4
            page.evaluate('vaccineTicks=0')
            second_barn=store.snapshot()['batches'][1]['barn_id']
            page.locator('#weekly-barn').select_option(second_barn)
            page.wait_for_selector('#weekly-a4-preview img')
            assert page.evaluate('vaccineTicks')==4
            assert page.evaluate('vaccineModels.at(-1).vaccinePlans[0].scope')=='cohort'
            page.locator('#weekly-close').click()
            page.locator('nav [href="#settings"]').click()
            form.locator('#vaccine-batch').select_option('MIXED|2026-07-01')
            form.locator('[name=dose1_date]').fill('2026-09-12')
            ended=store.mutate(admin,'batches',mixed[0]|{'status':'ended'},str(uuid.uuid4()),mixed[0]['id'])
            page.evaluate('async()=>await refresh()')
            assert form.locator('#vaccine-batch').input_value()==''
            page.wait_for_function("()=>document.querySelector('#vaccine-form fieldset').disabled")
            assert 'MIXED|2026-07-01' not in form.locator('#vaccine-batch option').evaluate_all('(items)=>items.map(i=>i.value)')
            store.mutate(admin,'batches',ended|{'status':'active'},str(uuid.uuid4()),ended['id'])
            page.evaluate('async()=>await refresh()')
            form.locator('#vaccine-batch').select_option('MIXED|2026-07-01')
            assert form.locator('[name=dose1_date]').input_value()=='2026-09-12'
            assert next(item for item in store.snapshot()['vaccine_plans'] if item.get('scope')=='cohort' and item['batch_id'] in [b['id'] for b in batches])['doses']['pr1']['done']
            for batch in batches:
                current=next(item for item in store.snapshot()['batches'] if item['id']==batch['id'])
                store.mutate(admin,'batches',current|{'status':'ended'},str(uuid.uuid4()),current['id'])
            page.evaluate('async()=>await refresh()')
            page.wait_for_function("()=>!Array.from(document.querySelector('#vaccine-batch').options).some(o=>o.value==='VACCINE-DEMO|2026-07-01')")
            historical=page.request.get(url+'/api/weekly-report?batch_id='+batches[0]['id']+'&batch_status=ended&all_records=1').json()
            assert historical['vaccine_plans'][0]['doses']['pr1']['done']
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
print('PASS grouped vaccine selection, shared completion and single-barn A4 checks')
