'use strict';
/* Shared daily work is listed once; dated work uses measured, large-print rows. */
window.workCalendarPDF=async function(model){
 const PW=595.28,PH=841.89,SCALE=3,M=24,W=PW-M*2,images=[];
 await document.fonts.ready;
 const canvas=document.createElement('canvas');canvas.width=Math.ceil(PW*SCALE);canvas.height=Math.ceil(PH*SCALE);
 const c=canvas.getContext('2d');c.scale(SCALE,SCALE);
 const family='-apple-system, BlinkMacSystemFont, "Noto Sans CJK TC", "Noto Sans TC", sans-serif';
 const labelW=78,widths=[labelW,(W-labelW)*.46,(W-labelW)*.54];
 function font(n,bold=false){c.font=`${bold?'600':'400'} ${n}px ${family}`;}
 function wrap(value,width,size){font(size);const out=[];for(const row of String(value).split('\n')){let line='';for(const ch of row){if(line&&c.measureText(line+ch).width>width){out.push(line);line='';}line+=ch;}out.push(line);}return out;}
 function taskLines(task,width,size){return [...wrap((task.time?task.time+' · ':'')+task.title,width,size),...(task.note?wrap(task.note,width,size):[])];}
 const signature=t=>JSON.stringify([t.title,t.time||'',t.note||'']);
 // Match occurrence counts, not just titles: genuine duplicate jobs stay visible.
 const remaining=model.days.map(d=>d.tasks.slice()),daily=[];
 for(const task of model.days[0].tasks){
  if(task.mode!=='weekly'||daily.length>=6||taskLines(task,W/2-18,15.5).length>2)continue;
  const key=signature(task),indices=remaining.map(tasks=>tasks.findIndex(t=>t.mode==='weekly'&&signature(t)===key));
  if(indices.every(i=>i>=0)){daily.push(task);indices.forEach((index,i)=>remaining[i].splice(index,1));}
 }
 function entries(tasks,width,size){return tasks.flatMap((t,i)=>taskLines(t,width,size).map((text,j)=>({text,gap:i&&j===0?4:0})));}
 function height(lines,lh){return lines.reduce((n,line,i)=>n+lh+(i?line.gap:0),0);}
 function plan(size){
  const lh=size*1.3,dailyRows=[];
  for(let i=0;i<daily.length;i+=2){const pair=daily.slice(i,i+2).map(t=>taskLines(t,W/2-18,size));dailyRows.push({pair,height:Math.max(...pair.map(lines=>lines.length))*lh+5});}
  const dailyHeight=daily.length?27+dailyRows.reduce((n,r)=>n+r.height,0)+6:0,headTop=76+dailyHeight+(daily.length?12:0),bodyTop=headTop+29,available=PH-46-bodyTop;
  const days=remaining.map(tasks=>['weekly','once'].map((mode,i)=>entries(tasks.filter(t=>t.mode===mode),widths[i+1]-16,size)));
  const heights=days.map(cols=>Math.max(64,...cols.map(lines=>height(lines,lh)+18))),total=heights.reduce((a,b)=>a+b,0),fits=total<=available;
  if(fits){const extra=(available-total)/7;return {size,lh,dailyRows,dailyHeight,headTop,bodyTop,days,heights:heights.map(h=>h+extra),pages:1,chunks:days.map(cols=>cols.map(lines=>[lines]))};}
  const rowH=available/7,capacity=rowH-18;
  function chunks(lines){const pages=[[]];let used=0;for(const line of lines){let gap=pages.at(-1).length?line.gap:0;if(used+gap+lh>capacity&&pages.at(-1).length){pages.push([]);used=0;gap=0;}pages.at(-1).push({...line,gap});used+=gap+lh;}return pages;}
  const split=days.map(cols=>cols.map(chunks));return {size,lh,dailyRows,dailyHeight,headTop,bodyTop,days,heights:Array(7).fill(rowH),pages:Math.max(1,...split.flatMap(cols=>cols.map(p=>p.length))),chunks:split};
 }
 let layout=plan(15.5);for(const size of [15,14.5,14]){if(layout.pages===1)break;layout=plan(size);}
 function text(value,x,y,size=layout.size,bold=false){font(size,bold);c.fillStyle='#111';c.textBaseline='top';c.textAlign='left';c.fillText(String(value),x,y);}
 function cell(x,y,w,h,shade=false){if(shade){c.fillStyle='#f1f3f6';c.fillRect(x,y,w,h);}c.strokeStyle='#444';c.lineWidth=.7;c.strokeRect(x,y,w,h);}
 for(let page=0;page<layout.pages;page++){
  c.fillStyle='#fff';c.fillRect(0,0,PW,PH);text(model.title,M,20,23,true);text(model.range,M,51,14);
  if(daily.length){
   cell(M,76,W,layout.dailyHeight);text(model.dailyTitle||'每日固定工作',M+8,82,14,true);let y=102;
   for(const row of layout.dailyRows){row.pair.forEach((lines,col)=>lines.forEach((line,i)=>text(line,M+8+col*W/2,y+i*layout.lh,layout.size,true)));y+=row.height;}
  }
  let x=M;for(let i=0;i<3;i++){cell(x,layout.headTop,widths[i],29,true);text(model.headers[i],x+7,layout.headTop+7,14,true);x+=widths[i];}
  let y=layout.bodyTop;
  for(let i=0;i<7;i++){
   const day=model.days[i],h=layout.heights[i];cell(M,y,labelW,h,true);text(model.weekdays[i],M+7,y+10,15,true);text(day.date.slice(5).replace('-','/'),M+7,y+32,14);
   let x=M+labelW;
   for(let col=0;col<2;col++){
    cell(x,y,widths[col+1],h);let on=y+9;for(const [index,line] of (layout.chunks[i][col][page]||[]).entries()){if(index)on+=line.gap;text(line.text,x+8,on);on+=layout.lh;}x+=widths[col+1];
   }
   y+=h;
  }
  text(`${model.range}    ${page+1} / ${layout.pages}`,M,PH-29,10);
  const blob=await new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('calendar_image_failed')),'image/jpeg',.96));
  images.push({bytes:new Uint8Array(await blob.arrayBuffer()),width:canvas.width,height:canvas.height});
 }
 canvas.width=canvas.height=1;
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
