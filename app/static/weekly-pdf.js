'use strict';
/* Fixed A4 pages, drawn locally: Safari does not paginate this PDF again.
   Images contain only the report already authorized and loaded in this tab. */
window.weeklyPdf = async function(model) {
 const PW=595.28,PH=841.89,SCALE=4,M=24,W=PW-2*M,images=[];
 const family='-apple-system, BlinkMacSystemFont, "Noto Sans CJK TC", "Noto Sans TC", sans-serif';
 await document.fonts.ready;
 for(let page=0;page<model.pages.length;page++){
  const canvas=document.createElement('canvas');canvas.width=Math.ceil(PW*SCALE);canvas.height=Math.ceil(PH*SCALE);
  const c=canvas.getContext('2d');c.scale(SCALE,SCALE);c.fillStyle='#fff';c.fillRect(0,0,PW,PH);c.strokeStyle='#444';c.lineWidth=.55;
  const font=(size,bold=false)=>c.font=`${bold?'600':'400'} ${size}px ${family}`;
  function lines(text,width,size,bold=false){font(size,bold);const out=[];for(const line of String(text??'').split('\n')){let part='';for(const ch of line){if(part&&c.measureText(part+ch).width>width){out.push(part);part='';}part+=ch;}out.push(part);}return out;}
  function text(value,x,y,width,size=9,bold=false,align='left',height=100,singleLine=false){
   const lh=size*1.25,all=singleLine?String(value??'').split('\n'):lines(value,width,size,bold),limit=Math.max(1,Math.floor(height/lh)),shown=all.slice(0,limit);
   if(all.length>limit)shown[shown.length-1]='… CSV';
   c.fillStyle='#111';c.textBaseline='top';c.textAlign=align;font(size,bold);
   for(let j=0;j<shown.length;j++){const ax=x+(align==='center'?width/2:0);if(singleLine)c.fillText(shown[j],ax,y+j*lh,width);else c.fillText(shown[j],ax,y+j*lh);}
   return all.length>limit;
  }
  function cell(value,x,y,w,h,{size=9,bold=false,shade=false,align='center',singleLine=false}={}){
   if(shade){c.fillStyle='#f0f0f0';c.fillRect(x,y,w,h);}c.strokeRect(x,y,w,h);const pad=singleLine?1.5:3;text(value,x+pad,y+4,w-2*pad,size,bold,align,h-7,singleLine);
  }
  text(model.title,M,22,W,18,true,'center',26);let y=50;
  for(let i=0;i<model.basics.length;i+=3){for(let j=0;j<3;j++){const pair=model.basics[i+j]||['',''],x=M+j*W/3;cell('',x,y,W/3,31);text(pair[0],x+5,y+3,W/3-10,8,false,'left',11);text(pair[1],x+5,y+14,W/3-10,10,true,'left',14);}y+=31;}
  y+=6;const ew=[.12,.24,.19,.20,.25].map(n=>W*n);
  const entryRows=[model.entryHeaders,...model.entries];for(let i=0;i<entryRows.length;i++){let x=M;for(let j=0;j<5;j++){cell(entryRows[i][j],x,y,ew[j],i?21:19,{size:8.5,bold:i===0,shade:i===0});x+=ew[j];}y+=i?21:19;}
  y+=6;text(model.period+(model.pages.length>1?` (${page+1}/${model.pages.length})`:''),M,y,W,8,false,'left',14);y+=17;
  const pre=model.preentry;
  if(pre){
   const shown=pre.entries.slice(0,6),rows=Math.ceil(shown.length/3),h=18+rows*12+(pre.entries.length>shown.length?12:0)+4;
   cell('',M,y,W,h);text(pre.title+' · '+pre.summary,M+4,y+3,W-8,9,true,'left',13,true);
   shown.forEach((entry,i)=>text(entry,M+4+(i%3)*W/3,y+18+Math.floor(i/3)*12,W/3-8,8.5,false,'left',12,true));
   if(pre.entries.length>shown.length)text(pre.more.replace('{n}',pre.entries.length-shown.length),M+4,y+h-12,W-8,8,false,'left',11,true);
   y+=h+5;
  }
  const bands=model.pages[page],tableHeight=bands.reduce((n,b)=>n+19+b.rows.reduce((sum,r)=>sum+r.height,0)+8,0);
  // Reserve room for the separate pre-entry section and all footer blocks.
  const feedRows=bands.flatMap(b=>b.rows).filter(r=>r.left),shrink=pre&&feedRows.length?Math.max(0,Math.ceil((y+tableHeight+112+8+120-(PH-M))/feedRows.length)):0;
  for(const band of bands){
   const n=band.headers.length,labelW=58,cw=(W-labelW)/n,size=n>16?7:8;
   const rows=[{label:model.cycle,cells:band.headers,height:19,shade:true,bold:true},...band.rows];
   for(const originalRow of rows){const row=originalRow.left?{...originalRow,height:Math.max(30,originalRow.height-shrink)}:originalRow;cell(row.label,M,y,labelW,row.height,{size:8.5,bold:true,shade:row.shade});for(let j=0;j<n;j++)cell(row.cells[j]||'',M+labelW+j*cw,y,cw,row.height,{size:row.bold?size+.5:size,bold:row.bold,shade:row.shade,align:row.left?'left':'center',singleLine:row.singleLine});y+=row.height;}
   y+=8;
  }
  // One death column per barn; each date stays under its own barn heading.
  const groups=model.death_groups||[],shownGroups=groups.slice(0,3),shipping=model.shipping_notes||[],shownShipping=shipping.slice(0,12),half=W/2;
  const extraGroups=groups.length-shownGroups.length,available=PH-M-y-128;
  const cap=Math.max(1,Math.min(6,Math.floor((available-52-(extraGroups?12:0))/10)));
  const deathRows=Math.max(0,...shownGroups.map(g=>Math.min(cap,g.notes.length))),deathMore=shownGroups.some(g=>g.notes.length>cap);
  const noteH=Math.max(44,18+16+deathRows*10+6+(deathMore?12:0)+(extraGroups?12:0),18+Math.ceil(shownShipping.length/2)*12+8+(shipping.length>12?13:0));
  cell(model.death_title||'',M,y,half,18,{size:9,bold:true,shade:true});cell('',M,y+18,half,noteH-18);
  shownGroups.forEach((g,index)=>{
   const cw=half/shownGroups.length,x=M+index*cw,shown=g.notes.slice(0,cap);
   cell(g.title,x,y+18,cw,16,{size:8.5,bold:true,shade:true});cell('',x,y+34,cw,noteH-34);
   shown.forEach((note,i)=>text(note,x+4,y+38+i*10,cw-8,8,false,'left',11,true));
   if(g.notes.length>shown.length)text(model.death_more.replace('{n}',g.notes.length-shown.length),x+4,y+noteH-12-(extraGroups?12:0),cw-8,7.5,false,'left',11,true);
  });
  if(extraGroups)text(model.death_groups_more.replace('{n}',extraGroups),M+4,y+noteH-12,half-8,8,false,'left',11,true);
  const sx=M+half;cell(model.shipping_title||'',sx,y,half,18,{size:9,bold:true,shade:true});cell('',sx,y+18,half,noteH-18);
  shownShipping.forEach((note,i)=>text(note,sx+4+(i%2)*half/2,y+23+Math.floor(i/2)*12,half/2-8,8.5,false,'left',12,true));
  if(shipping.length>shownShipping.length)text(model.shipping_more.replace('{n}',shipping.length-shownShipping.length),sx+4,y+noteH-13,half-8,8,false,'left',12,true);
  y+=noteH+8;
  // Footer stays within the fixed page; long individual cells explicitly point
  // to the full CSV instead of creating an unplanned second page.
  if(y+120>PH-M)throw new Error('weekly_pdf_layout_overflow');
  text(model.totalLabel,M,y,W,9,true,'left',14);y+=15;
  for(let i=0;i<model.totals.length;i++){const x=M+i*W/4,pair=model.totals[i];cell('',x,y,W/4,32);text(pair[0],x+4,y+3,W/4-8,8,false,'left',10);text(pair[1],x+4,y+15,W/4-8,11,true,'left',14);}y+=39;
  text(model.cumulative,M,y,W,9,true,'left',24);y+=27;
  text(model.legend,M,y,W,7.5,false,'left',35);
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
