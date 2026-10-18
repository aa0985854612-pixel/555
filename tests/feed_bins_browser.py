"""Real Chromium/HTTP, user-configured bin topology with synthetic records."""
import sys,tempfile,threading,uuid,json,io,csv,subprocess,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from app.feed import initial_bins,YANG_QUAN_BARNS
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(s):checks.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');owner=store.create_user('owner','83000011');store.create_user('worker','83000012','staff');store.create_user('reader','83000013','viewer')
 def add(kind,**d):return store.mutate(owner,kind,d,str(uuid.uuid4()))
 barns=[add('barns',name=f'{n}棟',feed_vendor='養全' if n in YANG_QUAN_BARNS else '新農科') for n in range(1,25)];batches=[add('batches',barn_id=b['id'],name='PAIR' if i<2 else f'B{i+1}',entry_date='2026-10-01',entry_count=100,entry_age_days=70,status='active') for i,b in enumerate(barns)];bins=[add('feed_bins',**b) for b in initial_bins(barns)];by_name={b['name']:b for b in bins}
 original=store.export_backup()['users'];server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(name,password):page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(password);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])');page.wait_for_function('()=>data?.feed_bins?.length===23')
   page.goto(url);login('owner','83000011');page.locator('nav [href="#feed"]').click();f=page.locator('#feed-order-form');assert f.locator('[name=item]').evaluate('(e)=>e.tagName')=='SELECT';assert f.locator('[name=item] option').all_text_contents()==['請選擇','大豬料','仔豬料','哺乳二期料'];assert f.locator('[name=feed_bin_id] option').count()==24
   page.locator('nav [href="#settings"]').click();page.locator('#barn-form').evaluate('(e)=>e.closest("details").open=true');assert page.locator('#barn-settings .table-wrap').evaluate('(e)=>e.scrollWidth<=e.clientWidth+2');page.locator(f'[data-edit=barns][data-id="{barns[0]["id"]}"]').click();bf=page.locator('#barn-form');assert bf.locator('[name=feed_vendor]').input_value()=='養全';bf.locator('[name=feed_vendor]').select_option('新農科')
   with page.expect_response(lambda r:'/api/barns/' in r.url and r.request.method=='PUT') as saved:bf.locator('button.primary').click()
   assert saved.value.status==200;page.wait_for_function('()=>pending===null&&data.barns.find(b=>b.name==="1棟").feed_vendor==="新農科"')
   page.locator('nav [href="#feed"]').click();f.locator('[name=barn_id]').select_option(barns[0]['id']);assert f.locator('[name=vendor]').input_value()=='新農科';assert f.locator('[name=feed_bin_id]').input_value()==by_name['1、2']['id'];assert page.locator('#feed-vendor-warning').is_visible();assert not f.locator('[name=batch_id]').is_visible()
   f.locator('[name=barn_id]').select_option(barns[10]['id']);assert f.locator('[name=vendor]').input_value()=='新農科';assert f.locator('[name=feed_bin_id]').input_value()=='';assert f.locator('[name=feed_bin_id] option').count()==3;assert f.locator('[name=feed_bin_id]').evaluate('(e)=>e.required');f.locator('[name=feed_bin_id]').select_option(by_name['11-2']['id']);assert f.locator('[name=vendor]').input_value()=='新農科'
   f.locator('[name=barn_id]').select_option(barns[13]['id']);assert f.locator('[name=vendor]').input_value()=='養全';assert f.locator('[name=feed_bin_id]').input_value()=='';assert f.locator('[name=feed_bin_id] option').count()==3
   f.locator('[name=barn_id]').select_option(barns[2]['id']);assert f.locator('[name=vendor]').input_value()=='養全';assert f.locator('[name=feed_bin_id]').input_value()==by_name['3、4']['id'];f.locator('[name=amount]').fill('1.5')
   for repeat in range(3):
    page.select_option('#language','vi');page.select_option('#language','zh');page.evaluate('async()=>await refresh()');assert f.locator('[name=barn_id]').input_value()==barns[2]['id'];assert f.locator('[name=vendor]').input_value()=='養全';assert f.locator('[name=amount]').input_value()=='1.5'
   page.locator('nav [href="#settings"]').click();page.locator('#barn-form').evaluate('(e)=>e.closest("details").open=true');assert page.locator('#barn-settings .table-wrap').evaluate('(e)=>e.scrollWidth<=e.clientWidth+2');page.locator(f'[data-edit=barns][data-id="{barns[0]["id"]}"]').click();bf.locator('[name=feed_vendor]').select_option('養全')
   with page.expect_response(lambda r:'/api/barns/' in r.url and r.request.method=='PUT') as saved:bf.locator('button.primary').click()
   assert saved.value.status==200;page.wait_for_function('()=>pending===null&&data.barns.find(b=>b.name==="1棟").feed_vendor==="養全"');page.locator('nav [href="#feed"]').click();f.locator('[name=barn_id]').select_option('');assert not f.locator('[name=feed_bin_id]').evaluate('(e)=>e.required')
   passed('barn setting saves supplier; barn-first input auto-fills vendor and single/shared bin, dual bins require choice; three sync/language rounds retain draft')
   f.locator('[name=feed_bin_id]').select_option(by_name['1、2']['id']);assert f.locator('[name=vendor]').input_value()=='養全';assert page.locator('[data-feed-barn]').count()==2;f.locator('[name=item]').select_option('大豬料');f.locator('[name=display_unit]').select_option('ton');f.locator('[name=amount]').fill('2');f.locator('[name=date]').fill('2026-10-12')
   for i in range(3):
    page.select_option('#language','vi');page.select_option('#language','zh');page.evaluate('async()=>await refresh()');assert f.locator('[name=amount]').input_value()=='2';assert f.locator('[name=item]').input_value()=='大豬料';assert f.locator('[name=vendor]').input_value()=='養全';assert f.locator('[name=feed_bin_id]').input_value()==by_name['1、2']['id']
   passed('three type dropdown, 23 physical bins, confirmed default vendor and three language/sync rounds preserve draft')
   def save():
    f.locator('button.primary').click();page.wait_for_selector('#feed-review-dialog[open]')
    with page.expect_response(lambda r:'/api/feed-order-apply' in r.url and r.request.method=='POST') as response:page.locator('#feed-review-confirm').click()
    assert response.value.status==201,response.value.text();page.wait_for_function('()=>pending===null&&document.querySelector("#feed-order-form [name=amount]").value===""')
   save();first=store.snapshot()['feed_orders'][0];assert first['kg']==2000 and len(first['target_batch_ids'])==2 and first['allocations']==[];page.wait_for_selector('.feed-order-record');assert '1、2' in page.locator('.feed-order-record').inner_text();passed('shared-bin order is stored once with both batch identities and no invented kg allocations')
   for name in ('11-1','11-2'):
    f.locator('[name=feed_bin_id]').select_option(by_name[name]['id']);assert f.locator('[name=vendor]').input_value()=='新農科';f.locator('[name=item]').select_option('仔豬料');f.locator('[name=amount]').fill('1');save()
   assert len(store.snapshot()['feed_orders'])==3;passed('11-1 and 11-2 independently save to the same barn with the correct vendor')
   page.locator('nav [href="#stats"]').click();page.locator('#open-weekly-report').click();page.locator('#weekly-cohort').select_option('PAIR|2026-10-01');page.locator('#weekly-to').fill('2026-10-15');page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-export-actions:not([hidden])');text=page.locator('#weekly-sheet-body').inner_text();assert '養全' in text and '大豬料' in text and '10/12+2（1、2）' in text
   with page.expect_download() as download:page.locator('#weekly-csv').click()
   rows=list(csv.reader(io.StringIO(Path(download.value.path()).read_text(encoding='utf-8-sig'))));assert any('大豬料' in row for row in rows) and any('養全' in row for row in rows)
   page.locator('#weekly-print').evaluate('(e)=>window.print=()=>{}');page.locator('#weekly-print').click();page.pdf(path=str(root/'artifacts/feed-bins-weekly.pdf'),prefer_css_page_size=True,print_background=True);info=subprocess.check_output(['pdfinfo',str(root/'artifacts/feed-bins-weekly.pdf')],text=True);assert re.search(r'Pages:\s+1\b',info);passed('weekly header, shared-bin notation, actual CSV and one portrait A4 contain supplier and feed type')
   page.locator('#weekly-barn').select_option(barns[0]['id']);page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-export-actions:not([hidden])');assert '共用料桶未分攤' in page.locator('#weekly-sheet-body').inner_text();page.locator('#weekly-close').click();passed('single-barn weekly report labels the shared amount as unallocated, never half or full assigned kg')
   page.locator('nav [href="#feed"]').click();ff=page.locator('#feed-filter');ff.locator('[name=scope_type]').select_option('barn');ff.locator('[name=barn_id]').select_option(barns[0]['id']);ff.locator('button').first.click();page.wait_for_function('()=>document.querySelectorAll("#feed-order-results .feed-order-record").length===1');assert '共用' in page.locator('#feed-order-results').inner_text();assert '0 kg' in page.locator('#feed-order-total').inner_text();q=page.evaluate('query(document.querySelector("#feed-filter"))');rows=list(csv.DictReader(io.StringIO(page.request.get(url+'/api/export?kind=feed_orders&'+q).text().lstrip('\ufeff'))));assert rows[0]['feed_bin']=='1、2' and rows[0]['selected_allocated_kg']=='' and rows[0]['feed_scope_state']=='shared_unallocated';passed('filtered history and CSV retain exact shared kg as reference with an empty per-barn allocation')
   page.locator('#feed-order-results [data-edit]').click();assert f.locator('[name=feed_bin_id]').input_value()==by_name['1、2']['id'];assert f.locator('[name=item]').input_value()=='大豬料';assert page.locator('[data-feed-barn]').count()==2;f.locator('[data-action=cancelEdit]').click();passed('editing an existing shared order restores its own bin, type and both batches')
   page.locator('nav [href="#settings"]').click();page.locator('#feed-bin-settings').evaluate('(e)=>e.open=true');page.wait_for_selector('.feed-bin-row');assert page.locator('.feed-bin-row').count()==23;page.locator(f'[data-edit=feed_bins][data-id="{by_name["14-1"]["id"]}"]').click();assert page.locator('#feed-bin-form [name=vendor]').input_value()=='養全';page.locator('#feed-bin-form [data-action=cancelEdit]').click();passed('admin can inspect supplier and membership of each bin without merging barn IDs')
   page.locator('nav [href="#feed"]').click();cases=0
   for width in (320,390,768,1366):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.select_option('#language',language)
     for size in ('small','medium','large'):
      page.locator('#font-control').evaluate('(e)=>e.open=true');page.locator(f'[data-text-size={size}]').click();page.locator('#font-control').evaluate('(e)=>e.open=false');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'),(width,language,size);cases+=1
   page.set_viewport_size({'width':390,'height':844});page.select_option('#language','zh');page.screenshot(path=str(root/'artifacts/feed-bins-mobile.png'),full_page=True);passed(f'{cases} viewport/language/font combinations fit without page overflow')
   page.locator('#logout').click();login('reader','83000013');page.locator('nav [href="#feed"]').click();assert f.locator('.primary').is_disabled();assert page.evaluate('async()=>{const r=await fetch("/api/feed_bins",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":me.csrf,"Idempotency-Key":crypto.randomUUID()},body:"{}"});return r.status}')==403
   assert store.export_backup()['users']==original;assert not errors,errors;passed('viewer cannot bypass supplier/bin write permissions; account hashes preserved and no browser errors')
   browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/feed-bins-browser-results.json').write_text(json.dumps({'version':VERSION,'mode':'Chromium real HTTP / synthetic SQLite, mobile viewport simulation; no physical phone','checks':checks},ensure_ascii=False,indent=2));print('Completed',len(checks),'feed bin scenarios')
