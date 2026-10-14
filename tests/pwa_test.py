"""Actual Chromium SW upgrade lifecycle with simulated old/new cache versions."""
import sys, tempfile, threading, shutil, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store
import app.server as server_module
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
    folder=Path(folder);static=folder/'static';shutil.copytree(root/'app/static',static)
    current=(static/'sw.js').read_text();(static/'sw.js').write_text(current.replace('pigledger-1.2.0','pigledger-0.9.0'))
    server_module.STATIC=static;store=Store(folder/'db.sqlite3');store.create_user('tester','browser-test-password')
    server=server_module.Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start()
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx=b.new_context();page=ctx.new_page();page.goto('http://127.0.0.1:'+str(server.server_port))
        page.wait_for_function('()=>navigator.serviceWorker.controller!==null')
        assert 'pigledger-0.9.0' in page.evaluate('()=>caches.keys()')
        page.locator('#login-form [name=username]').fill('tester');page.locator('#login-form [name=password]').fill('browser-test-password');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
        page.locator('#movement-form [name=quantity]').fill('7')
        (static/'sw.js').write_text(current);page.evaluate('async()=>{const r=await navigator.serviceWorker.getRegistration();await r.update()}')
        page.wait_for_function('async()=>!!(await navigator.serviceWorker.getRegistration()).waiting')
        page.locator('nav [href="#settings"]').click();page.wait_for_selector('#pwa-update:not([hidden])');page.locator('#pwa-update').click();page.wait_for_timeout(200)
        assert page.locator('#movement-form [name=quantity]').input_value()=='7'
        assert page.evaluate('async()=>!!(await navigator.serviceWorker.getRegistration()).waiting')
        page.evaluate("finishForm(document.querySelector('#movement-form'))")
        with page.expect_navigation(wait_until='networkidle'):
            page.locator('#pwa-update').click()
        page.wait_for_function("async()=>{const k=await caches.keys();return k.includes('pigledger-1.2.0')&&!k.includes('pigledger-0.9.0')}")
        keys=page.evaluate('async()=>{const cs=await caches.keys();const urls=[];for(const c of cs){for(const r of await (await caches.open(c)).keys())urls.push(r.url)}return urls}')
        assert not any('/api/' in u for u in keys)
        manifest=page.request.get('http://127.0.0.1:'+str(server.server_port)+'/manifest.webmanifest').json()
        assert any(i['sizes']=='192x192' for i in manifest['icons']);assert any(i['sizes']=='512x512' for i in manifest['icons'])
        b.close()
    server.shutdown();server.server_close()
(root/'artifacts/pwa-results.json').write_text(json.dumps({'type':'real Chromium, simulated old/new SW versions','checks':['old cache restored','unsaved input blocks activation','new version activates and removes old cache','API data never cached','192/512 PNG manifest icons']},indent=2))
print('PASS 5 PWA checks')
