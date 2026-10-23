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
  const font=(size,bold=false,monospace=false)=>c.font=`${bold?'600':'400'} ${size}px ${monospace?'monospace':family}`;
  function lines(text,width,size,bold=false){font(size,bold);const out=[];for(const line of String(text??'').split('\n')){let part='';for(const ch of line){if(part&&c.measureText(part+ch).width>width){out.push(part);part='';}part+=ch;}out.push(part);}return out;}
  function text(value,x,y,width,size=9,bold=false,align='left',height=100,singleLine=false,monospace=false){
   const lh=size*1.25,all=singleLine?String(value??'').split('\n'):lines(value,width,size,bold),limit=Math.max(1,Math.floor(height/lh)),shown=all.slice(0,limit);
   if(all.length>limit)shown[shown.length-1]='… CSV';
   c.fillStyle='#111';c.textBaseline='top';c.textAlign=align;font(size,bold,monospace);
   const feedScale=monospace&&singleLine?Math.min(1,width/Math.max(1,...all.filter(line=>!line.includes(' · ')).map(line=>c.measureText(line).width))):null;
   for(let j=0;j<shown.length;j++){const ax=x+(align==='center'?width/2:0);if(singleLine)c.fillText(shown[j],ax,y+j*lh,feedScale===null?width:Math.min(width,Math.max(1,c.measureText(shown[j]).width)*feedScale));else c.fillText(shown[j],ax,y+j*lh);}
   return all.length>limit;
  }
  function cell(value,x,y,w,h,{size=9,bold=false,shade=false,align='center',singleLine=false,monospace=false}={}){
   if(shade){c.fillStyle='#f0f0f0';c.fillRect(x,y,w,h);}c.strokeRect(x,y,w,h);const pad=singleLine?1.5:3;text(value,x+pad,y+4,w-2*pad,size,bold,align,h-7,singleLine,monospace);
  }
  text(model.title,M,22,W,18,true,'center',26);let y=50;
  for(let i=0;i<model.basics.length;i+=3){for(let j=0;j<3;j++){const pair=model.basics[i+j]||['',''],x=M+j*W/3;cell('',x,y,W/3,31);text(pair[0],x+5,y+3,W/3-10,8,false,'left',11);text(pair[1],x+5,y+14,W/3-10,10,true,'left',14);}y+=31;}
  y+=6;const ew=[.12,.24,.19,.20,.25].map(n=>W*n);
  const entryRows=[model.entryHeaders,...model.entries];for(let i=0;i<entryRows.length;i++){let x=M;for(let j=0;j<5;j++){cell(entryRows[i][j],x,y,ew[j],i?21:19,{size:8.5,bold:i===0,shade:i===0});x+=ew[j];}y+=i?21:19;}
  y+=6;text(model.period+(model.pages.length>1?` (${page+1}/${model.pages.length})`:''),M,y,W,8,false,'left',14);y+=17;
  const pre=model.preentry;
  if(pre){
   const shown=pre.entries.slice(0,6),rows=shown.length,h=18+rows*12+(pre.entries.length>shown.length?12:0)+4;
   cell('',M,y,W,h);text(pre.title+' · '+pre.summary,M+4,y+3,W-8,9,true,'left',13,true);
   shown.forEach((entry,i)=>text(entry,M+4,y+18+i*12,W-8,8.5,false,'left',12,true,true));
   if(pre.entries.length>shown.length)text(pre.more.replace('{n}',pre.entries.length-shown.length),M+4,y+h-12,W-8,8,false,'left',11,true);
   y+=h+5;
  }
  const bands=model.pages[page],tableHeight=bands.reduce((n,b)=>n+19+b.rows.reduce((sum,r)=>sum+r.height,0)+8,0);
  // Reserve room for the separate pre-entry section and all footer blocks.
  const feedRows=bands.flatMap(b=>b.rows).filter(r=>r.left),shrink=pre&&feedRows.length?Math.max(0,Math.ceil((y+tableHeight+112+8+120-(PH-M))/feedRows.length)):0;
  for(const band of bands){
   const n=band.headers.length,labelW=58,cw=(W-labelW)/n,size=n>16?7:8;
   const rows=[{label:model.cycle,cells:band.headers,height:19,shade:true,bold:true},...band.rows];
   for(const originalRow of rows){const row=originalRow.left?{...originalRow,height:Math.max(30,originalRow.height-shrink)}:originalRow;cell(row.label,M,y,labelW,row.height,{size:8.5,bold:true,shade:row.shade});for(let j=0;j<n;j++)cell(row.cells[j]||'',M+labelW+j*cw,y,cw,row.height,{size:row.bold?size+.5:size,bold:row.bold,shade:row.shade,align:row.left?'left':'center',singleLine:row.singleLine,monospace:row.monospace});y+=row.height;}
   y+=8;
  }
  // Measure complete notes against the space left by the actual tables and footer.
  // Normal reports keep every entry; only a physically full page uses a CSV count.
  const groups=model.death_groups||[],shipping=model.shipping_notes||[],half=W/2;
  const cumulativeH=lines(model.cumulative,W,9,true).length*9*1.25,legendH=lines(model.legend,W,7.5).length*7.5*1.25;
  const footerH=15+39+cumulativeH+6+legendH,available=PH-M-y-8-footerH;
  function notePlan(size,compact=false){
   const lh=size*1.25,gap=1,entryHeight=parts=>parts.length*lh+gap;
   const cols=Math.max(1,Math.min(3,groups.length)),cw=half/cols;
   let visible=groups,extra=0;
   if(compact){const maxRows=Math.max(1,Math.floor((available-18-12+4)/(28+lh+2)));visible=groups.slice(0,maxRows*cols);extra=groups.length-visible.length;}
   const tiles=[];
   for(let i=0;i<visible.length;i+=cols){
    const members=visible.slice(i,i+cols).map(g=>({...g,entries:g.notes.map(note=>lines(note,cw-8,size)),more:0}));
    tiles.push({members,full:Math.max(0,...members.map(g=>g.entries.reduce((n,parts)=>n+entryHeight(parts),0)))});
   }
   const overhead=18+tiles.length*24+Math.max(0,tiles.length-1)*4+(extra?lh+2:0),need=tiles.reduce((n,r)=>n+r.full,0);
   const content=Math.max(0,available-overhead),base=tiles.map(r=>Math.min(r.full,lh+2));
   const spare=Math.max(0,content-base.reduce((n,h)=>n+h,0)),remaining=need-base.reduce((n,h)=>n+h,0);
   tiles.forEach((r,i)=>r.budget=Math.min(r.full,base[i]+(remaining?spare*(r.full-base[i])/remaining:0)));
   for(const tile of tiles){
    if(compact)for(const g of tile.members){
     const budget=tile.budget,total=g.entries.reduce((n,parts)=>n+entryHeight(parts),0);
     if(total>budget){let used=0,count=0;while(count<g.entries.length&&used+entryHeight(g.entries[count])+lh+2<=budget){used+=entryHeight(g.entries[count++]);}g.more=g.entries.length-count;g.entries=g.entries.slice(0,count);}
    }
    tile.height=24+Math.max(0,...tile.members.map(g=>g.entries.reduce((n,parts)=>n+entryHeight(parts),0)+(g.more?lh+2:0)));
   }
   function shippingPlan(columns){
    const width=half/columns,rows=[];
    for(let i=0;i<shipping.length;i+=columns){const entries=shipping.slice(i,i+columns).map(note=>lines(note,width-8,size));rows.push({entries,height:Math.max(...entries.map(entryHeight))});}
    return {columns,width,rows,height:26+rows.reduce((n,r)=>n+r.height,0),more:0};
   }
   const candidates=[shippingPlan(2),shippingPlan(1)],out=candidates.sort((a,b)=>a.height-b.height)[0];
   if(compact&&out.height>available){let used=26,count=0;while(count<out.rows.length&&used+out.rows[count].height+lh+2<=available){used+=out.rows[count++].height;}out.more=out.rows.slice(count).reduce((n,r)=>n+r.entries.length,0);out.rows=out.rows.slice(0,count);out.height=used+(out.more?lh+2:0);}
   return {size,lh,gap,cols,cw,tiles,extra,shipping:out,height:Math.max(44,18+tiles.reduce((n,r)=>n+r.height,0)+Math.max(0,tiles.length-1)*4+(extra?lh+2:0),out.height)};
  }
  let plan;
  for(const size of [8.5,8,7.5,7]){plan=notePlan(size);if(plan.height<=available)break;}
  if(plan.height>available)plan=notePlan(7,true);
  const noteH=plan.height;
  function noteLines(parts,x,on,width){for(let i=0;i<parts.length;i++)text(parts[i],x,on+i*plan.lh,width,plan.size,false,'left',plan.lh+.1,true);}
  cell(model.death_title||'',M,y,half,18,{size:9,bold:true,shade:true});cell('',M,y+18,half,noteH-18);
  let tileY=y+18;
  for(const tile of plan.tiles){
   tile.members.forEach((g,index)=>{
    const x=M+index*plan.cw;
    cell(g.title,x,tileY,plan.cw,16,{size:8.5,bold:true,shade:true});cell('',x,tileY+16,plan.cw,tile.height-16);
    let on=tileY+20;
    for(const parts of g.entries){noteLines(parts,x+4,on,plan.cw-8);on+=parts.length*plan.lh+plan.gap;}
    if(g.more)text(model.death_more.replace('{n}',g.more),x+4,on,plan.cw-8,plan.size,false,'left',plan.lh+.1,true);
   });
   tileY+=tile.height+4;
  }
  if(plan.extra)text(model.death_groups_more.replace('{n}',plan.extra),M+4,y+noteH-plan.lh-2,half-8,plan.size,false,'left',plan.lh+.1,true);
  const sx=M+half;cell(model.shipping_title||'',sx,y,half,18,{size:9,bold:true,shade:true});cell('',sx,y+18,half,noteH-18);
  let shippingY=y+22;
  for(const row of plan.shipping.rows){row.entries.forEach((parts,i)=>noteLines(parts,sx+4+i*plan.shipping.width,shippingY,plan.shipping.width-8));shippingY+=row.height;}
  if(plan.shipping.more)text(model.shipping_more.replace('{n}',plan.shipping.more),sx+4,shippingY,half-8,plan.size,false,'left',plan.lh+.1,true);
  y+=noteH+8;
  // Footer stays within the fixed page; long individual cells explicitly point
  // to the full CSV instead of creating an unplanned second page.
  if(y+footerH>PH-M+.1)throw new Error('weekly_pdf_layout_overflow');
  text(model.totalLabel,M,y,W,9,true,'left',14);y+=15;
  for(let i=0;i<model.totals.length;i++){const x=M+i*W/4,pair=model.totals[i];cell('',x,y,W/4,32);text(pair[0],x+4,y+3,W/4-8,8,false,'left',10);text(pair[1],x+4,y+15,W/4-8,11,true,'left',14);}y+=39;
  text(model.cumulative,M,y,W,9,true,'left',cumulativeH+.1);y+=cumulativeH+6;
  text(model.legend,M,y,W,7.5,false,'left',legendH+.1);
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
