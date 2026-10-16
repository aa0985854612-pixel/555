"""Real Chromium UI with synthetic Excel; no customer data is included."""
import sys,tempfile,threading,json,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from legacy_fixture import workbook_fixture
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1];results=[]
def passed(name):results.append(name);print('PASS',name,flush=True)
with tempfile.TemporaryDirectory() as tmp:
    folder=Path(tmp);file=folder/'synthetic-source.xlsx';file.write_bytes(workbook_fixture());store=Store(folder/'farm.sqlite3');store.create_initial_admin('tester','83000002')
    server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);context=browser.new_context(accept_downloads=True,viewport={'width':1400,'height':1000});page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(url);page.locator('#login-form [name=username]').fill('tester');page.locator('#login-form [name=password]').fill('83000002');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
            page.locator('nav [href="#settings"]').click();page.locator('.settings-fold:has(#workbook-form) > summary').click();form=page.locator('#workbook-form');page.locator('#workbook-file').set_input_files(file);form.locator('[name=counts_as_of]').fill('2026-10-12');form.locator('[name=counts_text]').fill('1/50\n2/49');form.locator('[type=submit]').click();page.wait_for_function("()=>!document.querySelector('#apply-workbook').disabled")
            assert not store.snapshot()['workbooks'];assert '90' in page.locator('#workbook-preview').inner_text();passed('preview does not write records; conserved totals shown')
            form.locator('[name=counts_text]').focus();page.select_option('#language','vi');assert form.locator('[name=counts_text]').input_value()=='1/50\n2/49';assert form.locator('[name=counts_as_of]').input_value()=='2026-10-12';assert page.locator('#workbook-file').evaluate('(e)=>e.files[0].name')==file.name;page.select_option('#language','zh');passed('language change keeps chosen file, date and allocation')
            def lose_committed_response(route):
                route.fetch();route.abort('failed');page.unroute('**/api/workbook/import',lose_committed_response)
            page.route('**/api/workbook/import',lose_committed_response);page.locator('#apply-workbook').click();page.wait_for_function("()=>!document.querySelector('#apply-workbook').disabled")
            assert '尚未確認' in form.locator('.form-error').inner_text();assert len(store.snapshot()['workbooks'])==1;page.locator('#apply-workbook').click();page.wait_for_function("()=>document.querySelector('#workbook-preview').childElementCount===0");assert len(store.snapshot()['batches'])==2;passed('lost committed import response retries without duplicate or false save')
            page.locator('nav [href="#daily"]').click();page.wait_for_function("()=>document.querySelector('#home-metrics').textContent.includes('90')");assert page.locator('#home-legacy-note').is_visible();passed('source baseline dashboard with provisional allocation notice')
            page.locator('nav [href="#settings"]').click();page.locator('#workbook-sources > details > summary').click()
            with page.expect_download() as download_info:page.locator('[data-download-source]').click()
            original=download_info.value;path=folder/'download.xlsx';original.save_as(path);assert path.read_bytes()==file.read_bytes();assert original.suggested_filename==file.name;passed('original Excel download is byte-identical and correctly named')
            page.locator('#batch-settings > details > summary').first.click();page.locator('#batch-settings [data-edit=batches]').first.click();page.locator('#batch-form > details > summary').click();batch_form=page.locator('#batch-form');assert batch_form.locator('[name=entry_count]').evaluate('(e)=>!e.readOnly&&!e.required');batch_form.locator('[name=entry_age]').fill('77');batch_form.locator('.primary').click();page.wait_for_function('()=>pending===null');page.wait_for_timeout(150);assert store.snapshot()['batches'][0]['entry_age_days']==77;passed('administrator age correction keeps unknown entry count and source references')
            page.locator('nav [href="#history"]').click();hist=page.locator('#history-filter');hist.locator('[name=from]').fill('2026-10-14');hist.locator('[name=to]').fill('2026-10-14');hist.locator('[name=type]').select_option('sale');hist.locator('button').first.click();page.wait_for_function("()=>document.querySelector('#history-results').textContent.includes('肉豬各周存欄頭數')&&document.querySelectorAll('#history-results tbody tr').length===1");assert page.locator('#history-results tbody tr').count()==1;assert not page.locator('#history-results [data-edit]').count();passed('history source records are readonly and date/type filtered')
            page.locator('nav [href="#daily"]').click();page.locator('[data-add-barn]').first.click();movement=page.locator('#movement-form');movement.locator('[name=quantity]').fill('1');movement.locator('[name=type]').select_option('death');movement.locator('[name=date]').fill('2026-10-14');movement.locator('.primary').click();page.wait_for_function("()=>document.querySelector('#movement-form .form-error').textContent.includes('来源表')||document.querySelector('#movement-form .form-error').textContent.includes('來源表')");assert not store.snapshot()['movements'];movement.locator('[name=date]').fill('2026-10-15');movement.locator('.primary').click();page.wait_for_function('()=>pending===null');page.wait_for_timeout(150);assert len(store.snapshot()['movements'])==1;passed('baseline re-entry blocked; next-day new death stored once')
            page.locator('nav [href="#stats"]').click();stats=page.locator('#stats-filter');stats.locator('[name=from]').fill('');stats.locator('[name=to]').fill('2026-10-13');stats.locator('button').first.click();page.wait_for_function("()=>document.querySelector('#stats-results').textContent.includes('2026-10-13')&&document.querySelector('#stats-results .metrics').textContent.includes('—')");page.locator('[data-key=other-statistics] > summary').click();assert '—' in page.locator('#stats-results .metrics').inner_text();passed('incomplete historical date renders unknown, not zero')
            page.set_viewport_size({'width':390,'height':844});page.locator('nav [href="#settings"]').click();assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+2');assert not errors;passed('source review mobile layout and no uncaught JavaScript errors');browser.close()
    finally:server.shutdown();server.server_close()
(root/'artifacts/legacy-browser-results.json').write_text(json.dumps({'version':VERSION,'type':'real Chromium with synthetic Excel; public mobile network not tested','passed':results},ensure_ascii=False,indent=2))
print('Completed',len(results),'legacy browser scenarios')
