'use strict';
/* Read-only shipment preview. The existing save route still validates live stock. */
(() => {
Object.assign(words, {
 shipmentPreview:['出豬後剩幾頭','Tồn đàn sau khi xuất'],
 shipmentBefore:['目前存欄','Tồn đàn hiện tại'],
 shipmentQuantity:['本次出豬','Xuất lần này'],
 shipmentAfter:['出完剩餘','Còn lại'],
 shipmentChoose:['請先選擇日期、棟舍與批次。','Chọn ngày, chuồng và lứa trước.'],
 shipmentLoading:['正在核對存欄…','Đang kiểm tra tồn đàn…'],
 shipmentUnknown:['存欄資料不足，暫時無法計算剩餘頭數。','Chưa đủ dữ liệu tồn đàn để tính số còn lại.'],
 shipmentFailed:['暫時無法取得存欄，請檢查連線後重試。','Chưa lấy được tồn đàn; kiểm tra kết nối rồi thử lại.'],
 shipmentRetry:['重新核對','Kiểm tra lại'],
 shipmentTooMany:['出豬頭數超過存欄，請確認棟舍、批次與頭數。','Số xuất vượt tồn đàn; kiểm tra chuồng, lứa và số con.'],
 shipmentDate:['存欄計算至登記日期','Tồn đàn tính đến ngày ghi'],
 shipmentEntry:['登記日期早於進場日，請重新選擇日期。','Ngày ghi trước ngày nhập; chọn lại ngày.'],
 shipmentEdit:['更正預覽已先還原這筆原紀錄。','Đã hoàn lại bản ghi cũ để xem trước sửa đổi.'],
 shipmentStaleEdit:['找不到原紀錄，請重新開啟更正。','Không tìm thấy bản ghi cũ; mở lại để sửa.'],
 shipmentCheck:['預覽包含當日已登記異動；儲存時會再次核對存欄。','Xem trước gồm biến động đã ghi trong ngày; kiểm tra lại tồn đàn khi lưu.']
});
const base={build,conditional,selections,edit,finishForm,restorePending,translate};
let cached=null,flight=null,timer=null,generation=0;
function context(){
 const f=$('#movement-form');if(!f||!me||!data)return null;
 const batch=data.batches.find(b=>b.id===val(f,'batch_id')&&b.barn_id===val(f,'barn_id'));
 if(!batch||!/^\d{4}-\d{2}-\d{2}$/.test(val(f,'date')))return null;
 const date=val(f,'date'),id=f.dataset.editId||'',text=val(f,'quantity');
 const quantity=/^\d+$/.test(text)&&Number.isSafeInteger(Number(text))&&Number(text)>0?Number(text):null;
 return {f,batch,date,id,quantity,key:JSON.stringify([me.id,batch.id,date,id,f.dataset.revision||'',data.cursor||'']),snapshot:data};
}
function current(c){const now=context();return !!now&&now.key===c.key&&now.snapshot===c.snapshot;}
function contribution(m,id){
 const q=Number(m.quantity);if(!Number.isFinite(q))return null;
 if(m.type==='transfer')return (m.target_batch_id===id?q:0)-(m.batch_id===id?q:0);
 if(m.batch_id!==id)return 0;
 return ['sale','cull','death'].includes(m.type)?-q:['arrival','adjustment'].includes(m.type)?q:null;
}
function clear(){generation++;clearTimeout(timer);flight=null;cached=null;const f=$('#movement-form');f?.elements.quantity.setCustomValidity('');const box=$('#outgoing-preview');if(box){box.hidden=true;box.replaceChildren();}}
function paint(c,result){
 const f=$('#movement-form'),box=$('#outgoing-preview');if(!f||!box)return;
 f.elements.quantity.setCustomValidity('');
 box.hidden=!['sale','cull'].includes(val(f,'type'))||!me||!data;if(box.hidden)return;
 let before=null,after=null,message=c?'shipmentLoading':'shipmentChoose';
 if(c&&c.date<c.batch.entry_date)message='shipmentEntry';
 else if(result){before=result.heads;message=result.error||(before==null?'shipmentUnknown':'shipmentCheck');}
 if(before!=null&&c?.quantity!=null)after=before-c.quantity;
 const over=after!=null&&after<0;
 if(over){message='shipmentTooMany';f.elements.quantity.setCustomValidity(t(message));}
 const cell=(key,n)=>`<div class="outgoing-preview-step"><span>${esc(t(key))}</span><strong data-shipment="${key}">${fmt(n,0)} <small>${esc(t('heads'))}</small></strong></div>`;
 box.classList.toggle('outgoing-preview-error',over);
 box.innerHTML=`<h3>${esc(t('shipmentPreview'))}</h3>${c?`<p class="outgoing-preview-scope">${esc(batchName(c.batch.id))}${val(f,'outgoing_destination')?' · '+esc(val(f,'outgoing_destination')):''}${val(f,'outgoing_trip')?' · '+esc(val(f,'outgoing_trip')):''}</p><p class="hint">${esc(t('shipmentDate'))}：${esc(c.date)}</p>`:''}<div class="outgoing-preview-flow">${cell('shipmentBefore',before)}<span class="outgoing-preview-arrow" aria-hidden="true">→</span>${cell('shipmentQuantity',c?.quantity??null)}<span class="outgoing-preview-arrow" aria-hidden="true">→</span>${cell('shipmentAfter',after)}</div><p class="outgoing-preview-message">${esc(t(message))}</p>${result?.restored?`<p class="hint">${esc(t('shipmentEdit'))}</p>`:''}${result?.error==='shipmentFailed'?`<button type="button" data-shipment-retry>${esc(t('shipmentRetry'))}</button>`:''}`;
 box.querySelector('[data-shipment-retry]')?.addEventListener('click',()=>update(true));
}
function update(force=false){
 const f=$('#movement-form');if(!f||!$('#outgoing-preview'))return;
 if(!['sale','cull'].includes(val(f,'type'))||!me||!data){clear();return;}
 const c=context();
 if(!c||c.quantity==null){clear();return;}
 if(force){generation++;clearTimeout(timer);flight=null;cached=null;}
 if(!c||c.date<c.batch.entry_date){generation++;clearTimeout(timer);flight=null;cached=null;paint(c,null);return;}
 if(cached?.key===c.key&&cached.snapshot===c.snapshot){paint(c,cached);return;}
 paint(c,null);
 if(flight?.key===c.key&&flight.snapshot===c.snapshot)return;
 clearTimeout(timer);const mine=++generation;flight={key:c.key,snapshot:c.snapshot};
 timer=setTimeout(async()=>{
  let result={key:c.key,snapshot:c.snapshot,heads:null};
  try{
   const query=new URLSearchParams({summary:'1',batch_id:c.batch.id,to:c.date});
   const s=await api('/api/statistics?'+query);
   if(s.as_of!==c.date||s.ids?.length!==1||s.ids[0]!==c.batch.id)throw new Error('scope mismatch');
   if(s.cumulative.remaining!==null&&!Number.isSafeInteger(s.cumulative.remaining))throw new Error('invalid stock');
   result.heads=s.cumulative.remaining;
   if(c.id){
    const original=c.snapshot.movements.find(m=>m.id===c.id);
    if(!original){result.heads=null;result.error='shipmentStaleEdit';}
    else if(original.date<=c.date&&result.heads!==null){
     const delta=contribution(original,c.batch.id);
     if(delta===null){result.heads=null;result.error='shipmentStaleEdit';}
     else {result.heads-=delta;result.restored=true;}
    }
   }
  }catch(_){result={...result,heads:null,error:'shipmentFailed'};}
  if(mine!==generation||!current(c))return;
  cached=result;flight=null;paint(context(),result);
 },120);
}
build=()=>{
 base.build();const f=$('#movement-form');
 const box=document.createElement('section');box.id='outgoing-preview';box.className='outgoing-preview';box.setAttribute('aria-live','polite');box.setAttribute('aria-atomic','true');box.hidden=true;
 f.querySelector('.actions').before(box);
 f.addEventListener('input',()=>update());f.addEventListener('change',()=>update());f.addEventListener('reset',()=>queueMicrotask(()=>update(true)));
 document.addEventListener('pigledger:logout',clear);
};
conditional=(...args)=>{const r=base.conditional(...args);update();return r;};
selections=(...args)=>{const r=base.selections(...args);update();return r;};
edit=(...args)=>{const r=base.edit(...args);update();return r;};
finishForm=(...args)=>{const r=base.finishForm(...args);update(true);return r;};
restorePending=(...args)=>{const r=base.restorePending(...args);update();return r;};
translate=(...args)=>{const r=base.translate(...args);update();return r;};
})();
