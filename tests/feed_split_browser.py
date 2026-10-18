"""Real HTTP/Chromium: one bin, two cohorts, exact portions, two A4 sheets."""
import csv,io,json,re,subprocess,sys,tempfile,threading,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from app.domain import herd
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(s):checks.append(s);print('PASS',s,flush=True)
with tempfile.TemporaryDirectory() as temp:
 s=Store(Path(temp)/'db');u=s.create_user('owner','83000011');s.create_user('reader','83000012','viewer')
 def add(kind,**d):return s.mutate(u,kind,d,str(uuid.uuid4()))
 barns={n:add('barns',name=f'{n}棟',feed_vendor='養全') for n in (1,2,3,4,18)}
 batches={n:add('batches',name='JD-A' if n in (1,18) else 'JD-B',barn_id=b['id'],entry_date='2026-10-01',entry_age_days=70,entry_count=100,status='active') for n,b in barns.items()}
 bin=add('feed_bins',name='1、2',barn_ids=[barns[n]['id'] for n in (1,2)],vendor='養全',active=True)
 server=Server(('127.0.0.1',0),s);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}';before=s.export_backup()['users'];stock=herd(s.snapshot()['batches'],[],'2026-10-18')
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(name,pw):page.goto(url);page.locator('#login-form [name=username]').fill(name);page.locator('#login-form [name=password]').fill(pw);page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   login('owner','83000011');page.locator('nav [href="#feed"]').click();f=page.locator('#feed-order-form');f.locator('[name=date]').fill('2026-10-12');f.locator('[name=feed_bin_id]').select_option(bin['id']);assert f.locator('[name=feed_bin_id] option:checked').inner_text()=='1 · 養全';f.locator('[name=item]').select_option('大豬料');f.locator('[name=display_unit]').select_option('ton');f.locator('[name=amount]').fill('4');f.locator('details').evaluate('(e)=>e.open=true');f.locator('[name=bin_split_confirmed]').check();a=f.locator(f'[data-bin-portion-barn="{barns[1]["id"]}"]');b=f.locator(f'[data-bin-portion-barn="{barns[2]["id"]}"]');a.fill('2');f.locator('.primary').click();assert not page.locator('#feed-review-dialog').evaluate('(e)=>e.open');assert '合計' in f.locator('.form-error').inner_text();assert not s.snapshot()['feed_orders'];b.fill('2')
   assert '1棟、18棟｜JD-A' in f.locator('[data-feed-barn]').first.locator('option:checked').inner_text();assert '2棟、3棟、4棟｜JD-B' in f.locator('[data-feed-barn]').nth(1).locator('option:checked').inner_text()
   for _ in range(3):
    page.select_option('#language','vi');page.select_option('#language','zh');page.evaluate('async()=>await refresh()');assert a.input_value()=='2' and b.input_value()=='2';assert f.locator('[name=bin_split_confirmed]').is_checked()
   a.focus();old=batches[1];s.mutate(u,'batches',old|{'note':'sync revision','revision':old['revision']},str(uuid.uuid4()),old['id']);page.evaluate('async()=>await refresh()');assert a.evaluate('(e)=>e===document.activeElement');assert a.input_value()=='2' and b.input_value()=='2'
   f.locator('.primary').click();page.wait_for_selector('#feed-review-dialog[open]');text=page.locator('#feed-review-body').inner_text();assert '4 噸' in text and '1棟、18棟｜JD-A' in text and '2棟、3棟、4棟｜JD-B' in text and text.count('2 噸')==2
   passed('bin shorthand 1, explicit 2+2 portions and full cohort labels; incomplete total rejected; three language/sync rounds preserve portions and preview')
   def lose(route):route.fetch();route.abort()
   page.route('**/api/feed-order-apply',lose);page.locator('#feed-review-confirm').click();page.wait_for_selector('#pending:not([hidden])');assert len(s.snapshot()['feed_orders'])==1;page.unroute('**/api/feed-order-apply',lose);page.reload();page.wait_for_selector('#workspace:not([hidden])');page.locator('nav [href="#feed"]').click();f=page.locator('#feed-order-form');f.locator('details').evaluate('(e)=>e.open=true');assert f.locator('[name=bin_split_confirmed]').is_checked()
   assert f.locator('[data-bin-portion-barn]').nth(0).input_value()=='2';assert f.locator('[data-bin-portion-barn]').nth(1).input_value()=='2';page.locator('#retry').click();page.wait_for_function('()=>pending===null');assert len(s.snapshot()['feed_orders'])==1;record=s.snapshot()['feed_orders'][0];assert record['kg']==4000 and len(record['bin_allocations'])==2;assert not f.locator('[name=bin_split_confirmed]').is_checked()
   passed('lost response restores the exact split request; retry creates no duplicate and clears completed portions only after server success')
   page.locator('nav [href="#stats"]').click();page.locator('#open-weekly-report').click()
   for group,expected in [('JD-A',{'1棟','18棟'}),('JD-B',{'2棟','3棟','4棟'})]:
    page.locator('#weekly-cohort').select_option(group+'|2026-10-01');page.locator('#weekly-to').fill('2026-10-18');page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-export-actions:not([hidden])');page.wait_for_selector('#weekly-a4-preview img');page.locator('#weekly-sheet-body > details').evaluate('(e)=>e.open=true');sheet=page.locator('#weekly-sheet-body');assert '10/12+2（1）' in sheet.inner_text();assert '10/12+4' not in sheet.inner_text();assert all(x in sheet.inner_text() for x in expected)
    page.evaluate('()=>{window.splitDraws=[];const old=window.originalSplitDraw||CanvasRenderingContext2D.prototype.fillText;window.originalSplitDraw=old;CanvasRenderingContext2D.prototype.fillText=function(...a){splitDraws.push(a[0]);return old.apply(this,a)}}')
    page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-a4-preview img')
    with page.expect_download() as dl:page.locator('#weekly-print').click()
    pdf=root/f'artifacts/feed-split-{group}.pdf';dl.value.save_as(pdf);info=subprocess.check_output(['pdfinfo',str(pdf)],text=True);assert re.search(r'Pages:\s+1\b',info) and '595.28 x 841.89' in info;assert page.evaluate('splitDraws').count('10/12+2（1）')==1
    with page.expect_download() as dl:page.locator('#weekly-csv').click()
    rows=list(csv.reader(io.StringIO(Path(dl.value.path()).read_text(encoding='utf-8-sig'))));assert ['叫料登記量（噸）','2'] in rows;assert any('10/12+2（1）' in v for row in rows for v in row)
   page.locator('#weekly-close').click();passed('both cohort sheets independently show 2 tonnes with bin 1; downloaded CSV agrees and each actual PDF is one portrait A4')
   page.locator('nav [href="#feed"]').click();ff=page.locator('#feed-filter');ff.locator('[name=scope_type]').select_option('cohort');ff.locator('[name=cohort]').select_option('JD-A|2026-10-01');ff.locator('button').first.click();page.wait_for_function('()=>document.querySelector("#feed-order-results .order-quantity").textContent.includes("2")');assert '整桶 4 噸' in page.locator('#feed-order-results').inner_text();assert '2,000 kg' in page.locator('#feed-order-total').inner_text();query=page.evaluate('query(document.querySelector("#feed-filter"))');rows=list(csv.DictReader(io.StringIO(page.request.get(url+'/api/export?kind=feed_orders&'+query).text().lstrip('\ufeff'))));assert len(rows)==1 and rows[0]['quantity']=='4000.0' and float(rows[0]['selected_allocated_kg'])==2000 and rows[0]['feed_bin']=='1';assert len(json.loads(rows[0]['allocations']))==2
   page.locator('#feed-order-results [data-edit]').click();assert f.locator('[name=amount]').input_value()=='4';assert f.locator('[name=bin_split_confirmed]').is_checked();assert all(f.locator('[data-bin-portion-barn]').nth(i).input_value()=='2' for i in range(2));f.locator('[data-action=cancelEdit]').click();passed('filtered list, raw-total CSV with selected allocation and edit form keep scope and original physical total distinct')
   page.locator('#feed-order-results [data-edit]').click();cases=0
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.select_option('#language',language)
     for size in ('small','medium','large'):
      page.evaluate('(s)=>document.documentElement.dataset.textSize=s',size);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');assert f.locator('[name=bin_split_confirmed]').is_checked();cases+=1
   f.locator('[data-action=cancelEdit]').click();page.select_option('#language','zh');page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(root/'artifacts/feed-split-mobile.png'),full_page=True);passed(f'{cases} phone/tablet/desktop language/font layouts fit with portions retained')
   assert not errors,errors;assert s.export_backup()['users']==before;assert herd(s.snapshot()['batches'],[],'2026-10-18')==stock;assert not s.snapshot()['usages'];browser.close();passed('accounts, stock and FCR inputs unchanged; no browser errors')
 finally:server.shutdown();server.server_close()
(root/'artifacts/feed-split-browser-results.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'local real HTTP/Chromium/PDF, synthetic data; not physical phone/Safari/printer'},ensure_ascii=False,indent=2));print('Completed',len(checks),'split feed scenarios')
