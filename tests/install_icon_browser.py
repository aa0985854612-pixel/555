"""Real Chromium manifest and offline asset checks; no physical-phone installation claim."""
import json,re,struct,sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];results=[]
def passed(s):results.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as folder:
 store=Store(Path(folder)/'db');server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   ctx=p.chromium.launch_persistent_context(str(Path(folder)/'browser-profile'),executable_path='/usr/bin/chromium',args=['--no-sandbox'],headless=True,viewport={'width':390,'height':844});page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(base);page.wait_for_function('()=>navigator.serviceWorker.controller!==null');page.wait_for_function('()=>document.querySelector(".brand-icon img").naturalWidth===192')
   manifest_path=page.locator('link[rel=manifest]').get_attribute('href');assert VERSION in manifest_path;response=page.request.get(base+manifest_path);assert response.headers['content-type'].startswith('application/manifest+json');manifest=response.json();assert manifest['id']=='/' and manifest['start_url']=='/';assert manifest['name']==manifest['short_name']=='嘉得肉豬紀錄';passed('versioned manifest keeps app identity and Jia De home-screen name')
   assert {i['purpose'] for i in manifest['icons']}=={'any','maskable'}
   for icon in manifest['icons']:
    assert re.fullmatch(r'/jiade-icon-(?:192|512|maskable)-v[0-9.]+\.png',icon['src']);response=page.request.get(base+icon['src']);raw=response.body();assert response.status==200 and response.headers['content-type'].startswith('image/png');assert raw[:8]==b'\x89PNG\r\n\x1a\n';w,h=struct.unpack('>II',raw[16:24]);assert f'{w}x{h}'==icon['sizes']
   assert any(i['sizes']=='192x192' and i['purpose']=='any' for i in manifest['icons']);assert any(i['sizes']=='512x512' and i['purpose']=='maskable' for i in manifest['icons']);passed('Android regular and adaptive maskable icons are real PNGs with declared dimensions')
   apple=page.locator('link[rel=apple-touch-icon]').get_attribute('href');raw=page.request.get(base+apple).body();assert struct.unpack('>II',raw[16:24])==(180,180) and re.fullmatch(r'/jiade-icon-180-v[0-9.]+\.png',apple);assert page.locator('meta[name=apple-mobile-web-app-title]').get_attribute('content')=='嘉得肉豬紀錄';assert page.locator('link[rel=icon]').get_attribute('href')==next(i['src'] for i in manifest['icons'] if i['sizes']=='192x192');passed('iPhone touch icon and browser favicon point to the new pig image')
   session=ctx.new_cdp_session(page);parsed=session.send('Page.getAppManifest');assert not parsed.get('errors');assert json.loads(parsed['data'])['name']=='嘉得肉豬紀錄';installability=session.send('Page.getInstallabilityErrors');assert not installability['installabilityErrors'],installability;passed('Chromium parses the manifest and reports no installability errors')
   urls=[i['src'] for i in manifest['icons']]+[apple];ctx.set_offline(True);assets=page.evaluate('async(urls)=>await Promise.all(urls.map(async u=>{const r=await fetch(u);return {ok:r.ok,type:r.headers.get("content-type"),bytes:(await r.arrayBuffer()).byteLength}}))',urls);assert all(x['ok'] and x['type'].startswith('image/png') and x['bytes']>0 for x in assets);ctx.set_offline(False);passed('all Android and iPhone icons remain available from the new offline cache')
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900});assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+2')
   passed('new header image fits phone, tablet and desktop widths')
   preview=ctx.new_page();preview.set_content('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><style>body{font:18px system-ui;background:#edf0f4;padding:32px;color:#192e50}main{display:flex;gap:36px}figure{margin:0;text-align:center}img{width:120px;height:120px;box-shadow:0 2px 12px #0002}figcaption{margin-top:14px}p{font-size:14px}h1{font-size:24px}</style></head><body><h1>嘉得肉豬紀錄</h1><p>瀏覽器圖示預覽，非手機桌面截圖</p><main><figure><img style="border-radius:28px" src="'+base+next(i['src'] for i in manifest['icons'] if i['sizes']=='512x512' and i['purpose']=='any')+'"><figcaption>圓角圖示模擬</figcaption></figure><figure><img style="border-radius:50%" src="'+base+next(i['src'] for i in manifest['icons'] if i['purpose']=='maskable')+'"><figcaption>圓形裁切模擬</figcaption></figure></main></body></html>');preview.wait_for_function('()=>Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)');preview.screenshot(path=str(root/'artifacts/jiade-install-icon-preview.png'),full_page=True);assert not errors;passed('generated icon previews render without JavaScript errors');ctx.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/install-icon-browser-results.json').write_text(json.dumps({'version':VERSION,'mode':'real Chromium, isolated localhost; no physical phone installation','passed':results},ensure_ascii=False,indent=2));print('Completed',len(results),'install-icon browser checks')
