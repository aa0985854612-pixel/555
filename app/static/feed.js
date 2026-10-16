'use strict';
/* Manual order quantities are separate from received feed and actual consumption. */
(() => {
Object.assign(words,{
 feedSub:['只需登記日期與叫料量，其他資料可選填。','Chỉ ghi ngày và lượng đặt; thông tin khác tùy chọn.'],
 feed_orders:['叫料量','Lượng đặt thức ăn'],newFeedOrder:['登記叫料量','Ghi lượng đặt thức ăn'],orderAmount:['叫料量','Lượng đặt'],orderHistory:['叫料紀錄','Lịch sử đặt thức ăn'],orderTotal:['叫料合計','Tổng lượng đặt'],orderScope:['預設全場；指定棟舍時請選擇批次。','Mặc định toàn trại; chọn lứa nếu chỉ định chuồng.'],orderMeaning:['叫料量不代表實際耗料，不用於FCR計算。','Lượng đặt không phải lượng tiêu thụ, không dùng tính FCR.'],legacyFeed:['舊到料／用料紀錄','Lịch sử nhập / tiêu thụ'],legacyFeedHint:['保留原紀錄及計算依據；日常只使用上方叫料登記。','Giữ bản gốc và cơ sở tính; hằng ngày chỉ ghi lượng đặt phía trên.']
});
const base={build,renderCurrent,rowsHTML,collect,edit,restorePending,finishForm,selections,enter};
let feedUser=null;
function replaceRecords(id,html){
 const list=$('#'+id);if(list.innerHTML===html)return;
 const active=list.contains(document.activeElement)?document.activeElement:null,key=active?.dataset;
 list.innerHTML=html;
 if(active){const match=key?.id?Array.from(list.querySelectorAll('button[data-id]')).find(b=>b.dataset.id===key.id&&b.dataset.edit===key.edit&&b.dataset.delete===key.delete):null;list.tabIndex=-1;(match||list).focus({preventScroll:true});}
}
function loadOrder(f,r){
 f.elements.date.value=r.date;f.elements.display_unit.value=r.display_unit;f.dataset.unit=r.display_unit;
 f.elements.amount.value=r.display_unit==='ton'?r.kg/1000:r.kg;
 for(const k of ['vendor','item','note'])f.elements[k].value=r[k]||'';
 f.elements.barn_id.value='';updateScope(f.querySelector('.scope'));f.elements.batch_id.value='';
 const b=data.batches.find(b=>b.id===r.allocations?.[0]?.batch_id);
 if(b){f.elements.barn_id.value=b.barn_id;updateScope(f.querySelector('.scope'));f.elements.batch_id.value=b.id;}
 f.elements.batch_id.required=!!f.elements.barn_id.value;
}
function showLegacyForm(f){
 $('#legacy-feed').hidden=false;$('#legacy-feed').open=true;$('#legacy-feed-forms').hidden=false;
 $$('#legacy-feed-forms > .card').forEach(card=>card.hidden=!card.contains(f));
}
build=()=>{
 base.build();const page=$('#page-feed'),legacyForms=page.querySelector('.split'),filter=$('#feed-filter');
 legacyForms.id='legacy-feed-forms';legacyForms.hidden=true;
 const archive=document.createElement('details');archive.id='legacy-feed';archive.className='card';archive.hidden=true;
 archive.innerHTML=`<summary>${txt('legacyFeed')}</summary><p class="hint">${txt('legacyFeedHint')}</p>`;
 const oldExports=filter.nextElementSibling;archive.append(oldExports,legacyForms,$('#delivery-results').closest('.card'),$('#usage-results').closest('.card'));page.append(archive);
 page.insertAdjacentHTML('afterbegin',`<div class="card"><h2>${txt('newFeedOrder')}</h2><form id="feed-order-form" data-kind="feed_orders"><div class="grid three">${input('date','date','date','required')}${input('orderAmount','amount','number','min="0.000001" step="any" inputmode="decimal" required')}${select('unit','display_unit',option('kg','kg')+option('ton','ton'))}</div>${advanced(select('vendor','vendor',option('','choose')+'<option>養全</option><option>新農科</option>')+input('item','item')+`<p class="hint full">${txt('orderScope')}</p>`+scope()+input('note','note'))}<p class="hint">${txt('orderMeaning')}</p>${formActions()}</form></div>`);
 const results=document.createElement('div');results.className='card';results.innerHTML=`<div class="section-row"><h2>${txt('orderHistory')}</h2><output id="feed-order-total"></output></div><div id="feed-order-results"></div>`;page.insertBefore(results,archive);
 const exportButton=document.createElement('button');exportButton.type='button';exportButton.dataset.export='feed_orders';exportButton.dataset.filter='feed-filter';exportButton.innerHTML=txt('csv');filter.after(exportButton);
 $('#history-filter [name=record_kind]').insertAdjacentHTML('beforeend',option('feed_orders','feed_orders'));
 const f=$('#feed-order-form');f.elements.date.value=today();f.querySelectorAll('.scope select').forEach(e=>e.required=false);
 f.addEventListener('submit',saveForm);for(const event of ['input','change'])f.addEventListener(event,e=>{if(e.isTrusted)f.dataset.dirty='1';});
 f.elements.barn_id.addEventListener('change',()=>{updateScope(f.querySelector('.scope'),true);f.elements.batch_id.required=!!val(f,'barn_id');});
 f.elements.display_unit.addEventListener('change',e=>{const previous=f.dataset.unit||'kg',n=Number(val(f,'amount'));if(val(f,'amount'))f.elements.amount.value=previous==='ton'?n*1000:n/1000;f.dataset.unit=e.target.value;});
 archive.addEventListener('toggle',()=>{if(archive.open&&current==='feed')renderCurrent();});
};
collect=f=>{
 if(f.id!=='feed-order-form')return base.collect(f);
 const kg=Number(val(f,'amount'))*(val(f,'display_unit')==='ton'?1000:1);
 return {date:val(f,'date'),kg,display_unit:val(f,'display_unit'),vendor:val(f,'vendor'),item:val(f,'item'),note:val(f,'note'),allocations:val(f,'batch_id')?[{batch_id:val(f,'batch_id'),kg}]:[],...(f.dataset.editId?{revision:Number(f.dataset.revision)}:{})};
};
rowsHTML=(kind,rows)=>{
 if(kind!=='feed_orders')return base.rowsHTML(kind,rows);
 return rows.map(r=>`<article class="feed-order-record"><div class="section-row"><strong>${esc(r.date)}</strong><strong class="order-quantity">${fmt(r.display_unit==='ton'?r.kg/1000:r.kg)} <small>${esc(t(r.display_unit))}</small></strong></div><p>${[r.vendor,r.item,r.allocations.length?r.allocations.map(a=>batchName(a.batch_id)).join('、'):t('allFarm')].filter(Boolean).map(esc).join(' · ')}</p>${r.note?`<p class="order-note">${esc(r.note)}</p>`:''}<div class="actions">${recordActions(kind,r)}</div></article>`).join('')||empty();
};
renderCurrent=async()=>{
 if(current!=='feed')return base.renderCurrent();
 const ticket=++renderTicket,q=query($('#feed-filter')),archive=$('#legacy-feed');
 try{
  const requests=[api('/api/feed_orders?'+q)];if(archive.open)requests.push(api('/api/deliveries?'+q),api('/api/usages?'+q));
  const [orders,deliveries,usages]=await Promise.all(requests);if(ticket!==renderTicket||current!=='feed')return;
  replaceRecords('feed-order-results',rowsHTML('feed_orders',orders));$('#feed-order-total').textContent=t('orderTotal')+' '+fmt(orders.reduce((n,r)=>n+r.kg,0))+' kg';
  if(deliveries){replaceRecords('delivery-results',rowsHTML('deliveries',deliveries));replaceRecords('usage-results',rowsHTML('usages',usages.map(u=>({...u,computed_kg:calcConsumption(u)}))));}
 }catch(e){toast(messageError(e));}
};
selections=(force=false)=>{base.selections(force);if(data)$('#legacy-feed').hidden=!(data.deliveries.length||data.usages.length||pending&&['delivery-form','usage-form'].includes(pending.formId));};
edit=(kind,id)=>{
 if(kind==='feed_orders'){
  if(pending){toast(t('pending'));return;}
  const f=$('#feed-order-form');if(f.dataset.dirty==='1'){toast(t('saveBeforeSwitch'));return;}
  const r=data.feed_orders.find(r=>r.id===id);if(!r)return;
  loadOrder(f,r);f.dataset.editId=id;f.dataset.revision=r.revision;f.querySelector('[data-action=cancelEdit]').hidden=false;f.querySelector('.edit-label').hidden=false;
  location.hash='feed';setPage('feed',false);f.querySelector('details').open=true;f.scrollIntoView({block:'start'});return;
 }
 if(['deliveries','usages'].includes(kind))showLegacyForm($('#'+(kind==='deliveries'?'delivery-form':'usage-form')));
 base.edit(kind,id);
};
restorePending=()=>{base.restorePending();if(!pending||pending.user!==me?.id)return;if(pending.formId==='feed-order-form')loadOrder($('#feed-order-form'),pending.body);if(['delivery-form','usage-form'].includes(pending.formId))showLegacyForm($('#'+pending.formId));};
finishForm=f=>{base.finishForm(f);if(['delivery-form','usage-form'].includes(f.id)){$('#legacy-feed-forms').hidden=true;}if(f.id==='feed-order-form')delete f.dataset.pendingRestored;};
enter=async user=>{
 if(feedUser!==user.id){
  for(const id of ['feed-order-results','delivery-results','usage-results'])$('#'+id).replaceChildren();
  $('#feed-order-total').textContent='';$('#legacy-feed').open=false;$('#legacy-feed-forms').hidden=true;
  if(!pending||pending.user!==user.id)base.finishForm($('#feed-order-form'));
  feedUser=user.id;
 }
 return base.enter(user);
};
})();
