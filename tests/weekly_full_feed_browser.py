"""Every feed line is drawn within A4, including dense and pre-entry records on exactly one page."""
import sys,tempfile,threading,json,subprocess,re,copy,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store
from app.server import Server
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];(root/'artifacts').mkdir(exist_ok=True);checks=[]
def passed(text):checks.append(text);print('PASS '+text,flush=True)
def fixture(count=8):
 def band(start):
  cells=['\n'.join(f'{8 if start==11 else 10}/{n+1}+{start+n/1000:.3f}(5)' for n in range(count))]+['']*11
  return {'headers':[f'{n}週' for n in range(start,start+12)],'rows':[{'label':'起始日','cells':['8/21']+['']*11,'height':18},{'label':'死亡數','cells':['6']+['']*11,'height':23,'bold':True},{'label':'叫料（噸）','cells':cells,'height':46,'left':True,'singleLine':True,'monospace':True},{'label':'正常出豬','cells':['12']+['']*11,'height':20}]}
 return {'title':'嘉得 · 肉豬每週紀錄表','basics':[['批次','SYNTHETIC-33'],['棟舍','5棟、6棟、7棟'],['進場頭數','808頭'],['廠商','新農科'],['料別','仔豬料'],['週期','11週–32週']],'entryHeaders':['棟舍','進場日','進場數','日齡','均重'],'entries':[[f'{n}棟','2026-08-21','200','70天','22.56kg'] for n in (5,6,7)],'period':'2026-08-21 → 2026-10-23','cycle':'週期','continued':'續','pages':[[band(11),band(23)]],'death_title':'死亡備註','death_groups':[{'title':'第5棟','notes':['10/23 死亡1隻']}],'death_more':'另{n}筆，詳CSV','death_groups_more':'另有{n}棟，詳CSV','shipping_title':'出豬備註','shipping_notes':['10/23 南投12'],'shipping_more':'另有{n}筆出豬備註，詳CSV','totalLabel':'選定期間合計','totals':[['死亡數','6'],['叫料量','32'],['出豬數','12']],'cumulative':'目前剩餘頭數787 育成率98.88%','legend':'空白＝未登記或資料待補；叫料不等於實耗。叫料全部列出，資料多時接續下一頁。'}
def feed_lines(model):return [line for page in model['pages'] for band in page for row in band['rows'] if row.get('left') for cell in row['cells'] for line in cell.split('\n') if line]
with tempfile.TemporaryDirectory() as tmp:
 s=Store(Path(tmp)/'db');server=Server(('127.0.0.1',0),s);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url);page.wait_for_function('()=>typeof window.weeklyPdf==="function"')
   page.evaluate('()=>{window.draws=[];const ids=new WeakMap();let sequence=0;const draw=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...args){if(!ids.has(this.canvas))ids.set(this.canvas,++sequence);draws.push({text:args[0],x:args[1],y:args[2],font:this.font,width:args[3],page:ids.get(this.canvas)});return draw.apply(this,args)};window.fullFeedRender=async model=>{window.draws=[];const before=JSON.stringify(model),pdf=await weeklyPdf(model);window.previewFeedBlobs=pdf.previewPages;window.inputUnchanged=before===JSON.stringify(model);const a=document.createElement("a");a.href=URL.createObjectURL(pdf);a.download="full-feed.pdf";a.click();};}')
   def render(model,name):
    with page.expect_download() as download:page.evaluate('(m)=>fullFeedRender(m)',model)
    path=root/'artifacts'/name;download.value.save_as(path);raw=path.read_bytes();info=subprocess.check_output(['pdfinfo',str(path)],text=True);count=int(re.search(r'Pages:\s+(\d+)',info)[1]);assert '595.28 x 841.89' in info
    blobs=page.evaluate('async()=>Promise.all(previewFeedBlobs.map(async b=>Array.from(new Uint8Array(await b.arrayBuffer()))))');path.with_suffix('.jpg').write_bytes(bytes(blobs[0]));assert count==len(blobs);assert all(bytes(b) in raw for b in blobs);assert page.evaluate('inputUnchanged')
    draws=page.evaluate('draws');assert all(d['y']+float(re.search(r'([0-9.]+)px',d['font'])[1])*1.25<=818.1 for d in draws if d['text']);return draws,count
   model=fixture();draws,count=render(model,'weekly-full-feed-a4.pdf');assert count==1;assert collections.Counter(d['text'] for d in draws if '+' in d['text'])==collections.Counter(feed_lines(model));assert not any(d['text']=='… CSV' for d in draws)
   page.evaluate('async()=>{const img=document.createElement("img");img.id="full-feed-preview";img.src=URL.createObjectURL(previewFeedBlobs[0]);img.style.width="800px";document.body.append(img);await img.decode()}');page.locator('#full-feed-preview').screenshot(path=str(root/'artifacts/weekly-full-feed-a4.png'));passed('both weekly bands grow to print every one of eight lines per week on one A4, with no CSV truncation')
   dense=fixture(95);draws,count=render(dense,'weekly-all-feed-continuations-a4.pdf');assert count==1;assert collections.Counter(d['text'] for d in draws if '+' in d['text'])==collections.Counter(feed_lines(dense));assert sum(d['text']=='選定期間合計' for d in draws)==1;assert sum(d['text']=='目前剩餘頭數787 育成率98.88%' for d in draws)==1;assert sum(d['text']=='10/23 南投12' for d in draws)==1;assert sum(d['text']=='6' for d in draws)==3;assert not any(d['text']=='… CSV' for d in draws);passed('190 feed lines fit exactly one A4, each once; original movement cells and grand totals never duplicate')
   pre=fixture(2);pre['preentry']={'title':'進場前叫料','summary':'70噸','entries':['8/20+1(15-1)']+[f'    +{i}(15-1)' for i in range(2,71)],'more':'另有{n}筆，詳CSV'};draws,count=render(pre,'weekly-full-preentry-a4.pdf');assert count==1;actual=[d['text'] for d in draws if '+' in d['text']];assert len(actual)==74;assert collections.Counter(re.sub(r'^\d+/\d+|^\s+','',line) for line in actual)==collections.Counter(re.sub(r'^\d+/\d+|^\s+','',line) for line in pre['preentry']['entries']+feed_lines(pre));assert not any('另有' in d['text'] or d['text']=='… CSV' for d in draws);assert len([d for d in draws if re.match(r'^8/20\+',d['text'])])==1;passed('all seventy pre-entry feed lines print with their own section, preserving quantities and a single date heading')
   split=fixture(80);split['pages'][0][0]['rows'][2]['cells'][0]='9/23+2(20)\n'+'\n'.join(f'    +{i}(19)' for i in range(1,80));draws,count=render(split,'weekly-date-context-a4.pdf');assert count==1;pages={d['page'] for d in draws if '+' in d['text']};
   for number in pages:
    first=next(d['text'] for d in draws if d['page']==number and '+' in d['text']);assert re.match(r'^\d+/\d+\+',first),first
   assert collections.Counter(re.sub(r'^\d+/\d+|^\s+','',d['text']) for d in draws if '+' in d['text'])==collections.Counter(re.sub(r'^\d+/\d+|^\s+','',line) for line in feed_lines(split));passed('same-day compact dates continue safely: the A4 starts with its date and every feed amount appears once')
   long=fixture(2);long['pages'].append(copy.deepcopy(long['pages'][0]));draws,count=render(long,'weekly-multiple-period-panels.pdf');assert count==1;assert collections.Counter(d['text'] for d in draws if '+' in d['text'])==collections.Counter(feed_lines(long));assert sum(d['text']=='選定期間合計' for d in draws)==1;passed('multiple source panels fit one A4 with all feed lines and show the grand total only once')
   assert not errors,errors;browser.close()
 finally:server.shutdown();server.server_close()
print(json.dumps({'checks':checks,'passed':len(checks)},ensure_ascii=False))
