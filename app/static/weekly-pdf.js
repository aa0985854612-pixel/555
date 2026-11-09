'use strict';
/* One A4: keep the weekly tables readable; use one shared note font and rhythm. */
window.weeklyPdf = async function(model) {
 const PW=595.28,PH=841.89,SCALE=4,M=24,W=PW-2*M,images=[];
 const family='-apple-system, BlinkMacSystemFont, "Noto Sans CJK TC", "Noto Sans TC", sans-serif';
 await document.fonts.ready;
 const measure=document.createElement('canvas').getContext('2d');
 function wrap(value,width,size,bold=false){
  measure.font=`${bold?'600':'400'} ${size}px ${family}`;const out=[];
  for(const line of String(value??'').split('\n')){let part='';for(const ch of line){if(part&&measure.measureText(part+ch).width>width){out.push(part);part='';}part+=ch;}out.push(part);}return out;
 }
 const groups=(model.death_groups||[]).map(g=>({...g,notes:g.notes.slice()}));
 if(!groups.length&&(model.death_notes||[]).length)groups.push({title:model.death_title,notes:model.death_notes.slice()});
 const shipping=(model.shipping_notes||[]).slice();
 const rowFont=(n,scale)=>(n>16?7:8)*scale;
 const footerFont=7.5,footerH=15+36+wrap(model.cumulative,W,8.5,true).length*10.625+5+wrap(model.legend,W,footerFont).length*9.375;
 // Each barn owns its own pane. Long lists use the empty space to its right,
 // rather than pushing the next barn below the previous barn's remaining dates.
 const NOTE_SIZE=8,NOTE_LINE=1.25,NOTE_GAP=.25;
 function noteItems(values,width,size){return values.map(value=>{const parts=wrap(value,width,size);return {parts,height:(parts.length*NOTE_LINE+NOTE_GAP)*size};});}
 // Partition in the original order. A continuation always starts in the next
 // column, and every column shares the same line height and inter-record gap.
 function divide(items,columns){
  if(columns===1||items.length<2)return [items];
  let low=Math.max(...items.map(item=>item.height)),high=items.reduce((n,item)=>n+item.height,0);
  function partition(limit){const out=[[]];let used=0;for(const item of items){if(used+item.height>limit+.0001&&out.at(-1).length){out.push([]);used=0;}out.at(-1).push(item);used+=item.height;}return out;}
  for(let i=0;i<24;i++){const mid=(low+high)/2;if(partition(mid).length<=columns)high=mid;else low=mid;}
  return partition(high+.0001);
 }
 function panePlan(values,width,size,available=0){
  let best=null;
  for(let columns=1;columns<=Math.min(4,Math.max(1,Math.floor(width/48)));columns++){
   const parts=divide(noteItems(values,width/columns-8,size),columns),height=Math.max(0,...parts.map(col=>col.reduce((n,item)=>n+item.height,0)));
   const plan={size,columns,parts,height};
   if(available&&height<=available+.001)return plan;
   if(!best||height<best.height-.001)best=plan;
  }
  return best;
 }
 function notesPlan(size){
  const half=W/2,cols=Math.max(1,Math.min(3,groups.length)),rows=[];
  for(let i=0;i<groups.length;i+=cols){
   const selected=groups.slice(i,i+cols),minimum=half/selected.length*.7,extra=half*.3,total=selected.reduce((n,g)=>n+Math.max(1,g.notes.length),0);
   const barns=selected.map(group=>{const width=minimum+extra*Math.max(1,group.notes.length)/total;return {group,width,...panePlan(group.notes,width,size)};});
   rows.push({barns,height:21+Math.max(0,...barns.map(g=>g.height))});
  }
  const deathH=rows.reduce((n,row)=>n+row.height,0),ship=panePlan(shipping,half,size);
  return {size,cols,rows,height:Math.max(44,18+deathH,39+ship.height)};
 }
 function upperPlan(scale){
  const titleH=26,basicsH=Math.ceil(model.basics.length/3)*26;
  const entryFont=8*scale,entryLH=entryFont*1.25,padding=5*scale;
  const widths=[.12,.24,.19,.20,.25].map(n=>W*n);
  const entryRows=[model.entryHeaders,...model.entries].map((row,index)=>({values:row,height:Math.max(12*scale,padding+Math.max(1,...row.map((v,i)=>wrap(v,widths[i]-6,entryFont,index===0).length))*entryLH)}));
  let height=titleH+basicsH+4+entryRows.reduce((n,row)=>n+row.height,0)+14*scale;
  let preentry=null;
  if(model.preentry?.entries.length){
   const columns=Math.min(4,Math.max(1,Math.ceil(model.preentry.entries.length/12))),perColumn=Math.ceil(model.preentry.entries.length/columns),font=8*scale,lh=font*1.25;
   preentry={columns,perColumn,font,lh,height:16*scale+perColumn*lh+6*scale};height+=preentry.height+4*scale;
  }
  const bands=[];
  for(const inputPage of model.pages)for(const input of inputPage){
   const size=rowFont(input.headers.length,scale),lh=size*1.25,cw=(W-58)/input.headers.length;
   const rows=input.rows.map(row=>{
    const cells=row.cells.map(value=>row.singleLine||row.left?String(value??'').split('\n'):wrap(value,cw-4,size,row.bold));
    const lines=Math.max(1,...cells.map(parts=>parts.length)),minimum=row.left?18*scale:12*scale;
    return {...row,cells,height:Math.max(minimum,(row.height||0)*scale,lines*lh+5*scale)};
   });
   const band={...input,rows,size,headerH:14*scale,cw};height+=band.headerH+rows.reduce((n,row)=>n+row.height,0)+5*scale;bands.push(band);
  }
  return {scale,height,entryRows,entryFont,entryLH,widths,preentry,bands};
 }
 const room=PH-2*M-footerH-6;
 let upper=upperPlan(1),notes=notesPlan(NOTE_SIZE);
 const fits=(u,n)=>u.height+n.height<=room+.001;
 // The weekly detail is the primary record. Keep it at its normal size unless
 // its own content leaves less than a modest minimum area for the notes.
 const noteMinimum=Math.max(136,notesPlan(.05).height);
 if(upper.height+noteMinimum>room){
  let low=.05,high=1;upper=upperPlan(low);
  for(let i=0;i<24;i++){const mid=(low+high)/2,attempt=upperPlan(mid);if(attempt.height+noteMinimum<=room){low=mid;upper=attempt;}else high=mid;}
 }
 if(!fits(upper,notes)){
  let low=.05,high=NOTE_SIZE;notes=notesPlan(low);
  for(let i=0;i<24;i++){const mid=(low+high)/2,attempt=notesPlan(mid);if(fits(upper,attempt)){low=mid;notes=attempt;}else high=mid;}
 }
 if(!fits(upper,notes))throw new Error('weekly_pdf_layout_overflow');
 function fillPane(values,width,height){
  const plan=panePlan(values,width,notes.size,height);
  if(plan.height>height+.01)throw new Error('weekly_pdf_note_overflow');
  plan.draws=[];
  plan.parts.forEach((items,column)=>{let on=0;for(const item of items){plan.draws.push({parts:item.parts,x:4+column*width/plan.columns,y:on});on+=item.height;}});
  return plan;
 }
 const canvas=document.createElement('canvas');canvas.width=Math.ceil(PW*SCALE);canvas.height=Math.ceil(PH*SCALE);
 const c=canvas.getContext('2d');c.scale(SCALE,SCALE);c.fillStyle='#fff';c.fillRect(0,0,PW,PH);c.strokeStyle='#444';c.lineWidth=.5;
 function text(value,x,y,width,size=8,bold=false,align='left',single=false,mono=false,color='#111'){
  const parts=Array.isArray(value)?value:single?[String(value??'')]:wrap(value,width,size,bold);
  c.fillStyle=color;c.textBaseline='top';c.textAlign=align;c.font=`${bold?'600':'400'} ${size}px ${mono?'monospace':family}`;
  for(let i=0;i<parts.length;i++){const ax=x+(align==='center'?width/2:0);c.fillText(parts[i],ax,y+i*size*1.25,width);}
 }
 function box(x,y,w,h,shade=false){if(shade){c.fillStyle='#f0f0f0';c.fillRect(x,y,w,h);}c.strokeRect(x,y,w,h);}
 text(model.title,M,M,W,16,true,'center',true);let y=M+26;
 for(let i=0;i<model.basics.length;i+=3){for(let j=0;j<3;j++){const pair=model.basics[i+j]||['',''],x=M+j*W/3;box(x,y,W/3,26);text(pair[0],x+4,y+2,W/3-8,6.8,false,'left',true);text(pair[1],x+4,y+12,W/3-8,9,true,'left',true);}y+=26;}
 y+=4;
 for(let index=0;index<upper.entryRows.length;index++){const row=upper.entryRows[index];let x=M;row.values.forEach((v,j)=>{box(x,y,upper.widths[j],row.height,index===0);text(v,x+3,y+2*upper.scale,upper.widths[j]-6,upper.entryFont,index===0,'center');x+=upper.widths[j];});y+=row.height;}
 text(model.period,M,y+2*upper.scale,W,7*upper.scale,false,'left',true);y+=14*upper.scale;
 const pre=upper.preentry;
 if(pre){box(M,y,W,pre.height);text(model.preentry.title+' · '+model.preentry.summary,M+3,y+2*upper.scale,W-6,8*upper.scale,true,'left',true);model.preentry.entries.forEach((entry,index)=>text(entry,M+3+Math.floor(index/pre.perColumn)*W/pre.columns,y+16*upper.scale+index%pre.perColumn*pre.lh,W/pre.columns-6,pre.font,false,'left',true,true));y+=pre.height+4*upper.scale;}
 for(const band of upper.bands){
  box(M,y,58,band.headerH,true);text(model.cycle,M+2,y+2*upper.scale,54,7.5*upper.scale,true,'center',true);
  band.headers.forEach((value,j)=>{const x=M+58+j*band.cw;box(x,y,band.cw,band.headerH,true);text(value,x+2,y+2*upper.scale,band.cw-4,band.size,true,'center',true);});y+=band.headerH;
  for(const row of band.rows){box(M,y,58,row.height);text(row.label,M+2,y+2*upper.scale,54,7.5*upper.scale,true,'left',true);row.cells.forEach((parts,j)=>{const x=M+58+j*band.cw;box(x,y,band.cw,row.height);text(parts,x+2,y+2*upper.scale,band.cw-4,band.size,row.bold,row.left?'left':'center',true,row.monospace,row.color);});y+=row.height;}
  y+=5*upper.scale;
 }
 const noteH=PH-M-footerH-y-6,half=W/2;
 for(const [index,title] of [[0,model.death_title],[1,model.shipping_title]]){box(M+index*half,y,half,18,true);text(title,M+index*half+4,y+3,half-8,10.5,true,'left',true);box(M+index*half,y+18,half,noteH-18);}
 function drawPane(plan,x,on,width){for(const entry of plan.draws)text(entry.parts,x+entry.x,on+entry.y,width/plan.columns-8,plan.size,false,'left',true);}
 const baseDeathH=notes.rows.reduce((n,row)=>n+row.height,0),extraDeathH=Math.max(0,noteH-18-baseDeathH);
 let barnY=y+18;
 for(const row of notes.rows){
  const rowH=row.height+extraDeathH*(row.height/baseDeathH);let barnX=M;
  row.barns.forEach((reserved,index)=>{
   const x=barnX,width=reserved.width,plan=fillPane(reserved.group.notes,width,rowH-21);barnX+=width;
   box(x,barnY,width,rowH);text(reserved.group.title,x+4,barnY+3,width-8,8.5,true,'left',true);
   drawPane(plan,x,barnY+17,width);
  });barnY+=rowH;
 }
 drawPane(fillPane(shipping,half,noteH-39),M+half,y+35,half);
 y+=noteH+6;text(model.totalLabel,M,y,W,8.5,true,'left',true);y+=15;
 const totalW=W/Math.max(1,model.totals.length);
 model.totals.forEach((pair,i)=>{const x=M+i*totalW;box(x,y,totalW,30);text(pair[0],x+4,y+3,totalW-8,7,false,'left',true);text(pair[1],x+4,y+15,totalW-8,10,true,'left',true,false,model.total_colors?.[i]);});y+=36;
 text(model.cumulative,M,y,W,8.5,true);y+=wrap(model.cumulative,W,8.5,true).length*10.625+5;text(model.legend,M,y,W,footerFont);
 const blob=await new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('weekly_pdf_image_failed')),'image/jpeg',.96));
 images.push({bytes:new Uint8Array(await blob.arrayBuffer()),width:canvas.width,height:canvas.height});canvas.width=canvas.height=1;
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
