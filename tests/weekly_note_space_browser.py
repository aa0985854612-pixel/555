"""Real A4 rendering uses remaining space before omitting a complete dated note."""
import sys,tempfile,threading,json,subprocess,re,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store,VERSION
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];checks=[]
def passed(s):checks.append(s);print('PASS',s,flush=True)
def fixture():
 return {'title':'測試肉豬每週紀錄表','basics':[['批次','SYNTHETIC'],['棟舍','8棟、14棟'],['進場頭數','1400頭'],['廠商','養全'],['料別',''],['週期','10週–32週']],'entryHeaders':['棟舍','進場日期','進場頭數','進場日齡','入場均重'],'entries':[['8棟','2026-07-24','700','66天','20kg'],['14棟','2026-07-31','700','71天','21kg']],'period':'2026-07-24 → 2026-10-18','cycle':'週期','pages':[[{'headers':[str(n)+'週' for n in range(a,a+13)],'rows':[{'label':'起始日','cells':['7/24']+['']*12,'height':18},{'label':'淘汰數','cells':['']*13,'height':20},{'label':'死亡數','cells':['1']+['']*12,'height':23,'bold':True},{'label':'叫料（噸）','cells':['8/1+2（8）\n8/3+2（8）']+['']*12,'height':78,'left':True,'singleLine':True},{'label':'正常出豬','cells':['']*13,'height':20}]} for a in (10,23)]],'death_title':'死亡備註','death_groups':[{'title':f'第{n}棟','notes':[f'9/{i} 死亡1隻' for i in range(1,10)]} for n in (8,14)],'death_more':'另{n}筆，詳CSV','death_groups_more':'另有{n}棟，詳CSV','shipping_title':'出豬備註','shipping_notes':[],'shipping_more':'另有{n}筆出豬備註，詳CSV','totalLabel':'選定期間合計','totals':[['淘汰數',''],['死亡數','18'],['叫料量','4'],['出豬數','']],'cumulative':'目前剩餘頭數1382 育成率98.71%','legend':'空白＝未登記或資料待補；叫料不等於實耗。備註依實際內容與剩餘空間排列。每7天一欄，週期預排至32週；所選日期以外的數量留白。'}
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');server=Server(('127.0.0.1',0),store);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page();page.goto(url);page.wait_for_function('()=>typeof window.weeklyPdf==="function"');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.evaluate('()=>{const draw=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...a){window.noteDraws.push({text:a[0],x:a[1],y:a[2],font:this.font,width:a[3]});return draw.apply(this,a)};window.renderNoteFixture=async model=>{window.noteDraws=[];const pdf=await weeklyPdf(model);const a=document.createElement("a");a.href=URL.createObjectURL(pdf);a.download="notes.pdf";a.click();};}')
   def render(model,name):
    with page.expect_download() as dl:page.evaluate('m=>renderNoteFixture(m)',model)
    output=root/'artifacts'/name;dl.value.save_as(output);info=subprocess.check_output(['pdfinfo',str(output)],text=True);assert re.search(r'Pages:\s+1\b',info);assert '595.28 x 841.89' in info;draws=page.evaluate('noteDraws');assert all(d['y']+float(re.search(r'([0-9.]+)px',d['font'])[1])*1.25<=818.1 for d in draws if d['text']);return draws
   model=fixture();draws=render(model,'weekly-nine-per-barn-a4.pdf')
   for index,g in enumerate(model['death_groups']):
    for note in g['notes']:assert len([d for d in draws if d['text']==note and 24+index*136.82<=d['x']<24+(index+1)*136.82])==1
   assert not any(re.match(r'另\d+筆',d['text']) for d in draws);passed('nine complete dated deaths per barn fit on one portrait A4 with tall feed rows; no six-entry cap or false omitted-note count')
   model=fixture();model['shipping_notes']=[f'10/{i} 南投 {i+10}（8）' for i in range(1,19)];model['death_groups'][0]['notes']=[];model['death_groups'][1]['notes']=[];draws=render(model,'weekly-eighteen-shipments-a4.pdf');assert all(any(d['text']==s and d['x']>=297.64 for d in draws) for s in model['shipping_notes']);assert not any(re.match(r'另有\d+筆出豬',d['text']) for d in draws);passed('all eighteen shipping notes use the right-hand area without a twelve-entry cap or overlapping the footer')
   model=fixture();model['death_groups']=[{'title':f'第{n}棟','notes':[f'9/{n} 死亡1隻']} for n in (5,6,7,8)];draws=render(model,'weekly-four-note-groups-a4.pdf');assert all(any(d['text']==g['title'] for d in draws) and any(d['text']==g['notes'][0] for d in draws) for g in model['death_groups']);passed('four barn headings and their dated notes all remain visible, using a second row of barn columns')
   model=fixture();note='10/1 死亡1隻 · '+'完整備註內容，逐字保留。'*8;model['death_groups']=[{'title':'第8棟','notes':[note]}];shipping='10/2 南投 80（8） · '+'出豬備註完整保存。'*8;model['shipping_notes']=[shipping];draws=render(model,'weekly-wrapped-notes-a4.pdf');left=''.join(d['text'] for d in draws if 24<=d['x']<297.64);right=''.join(d['text'] for d in draws if d['x']>=297.64);assert note in left and shipping in right;assert '… CSV' not in [d['text'] for d in draws];passed('long death and shipment notes wrap without losing characters and stay in separate left/right areas')
   assert not errors,errors;browser.close()
 finally:server.shutdown();server.server_close()
(root/'artifacts/weekly-note-space-browser.json').write_text(json.dumps({'version':VERSION,'checks':checks,'mode':'real Chromium canvas and one-page A4 PDF downloads, synthetic data'},ensure_ascii=False,indent=2))
