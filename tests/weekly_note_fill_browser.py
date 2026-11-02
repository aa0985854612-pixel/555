"""Reproduce the user's9/23-barn whitespace: bigger notes fill their labeled panes."""
import copy,json,re,subprocess,sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[];(root/'artifacts').mkdir(exist_ok=True)
def passed(s):checks.append(s);print('PASS '+s,flush=True)
def fixture():
 def band(start):
  feed=['\n'.join(f'{9 if start==23 else 8}/{i+1}+2({23 if i%2 else 9})' for i in range(6))]+['']*11
  return {'headers':[str(i)+'週' for i in range(start,start+12)],'rows':[{'label':'起始日','cells':['9/4']+['']*11,'height':18},{'label':'死亡數（隻）','cells':['1','2','4','3']+['']*8,'bold':True,'height':23},{'label':'飼料（噸）','cells':feed,'left':True,'singleLine':True,'monospace':True,'height':46},{'label':'售出數','cells':['','5','5','','5、14','20、63','80、80、66','41、41、60、21、90','41、47','','',''],'complete':True,'height':20}]}
 dates9=['6/20','7/20','8/25','8/26','8/31','9/9','9/15','9/17','9/18','9/19','9/26','9/27','9/30'];dates23=['7/12','7/19','7/24','8/9','9/20','10/15','10/20']
 shipping=['9/17 南投5','9/19 南投5','10/5 南投5','10/6 新北14','10/13 20（23）','10/15 南投63','10/17 南投80','10/19 南投80','10/20 新北66','10/23 南投41','10/23 嘉義41','10/26 南投60','10/27 南投21','10/27 新北90','10/30 嘉義41','10/31 南投47']
 return {'title':'嘉得 · 肉豬每週紀錄表','basics':[['批次','JD-SYNTHETIC'],['棟舍','9棟、23棟'],['進場頭數','702頭'],['廠商','新農科'],['料別','大豬料'],['週期','11週–34週']],'entryHeaders':['棟舍','進場日','進場數','日齡','均重'],'entries':[['9棟','2026-06-12','350','71天','20kg'],['23棟','2026-06-12','352','71天','20kg']],'period':'2026-06-12 → 2026-11-02','cycle':'週期','pages':[[band(11),band(23)]],'death_title':'死亡備註','death_groups':[{'title':'第9棟','notes':[d+f' 死亡{2 if i in (2,8) else 1}隻' for i,d in enumerate(dates9)]},{'title':'第23棟','notes':[d+' 死亡1隻' for d in dates23]}],'shipping_title':'出豬備註','shipping_notes':shipping,'totalLabel':'全部登記合計','totals':[['死亡數','22'],['飼料（噸）','165'],['售出數','679']],'cumulative':'目前剩餘頭數0 育成率96.88%','legend':'固定一頁A4，框內文字與行距依可用空間調整。'}
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page();page.goto(url);page.wait_for_function('()=>typeof weeklyPdf==="function"');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.evaluate('()=>{window.draws=[];window.rects=[];const text=CanvasRenderingContext2D.prototype.fillText,rect=CanvasRenderingContext2D.prototype.strokeRect;CanvasRenderingContext2D.prototype.fillText=function(...a){draws.push({text:String(a[0]),x:a[1],y:a[2],size:parseFloat(this.font.match(/([0-9.]+)px/)[1])});return text.apply(this,a)};CanvasRenderingContext2D.prototype.strokeRect=function(...a){rects.push({x:a[0],y:a[1],w:a[2],h:a[3]});return rect.apply(this,a)};window.renderFill=async m=>{draws=[];rects=[];const before=JSON.stringify(m),pdf=await weeklyPdf(m);window.unchanged=before===JSON.stringify(m);window.noteImages=pdf.previewPages;const a=document.createElement("a");a.href=URL.createObjectURL(pdf);a.download="fill.pdf";a.click()}}')
   model=fixture()
   with page.expect_download() as dl:page.evaluate('m=>renderFill(m)',model)
   output=root/'artifacts/weekly-9-23-note-fill.pdf';dl.value.save_as(output);info=subprocess.check_output(['pdfinfo',str(output)],text=True);assert re.search(r'Pages:\s+1\b',info);assert page.evaluate('noteImages.length===1&&unchanged')
   (root/'artifacts/weekly-9-23-note-fill.jpg').write_bytes(bytes(page.evaluate('async()=>Array.from(new Uint8Array(await noteImages[0].arrayBuffer()))')))
   draws=page.evaluate('draws');rects=page.evaluate('rects');head=next(d for d in draws if d['text']=='死亡備註');body=next(r for r in rects if abs(r['x']-24)<.01 and abs(r['y']-(head['y']+15))<.01 and abs(r['w']-(595.28-48)/2)<.01);bottom=body['y']+body['h']
   for g in model['death_groups']:
    own=[next(d for d in draws if d['text']==n) for n in g['notes']];assert len({d['x'] for d in own})==1;assert min(d['size'] for d in own)>10;last=own[-1];assert abs(last['y']+last['size']*1.25-(bottom-2))<.1
   passed('9-barn13 entries and23-barn7 entries stay in single columns, grow above10pt, and both reach the bottom instead of leaving a blank lower box')
   panes=[r for r in rects if abs(r['y']-body['y'])<.01 and abs(r['w']-body['w']/2)<.01];assert len(panes)==2 and all(abs(r['y']+r['h']-bottom)<.1 for r in panes);passed('each labeled barn pane extends to the full frame bottom; there is no empty unlabeled rectangle below the barn lists')
   outgoing=[next(d for d in draws if d['text']==n) for n in model['shipping_notes']];assert len({d['x'] for d in outgoing})==1;assert min(d['size'] for d in outgoing)>10;last=outgoing[-1];assert abs(last['y']+last['size']*1.25-(bottom-4))<.1;passed('all16 shipments use a larger single column and spaced lines through the bottom, while preserving every destination and quantity')
   assert all(sum(d['text']==n for d in draws)==1 for g in model['death_groups'] for n in g['notes']);assert not any('淘汰' in d['text'] or 'CSV' in d['text'] or '…' in d['text'] for d in draws);assert all(d['y']+d['size']*1.25<=818.1 for d in draws if d['text']);assert not errors,errors;passed('actual A4 is one page with every original note once, no crop, no cull row and no CSV');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/weekly-note-fill-results.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'real Chromium and A4 PDF, synthetic reproduction of screenshot; no live farm writes'},ensure_ascii=False,indent=2));print('Completed',len(checks),'note-fill scenarios')
