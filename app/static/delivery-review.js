'use strict';
/* Old receipt rows remain editable in the original form after quick entry retires. */
(() => {
Object.assign(words,{
 receiptEditTitle:['核對到料更正','Đối chiếu sửa cám nhận'],receiptEditBefore:['原數量','Lượng cũ'],receiptEditAfter:['更正後','Sau sửa'],receiptEditSave:['確認更正','Xác nhận sửa'],receiptEditStock:['更正後帳面庫存','Tồn sổ sau sửa'],receiptEditAck:['已核對並確認','Đã đối chiếu và xác nhận']
});
const base={build,saveForm,persistPending,translate};let draft=null,busy=false,serial=0;
const dialog=()=>$('#receipt-edit-dialog');
function controls(){if(!dialog())return;$('#receipt-edit-confirm').disabled=busy||!!pending||!draft||Array.from($('#receipt-edit-warnings').querySelectorAll('input')).some(e=>!e.checked);$('#receipt-edit-close').disabled=!!pending;$('#receipt-edit-retry').hidden=!(pending?.formId==='delivery-form'&&pending.path==='/api/quick-records/save');}
function render(){
 if(!draft)return;const p=draft.preview,r=p.record;
 $('#receipt-edit-body').innerHTML=`<p><strong>${esc(r.date)} · ${esc(p.barn.name)}</strong></p><p>${t('receiptEditBefore')} ${fmtFeed(p.previous.kg/1000)} ${t('ton')} → ${t('receiptEditAfter')} ${fmtFeed(r.kg/1000)} ${t('ton')}</p>${r.vendor?`<p>${esc(r.vendor)} · ${esc(r.item||'')}</p>`:''}${r.note?`<p class="receipt-edit-note">${esc(r.note)}</p>`:''}${(r.allocations||[]).map(a=>`<p>${esc(feedBatchScope(a.batch_id))}：${fmtFeed(a.kg/1000)} ${t('ton')}</p>`).join('')}${(p.inventories||[]).filter(x=>x.after.enabled).map(x=>`<p>${t('receiptEditStock')}：${x.after.kg==null?'—':fmtFeed(x.after.kg/1000)+' '+t('ton')}</p>`).join('')}`;
 $('#receipt-edit-warnings').innerHTML=p.warnings.map(code=>`<label class="check"><input type="checkbox" data-receipt-warning="${esc(code)}">${t('receiptEditAck')}：${esc(t(code))}</label>`).join('');controls();
}
build=()=>{
 base.build();document.body.insertAdjacentHTML('beforeend',`<dialog id="receipt-edit-dialog" aria-labelledby="receipt-edit-title"><h2 id="receipt-edit-title">${txt('receiptEditTitle')}</h2><div id="receipt-edit-body"></div><div id="receipt-edit-warnings"></div><p id="receipt-edit-error" class="form-error" role="alert"></p><div class="actions"><button type="button" id="receipt-edit-close">${txt('cancel')}</button><button type="button" id="receipt-edit-retry" hidden>${txt('retry')}</button><button type="button" id="receipt-edit-confirm" class="primary">${txt('receiptEditSave')}</button></div></dialog>`);
 $('#receipt-edit-close').onclick=()=>dialog().close();$('#receipt-edit-retry').onclick=()=>retryPending();dialog().addEventListener('cancel',e=>{if(pending)e.preventDefault();});dialog().addEventListener('close',()=>{serial++;draft=null;$('#receipt-edit-body').replaceChildren();$('#receipt-edit-warnings').replaceChildren();});$('#receipt-edit-warnings').onchange=controls;
 $('#receipt-edit-confirm').onclick=()=>{if(!draft||pending||busy)return;startWrite('/api/quick-records/save','POST',{request:draft.request,confirmed:true,preview_token:draft.preview.preview_token,acknowledged:Array.from($('#receipt-edit-warnings').querySelectorAll('input:checked')).map(e=>e.dataset.receiptWarning)},'delivery-form');};
 document.addEventListener('pigledger:quick-saved',()=>{if(draft)dialog().close();});document.addEventListener('pigledger:quick-failed',e=>{if(draft){$('#receipt-edit-error').textContent=messageError(e.detail);draft=null;controls();}});document.addEventListener('pigledger:logout',()=>{serial++;draft=null;dialog().close();});
};
saveForm=async e=>{
 const f=e.target,r=f.id==='delivery-form'&&f.dataset.editId?data.deliveries.find(r=>r.id===f.dataset.editId):null;
 if(!r?.quick_source)return base.saveForm(e);e.preventDefault();if(pending||busy||!f.reportValidity())return;
 const d=collect(f),barn=r.requested_barn_id||r.quick_source.barn_id,batch=d.allocations.find(a=>data.batches.find(b=>b.id===a.batch_id)?.barn_id===barn)?.batch_id;
 const request={action:'update',kind:'deliveries',id:r.id,revision:d.revision,text:r.quick_source.text,operation_id:r.quick_source.operation_id,corrections:{type:'delivery',date:d.date,barn_id:barn,quantity:d.display_unit==='ton'?d.kg/1000:d.kg,unit:d.display_unit,feed_bin_id:r.feed_bin_id,vendor:d.vendor,item:d.item,note:d.note,allocations:d.allocations,...(batch?{batch_id:batch}:{})}};
 const mine=++serial,user=me.id;busy=true;controls();f.querySelector('.form-error').textContent='';
 try{const p=await api('/api/quick-records/preview',{method:'POST',body:JSON.stringify(request)});if(mine!==serial||user!==me?.id)return;if(!p.can_confirm)throw {error:p.errors?.[0]||'invalid_request'};draft={request,preview:p};$('#receipt-edit-error').textContent='';render();dialog().showModal();}
 catch(error){if(user===me?.id)f.querySelector('.form-error').textContent=messageError(error);}finally{busy=false;controls();}
};
persistPending=()=>{base.persistPending();controls();};translate=()=>{base.translate();render();};
})();
