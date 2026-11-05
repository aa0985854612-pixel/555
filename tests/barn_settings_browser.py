"""Safe configuration deletion through the real SQLite and Hrana-backed HTTP API."""
import json,os,sys,uuid
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
from ui_fixture import workspace_fixture
from app.store import VERSION
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);checks=[]
def passed(mode,message):checks.append(mode+': '+message);print('PASS '+checks[-1],flush=True)
with patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':'1','FEED_AUTO_ALLOCATION':'equal'}),sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for cloud in (False,True):
  mode='Hrana' if cloud else 'SQLite'
  with workspace_fixture(cloud=cloud) as farm:
   store=farm['store'];owner=farm['admin']
   def add(kind,**body):return store.mutate(owner,kind,body,str(uuid.uuid4()))
   extra={n:add('barns',name=f'{n}棟',feed_vendor='新農科') for n in (23,3,15,10,16,9,5,4)}
   linked=add('batches',name='JD-NEW-9',barn_id=extra[9]['id'],entry_date=farm['on'](30),entry_count=100,status='active')
   ended=add('batches',name='JD-ENDED-15',barn_id=extra[15]['id'],entry_date='2025-01-01',entry_count=0,status='ended')
   bin=add('feed_bins',name='16',barn_ids=[extra[16]['id']],vendor='新農科',active=False)
   baseline=store.export_backup();page=browser.new_page(viewport={'width':390,'height':900},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def login(target,name='owner',pin='83000111'):
    target.goto(farm['url']);target.fill('#login-form [name=username]',name);target.fill('#login-form [name=password]',pin);target.click('#login-form button');target.wait_for_function('()=>!!data?.dashboard')
   def remove(n):
    page.locator('[data-barn-delete="'+extra[n]['id']+'"]').click();page.wait_for_selector('#barn-delete-dialog[open]')
   def close():page.click('#barn-delete-cancel');page.wait_for_selector('#barn-delete-dialog',state='hidden')
   def confirm():page.click('#barn-delete-confirm');page.wait_for_function('()=>pending===null')
   def audit_deletes(id):return [a for a in store.export_backup()['audit'] if a['kind']=='barns' and a['record_id']==id and a['action']=='delete']
   def api_delete(target,kind,id,revision,csrf=True):return target.evaluate('''async args=>{const headers={'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()};if(args.csrf)headers['X-CSRF-Token']=me.csrf;const r=await fetch('/api/'+args.kind+'/'+args.id,{method:'DELETE',headers,body:JSON.stringify({revision:args.revision})});return {status:r.status,body:await r.json()}}''',{'kind':kind,'id':id,'revision':revision,'csrf':csrf})
   login(page);page.click('nav [href="#settings"]');page.locator('#barn-form').evaluate('(e)=>e.closest("details").open=true');page.select_option('#batch-status','');groups=page.locator('#batch-settings .cohort-setting').evaluate_all('(es)=>es.map(e=>e.dataset.cohortKey)')
   labels=page.locator('#barn-settings tbody tr td:first-child strong').all_text_contents();assert labels==[f'{n}棟' for n in (1,2,3,4,5,8,9,10,12,14,15,16,23,24)],labels;assert groups[0].startswith('JD-NEW-9|') and groups[-1].startswith('JD-ENDED-15|');passed(mode,'standalone barn settings are numeric while batch groups retain their original date-based order')
   page.locator('[data-edit=barns][data-id="'+extra[10]['id']+'"]').click();page.fill('#barn-form [name=name]','23棟');page.locator('#barn-form button.primary').click();page.wait_for_function('()=>document.querySelector("#barn-form .form-error").textContent.includes("同名")');remove(10);assert page.locator('#barn-delete-name').inner_text()=='10棟';assert page.locator('#barn-delete-confirm').is_enabled();close();assert page.locator('#barn-form [name=name]').input_value()=='23棟';assert not audit_deletes(extra[10]['id']);passed(mode,'duplicate-name editing does not change the deletion target; cancel keeps the unsaved correction and writes nothing')
   remove(10);confirm();page.wait_for_selector('[data-barn-delete="'+extra[10]['id']+'"]',state='detached');assert page.locator('#barn-form [name=name]').input_value()=='';assert page.locator('#barn-form').get_attribute('data-edit-id') is None;assert any(b['id']==extra[23]['id'] for b in store.snapshot()['barns']);raw=next(r for r in store.export_backup()['records'] if r['id']==extra[10]['id']);assert raw['deleted']==1 and len(audit_deletes(extra[10]['id']))==1;passed(mode,'confirmed delete removes the exact unused barn from the visible list and selectors, clears its editor and retains a soft-delete audit')
   page.locator('[data-edit=barns][data-id="'+extra[3]['id']+'"]').click();page.fill('#barn-form [name=name]','第三棟草稿');remove(23);confirm();page.wait_for_selector('[data-barn-delete="'+extra[23]['id']+'"]',state='detached');assert page.locator('#barn-form [name=name]').input_value()=='第三棟草稿';assert page.locator('#barn-form').get_attribute('data-edit-id')==extra[3]['id'];passed(mode,'deleting a different unused row preserves the current barn draft and original editing identity')
   for n,text in ((9,'JD-NEW-9'),(15,'JD-ENDED-15'),(16,'16')):
    remove(n);assert page.locator('#barn-delete-confirm').is_disabled();assert text in page.locator('#barn-delete-links').inner_text();close();assert not audit_deletes(extra[n]['id'])
   blocked=api_delete(page,'barns',extra[16]['id'],extra[16]['revision']);assert blocked['status']==400 and blocked['body']['error']=='referenced_record';passed(mode,'active and ended batches plus inactive bin references are explained and blocked; direct API calls cannot bypass reference validation')
   def lost(route):response=route.fetch();assert response.status==200;route.abort('failed')
   page.route('**/api/barns/'+extra[5]['id'],lost);remove(5);page.click('#barn-delete-confirm');page.wait_for_selector('#pending:not([hidden])');assert len(audit_deletes(extra[5]['id']))==1;page.unroute('**/api/barns/'+extra[5]['id']);page.click('#retry');page.wait_for_function('()=>pending===null');page.wait_for_selector('[data-barn-delete="'+extra[5]['id']+'"]',state='detached');assert len(audit_deletes(extra[5]['id']))==1;assert page.locator('#barn-form [name=name]').input_value()=='第三棟草稿';passed(mode,'lost delete response and same-key retry produce one tombstone and one audit while preserving an unrelated draft')
   remove(3);race=add('batches',name='JD-RACE-3',barn_id=extra[3]['id'],entry_date=farm['on'](80),entry_count=0,status='active');confirm();assert '關聯' in page.locator('#barn-form .form-error').inner_text();assert any(b['id']==extra[3]['id'] for b in store.snapshot()['barns']);assert not audit_deletes(extra[3]['id']);page.evaluate('async()=>await refresh()');remove(3);assert page.locator('#barn-delete-confirm').is_disabled() and 'JD-RACE-3' in page.locator('#barn-delete-links').inner_text();close();passed(mode,'a batch attached after confirmation opens is caught transactionally without deleting the barn or leaving a partial write')
   remove(4);updated=store.mutate(owner,'barns',extra[4]|{'name':'4棟（更正）'},str(uuid.uuid4()),extra[4]['id']);confirm();assert not audit_deletes(extra[4]['id']);assert next(b for b in store.snapshot()['barns'] if b['id']==extra[4]['id'])['name']=='4棟（更正）';page.evaluate('async()=>await refresh()');passed(mode,'stale revision rejects the delete and preserves another user\'s renamed barn')
   denied=api_delete(page,'barns',extra[4]['id'],updated['revision'],False);assert denied['status']==403;old=store.snapshot()['movements'][0];denied=api_delete(page,'movements',old['id'],old['revision']);assert denied['status']==400 and denied['body']['error']=='void_preview_required';passed(mode,'CSRF checks remain enforced and ordinary movement deletes still require their original void preview')
   remove(4)
   for language in ('vi','zh'):
    page.evaluate('(l)=>{lang=l;translate()}',language)
    for width in (320,390,768,1440):
     page.set_viewport_size({'width':width,'height':900});page.evaluate('document.documentElement.dataset.textSize="large"');assert page.locator('#barn-delete-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
   page.set_viewport_size({'width':390,'height':900});page.evaluate('document.documentElement.dataset.textSize="medium"');page.screenshot(path=str(root/f'artifacts/barn-delete-{mode}.png'));close();passed(mode,'dedicated confirmation remains bilingual and fits phone/tablet/desktop widths including large text')
   for name,pin in (('worker','83000112'),('reader','83000113')):
    other=browser.new_page();login(other,name,pin);other.click('nav [href="#settings"]');assert other.locator('[data-barn-delete]').count()==0;result=api_delete(other,'barns',extra[4]['id'],updated['revision']);assert result['status']==403;assert not other.evaluate('(id)=>data.barns.some(b=>b.id===id)',extra[10]['id']);other.close()
   passed(mode,'staff and viewer cannot delete in UI or API; another device sees the synchronized removal')
   before={r['id']:r for r in baseline['records']};after={r['id']:r for r in store.export_backup()['records']};allowed={extra[n]['id'] for n in (10,23,5,4)};assert all(after[k]==v for k,v in before.items() if k not in allowed);assert store.export_backup()['users']==baseline['users'];assert not errors,errors;page.close();passed(mode,'every original movement/feed/weight record, linked batch, original ID and account remains unchanged with no JavaScript errors')
 browser.close()
(root/'artifacts/barn-settings-results.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'real Chromium/HTTP/isolated SQLite and CloudStore with Hrana fixture; no production farm writes'},ensure_ascii=False,indent=2));print('Completed',len(checks),'barn settings scenarios')
