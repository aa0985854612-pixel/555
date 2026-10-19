'use strict';
/* Exact preview bytes are embedded in a fixed-size portrait A4 PDF. */
window.workCalendarPDF=async function(model){
 const PW=595.28,PH=841.89,SCALE=3,M=24,W=PW-M*2,images=[];
 await document.fonts.ready;
 const canvas=document.createElement('canvas');canvas.width=Math.ceil(PW*SCALE);canvas.height=Math.ceil(PH*SCALE);
 const c=canvas.getContext('2d');c.scale(SCALE,SCALE);
 const family='-apple-system, BlinkMacSystemFont, "Noto Sans CJK TC", "Noto Sans TC", sans-serif';
 const labelW=68,cw=(W-labelW)/2,rowH=98,top=96;
 function font(n,bold=false){c.font=`${bold?'600':'400'} ${n}px ${family}`;}
 function wrap(value,width,size){font(size);const out=[];for(const row of String(value).split('\n')){let line='';for(const ch of row){if(line&&c.measureText(line+ch).width>width){out.push(line);line='';}line+=ch;}out.push(line);}return out;}
 function plan(size){const lh=size*1.35,max=Math.floor((rowH-12)/lh),days=model.days.map(day=>['weekly','once'].map(mode=>day.tasks.filter(t=>t.mode===mode).flatMap(task=>[...wrap((task.time?task.time+' · ':'')+task.title,cw-22,size),...(task.note?wrap(task.note,cw-22,size):[]),''])));return {size,lh,max,days,pages:Math.max(1,...days.flatMap(day=>day.map(lines=>Math.ceil(lines.length/max))))};}
 let layout=plan(11);for(const size of [10,9,8]){if(layout.pages===1)break;layout=plan(size);}
 function text(value,x,y,size=10,bold=false){font(size,bold);c.fillStyle='#111';c.textBaseline='top';c.textAlign='left';c.fillText(String(value),x,y);}
 function cell(x,y,w,h,shade=false){if(shade){c.fillStyle='#f1f3f6';c.fillRect(x,y,w,h);}c.strokeStyle='#555';c.lineWidth=.6;c.strokeRect(x,y,w,h);}
 for(let page=0;page<layout.pages;page++){
  c.fillStyle='#fff';c.fillRect(0,0,PW,PH);text(model.title,M,23,19,true);text(model.range,M,52,11);
  let x=M;for(const [i,w] of [labelW,cw,cw].entries()){cell(x,72,w,24,true);text(model.headers[i],x+7,79,10,true);x+=w;}
  for(let i=0;i<7;i++){
   const y=top+i*rowH,day=model.days[i];cell(M,y,labelW,rowH,true);text(model.weekdays[i],M+6,y+10,10,true);text(day.date.slice(5).replace('-','/'),M+6,y+28,10);
   for(let col=0;col<2;col++){
    const x=M+labelW+col*cw;cell(x,y,cw,rowH);const lines=layout.days[i][col].slice(page*layout.max,(page+1)*layout.max);
    lines.forEach((line,j)=>text(line,x+8,y+7+j*layout.lh,layout.size));
   }
  }
  text(`${model.range}    ${page+1} / ${layout.pages}`,M,803,9);
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
