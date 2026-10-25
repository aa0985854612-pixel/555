"""A4, PDF and CSV group a cohort's shipments, retaining raw barn events."""
import csv,io,json,tempfile,threading,uuid,sys,subprocess,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);checks=[]
def passed(s):checks.append(s);print('PASS '+s,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 s=Store(Path(tmp)/'db');u=s.create_user('owner','83000011')
 def add(kind,**body):return s.mutate(u,kind,body,str(uuid.uuid4()))
 barns=[add('barns',name=f'{n}棟') for n in (12,24,5)]
 lots=[add('batches',barn_id=b['id'],name='OTHER' if i==2 else 'GROUPED',entry_date='2026-10-09',entry_count=400,entry_age_days=70,status='active') for i,b in enumerate(barns)]
 rows=[('2026-10-20','sale',30,0,'南投',''),('2026-10-20','sale',30,1,'南投',''),('2026-10-21','sale',10,0,'南投','第1車'),('2026-10-21','sale',20,1,'南投','第1車'),('2026-10-21','sale',5,0,'南投','第2車'),('2026-10-21','sale',7,1,'南投','第2車'),('2026-10-21','sale',8,0,'新北','第1車'),('2026-10-22','sale',9,0,'南投',''),('2026-10-21','cull',2,0,'南投','第1車'),('2026-10-21','cull',1,1,'南投','第1車'),('2026-10-20','sale',50,2,'南投','')]
 for on,kind,q,index,destination,trip in rows:add('movements',batch_id=lots[index]['id'],date=on,type=kind,quantity=q,outgoing_destination=destination,outgoing_trip=trip)
 server=Server(('127.0.0.1',0),s);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':900},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(url);page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   f=page.locator('#movement-form');f.locator('details').evaluate('(e)=>e.open=true');f.locator('[name=type]').select_option('sale');f.locator('[name=barn_id]').select_option(barns[0]['id']);f.locator('[name=batch_id]').select_option(lots[0]['id']);f.locator('[name=date]').fill('2026-10-23');f.locator('[name=outgoing_destination]').select_option('南投');f.locator('[name=outgoing_trip]').fill('第3車');f.locator('[name=quantity]').fill('6');f.locator('button.primary').click();page.wait_for_function('()=>pending===null&&document.querySelector("#movement-form [name=quantity]").value===""');saved=s.snapshot()['movements'][-1];assert saved['outgoing_trip']=='第3車';page.evaluate('(id)=>edit("movements",id)',saved['id']);assert f.locator('[name=outgoing_trip]').input_value()=='第3車';f.locator('[data-action=cancelEdit]').click();passed('optional trip saves through the normal movement form and reopens on edit')
   before=s.export_backup()['records'];page.evaluate('()=>{const original=window.weeklyPdf;window.weeklyPdf=model=>{window.lastShipmentModel=model;return original(model);};window.shipmentPreviewBlobs=new Map();const create=URL.createObjectURL;URL.createObjectURL=b=>{const u=create(b);shipmentPreviewBlobs.set(u,b);return u;};}')
   page.locator('#open-daily-weekly-report').click();page.locator('#weekly-cohort').select_option('GROUPED|2026-10-09');page.locator('#weekly-barn').select_option('');page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-a4-preview img');page.wait_for_function('()=>!!window.lastShipmentModel')
   expected={'10/20 南投60','10/21 南投30（第1車）','10/21 南投12（第2車）','10/21 新北8（第1車）','10/22 南投9','10/21 南投 淘汰3（第1車）','10/23 南投6（第3車）'}
   model=page.evaluate('lastShipmentModel');assert set(model['shipping_notes'])==expected,model['shipping_notes'];sheet=page.locator('#weekly-sheet-body');assert set(sheet.locator('.weekly-shipping-notes .weekly-outgoing-entry').all_text_contents())==expected;assert all('（12）' not in line and '（24）' not in line for line in expected);passed('same batch/day/destination groups 12+24 barn 30+30 as 南投60; separate trips, dates, cities and culls remain separate')
   raw_image=page.evaluate('async()=>Array.from(new Uint8Array(await shipmentPreviewBlobs.get(document.querySelector("#weekly-a4-preview img").src).arrayBuffer()))')
   with page.expect_download() as download:page.locator('#weekly-print').click()
   path=root/'artifacts/grouped-shipments-a4.pdf';download.value.save_as(path);pdf=path.read_bytes();info=subprocess.check_output(['pdfinfo',str(path)],text=True);assert re.search(r'Pages:\s+1\b',info);assert bytes(raw_image) in pdf;page.locator('#weekly-a4-preview img').screenshot(path=str(root/'artifacts/grouped-shipments-a4.png'));passed('one-page portrait A4 download embeds the exact grouped image shown in preview')
   with page.expect_download() as download:page.locator('#weekly-csv').click()
   csv_rows=list(csv.reader(io.StringIO(Path(download.value.path()).read_text(encoding='utf-8-sig'))));summary=next(row for row in csv_rows if len(row)>2 and row[0]=='出豬備註');joined='；'.join(summary[1:]);assert all(n in joined for n in expected)
   header=next(i for i,row in enumerate(csv_rows) if len(row)==8 and row[0]=='日期' and row[-1]=='車次');raw=[]
   for row in csv_rows[header+1:]:
    if not row:break
    raw.append(row)
   assert len(raw)==11;assert sum(int(row[3]) for row in raw if row[2]=='正常出豬')==125;assert sum(int(row[3]) for row in raw if row[2]=='淘汰')==3;assert {row[1] for row in raw}=={'12棟','24棟'};assert '第3車' in [row[-1] for row in raw];assert len([row for row in raw if row[0]=='2026-10-20' and row[3]=='30'])==2;passed('CSV summary uses the same grouped notes; raw section retains both 30-head barn events and trip IDs')
   exported=page.evaluate('async()=>{const r=await fetch("/api/export?kind=movements&cohort="+encodeURIComponent("GROUPED|2026-10-09"));return r.text();}');exports=list(csv.DictReader(io.StringIO(exported.lstrip('\ufeff'))));assert len(exports)==11 and '第3車' in [row['outgoing_trip'] for row in exports];passed('history CSV also exports the optional trip without losing raw movements')
   page.locator('#weekly-barn').select_option(barns[0]['id']);page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-a4-preview img');assert '10/20 南投30' in page.evaluate('lastShipmentModel.shipping_notes');assert '10/20 南投60' not in page.evaluate('lastShipmentModel.shipping_notes')
   page.locator('#weekly-cohort').select_option('OTHER|2026-10-09');page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-a4-preview img');assert page.evaluate('lastShipmentModel.shipping_notes')==['10/20 南投50'];assert s.export_backup()['records']==before;assert not errors,errors;passed('single-barn and other-batch reports never mix quantities; report operations write no farm records; no browser errors');browser.close()
  print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False))
 finally:server.shutdown();server.server_close()
