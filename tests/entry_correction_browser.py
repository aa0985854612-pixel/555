"""Real Chromium and isolated synthetic single-barn source; no production writes."""
import base64,json,tempfile,threading,uuid
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from app.domain import herd
from test_entry_correction import single_barn_workbook
from playwright.sync_api import sync_playwright
results=[]
def passed(s):results.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as folder:
 store=Store(Path(folder)/'db');admin=store.create_user('owner','83000011')
 store.import_workbook(admin,{'filename':'synthetic.xlsx','base64':base64.b64encode(single_barn_workbook()).decode(),'counts_as_of':'2026-10-12','counts_text':'15/99'},str(uuid.uuid4()));batch=store.snapshot()['batches'][0]
 server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(f'http://127.0.0.1:{server.server_port}');page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])');page.locator('[href="#settings"]').click();page.locator('#batch-settings > details > summary').first.click();page.locator(f'[data-edit="batches"][data-id="{batch["id"]}"]').click();f=page.locator('#batch-form');n=f.locator('[name=entry_count]');reason=f.locator('[name=entry_count_reason]');assert n.is_editable();assert n.input_value()=='100';assert page.locator('#entry-count-correction').is_visible();n.fill('120');assert reason.evaluate('(e)=>e.required');assert not f.evaluate('(e)=>e.checkValidity()');reason.fill('核對入場單據');assert '20' in page.locator('#entry-count-impact').inner_text();passed('15 barn source entry editable; reason required and delta visible')
   for i in range(3):
    page.evaluate('async()=>await refresh()');page.select_option('#language','vi' if i%2==0 else 'zh');assert n.input_value()=='120';assert reason.input_value()=='核對入場單據';assert n.is_editable()
   page.select_option('#language','zh');passed('three language and sync rounds preserve unsaved entry correction')
   f.locator('button.primary').click();page.wait_for_function('()=>pending===null&&!document.querySelector("#batch-form").dataset.editId');d=store.snapshot();assert d['batches'][0]['entry_count']==120;assert herd(d['batches'],d['movements'],'2026-10-14')['remaining']==110;assert d['workbooks'][0]['report']['rows'][0]['totals']['entry']==100;passed('real form PUT saves correction; herd recalculates and original Excel stays unchanged')
   page.reload();page.wait_for_selector('#workspace:not([hidden])');page.locator('[href="#settings"]').click();page.locator('#batch-settings > details > summary').first.click();page.locator(f'[data-edit="batches"][data-id="{batch["id"]}"]').click();assert n.input_value()=='120';assert reason.input_value()=='';assert not reason.evaluate('(e)=>e.required');n.fill('100');assert reason.evaluate('(e)=>e.required');f.locator('[data-action=cancelEdit]').click();assert page.locator('#entry-count-correction').is_hidden();assert store.snapshot()['batches'][0]['entry_count']==120;assert not errors;passed('reload retains correction; restore-original needs reason; cancel does not save')
   browser.close()
 finally:server.shutdown();server.server_close()
root=Path(__file__).resolve().parents[1];(root/'artifacts/entry-correction-browser-results.json').write_text(json.dumps({'version':VERSION,'mode':'real Chromium; synthetic data; no physical phone','passed':results},ensure_ascii=False,indent=2));print('Completed',len(results),'entry correction browser scenarios')
