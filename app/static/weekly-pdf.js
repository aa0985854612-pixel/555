'use strict';
/* Fixed A4 pages, drawn locally: Safari does not paginate this PDF again.
   Images contain only the report already authorized and loaded in this tab. */
window.weeklyPdf = async function(model) {
 const PW=595.28,PH=841.89,SCALE=4,M=24,W=PW-2*M,images=[];
 const family='-apple-system, BlinkMacSystemFont, "Noto Sans CJK TC", "Noto Sans TC", sans-serif';
 await document.fonts.ready;
 // Plan physical pages from actual feed lines, before drawing any cells.
 // Feed and shipment values continue in full across fixed pages.
 const measure=document.createElement('canvas').getContext('2d');
 function wrap(value,width,size,bold=false){
  measure.font=`${bold?'600':'400'} ${size}px ${family}`;const out=[];
  for(const line of String(value??'').split('\n')){let part='';for(const ch of line){if(part&&measure.measureText(part+ch).width>width){out.push(part);part='';}part+=ch;}out.push(part);}return out;
 }
 const wrappedCount=(...args)=>wrap(...args).length;
 const headerH=98+Math.ceil(model.basics.length/3)*31+model.entries.length*21;
 const footerReserve=15+39+wrappedCount(model.cumulative,W,9,true)*11.25+6+wrappedCount(model.legend,W,7.5)*9.375;
 const noteReserve=Math.max(64,18+Math.ceil(Math.min(6,(model.death_groups||[]).length)/3)*35+4);
 const capacity=PH-M-headerH-footerReserve-noteReserve-8,layouts=[];
 function newPage(){const next={bands:[],preentry:null,height:0};layouts.push(next);return next;}
 let currentPage=newPage();
 function continuationLines(value,offset,count){
  const all=value?String(value).split('\n'):[],out=all.slice(offset,offset+count);
  // A continued page repeats its first line's date for unambiguous reading.
  if(offset&&/^\s+\+/.test(out[0]||'')){
   for(let i=offset-1;i>=0;i--){const date=all[i].match(/^(\d+\/\d+)(?=\+)/);if(date){out[0]=out[0].replace(/^\s+/,date[1]);break;}}
  }
  return out;
 }
 if(model.preentry?.entries.length){
  const perPage=Math.floor((capacity-27)/12);if(perPage<1)throw new Error('weekly_pdf_layout_overflow');
  for(let offset=0;offset<model.preentry.entries.length;offset+=perPage){
   if(offset)currentPage=newPage();
   const entries=continuationLines(model.preentry.entries.join('\n'),offset,perPage);
   currentPage.preentry={...model.preentry,entries};currentPage.height=27+entries.length*12;
  }
 }
 function addBand(band){
  const height=19+band.rows.reduce((n,r)=>n+r.height,0)+8;
  if(currentPage.height+height>capacity&&(currentPage.bands.length||currentPage.preentry))currentPage=newPage();
  if(height>capacity+.01)throw new Error('weekly_pdf_layout_overflow');
  currentPage.bands.push(band);currentPage.height+=height;
 }
 for(const inputPage of model.pages)for(const input of inputPage){
  const size=input.headers.length>16?7:8,lh=size*1.25,cw=(W-58)/input.headers.length;
  const rows=input.rows.map(row=>{
   const cells=row.cells.map(v=>row.complete?wrap(v,cw-6,size,row.bold).join('\n'):v);
   const complete=row.left||row.complete;
   return {...row,cells,singleLine:complete||row.singleLine,height:complete?Math.max(row.height,8+Math.max(0,...cells.map(v=>v?String(v).split('\n').length:0))*lh):row.height};
  });
  const height=19+rows.reduce((n,r)=>n+r.height,0)+8;
  if(height<=capacity){addBand({...input,rows});continue;}
  const first=rows[0];let chunk=[first],continued=false;
  const flush=()=>{if(chunk.length>1){addBand({...input,rows:chunk,continued});continued=true;}chunk=[first];};
  for(const row of rows.slice(1)){
   if(row.height+19+first.height+8<=capacity){if(19+chunk.reduce((n,r)=>n+r.height,0)+row.height+8>capacity)flush();chunk.push(row);continue;}
   if(!row.left&&!row.complete)throw new Error('weekly_pdf_layout_overflow');
   const total=Math.max(0,...row.cells.map(v=>v?String(v).split('\n').length:0));let offset=0;
   while(offset<total){
    const room=capacity-19-chunk.reduce((n,r)=>n+r.height,0)-8,maxLines=Math.floor((room-8)/lh);
    if(maxLines<1){flush();continue;}
    const cells=row.cells.map(v=>continuationLines(v,offset,maxLines).join('\n'));
    chunk.push({...row,cells,height:8+Math.max(1,...cells.map(v=>v?v.split('\n').length:0))*lh});offset+=maxLines;if(offset<total)flush();
   }
  }
  flush();
 }
 // Notes fill a column from top to bottom, then continue at its right.
 // Both sections use all remaining writing space, and continue on A4 pages.
 let death=(model.death_groups||[]).filter(g=>g.notes.length).flatMap(g=>[{value:g.title,bold:true},...g.notes.map(value=>({value}))]);
 let shipping=(model.shipping_notes||[]).map(value=>({value}));
 if(!death.length&&(model.death_notes||[]).length)death=model.death_notes.map(value=>({value}));
 function flow(items,height){
  const size=8.5,lh=size*1.25,gap=2,half=W/2;
  const one=items.map(item=>({...item,parts:wrap(item.value,half-8,size,item.bold)}));
  const columns=one.reduce((n,item)=>n+item.parts.length*lh+gap,0)<=height?1:2,cw=half/columns;
  const draws=[];let column=0,y=0;
  for(let index=0;index<items.length;index++){
   const item=items[index],parts=wrap(item.value,cw-8,size,item.bold);
   for(let line=0;line<parts.length;line++){
    if(y+lh>height){column++;y=0;}
    if(column>=columns)return {draws,remaining:[{...item,value:parts.slice(line).join('\n')},...items.slice(index+1)],size,lh,cw};
    draws.push({text:parts[line],x:4+column*cw,y,bold:item.bold});y+=lh;
   }
   y+=gap;
  }
  return {draws,remaining:[],size,lh,cw};
 }
 let notePage=currentPage;
 do{
  const available=PH-M-headerH-notePage.height-footerReserve-8;
  if(available<44){notePage=newPage();continue;}
  const left=flow(death,available-24),right=flow(shipping,available-24);
  notePage.notes={height:available,left,right};death=left.remaining;shipping=right.remaining;
  if(death.length||shipping.length)notePage=newPage();
 }while(death.length||shipping.length||!notePage.notes);
 for(let page=0;page<layouts.length;page++){
  const canvas=document.createElement('canvas');canvas.width=Math.ceil(PW*SCALE);canvas.height=Math.ceil(PH*SCALE);
  const c=canvas.getContext('2d');c.scale(SCALE,SCALE);c.fillStyle='#fff';c.fillRect(0,0,PW,PH);c.strokeStyle='#444';c.lineWidth=.55;
  const font=(size,bold=false,monospace=false)=>c.font=`${bold?'600':'400'} ${size}px ${monospace?'monospace':family}`;
  function lines(text,width,size,bold=false){font(size,bold);const out=[];for(const line of String(text??'').split('\n')){let part='';for(const ch of line){if(part&&c.measureText(part+ch).width>width){out.push(part);part='';}part+=ch;}out.push(part);}return out;}
  function text(value,x,y,width,size=9,bold=false,align='left',height=100,singleLine=false,monospace=false,complete=false){
   const lh=size*1.25,all=singleLine?String(value??'').split('\n'):lines(value,width,size,bold),limit=Math.max(1,Math.floor(height/lh)),shown=all.slice(0,limit);
   if(all.length>limit){if(complete)throw new Error('weekly_pdf_feed_overflow');shown[shown.length-1]='…';}
   c.fillStyle='#111';c.textBaseline='top';c.textAlign=align;font(size,bold,monospace);
   const feedScale=monospace&&singleLine?Math.min(1,width/Math.max(1,...all.filter(line=>!line.includes(' · ')).map(line=>c.measureText(line).width))):null;
   for(let j=0;j<shown.length;j++){const ax=x+(align==='center'?width/2:0);if(singleLine)c.fillText(shown[j],ax,y+j*lh,feedScale===null?width:Math.min(width,Math.max(1,c.measureText(shown[j]).width)*feedScale));else c.fillText(shown[j],ax,y+j*lh);}
   return all.length>limit;
  }
  function cell(value,x,y,w,h,{size=9,bold=false,shade=false,align='center',singleLine=false,monospace=false,complete=false}={}){
   if(shade){c.fillStyle='#f0f0f0';c.fillRect(x,y,w,h);}c.strokeRect(x,y,w,h);const pad=singleLine?1.5:3;text(value,x+pad,y+4,w-2*pad,size,bold,align,h-7,singleLine,monospace,complete);
  }
  text(model.title,M,22,W,18,true,'center',26);let y=50;
  for(let i=0;i<model.basics.length;i+=3){for(let j=0;j<3;j++){const pair=model.basics[i+j]||['',''],x=M+j*W/3;cell('',x,y,W/3,31);text(pair[0],x+5,y+3,W/3-10,8,false,'left',11);text(pair[1],x+5,y+14,W/3-10,10,true,'left',14);}y+=31;}
  y+=6;const ew=[.12,.24,.19,.20,.25].map(n=>W*n);
  const entryRows=[model.entryHeaders,...model.entries];for(let i=0;i<entryRows.length;i++){let x=M;for(let j=0;j<5;j++){cell(entryRows[i][j],x,y,ew[j],i?21:19,{size:8.5,bold:i===0,shade:i===0});x+=ew[j];}y+=i?21:19;}
  y+=6;text(model.period+(layouts.length>1?` (${page+1}/${layouts.length})`:''),M,y,W,8,false,'left',14);y+=17;
  const pre=layouts[page].preentry;
  if(pre){
   const shown=pre.entries,rows=shown.length,h=18+rows*12+4;
   cell('',M,y,W,h);text(pre.title+' · '+pre.summary,M+4,y+3,W-8,9,true,'left',13,true);
   shown.forEach((entry,i)=>text(entry,M+4,y+18+i*12,W-8,8.5,false,'left',12,true,true));
   y+=h+5;
  }
  const bands=layouts[page].bands;
  for(const band of bands){
   const n=band.headers.length,labelW=58,cw=(W-labelW)/n,size=n>16?7:8;
   const rows=[{label:model.cycle+(band.continued?' · '+(model.continued||'續'):''),cells:band.headers,height:19,shade:true,bold:true},...band.rows];
   for(const originalRow of rows){const row=originalRow;cell(row.label,M,y,labelW,row.height,{size:8.5,bold:true,shade:row.shade});for(let j=0;j<n;j++)cell(row.cells[j]||'',M+labelW+j*cw,y,cw,row.height,{size:row.bold?size+.5:size,bold:row.bold,shade:row.shade,align:row.left?'left':'center',singleLine:row.singleLine,monospace:row.monospace,complete:row.left||row.complete});y+=row.height;}
   y+=8;
  }
  const planned=layouts[page].notes;
  const cumulativeH=lines(model.cumulative,W,9,true).length*9*1.25,legendH=lines(model.legend,W,7.5).length*7.5*1.25;
  if(planned){
   const half=W/2;
   for(const [index,title,plan] of [[0,model.death_title,planned.left],[1,model.shipping_title,planned.right]]){
    const x=M+index*half;cell(title||'',x,y,half,18,{size:9,bold:true,shade:true});cell('',x,y+18,half,planned.height-18);
    for(const entry of plan.draws)text(entry.text,x+entry.x,y+22+entry.y,plan.cw-8,plan.size,entry.bold,'left',plan.lh+.1,true);
   }
   y+=planned.height+8;
  }
  if(page===layouts.length-1){
  const footerH=15+39+cumulativeH+6+legendH;
  if(y+footerH>PH-M+.1)throw new Error('weekly_pdf_layout_overflow');
  text(model.totalLabel,M,y,W,9,true,'left',14);y+=15;
  for(let i=0;i<model.totals.length;i++){const x=M+i*W/4,pair=model.totals[i];cell('',x,y,W/4,32);text(pair[0],x+4,y+3,W/4-8,8,false,'left',10);text(pair[1],x+4,y+15,W/4-8,11,true,'left',14);}y+=39;
  text(model.cumulative,M,y,W,9,true,'left',cumulativeH+.1);y+=cumulativeH+6;
  text(model.legend,M,y,W,7.5,false,'left',legendH+.1);
  }
  const blob=await new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('weekly_pdf_image_failed')),'image/jpeg',.96));
  images.push({bytes:new Uint8Array(await blob.arrayBuffer()),width:canvas.width,height:canvas.height});canvas.width=canvas.height=1;
 }
 const enc=new TextEncoder(),parts=[],offsets=[0];let length=0;
 const append=part=>{const bytes=typeof part==='string'?enc.encode(part):part;parts.push(bytes);length+=bytes.length;};
 const object=(id,body)=>{offsets[id]=length;append(`${id} 0 obj\n`);for(const piece of body)append(piece);append('\nendobj\n');};
 append('%PDF-1.4\n');object(1,['<< /Type /Catalog /Pages 2 0 R >>']);object(2,[`<< /Type /Pages /Count ${images.length} /Kids [${images.map((_,i)=>`${3+i*3} 0 R`).join(' ')}] >>`]);
 for(let i=0;i<images.length;i++){
  const im=images[i],id=3+i*3,stream=`q ${PW} 0 0 ${PH} 0 0 cm /Sheet Do Q\n`;
  object(id,[`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PW} ${PH}] /Resources << /XObject << /Sheet ${id+1} 0 R >> >> /Contents ${id+2} 0 R >>`]);
  object(id+1,[`<< /Type /XObject /Subtype /Image /Width ${im.width} /Height ${im.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${im.bytes.length} >>\nstream\n`,im.bytes,'\nendstream']);
  object(id+2,[`<< /Length ${enc.encode(stream).length} >>\nstream\n`,stream,'endstream']);
 }
 const xref=length;append(`xref\n0 ${offsets.length}\n0000000000 65535 f \n`);for(const n of offsets.slice(1))append(String(n).padStart(10,'0')+' 00000 n \n');append(`trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
 const pdf=new Blob(parts,{type:'application/pdf'});
 // These exact JPEG bytes are embedded in the PDF, so preview and download agree.
 pdf.previewPages=images.map(im=>new Blob([im.bytes],{type:'image/jpeg'}));
 return pdf;
};
