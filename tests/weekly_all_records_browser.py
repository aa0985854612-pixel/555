"""The paper reads all saved feed, including future rows, from the original ledger."""
import collections,csv,io,json,os,sys,tempfile,threading,uuid,subprocess,re
from datetime import datetime as RealDatetime,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from app.feed import initial_bins
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);checks=[]
def passed(s):checks.append(s);print('PASS '+s,flush=True)
class Clock(RealDatetime):
 @classmethod
 def now(cls,tz=None):return RealDatetime(2026,10,25,4,tzinfo=timezone.utc).astimezone(tz)
with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'FEED_ORDERS_ARE_ARRIVALS':'1'}),patch('app.weekly.datetime',Clock):
 s=Store(Path(tmp)/'db');u=s.create_user('owner','83000011');s.create_user('reader','83000012','viewer')
 def add(kind,**body):return s.mutate(u,kind,body,str(uuid.uuid4()))
 barns={n:add('barns',name=f'{n}棟') for n in (1,2,3,4,5,6,7,8,12,13,14,15,16,17,18,19,20,21,22)}
 group={n:'WHITEBOARD-DEMO' if n in (13,22) else 'GROUP-'+str(next(i for i,g in enumerate(((1,2,3,4),(5,6,7),(8,12,14),(15,16,17),(18,19,20,21))) if n in g)) for n in barns}
 batches={n:add('batches',name=group[n],barn_id=b['id'],entry_date='2026-07-17',entry_count=100,entry_age_days=71,status='active') for n,b in barns.items()}
 for n in (13,22):batches[n]=s.mutate(u,'batches',batches[n]|{'entry_mean_kg':22.56},str(uuid.uuid4()),batches[n]['id'])
 lots=[{'date':'2026-07-17','count':60,'mean_kg':21.36},{'date':'2026-07-24','count':40,'mean_kg':22.2}]
 batches[15]=s.mutate(u,'batches',batches[15]|{'report_entry_lots':lots,'report_entry_lots_source':'verified'},str(uuid.uuid4()),batches[15]['id'])
 bins={b['name']:add('feed_bins',**b) for b in initial_bins(list(barns.values()))}
 old=add('batches',name='OLD-13',barn_id=barns[13]['id'],entry_date='2026-01-01',entry_count=100,status='ended')
 photo=[('養全','10-22',[('8',2),('12',8),('18',2),('21',2)]),('養全','10-27',[('8',4),('12',4),('14-1',8),('1、2',4),('3、4',4),('18',2),('21',2)]),('新農科','10-22',[('20',2),('7',2),('15-1',4),('22',2)]),('新農科','10-24',[('13',4)]),('新農科','10-26',[('5、6',2),('16、17',2),('20',2),('7',2),('13',4),('15-1',6),('19',2),('22',2)])]
 original=[]
 for vendor,on,rows in photo:
  for name,tons in rows:
   bin=bins[name];original.append(add('feed_orders',date='2026-'+on,kg=tons*1000,display_unit='ton',vendor=vendor,item='仔豬料',feed_bin_id=bin['id'],target_batch_ids=[b['id'] for b in batches.values() if b['barn_id'] in bin['barn_ids']]))
 assert len(original)==24 and sum(r['kg'] for r in original)==78000
 for typ,on,q in [('cull','2026-10-24',2),('cull','2026-10-26',3),('death','2026-10-24',1)]:add('movements',date=on,batch_id=batches[13]['id'],type=typ,quantity=q)
 add('movements',date='2026-10-25',batch_id=batches[13]['id'],type='sale',quantity=4,outgoing_destination='南投',note='上午出豬')
 source_barns=[add('barns',name=name) for name in ('23棟','24棟','第25棟')]
 for barn in source_barns:add('batches',name='SOURCE-TEST',barn_id=barn['id'],entry_date='2026-07-17',entry_count=10,entry_age_days=71,status='active')
 before=s.export_backup()['records'];server=Server(('127.0.0.1',0),s);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844},timezone_id='Asia/Taipei');errors=[];page.on('pageerror',lambda e:(errors.append(str(e)),print('BROWSER ERROR',e,flush=True)));page.on('response',lambda r: print('REPORT ERROR',r.status,r.text(),flush=True) if '/api/weekly-report?' in r.url and r.status!=200 else None)
   page.goto(url);page.locator('#login-form [name=username]').fill('owner');page.locator('#login-form [name=password]').fill('83000011');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])')
   page.evaluate('()=>{window.models=[];window.feedDraws=[];window.colourDraws=[];const pdf=weeklyPdf;window.weeklyPdf=async m=>{models.push(m);const result=await pdf(m);window.renderedPDF=result;return result};const draw=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...args){if(String(args[0]).includes("+"))feedDraws.push(args[0]);colourDraws.push({text:String(args[0]),colour:this.fillStyle,font:this.font,x:args[1],y:args[2]});return draw.apply(this,args)};}')
   page.locator('nav [href="#stats"]').click();page.locator('#stats-filter [name=from]').fill('2026-10-01');page.locator('#stats-filter [name=to]').fill('2026-10-20');page.locator('#stats-filter [name=barn_id]').select_option(barns[13]['id'],force=True)
   page.locator('#open-weekly-report').click();page.wait_for_selector('#weekly-a4-preview img');assert page.locator('#weekly-report-form input[type=date]').count()==0;assert page.locator('#weekly-barn').input_value()==barns[13]['id'];assert page.locator('#weekly-cohort').input_value()=='WHITEBOARD-DEMO|2026-07-17';assert page.locator('#weekly-report-form label').all_text_contents()[0].startswith('批號')
   page.locator('#weekly-cohort').select_option('GROUP-3|2026-07-17');page.wait_for_selector('#weekly-a4-preview img')
   page.locator('#weekly-barn').select_option(barns[15]['id']);page.wait_for_selector('#weekly-a4-preview img')
   entry_model=page.evaluate('models.at(-1)')
   assert [(e['date'],e['count'],e['mean']) for e in entry_model['headerEntries']]==[('2026-07-17',60,21.36),('2026-07-24',40,22.2)]
   page.wait_for_function("()=>colourDraws.some(d=>d.text==='7/24 40頭')")
   entry_draws=page.evaluate('colourDraws')
   assert {'7/17 60頭','7/24 40頭','2026-07-17','2026-07-24','7/17 21.36 kg','7/24 22.2 kg'} <= {d['text'] for d in entry_draws if 193<d['y']<223}, [d for d in entry_draws if 193<d['y']<223]
   page.locator('#weekly-cohort').select_option('SOURCE-TEST|2026-07-17');page.wait_for_selector('#weekly-a4-preview img')
   assert dict(page.evaluate('models.at(-1).basics'))['豬源']=='曾勝誠、殷慶盛'
   for barn in source_barns[:2]:
    page.locator('#weekly-barn').select_option(barn['id']);page.wait_for_selector('#weekly-a4-preview img')
    assert dict(page.evaluate('models.at(-1).basics'))['豬源']=='曾勝誠'
   page.locator('#weekly-cohort').select_option('WHITEBOARD-DEMO|2026-07-17');page.wait_for_selector('#weekly-a4-preview img')
   page.locator('#weekly-barn').select_option('');page.wait_for_selector('#weekly-a4-preview img')
   page.evaluate('colourDraws=[]');page.locator('#weekly-generate').click();page.wait_for_function("()=>colourDraws.some(d=>d.text==='入場均重：22.56 kg')")
   header_draws=page.evaluate("colourDraws.filter(d=>d.y>=193&&d.y<223).map(d=>d.text)")
   assert header_draws.count('入場日期：2026-07-17')==1 and header_draws.count('入場均重：22.56 kg')==1,header_draws
   page.locator('#weekly-barn').select_option(barns[13]['id']);page.wait_for_selector('#weekly-a4-preview img')
   labels=page.locator('#weekly-cohort option').all_text_contents();assert all('｜' in label and not re.search(r'2026-\d{2}-\d{2}',label) for label in labels);assert 'WHITEBOARD-DEMO｜13棟、22棟' in labels,labels
   assert page.locator('#weekly-barn option').all_text_contents()==['同批全部棟舍','13棟','22棟']
   def lines():return page.locator('#weekly-sheet-body .weekly-feed-entry').all_text_contents()
   assert lines()==['10/24+4(13)','10/26+4(13)'],lines();assert dict(page.evaluate('models.at(-1).totals'))['飼料到料（噸）']=='8';passed('batch-first selector shows batch and barns without entry dates; only matching barns are offered; old stats end date cannot hide the saved October 24/26 feed')
   page.evaluate('colourDraws=[]');page.locator('#weekly-generate').click();page.wait_for_function('()=>colourDraws.length>0');page.wait_for_selector('#weekly-a4-preview img')
   model=page.evaluate('models.at(-1)');bands=model['pages'][0]
   assert [band['headers'] for band in bands]==[[f'{week}週' for week in range(start,end+1)] for start,end in [(4,16),(17,29),(30,32)]]
   assert bands[0]['stages']==[['保育段棟舍',8],['肉豬段棟舍',5]] and bands[2]['summary']
   assert bands[0]['rows'][0]['cells'][:7]==['']*7
   rows=[row for band in bands for row in band['rows']];culls=[row for row in rows if row['label']=='淘汰數（隻）'];assert len(culls)==3 and sum(int(v) for row in culls for v in row['cells'] if v)==5
   assert all('淘汰' not in pair[0] for pair in model['totals']) and not any('淘汰' in note for note in model['shipping_notes']+model['death_notes'])
   assert model['nancyTemplate'] and model['survival']=='97.00'
   stats=page.request.get(url+'/api/statistics?batch_id='+batches[13]['id']+'&to=2026-10-25').json()
   assert stats['cumulative']['survival']==97
   assert stats['cumulative']['dead']==1 and stats['cumulative']['culled']==2
   colours=page.evaluate('colourDraws')
   reminders=[d for d in colours if 704<d['y']<762 and d['text'] in ('安排棟舍','豬隻秤重','安排空白料','起始日','開始出豬')]
   assert [d['text'] for d in reminders].count('安排棟舍')==2
   assert [d['text'] for d in reminders].count('豬隻秤重')==2
   assert [d['text'] for d in reminders].count('安排空白料')==1
   assert [d['text'] for d in reminders].count('開始出豬')==2
   assert all('Noto Serif CJK TC' in draw['font'] for draw in colours)
   assert {'牧場：嘉得','豬源：殷慶盛','肉豬批號：WHITEBOARD-DEMO','入場頭數：100 頭'} <= {draw['text'] for draw in colours}
   feed_fonts={d['font'] for d in colours if d['text'].startswith('+') and 355<d['y']<680}
   assert len(feed_fonts)==1 and next(iter(feed_fonts)).startswith(('700 ', 'bold ')),feed_fonts
   assert any(d['text']=='5' and 506<d['x']<554 and 532<d['y']<555 and d['colour']=='#111111' for d in colours)
   red=[d for d in colours if d['colour']=='#b42332' and d['text']]
   assert len(red)==2 and all(d['text']=='1' for d in red)
   assert any(506<d['x']<554 and 555<d['y']<580 for d in red)
   assert any(268<d['x']<363 and 854<d['y']<884 for d in red)
   death_note=next(d for d in colours if d['text']=='10/24 死亡1隻')
   assert death_note['colour']=='#111111' and death_note['y']<842
   assert any(d['text']=='出豬備註' and 762<d['y']<792 for d in colours)
   shipping_draws=[d['text'] for d in colours if d['x']>363 and 792<d['y']<1161]
   assert shipping_draws==['10/25 南投4 · 上午出豬'],shipping_draws
   assert any(d['text']=='起始日' and '17px' in d['font'] for d in colours)
   feed_plus=[d for d in colours if d['text']=='+4(13)' and 580<d['y']<680]
   assert len(feed_plus)==2 and feed_plus[0]['x']==feed_plus[1]['x'],feed_plus
   assert all(d['font'].startswith(('700 ', 'bold ')) for d in colours if re.fullmatch(r'(1[7-9]|2[0-9])w',d['text']) and 478<d['y']<508)
   assert page.locator('#weekly-sheet-body .weekly-death td').first.evaluate('(e)=>getComputedStyle(e).color')=='rgb(180, 35, 50)';assert page.locator('#weekly-sheet-body .weekly-death-entry').first.evaluate('(e)=>getComputedStyle(e).color')=='rgb(17, 17, 17)';assert page.locator('#weekly-sheet-body .weekly-total-death strong').evaluate('(e)=>getComputedStyle(e).color')=='rgb(180, 35, 50)'
   preview=root/'artifacts/weekly-red-deaths-culls.jpg';preview.write_bytes(bytes(page.evaluate('async()=>Array.from(new Uint8Array(await renderedPDF.previewPages[0].arrayBuffer()))')))
   from PIL import Image
   image=Image.open(preview).convert('RGB')
   # Main table, totals, and vaccine rows use the same single-width rule.
   gray=image.convert('L')
   grid_x=round((image.width-690*.79*5)/2+(300-62)*.79*5)
   for grid_y in (792,823,854,884,926,952,975,1007,1036,1063,1089):
    line_y=round(105+(grid_y-69)*.72*5)
    assert gray.getpixel((grid_x,line_y))<130
    assert gray.getpixel((grid_x,line_y-8))>180 and gray.getpixel((grid_x,line_y+8))>180
   assert page.locator('#weekly-image').inner_text()=='下載第一張 PNG 圖片'
   with page.expect_download() as image_download:page.locator('#weekly-image').click()
   downloaded=Path(tmp)/'first-page.png';image_download.value.save_as(downloaded)
   assert image_download.value.suggested_filename.endswith('.png')
   assert downloaded.read_bytes()==bytes(page.evaluate('async()=>Array.from(new Uint8Array(await renderedPDF.firstPageImage.arrayBuffer()))'))
   from PIL import ImageChops, ImageStat
   with Image.open(downloaded) as exported:
    assert exported.format=='PNG' and exported.size==(2977,4210)
    difference=ImageChops.difference(exported.convert('RGB'),image)
    assert max(ImageStat.Stat(difference).mean)<2
   assert len(page.evaluate('renderedPDF.previewPages'))==2
   from PIL import Image
   page.evaluate('window.print=()=>{window.printInvoked=true}');page.click('#weekly-browser-print');page.wait_for_function('()=>window.printInvoked===true');assert page.locator('#weekly-print-root img').count()==2;assert page.locator('#weekly-print-root img').first.get_attribute('src')==page.locator('#weekly-a4-preview img').first.get_attribute('src')
   printed=Path(tmp)/'browser-print.pdf';page.pdf(path=printed,prefer_css_page_size=True,print_background=True)
   printed_info=subprocess.check_output(['pdfinfo',str(printed)],text=True);assert re.search(r'Pages:\s+2\b',printed_info) and '(A4)' in printed_info,printed_info
   page.evaluate('dispatchEvent(new Event("afterprint"))')
   passed('saved and future culls appear only in upper weekly rows; death values and total stay red while notes are black in HTML and actual embedded PDF image; browser printing uses the identical one-page preview')

   page.locator('#weekly-barn').select_option('');page.wait_for_selector('#weekly-a4-preview img');assert len(lines())==4,lines();assert dict(page.evaluate('models.at(-1).totals'))['飼料到料（噸）']=='12'
   full=[]
   for name in set(group.values()):
    result=page.request.get(url+'/api/weekly-report?all_records=1&cohort='+name+'%7C2026-07-17');assert result.status==200
    full.extend(d for w in result.json()['weeks'] for d in w['feed_details'])
   assert len(full)==24 and sum(d['kg'] for d in full)==78000;assert {d['id'] for d in full}=={o['id'] for o in original};assert next(d for d in full if d.get('bin')=='14')['kg']==8000;passed('all 24 synthetic whiteboard records are present once across their proper batches, totaling 78 tons including October 26/27; a two-barn paper prints its own four rows and 12 tons')
   assert page.locator('#weekly-csv').count()==0
   # The current paper intentionally has no CSV. The original API rows above
   # still verify every original receipt, while the preview/PDF stay complete.
   page.evaluate('feedDraws=[]');page.locator('#weekly-generate').click();page.wait_for_selector('#weekly-a4-preview img');draws=page.evaluate('feedDraws');assert draws.count('+4(13)')==2,(draws,lines())
   with page.expect_download() as d:page.locator('#weekly-print').click()
   pdf=root/'artifacts/weekly-all-records-whiteboard.pdf';d.value.save_as(pdf);info=subprocess.check_output(['pdfinfo',str(pdf)],text=True);assert '595.28 x 841.89' in info;assert re.search(r'Pages:\s+2\b',info);assert '叫料不等於到料' not in page.locator('#weekly-sheet-body').inner_text();passed('HTML and A4 PDF draw the same four scoped feed lines including future October 26, without duplicate arrivals or a paper CSV button')
   assert 'OLD-13|2026-01-01' not in page.locator('#weekly-cohort option').evaluate_all('(es)=>es.map(e=>e.value)')
   page.locator('#weekly-ended-records').click();page.wait_for_selector('#ended-records[open]');page.locator(f'[data-cleared-report="{old["id"]}"]').click();page.wait_for_selector('#weekly-a4-preview img');assert not lines();assert page.locator('#weekly-barn option').all_text_contents()==['同批全部棟舍','13棟'];page.locator('#weekly-close').click()
   page.locator('nav [href="#stats"]').click();page.locator('#open-weekly-report').click();page.wait_for_selector('#weekly-a4-preview img');page.locator('#weekly-cohort').select_option('GROUP-0|2026-07-17');page.wait_for_selector('#weekly-a4-preview img');page.locator('#weekly-cohort').select_option('WHITEBOARD-DEMO|2026-07-17');page.wait_for_selector('#weekly-a4-preview img');assert len(lines())==4;assert page.locator('#weekly-barn').input_value()=='';page.locator('#weekly-barn').select_option(barns[13]['id']);page.wait_for_selector('#weekly-a4-preview img');assert len(lines())==2;passed('switching active batch resets its barns; ended batches open only through history and keep their original feed separate')
   later=add('feed_orders',date='2026-11-03',kg=1500,display_unit='ton',vendor='新農科',item='大豬料',allocations=[{'batch_id':batches[13]['id'],'kg':1500}]);page.evaluate('()=>refresh()');page.wait_for_selector('#weekly-a4-preview img');assert lines()[-1]=='11/3+1.5(13)';assert dict(page.evaluate('models.at(-1).totals'))['飼料到料（噸）']=='9.5';passed('another device saving a wholly future week automatically refreshes the open paper and PDF; future records are not blanked')
   updated=s.mutate(u,'feed_orders',dict(later,kg=1000,allocations=[{'batch_id':batches[13]['id'],'kg':1000}]),str(uuid.uuid4()),later['id']);page.evaluate('()=>refresh()');page.wait_for_selector('#weekly-a4-preview img');assert lines()[-1]=='11/3+1(13)';assert len(lines())==3
   s.mutate(u,'feed_orders',{'revision':updated['revision']},str(uuid.uuid4()),later['id'],delete=True);page.evaluate('()=>refresh()');page.wait_for_selector('#weekly-a4-preview img');assert lines()==['10/24+4(13)','10/26+4(13)'];assert [r for r in s.export_backup()['records'] if r['id']!=later['id']]==before;passed('editing and deleting the original future order refreshes the paper, with no extra arrivals or accumulated old quantities')
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for language in ('zh','vi'):
     page.evaluate('(l)=>{lang=l;translate()}',language);page.wait_for_selector('#weekly-a4-preview img');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');assert page.locator('#weekly-report-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
   page.set_viewport_size({'width':390,'height':844});page.evaluate('lang="zh";translate()');page.wait_for_selector('#weekly-a4-preview img');page.locator('#weekly-report-dialog').evaluate('(e)=>e.scrollTop=0');page.screenshot(path=str(root/'artifacts/weekly-all-records-mobile.png'));passed('batch-first form and A4 preview fit 320/390/768/1440 screens in Traditional Chinese and Vietnamese')
   page.locator('#weekly-close').click();page.locator('#logout').click();page.locator('#login-form [name=username]').fill('reader');page.locator('#login-form [name=password]').fill('83000012');page.locator('#login-form button').click();page.wait_for_selector('#workspace:not([hidden])');r=page.request.get(url+'/api/weekly-report?batch_id='+batches[13]['id']+'&all_records=1');assert r.status==200 and r.json()['totals']['feed_orders']==8000;page.locator('#logout').click();page.wait_for_selector('#login-view:not([hidden])');assert page.request.get(url+'/api/weekly-report?batch_id='+batches[13]['id']+'&all_records=1').status==401;assert not errors,errors;passed('viewer can read the complete report, logged-out requests are rejected and no browser errors occur');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/weekly-all-records-results.json').write_text(json.dumps({'version':VERSION,'mode':'real Chromium/HTTP/isolated SQLite and synthetic whiteboard; no production farm writes','checks':checks},ensure_ascii=False,indent=2));print('Completed',len(checks),'complete paper scenarios')
