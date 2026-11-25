'use strict';
/* One A4: keep the weekly tables readable; use one shared note font and rhythm. */
const WEEKLY_PDF_WIDTH=595.28,WEEKLY_PDF_HEIGHT=841.89,WEEKLY_PDF_SCALE=5.5;
window.weeklyPdf = async function(model) {
 const PW=WEEKLY_PDF_WIDTH,PH=WEEKLY_PDF_HEIGHT,SCALE=WEEKLY_PDF_SCALE,M=24,W=PW-2*M;
 if(model.nancyTemplate)return renderNancyWeeklyPdf(model);
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
 const basicColumns=model.basicColumns||3,basicHeight=model.basicColumns?22:26;
 const inlineTotals=model.pages.some(page=>page.some(band=>band.summary));
 const footerFont=7.5,footerH=(inlineTotals?0:51)+wrap(model.cumulative,W,8.5,true).length*10.625+5+wrap(model.legend,W,footerFont).length*9.375;
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
  const titleH=26,basicsH=Math.ceil(model.basics.length/basicColumns)*basicHeight;
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
   const size=rowFont(input.headers.length,scale),lh=size*1.25,cw=(W-58)/(model.weekColumns||input.headers.length);
   const rows=input.rows.map(row=>{
    const cells=row.cells.map(value=>row.singleLine||row.left?String(value??'').split('\n'):wrap(value,cw-4,size,row.bold));
    const lines=Math.max(1,...cells.map(parts=>parts.length)),minimum=row.left?18*scale:12*scale;
    return {...row,cells,height:Math.max(minimum,(row.height||0)*scale,lines*lh+5*scale)};
   });
   const band={...input,rows,size,headerH:14*scale,stageH:input.stages?.length?15*scale:0,cw};height+=band.stageH+band.headerH+rows.reduce((n,row)=>n+row.height,0)+5*scale;bands.push(band);
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
 const basicWidth=W/basicColumns;
 for(let i=0;i<model.basics.length;i+=basicColumns){
  for(let j=0;j<basicColumns;j++){
   const pair=model.basics[i+j]||['',''],x=M+j*basicWidth;
   box(x,y,basicWidth,basicHeight);
   text(pair[0],x+4,y+2,basicWidth-8,6.8,false,'left',true);
   text(pair[1],x+4,y+10,basicWidth-8,9,true,'left',true);
  }
  y+=basicHeight;
 }
 y+=4;
 for(let index=0;index<upper.entryRows.length;index++){const row=upper.entryRows[index];let x=M;row.values.forEach((v,j)=>{box(x,y,upper.widths[j],row.height,index===0);text(v,x+3,y+2*upper.scale,upper.widths[j]-6,upper.entryFont,index===0,'center');x+=upper.widths[j];});y+=row.height;}
 text(model.period,M,y+2*upper.scale,W,7*upper.scale,false,'left',true);y+=14*upper.scale;
 const pre=upper.preentry;
 if(pre){box(M,y,W,pre.height);text(model.preentry.title+' · '+model.preentry.summary,M+3,y+2*upper.scale,W-6,8*upper.scale,true,'left',true);model.preentry.entries.forEach((entry,index)=>text(entry,M+3+Math.floor(index/pre.perColumn)*W/pre.columns,y+16*upper.scale+index%pre.perColumn*pre.lh,W/pre.columns-6,pre.font,false,'left',true,true));y+=pre.height+4*upper.scale;}
 for(const band of upper.bands){
  const summaryX=M+58+band.headers.length*band.cw,summaryW=M+W-summaryX;
  box(M,y,58,band.headerH+band.stageH,true);
  text(model.cycle,M+2,y+2*upper.scale,54,7.5*upper.scale,true,'center',true);
  if(band.stageH){
   let x=M+58;
   for(const [label,count] of band.stages){
    const width=count*band.cw;
    box(x,y,width,band.stageH,true);
    text(label,x+3,y+2*upper.scale,width-6,band.size,true,'center',true);
    x+=width;
   }
   y+=band.stageH;
  }
  band.headers.forEach((value,j)=>{
   const x=M+58+j*band.cw;
   box(x,y,band.cw,band.headerH,true);
   text(value,x+2,y+2*upper.scale,band.cw-4,band.size,true,'center',true);
  });
  if(band.summary){
   box(summaryX,y,summaryW,band.headerH,true);
   text(model.formTotalLabel,summaryX+4,y+2*upper.scale,summaryW-8,band.size,true,'center',true);
  }
  y+=band.headerH;
  for(const row of band.rows){
   const on=y+2*upper.scale;
   box(M,y,58,row.height);
   text(row.label,M+2,on,54,7.5*upper.scale,true,'left',true);
   row.cells.forEach((parts,j)=>{
    const x=M+58+j*band.cw;
    box(x,y,band.cw,row.height);
    text(parts,x+2,on,band.cw-4,band.size,row.bold,row.left?'left':'center',true,row.monospace,row.color);
   });
   if(band.summary){
    box(summaryX,y,summaryW,row.height);
    const total=model.totals[row.totalIndex];
    if(total){
     text(total[0],summaryX+4,on,summaryW/2-8,band.size,false,'left',true);
     text(total[1],summaryX+summaryW/2,on,summaryW/2-4,band.size,true,'center',true,false,model.total_colors?.[row.totalIndex]);
    }
   }
   y+=row.height;
  }
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
 y+=noteH+6;
 if(!inlineTotals){
  text(model.totalLabel,M,y,W,8.5,true,'left',true);y+=15;
  const totalW=W/Math.max(1,model.totals.length);
  model.totals.forEach((pair,i)=>{const x=M+i*totalW;box(x,y,totalW,30);text(pair[0],x+4,y+3,totalW-8,7,false,'left',true);text(pair[1],x+4,y+15,totalW-8,10,true,'left',true,false,model.total_colors?.[i]);});y+=36;
 }
 text(model.cumulative,M,y,W,8.5,true);y+=wrap(model.cumulative,W,8.5,true).length*10.625+5;text(model.legend,M,y,W,footerFont);
 return weeklyCanvasPdf(canvas);
};

async function weeklyCanvasPdf(canvas){
 const canvases=Array.isArray(canvas)?canvas:[canvas];
 const PW=WEEKLY_PDF_WIDTH,PH=WEEKLY_PDF_HEIGHT;
 const images=[];
 const firstPageImage=await new Promise((resolve,reject)=>canvases[0].toBlob(
  blob=>blob?resolve(blob):reject(new Error('weekly_image_failed')),'image/png'
 ));
 for(const page of canvases){
  const blob=await new Promise((resolve,reject)=>page.toBlob(b=>b?resolve(b):reject(new Error('weekly_pdf_image_failed')),'image/jpeg',.96));
  images.push({bytes:new Uint8Array(await blob.arrayBuffer()),width:page.width,height:page.height});
  page.width=page.height=1;
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
 pdf.firstPageImage=firstPageImage;
 return pdf;
}

// Coordinates follow the original print grid with the two source pages joined.
async function renderNancyWeeklyPdf(model){
 const template=new Image();
 template.src='/weekly-nancy-template.png';
 await Promise.all([template.decode(),document.fonts.ready]);
 const canvas=document.createElement('canvas'),scale=WEEKLY_PDF_SCALE;
 canvas.width=Math.ceil(WEEKLY_PDF_WIDTH*scale);
 canvas.height=Math.ceil(WEEKLY_PDF_HEIGHT*scale);
 const ctx=canvas.getContext('2d');
 ctx.fillStyle='#fff';
 ctx.fillRect(0,0,canvas.width,canvas.height);
 const formWidthScale=.79*scale,formHeightScale=.72*scale;
 ctx.translate((canvas.width-690*formWidthScale)/2,21*scale);
 ctx.scale(formWidthScale,formHeightScale);
 ctx.translate(-62,-69);
 const cleanTemplate=document.createElement('canvas');
 cleanTemplate.width=template.naturalWidth;cleanTemplate.height=template.naturalHeight;
 const templateCtx=cleanTemplate.getContext('2d');
 templateCtx.drawImage(template,0,0);
 const pixels=templateCtx.getImageData(0,0,cleanTemplate.width,cleanTemplate.height);
 for(let i=0;i<pixels.data.length;i+=4){
  if(pixels.data[i]>210&&pixels.data[i+1]>210&&pixels.data[i+2]<100)pixels.data[i+2]=255;
 }
 templateCtx.putImageData(pixels,0,0);
 ctx.drawImage(cleanTemplate,62,69,690,1094);

 const black='#111111',family='"Noto Serif CJK TC", "Noto Serif TC", "PMingLiU", serif';
 function drawLines(lines,x,y,width,height,{size=12,align='left',color=black,bold=false}={}){
  if(!lines.length)return;
  size=Math.min(size,(height-2)/(lines.length*1.22));
  ctx.font=`${bold?700:400} ${size}px ${family}`;
  ctx.fillStyle=color;
  ctx.textAlign=align;
  ctx.textBaseline='top';
  const left=align==='center'?x+width/2:x+2;
  const top=y+(height-lines.length*size*1.22)/2;
  lines.forEach((line,index)=>ctx.fillText(line,left,top+index*size*1.22,width-4));
 }
 // Preserve the logo and title from the source sheet while removing the
 // spreadsheet's unused cells around the logo and inside the heading fields.
 ctx.fillStyle='#fff';
 ctx.fillRect(64,69,206,58);
 ctx.fillRect(510,69,236,58);
 ctx.fillRect(64,69,682,5);
 ctx.fillRect(64,126,5,34);
 ctx.fillRect(742,126,5,34);
 ctx.fillRect(67,163,677,59);
 const headerRows=[
  {top:163,bottom:193,columns:[['牧場',0,116],['豬源',1,110],['飼料',2,177],['肉豬批號',3,276]]},
  {top:193,bottom:223,columns:[['入場頭數',4,160],['入場日期',5,191],['入場日齡',6,162],['入場均重',7,166]]}
 ];
 ctx.strokeStyle=black;
 ctx.lineWidth=.9;
 ctx.beginPath();
 ctx.moveTo(66,193);ctx.lineTo(745,193);
 for(const {top,bottom,columns} of headerRows){
  let x=66;
  for(const [label,index,width] of columns){
   if(x>66){ctx.moveTo(x,top);ctx.lineTo(x,bottom);}
   const value=model.basics[index]?.[1]||'—';
   const entries=model.headerEntries||[];
   const dates=[...new Set(entries.map(entry=>entry.date||'—'))];
   const weights=[...new Set(entries.map(entry=>entry.mean==null?null:entry.mean))];
   const separate=(index===4||index===5)?dates.length>1:index===7&&weights.length>1;
   if(separate){
    const shortDate=date=>date?Number(date.slice(5,7))+'/'+Number(date.slice(8,10)):'—';
    let lines;
    if(index===4){
     lines=dates.map(date=>{
      const counts=entries.filter(entry=>entry.date===date).map(entry=>entry.count);
      const total=counts.every(count=>count!=null)?counts.reduce((sum,count)=>sum+count,0)+'頭':'—';
      return shortDate(date)+' '+total;
     });
    }else if(index===5){
     lines=dates;
    }else{
     lines=[...new Set(entries.map(entry=>shortDate(entry.meanDate||entry.date)+' '+(entry.mean==null?'—':entry.mean+' kg')))];
    }
    ctx.font=`600 13px ${family}`;
    const labelWidth=ctx.measureText(label+'：').width+2;
    drawLines([label+'：'],x+5,top,labelWidth,bottom-top,{size:13,bold:true});
    drawLines(lines,x+5+labelWidth,top,width-labelWidth-12,bottom-top,{size:12});
   }else{
    drawLines([label+'：'+value],x+7,top,width-14,bottom-top,{size:14});
   }
   x+=width;
  }
 }
 ctx.stroke();

 // The source places the selected barns in the finishing-stage header.
 const barnNames=model.basics[8]?.[1]||'';
 ctx.fillStyle='#fff';ctx.fillRect(508,224,235,28);
 drawLines(['肉豬段棟舍：'+barnNames],510,224,232,28,{size:13,align:'center'});

 const weekColumns=[125,172,220,268,315,363,411,459,506,554,602,650,698,745];
 const sections=[
  {week:4,x:weekColumns,y:[283,307,331,355,425,449],headerTop:223,notesBottom:478},
  {week:17,x:weekColumns,y:[508,532,555,580,680,704],headerTop:478,notesBottom:762},
  {week:30,x:weekColumns.slice(0,4),y:[792,823,854,884,926,952],headerTop:762,notesBottom:1007}
 ];
 function panel(x,y,width,height,fill='#fff'){
  ctx.fillStyle=fill;ctx.fillRect(x,y,width,height);
  ctx.strokeStyle=black;ctx.lineWidth=.9;ctx.strokeRect(x,y,width,height);
 }
 function leftLabel(lines,top,bottom){
  panel(66,top,59,bottom-top,'#f4f4f4');
  drawLines(lines,67,top,57,bottom-top,{size:17,bold:true,align:'center'});
 }
 const rowLabels=[['起始日'],['淘汰數'],['死亡數'],['飼料量','（噸）'],['售出數']];
 const bands=model.pages.flat(),extraWeeks=bands.filter(band=>band.firstWeek==null);
 // One size across every feed cell, accounting for both height and line width.
 let feedSize=17;
 ctx.font=`800 17px ${family}`;
 for(const {week,x,y} of sections){
  const row=bands.find(band=>band.firstWeek===week)?.rows[3];
  if(!row)continue;
  const height=week===4?y[5]-y[3]:y[4]-y[3];
  row.cells.forEach((value,column)=>{
   if(!value)return;
   const lines=value.split('\n'),width=x[column+1]-x[column]-4;
   feedSize=Math.min(feedSize,(height-2)/(lines.length*1.22));
   const split=lines.map(line=>{
    const plus=line.indexOf('+');
    return plus<0?{date:'',amount:line}:{date:line.slice(0,plus).trim(),amount:line.slice(plus)};
   });
   const dateWidth=Math.max(0,...split.map(line=>ctx.measureText(line.date).width));
   const amountWidth=Math.max(0,...split.map(line=>ctx.measureText(line.amount).width));
   if(dateWidth+amountWidth>0)feedSize=Math.min(feedSize,17*width/(dateWidth+amountWidth));
  });
 }


 for(const {week,x,y,headerTop,notesBottom} of sections){
  const band=bands.find(band=>band.firstWeek===week);
  leftLabel(['週期'],headerTop,y[0]);
  if(week===17){
   for(let column=0;column<x.length-1;column++){
    const width=x[column+1]-x[column];
    panel(x[column],headerTop,width,y[0]-headerTop);
    drawLines([String(week+column)+'w'],x[column],headerTop,width,y[0]-headerTop,{size:15,bold:true,align:'center'});
   }
  }
  for(const [rowIndex,label] of rowLabels.entries()){
   if(week===4&&rowIndex===4)continue;
   const top=y[rowIndex],height=week===4&&rowIndex===3?y[5]-top:y[rowIndex+1]-top;
   leftLabel(label,top,top+height);
   const row=band?.rows[rowIndex];
   for(let column=0;column<x.length-1;column++){
    const width=x[column+1]-x[column],value=row?.cells[column];
    panel(x[column],top,width,height);
    if(!value)continue;
    const parts=value.split('\n'),feed=rowIndex===3;
    if(feed&&parts.some(line=>line.includes('+'))){
     ctx.font=`800 ${feedSize}px ${family}`;
     ctx.fillStyle=black;ctx.textBaseline='top';
     const dateWidth=Math.max(0,...parts.map(line=>ctx.measureText(line.split('+')[0].trim()).width));
     const plusX=x[column]+2+dateWidth;
     const startY=top+(height-parts.length*feedSize*1.22)/2;
     parts.forEach((line,index)=>{
      const plus=line.indexOf('+'),lineY=startY+index*feedSize*1.22;
      if(plus<0){ctx.textAlign='left';ctx.fillText(line,x[column]+2,lineY);return;}
      ctx.textAlign='right';ctx.fillText(line.slice(0,plus).trim(),plusX,lineY);
      ctx.textAlign='left';ctx.fillText(line.slice(plus),plusX,lineY);
     });
    }else{
     drawLines(parts,x[column],top,width,height,{
      size:feed?feedSize:12,align:feed?'left':'center',color:row.color,bold:feed||row.bold
     });
    }
   }
  }
  leftLabel(['備註'],y.at(-1),notesBottom);
  for(let column=0;column<x.length-1;column++)panel(x[column],y.at(-1),x[column+1]-x[column],notesBottom-y.at(-1));
  if(week===17){
   const reminders={17:['安排棟舍','豬隻秤重'],23:['安排棟舍','豬隻秤重'],24:['安排空白料','起始日'],27:['開始出豬'],28:['開始出豬']};
   for(const [number,lines] of Object.entries(reminders)){
    const column=Number(number)-week;
    drawLines(lines,x[column],y.at(-1),x[column+1]-x[column],notesBottom-y.at(-1),{size:10,bold:true,align:'center'});
   }
  }
 }
 const totalRows=[[854,884],[884,926],[926,952]];
 panel(268,823,95,31);
 // Align the totals' feed and sales rows with the resized weekly rows.
 for(const [index,unit] of [[1,'噸'],[2,'頭']]){
  const [top,bottom]=totalRows[index];
  panel(268,top,95,bottom-top);
  drawLines([unit],344,top,18,bottom-top,{size:13,bold:true,align:'center'});
 }
 model.totals.forEach(([,value],index)=>{
  if(!value)return;
  const [top,bottom]=totalRows[index];
  drawLines([value],269,top,72,bottom-top,{align:'center',bold:true,color:model.total_colors[index]});
 });
 panel(268,952,95,23,'#f4f4f4');
 drawLines(['育成率'],269,952,93,23,{align:'center',size:16,bold:true});
 if(model.survival)drawLines([model.survival],269,975,75,31,{align:'center',bold:true});

 const deaths=model.death_groups.flatMap(group=>[
  {value:group.title,bold:true},...group.notes.map(value=>({value}))
 ]);
 const metadata=[
  ...model.basics.slice(8).filter(([,value])=>value).map(([label,value])=>({value:label+' '+value})),
  ...model.entries.map(entry=>({value:entry.filter(Boolean).join(' · ').replace(/\n/g,' · ')})),
  {value:model.period},{value:model.cumulative},
  ...(model.preentry?[{value:model.preentry.title+' '+model.preentry.summary,bold:true},...model.preentry.entries.map(value=>({value}))]:[]),
  {value:model.legend}
 ];
 function fitNotes(items,x,top,width,height,sizeLimit){
  function flow(size,columns){
   const lines=[],columnWidth=width/columns;
   for(const {value,bold,color} of items){
    ctx.font=`${bold?700:400} ${size}px ${family}`;
    let line='';
    for(const char of value){
     if(line&&ctx.measureText(line+char).width>columnWidth-5){
      lines.push({line,bold,color});line='';
     }
     line+=char;
    }
    if(line)lines.push({line,bold,color});
   }
   const perColumn=Math.floor(height/(size*1.22));
   return {lines,columnWidth,perColumn,fits:perColumn*columns>=lines.length};
  }
  let low=.01,high=sizeLimit,best;
  for(let attempt=0;attempt<24;attempt++){
   const size=(low+high)/2;
   const layout=[1,2,3].map(columns=>flow(size,columns)).find(plan=>plan.fits);
   if(layout){low=size;best=layout;}else high=size;
  }
  best?.lines.forEach(({line,bold,color},i)=>drawLines([line],
   x+Math.floor(i/best.perColumn)*best.columnWidth,top+(i%best.perColumn)*low*1.22,
   best.columnWidth,low*1.22+2,{size:low,bold,color}));
 }
 const details=extraWeeks.flatMap(band=>band.headers.flatMap((heading,i)=>{
  const items=band.rows.flatMap(row=>row.cells[i]?row.cells[i].split('\n').map(value=>({value:row.label+' '+value,color:row.color})):[]);
  return items.length?[{value:heading,bold:true},...items]:[];
 }));
 panel(363,762,382,30,'#f4f4f4');
 drawLines([model.shipping_title],364,762,380,30,{bold:true,size:17,align:'center'});
 panel(363,792,382,285);
 fitNotes(model.shipping_notes.map(value=>({value})),370,801,367,268,14);

 // PR and APP retain separate dates, bottle counts and completion states.
 const plans=new Map((model.vaccinePlans||[]).filter(plan=>plan.scope!=='cohort').map(plan=>[plan.batch_id,plan]));
 const sharedPlans=(model.vaccinePlans||[]).filter(plan=>plan.scope==='cohort');
 const batchIds=model.vaccineBatchIds||[];
 const vaccineCells=[
  {key:'pr1',x:220,top:1063,bottleTop:1089},
  {key:'app1',x:268,top:1063,bottleTop:1089},
  {key:'pr2',x:220,top:1113,bottleTop:1137},
  {key:'app2',x:268,top:1113,bottleTop:1137}
 ];
 const vaccineStatus={};
 for(const cell of vaccineCells){
  const doses=sharedPlans.length?sharedPlans.map(plan=>plan.doses?.[cell.key]):batchIds.map(id=>plans.get(id)?.doses?.[cell.key]);
  const dates=[...new Set(doses.map(dose=>dose?.date||''))];
  const bottles=[...new Set(doses.map(dose=>dose?.bottles??null))];
  const complete=doses.length>0&&doses.every(dose=>dose?.done);
  const partial=!complete&&doses.some(dose=>dose?.done);
  const values=dates.filter(Boolean).map(date=>date.slice(5).replace('-','/'));
  if(dates.length>1&&dates.includes(''))values.push('—');
  drawLines(values,cell.x+1,cell.top,46,26,{size:11,align:'center'});
  const amounts=bottles.filter(value=>value!=null).map(String);
  if(bottles.length>1&&bottles.includes(null))amounts.push('—');
  drawLines(amounts,cell.x+1,cell.bottleTop,46,24,{size:11,align:'center'});
  vaccineStatus[cell.key]=complete?'complete':partial?'partial':'';
 }
 function vaccineCheck(x,y){
  ctx.save();ctx.strokeStyle='#b42332';ctx.lineWidth=1.7;
  ctx.beginPath();ctx.moveTo(x,y+5);ctx.lineTo(x+4,y+9);ctx.lineTo(x+12,y);ctx.stroke();ctx.restore();
 }
 for(const [round,top,bottleTop] of [[1,1063,1089],[2,1113,1137]]){
  const pr=vaccineStatus['pr'+round],app=vaccineStatus['app'+round];
  if(pr==='complete'&&app==='complete'){
   vaccineCheck(331,top+8);
   vaccineCheck(331,bottleTop+7);
   continue;
  }
  const states=[['PR',pr],['APP',app]].filter(([,status])=>status);
  states.forEach(([name,status],index)=>{
   const height=states.length===1?26:13,on=top+index*height;
   drawLines([name+(status==='partial'?' 部分':'')],317,on,status==='partial'?44:23,height,{size:states.length===1?9:7,bold:true});
   if(status==='complete')vaccineCheck(344,on+(height-9)/2);
  });
 }
 // Replace the source sheet's thick borders with the same line used by the
 // generated cells. Draw the whole grid as one path to keep joins consistent.
 ctx.beginPath();
 function gridLine(x1,y1,x2,y2){ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);}
 ctx.rect(66,162,679,1000);
 for(const y of [193,223])gridLine(66,y,745,y);
 for(const row of headerRows){
  let x=66;
  for(const column of row.columns.slice(0,-1)){
   x+=column[2];gridLine(x,row.top-1,x,row.bottom);
  }
 }
 gridLine(125,223,125,1007);
 gridLine(506,223,506,253);
 gridLine(125,253,745,253);
 for(const x of weekColumns.slice(1,-1))gridLine(x,253,x,478);
 for(const y of [283,307,331,355,449,478])gridLine(66,y,745,y);
 for(const x of weekColumns.slice(1,-1))gridLine(x,478,x,762);
 for(const y of [508,532,555,580,680,704,762])gridLine(66,y,745,y);
 for(const x of [172,220,268])gridLine(x,762,x,1007);
 gridLine(363,762,363,1162);
 for(const y of [792,823,854,884,926,952])gridLine(66,y,363,y);
 gridLine(268,975,363,975);
 gridLine(66,1007,363,1007);
 for(const y of [1036,1063,1089,1113,1137])gridLine(66,y,363,y);
 for(const x of [220,268,315])gridLine(x,1036,x,1162);
 gridLine(363,792,745,792);
 gridLine(363,1077,745,1077);
 ctx.strokeStyle='#fff';ctx.lineWidth=4;ctx.lineJoin='miter';ctx.stroke();
 ctx.strokeStyle=black;ctx.lineWidth=.9;ctx.stroke();


 // A second A4 carries the supporting entries, including records beyond 32 weeks.
 const detailCanvas=document.createElement('canvas');
 detailCanvas.width=canvas.width;detailCanvas.height=canvas.height;
 const detailCtx=detailCanvas.getContext('2d');
 detailCtx.fillStyle='#fff';detailCtx.fillRect(0,0,detailCanvas.width,detailCanvas.height);
 detailCtx.scale(scale,scale);
 detailCtx.fillStyle=black;detailCtx.textBaseline='top';
 const pageItems=[
  {value:model.title+' · 明細',bold:true},
  ...model.basics.filter(([,value])=>value).map(([label,value])=>({value:label+'：'+value})),
  {value:'各棟進場資料',bold:true},
  ...model.entries.map(entry=>({value:entry.filter(Boolean).join(' · ').replace(/\n/g,' · ')})),
  {value:'疫苗施打明細',bold:true},
  ...(model.vaccinePlans||[]).flatMap(plan=>[
   {value:plan.scope==='cohort'?'整批':model.vaccineBarns?.[plan.batch_id]||'',bold:true},
   ...['pr1','app1','pr2','app2'].flatMap(key=>{
    const dose=plan.doses[key];
    if(!dose.date&&dose.bottles==null&&!dose.done)return [];
    const name=key.startsWith('pr')?'PR':'APP';
    const number=key.endsWith('1')?'第一次':'第二次';
    return [{value:name+' '+number+' '+(dose.date||'—')+' · '+(dose.bottles==null?'—':dose.bottles+' 瓶')+' · '+(dose.done?'已施打':'未施打')}];
   })
  ]),
  {value:model.death_title,bold:true},...deaths,
  {value:model.shipping_title,bold:true},...model.shipping_notes.map(value=>({value})),
  {value:'每週飼料明細',bold:true},
  ...bands.flatMap(band=>band.headers.flatMap((heading,i)=>{
   const feed=band.rows[3]?.cells[i];
   return feed?[{value:heading+'  '+feed.replace(/\n/g,'  ')}]:[];
  })),
  ...details,
  ...bands.flatMap(band=>band.headers.flatMap((heading,i)=>{
   const sale=band.rows[4]?.cells[i];
   return sale?[{value:heading+' 售出數 '+sale}]:[];
  })),
  ...(model.preentry?[{value:model.preentry.title+' '+model.preentry.summary,bold:true},...model.preentry.entries.map(value=>({value}))]:[]),
  {value:model.period},{value:model.cumulative}
 ];
 function detailLayout(size){
  const lines=[],width=(WEEKLY_PDF_WIDTH-64)/2-12;
  for(const item of pageItems){
   detailCtx.font=`${item.bold?600:400} ${size}px ${family}`;
   let line='';
   for(const char of item.value){
    if(line&&detailCtx.measureText(line+char).width>width){lines.push({...item,value:line});line='';}
    line+=char;
   }
   if(line)lines.push({...item,value:line});
  }
  return {lines,width,perColumn:Math.floor((WEEKLY_PDF_HEIGHT-64)/(size*1.35))};
 }
 let low=.1,high=11,plan;
 for(let i=0;i<24;i++){
  const size=(low+high)/2,candidate=detailLayout(size);
  if(candidate.lines.length<=candidate.perColumn*2){low=size;plan=candidate;}else high=size;
 }
 for(const [index,item] of plan.lines.entries()){
  detailCtx.font=`${item.bold?600:400} ${low}px ${family}`;
  detailCtx.fillText(item.value,32+Math.floor(index/plan.perColumn)*(plan.width+24),32+(index%plan.perColumn)*low*1.35,plan.width);
 }
 return weeklyCanvasPdf([canvas,detailCanvas]);
}
