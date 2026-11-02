"""Weekly detail has priority; all note panes use one font and fixed spacing."""
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
   def note_draws(model):
    draws=page.evaluate('draws');notes=[n for group in model['death_groups'] for n in group['notes']]+model['shipping_notes'];actual=[d for d in draws if d['text'] in notes]
    assert len(actual)==len(notes),(len(actual),len(notes));assert len({round(d['size'],5) for d in actual})==1;assert actual[0]['size']<=8
    for group in model['death_groups']+[{'notes':model['shipping_notes']}]:
     positions={};left=297.64;right=571.28
     if 'title' in group:
      head=next(d for d in draws if d['text']==group['title']);left=head['x'];right=min([d['x'] for d in draws if d['text'] in [g['title'] for g in model['death_groups']] and d['x']>left]+[297.64])
     for note in group['notes']:
      found=[d for d in draws if d['text']==note and left<=d['x']<right];assert len(found)==1,(note,left,right,found);d=found[0];positions.setdefault(d['x'],[]).append(d)
     for column in positions.values():
      for before,after in zip(column,column[1:]):assert abs(after['y']-before['y']-before['size']*1.5)<.01
    assert not any('淘汰' in d['text'] or 'CSV' in d['text'] or '…' in d['text'] for d in draws);assert all(d['y']+d['size']*1.25<=818.1 for d in draws if d['text'])
    return draws,actual
   draws,actual=note_draws(model)
   assert all(d['size']==8 for d in actual);feed=[d for d in draws if '+' in d['text']];assert all(d['size']==8 for d in feed)
   passed('normal weekly tables keep8pt detail; both barns and all16 shipments share8pt text and12pt pitch without stretching to the frame bottom')
   assert next(d for d in draws if d['text']==model['death_groups'][0]['notes'][0])['y']==next(d for d in draws if d['text']==model['shipping_notes'][0])['y'];passed('barn note columns and shipment notes start on the same baseline; all records appear exactly once on one A4')
   dense=fixture();dense['basics'][0][1]='JD-DEMO-20.21';dense['basics'][1][1]='11棟、21棟';dense['basics'][2][1]='1400頭';dense['entries'][0][0]='11棟';dense['entries'][1][0]='21棟';dense['entries'][0][2]=dense['entries'][1][2]='700';dense['totals']=[['死亡數','74'],['飼料（噸）','24'],['售出數','1173']];dense['cumulative']='目前剩餘頭數153 育成率94.71%';dense['legend']='合成資料版面驗證：週表優先，備註統一字級與行距，固定一頁A4。';dense['death_groups']=[{'title':'第11棟','notes':[f'{6+i//28}/{i%28+1} 死亡1隻' for i in range(43)]},{'title':'第21棟','notes':[f'6/{i+1} 死亡1隻' for i in range(17)]},{'title':'未指定','notes':[f'7/{i+1} 死亡2隻' for i in range(7)]}];dense['shipping_notes']=[f'9/{i+1} 南投{40+i}' for i in range(23)]
   with page.expect_download() as dl:page.evaluate('m=>renderFill(m)',dense)
   output=root/'artifacts/weekly-priority-uniform.pdf';dl.value.save_as(output);assert re.search(r'Pages:\s+1\b',subprocess.check_output(['pdfinfo',str(output)],text=True));draws,actual=note_draws(dense);assert all(d['size']==8 for d in draws if '+' in d['text']);assert all(6<=d['size']<=8 for d in actual),actual[0]['size']
   edge=next(d['x'] for d in draws if d['text']=='第21棟');first=[d for d in actual if d['text'] in dense['death_groups'][0]['notes'] and d['x']<edge];assert len({d['x'] for d in first})==2;assert page.evaluate('unchanged');(root/'artifacts/weekly-priority-uniform.jpg').write_bytes(bytes(page.evaluate('async()=>Array.from(new Uint8Array(await noteImages[0].arrayBuffer()))')))
   passed('screenshot-shaped43/17/7 deaths and23 shipments preserve full-size upper tables; the long barn continues beside itself and all panes share the same compact font and fixed spacing')
   sparse=fixture();sparse['death_groups']=[{'title':'第8棟','notes':['10/1 死亡1隻','10/2 死亡2隻']}];sparse['shipping_notes']=['10/3 嘉義50']
   with page.expect_download() as dl:page.evaluate('m=>renderFill(m)',sparse)
   draws,actual=note_draws(sparse);assert all(d['size']==8 for d in actual);assert not errors,errors;passed('sparse notes stay8pt with fixed spacing rather than becoming oversized; original report data is unchanged');browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/weekly-note-fill-results.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'real Chromium and one A4 PDF; synthetic uneven note counts; no live farm writes'},ensure_ascii=False,indent=2));print('Completed',len(checks),'note-fill scenarios')
