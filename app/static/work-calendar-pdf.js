'use strict';
/* A readable weekly work sheet; images and PDF use exactly the same drawing. */
window.workCalendarPDF=async function(model){
 const PW=595.28,PH=841.89,SCALE=3,M=24,W=PW-M*2,images=[],language=model.language||'zh',presentation=window.calendarPresentation;
 await document.fonts.ready;
 const canvas=document.createElement('canvas');canvas.width=Math.ceil(PW*SCALE);canvas.height=Math.ceil(PH*SCALE);
 const c=canvas.getContext('2d');c.scale(SCALE,SCALE);
 const family='-apple-system, BlinkMacSystemFont, "Noto Sans CJK TC", "Noto Sans TC", sans-serif';
 const labelW=72,widths=[labelW,(W-labelW)*.46,(W-labelW)*.54],navy='#18374b',muted='#516372',lineColor='#cbd5df';
 function font(n,bold=false){c.font=`${bold?'600':'400'} ${n}px ${family}`;}
 function wrap(value,width,size){font(size);const out=[];for(const row of String(value).split('\n')){let part='';for(const ch of row){if(part&&c.measureText(part+ch).width>width){out.push(part);part='';}part+=ch;}out.push(part);}return out;}
 function taskLines(row,width,size,withTime=true){const t=presentation.task(row,language);return [...wrap((withTime&&t.timeLabel?t.timeLabel+'｜':'')+t.title,width,size),...(t.note?wrap(t.note,width,size):[])];}
 function routineRows(rows,size){
  const groups=presentation.groups(rows,language),result=[],columns=Math.max(1,Math.min(3,groups.length)),cw=(W-10*(columns-1))/columns,lh=size*1.3;
  for(let i=0;i<groups.length;i+=columns){const cards=groups.slice(i,i+columns).map(group=>({...group,lines:group.tasks.flatMap((row,index)=>taskLines(row,cw-30,size,false).map((text,j)=>({text,first:j===0,gap:index&&j===0?5:0})))}));
   result.push({cards,height:Math.max(...cards.map(card=>40+card.lines.reduce((n,item,i)=>n+lh+(i?item.gap:0),0)+10))});
  }
  return {rows:result,columns,height:result.length?24+result.reduce((n,row)=>n+row.height,0)+(result.length-1)*8:0};
 }
 const {daily,remaining}=presentation.sharedDaily(model.days,rows=>routineRows(rows,17).height<=150);
 function entries(rows,width,size){return rows.flatMap((row,index)=>taskLines(row,width-11,size).map((text,j)=>({text,first:j===0,gap:index&&j===0?7:0})));}
 function height(lines,lh){return lines.reduce((n,item,i)=>n+lh+(i?item.gap:0),0);}
 function plan(size){
  const lh=size*1.32,routines=routineRows(daily,size),headTop=78+routines.height+(daily.length?14:0),bodyTop=headTop+30,available=PH-46-bodyTop;
  const days=remaining.map(rows=>['weekly','once'].map((mode,i)=>entries(rows.filter(row=>row.mode===mode),widths[i+1]-18,size)));
  const heights=days.map(cols=>Math.max(59,...cols.map(lines=>height(lines,lh)+20))),total=heights.reduce((a,b)=>a+b,0);
  if(total<=available){const extra=(available-total)/7;return {size,lh,routines,headTop,bodyTop,heights:heights.map(h=>h+extra),pages:1,chunks:days.map(cols=>cols.map(lines=>[lines]))};}
  const rowH=available/7,capacity=rowH-20;
  function chunks(lines){const result=[[]];let used=0;for(const item of lines){let gap=result.at(-1).length?item.gap:0;if(used+gap+lh>capacity&&result.at(-1).length){result.push([]);used=0;gap=0;}result.at(-1).push({...item,gap});used+=gap+lh;}return result;}
  const split=days.map(cols=>cols.map(chunks));return {size,lh,routines,headTop,bodyTop,heights:Array(7).fill(rowH),pages:Math.max(1,...split.flatMap(cols=>cols.map(p=>p.length))),chunks:split};
 }
 let layout=plan(17);for(const size of [16.5,16,15,14.5,14]){if(layout.pages===1)break;layout=plan(size);}
 function text(value,x,y,size=layout.size,bold=false,color='#18242d'){font(size,bold);c.fillStyle=color;c.textBaseline='top';c.textAlign='left';c.fillText(String(value),x,y);}
 function rect(x,y,w,h,fill='#fff',stroke=true){c.fillStyle=fill;c.fillRect(x,y,w,h);if(stroke){c.strokeStyle=lineColor;c.lineWidth=.55;c.strokeRect(x,y,w,h);}}
 function dot(x,y){c.beginPath();c.arc(x,y,1.8,0,Math.PI*2);c.fillStyle='#3b6470';c.fill();}
 for(let page=0;page<layout.pages;page++){
  rect(0,0,PW,PH,'#fff',false);text(model.title,M,20,23,true,navy);text(model.range,M,53,14,false,muted);
  if(daily.length){
   text(model.dailyTitle||(language==='zh'?'每天都要做':'Việc mỗi ngày'),M,80,14.5,true,navy);let y=102;
   for(const row of layout.routines.rows){row.cards.forEach((card,index)=>{const w=(W-10*(layout.routines.columns-1))/layout.routines.columns,x=M+index*(w+10);rect(x,y,w,row.height,index?'#f8f5ef':'#f1f6fa');rect(x,y,3,row.height,index?'#947044':'#355c79',false);text(card.time||(language==='zh'?'每天完成':'Mỗi ngày'),x+13,y+10,16,true,navy);let on=y+37;for(const [i,item] of card.lines.entries()){if(i)on+=item.gap;if(item.first)dot(x+15,on+layout.size*.55);text(item.text,x+24,on);on+=layout.lh;}});y+=row.height+8;}
  }
  let x=M;for(let i=0;i<3;i++){rect(x,layout.headTop,widths[i],30,navy,false);text(model.headers[i],x+9,layout.headTop+8,14.5,true,'#fff');x+=widths[i];}
  let y=layout.bodyTop;
  for(let i=0;i<7;i++){
   const day=model.days[i],h=layout.heights[i],weekend=(day.weekday??i)>=5;rect(M,y,labelW,h,weekend?'#fff5f5':'#f1f5f9');text(day.date.slice(5).replace('-','/'),M+9,y+10,17,true,weekend?'#755e63':navy);text(model.weekdays[i],M+9,y+34,14,false,weekend?'#755e63':muted);let x=M+labelW;
   for(let col=0;col<2;col++){rect(x,y,widths[col+1],h,weekend?'#fffbfb':'#fff');let on=y+10;for(const [index,item] of (layout.chunks[i][col][page]||[]).entries()){if(index)on+=item.gap;if(item.first)dot(x+10,on+layout.size*.55);text(item.text,x+18,on);on+=layout.lh;}x+=widths[col+1];}y+=h;
  }
  text(`${model.range}    ${page+1} / ${layout.pages}`,M,PH-29,10,false,muted);
  const blob=await new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('calendar_image_failed')),'image/jpeg',.96));images.push({bytes:new Uint8Array(await blob.arrayBuffer()),width:canvas.width,height:canvas.height});
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
