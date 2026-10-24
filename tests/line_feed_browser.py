"""Real browser and HTTP exercise of LINE setup, photo intake and human approval."""
import base64,hashlib,hmac,json,os,sys,tempfile,threading,uuid
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,encode
from app.server import Server
from app import line_feed as line
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);checks=[]
env={'LINE_CHANNEL_SECRET':'synthetic-secret','LINE_CHANNEL_ACCESS_TOKEN':'synthetic-line','OPENAI_API_KEY':'synthetic-openai'}
group='C'+'1'*32
def passed(text):checks.append(text);print('PASS '+text,flush=True)

with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{k:'' for k in env}),patch.object(line,'_image',return_value=(b'synthetic','image/jpeg')),patch.object(line,'recognize',return_value=[{'date':'2026-10-24','bin':'13','vendor':'新農科','item':'大豬料','tons':4,'note':'中午前；林可黴素220ppm、旭維康1kg','warning':'請核對年份'}]),patch.object(line,'_reply'):
    s=Store(Path(tmp)/'db');owner=s.create_user('owner','83000011');reader=s.create_user('reader','83000012','viewer')
    def add(kind,**b):return s.mutate(owner,kind,b,str(uuid.uuid4()))
    barn=add('barns',name='13棟');batch=add('batches',name='JD-28',barn_id=barn['id'],entry_date='2026-10-01',entry_count=100,entry_age_days=70,status='active');bin=add('feed_bins',name='13',vendor='新農科',barn_ids=[barn['id']],active=True)
    server=Server(('127.0.0.1',0),s);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://127.0.0.1:'+str(server.server_port)
    def send(message):
        event={'type':'message','webhookEventId':'event-1001','replyToken':'synthetic-reply','timestamp':1792800000000,'source':{'type':'group','groupId':group,'userId':'synthetic-sender'},'message':message}
        raw=encode({'events':[event]}).encode();sig=base64.b64encode(hmac.new(env['LINE_CHANNEL_SECRET'].encode(),raw,hashlib.sha256).digest()).decode()
        with urlopen(Request(url+'/api/line/webhook',raw,{'X-Line-Signature':sig,'Content-Type':'application/json'}),timeout=10) as r:return json.load(r)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':900},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            def login(name,pw,destination=url):
                page.goto(destination);page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(pw);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])');page.locator('nav [href="#feed"]').click()
            login('owner','83000011');assert page.locator('#line-feed-settings').is_hidden();assert 'LINE' not in page.locator('#feed-drafts').inner_text();assert page.locator('#bin-stock-panel').is_hidden();assert page.locator('#delivery-results').locator('..').is_hidden();passed('unused LINE, inventory and empty receipts are hidden; draft help has no unavailable LINE reference')
            os.environ.update(env);page.reload();page.wait_for_selector('#workspace:not([hidden])');page.locator('nav [href="#feed"]').click();page.locator('#feed-drafts>summary').click();page.wait_for_selector('#line-feed-settings:not([hidden])');page.locator('#line-feed-settings>summary').click();page.wait_for_function('()=>!document.querySelector("#line-feed-pair").disabled');page.locator('#line-feed-pair').click();page.wait_for_selector('#line-feed-code:not([hidden])');command=page.locator('#line-feed-command').inner_text();assert command.startswith('綁定飼料 ');send({'type':'text','text':command});page.wait_for_function('()=>!document.querySelector("#line-feed-refresh").disabled');page.locator('#line-feed-refresh').click();page.wait_for_function('()=>document.querySelector("#line-feed-binding").textContent.includes("已綁定")');passed('admin generates one-time pairing command and signed LINE group webhook binds without a browser session')
            for width in (320,390,768,1440):
                page.set_viewport_size({'width':width,'height':900})
                for language in ('zh','vi'):
                    page.select_option('#language',language);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'),(width,language)
            page.select_option('#language','zh');page.set_viewport_size({'width':390,'height':900});page.locator('#line-feed-settings').screenshot(path=str(root/'artifacts/line-feed-setup-mobile.png'));passed('LINE setup fits 320/390/768/1440 widths in Chinese and Vietnamese')
            send({'type':'image','id':'1001'});send({'type':'image','id':'1001'});assert len(s.snapshot()['feed_drafts'])==1;assert not s.snapshot()['feed_orders'];page.locator('#feed-draft-refresh').click();page.wait_for_selector('[data-open-feed-draft]');page.locator('[data-open-feed-draft]').first.click();assert page.locator('[data-draft-field=tons]').input_value()=='4';assert '林可黴素220ppm' in page.locator('[data-draft-field=note]').input_value();assert '請核對年份' in page.locator('.feed-draft-row').inner_text();page.locator('#feed-draft-prepare').click();page.wait_for_selector('#feed-draft-preview:not([hidden])');assert page.locator('#feed-draft-confirm').is_disabled();assert not s.snapshot()['feed_orders'];passed('signed image creates one editable pending draft, preserves drug units and warnings, and duplicate webhook does not add feed')
            page.locator('#feed-draft-close').click();draft=s.snapshot()['feed_drafts'][0];page.goto(url+'/?feed_draft='+draft['id']+'#feed');page.wait_for_selector('#feed-draft-dialog[open]');assert 'feed_draft=' not in page.url;page.locator('[data-draft-field=tons]').fill('5');page.locator('#feed-draft-prepare').click();page.wait_for_selector('#feed-draft-preview:not([hidden])');assert page.locator('#feed-draft-confirm').is_disabled();page.locator('#feed-draft-ack').check();page.locator('#feed-draft-confirm').click();page.wait_for_selector('#feed-draft-dialog',state='hidden');assert s.snapshot()['feed_orders'][0]['kg']==5000;assert s.snapshot()['feed_drafts'][0]['status']=='confirmed';send({'type':'image','id':'1002'});assert len(s.snapshot()['feed_orders'])==1;assert len(s.snapshot()['feed_drafts'])==1;passed('LINE review deep link opens exact draft; editing and explicit website checkbox are required before a single formal write')
            page.locator('#line-feed-settings>summary').click();page.wait_for_function('()=>!document.querySelector("#line-feed-disconnect").disabled');page.on('dialog',lambda d:d.accept());page.locator('#line-feed-disconnect').click();page.wait_for_function('()=>document.querySelector("#line-feed-binding").textContent.includes("尚未綁定")');send({'type':'image','id':'1003'});assert len(s.snapshot()['feed_drafts'])==1;page.locator('#logout').click();page.wait_for_selector('#login-view:not([hidden])');login('reader','83000012');assert page.locator('#line-feed-settings').is_hidden();assert page.evaluate('async()=>{try{await api("/api/line/status");return 200}catch(e){return e.status}}')==403;assert not errors,errors;passed('disconnect stops intake while preserving records; viewer cannot see settings or query integration status');browser.close()
    finally:server.shutdown();server.server_close()
print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False))
