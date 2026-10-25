'use strict';
/* One dated list is reviewed and committed atomically; drafts are scoped to each user. */
(() => {
Object.assign(words,{
 feedBulkTitle:['本次叫料清單','Danh sách đặt cám lần này'],feedBulkAdd:['加入本次清單','Thêm vào danh sách'],feedBulkReplace:['更新清單這一筆','Cập nhật mục này'],feedBulkHint:['多筆登記：選一次日期，逐筆填料桶與數量後加入清單，最後一起核對儲存。日期會套用到整張清單。','Ghi nhiều lần: chọn ngày một lần, điền bồn và lượng rồi thêm danh sách, đối chiếu và lưu cùng lúc. Ngày áp dụng cho cả danh sách.'],feedBulkDraft:['尚未儲存的清單會保留在這台裝置，登入自己的帳號可繼續。','Danh sách chưa lưu được giữ trên thiết bị này, đăng nhập tài khoản của bạn để tiếp tục.'],feedBulkReview:['核對並儲存清單','Đối chiếu và lưu danh sách'],feedBulkCount:['筆','mục'],feedBulkEdit:['取回修改','Lấy lại để sửa'],feedBulkRemove:['移除','Bỏ mục'],feedBulkEditing:['正在修改清單第{n}筆','Đang sửa mục {n}'],feedBulkFinish:['請先把目前這筆加入清單，再核對整張清單。','Thêm mục đang nhập vào danh sách trước khi đối chiếu tất cả.'],feedBulkSaveFirst:['請先完成本次清單，再修改歷史紀錄。','Hoàn tất danh sách lần này trước khi sửa lịch sử.'],feedBulkRowsDuplicate:['與本清單第{n}筆使用相同料桶，請確認是否為另一次叫料。','Cùng bồn với mục {n} trong danh sách; xác nhận có phải lần đặt khác.'],feedBulkSave:['確認全部儲存','Xác nhận lưu tất cả'],feedBulkStaged:['已加入清單，尚未儲存。','Đã thêm danh sách, chưa lưu.'],feedBulkLimit:['每張清單最多50筆，請先儲存目前清單。','Tối đa 50 mục; lưu danh sách hiện tại trước.'],feedBulkCancelEdit:['取消這次修改','Hủy lần sửa này'],feedBulkEditHint:['清單尚未修改；完成輸入後按「更新清單這一筆」。','Danh sách chưa đổi; điền xong rồi nhấn cập nhật mục này.'],feedBulkCancelSingle:['請先完成或取消歷史紀錄的更正。','Hoàn tất hoặc hủy sửa lịch sử trước.']
});
Object.assign(errorWords,{invalid_feed_bulk:['請核對清單日期與每筆叫料資料；每次最多50筆。','Kiểm tra ngày và từng mục; tối đa 50 mục.'],feed_bulk_same_target:['清單內兩筆選到同一筆原紀錄，請只保留一次更正。','Hai mục chọn sửa cùng bản ghi cũ; chỉ giữ một lần sửa.']});
const base={build,enter,translate,edit,persistPending,hasUnsavedWork,saveForm};
let owner=null,queue=null,editing=null,review=null,busy=false,serial=0;
const form=()=>$('#feed-order-form'),key=id=>'pig-feed-queue:'+id,locked=()=>!!pending||busy||me?.role==='viewer';
function fresh(){return {draft_id:crypto.randomUUID(),date:form().elements.date.value,rows:[]};}
function persist(){if(!queue||!owner)return;if(queue.rows.length)localStorage.setItem(key(owner),JSON.stringify(queue));else localStorage.removeItem(key(owner));}
function scope(r){return r.feed_bin_id?feedBinLabel(data?.feed_bins.find(b=>b.id===r.feed_bin_id)||{}):r.allocations?.map(a=>batchName(a.batch_id)).join('、')||t('allFarm');}
const amount=r=>fmtFeed(r.kg/1000)+' '+t('ton');
const parts=r=>(r.bin_allocations||[]).map(a=>`<small>${esc(feedBatchScope(a.batch_id))}：${amount(a)}</small>`).join('');
function summary(r){return `${scope(r)} · ${amount(r)} · ${r.item||'—'} · ${r.vendor||'—'}`;}
function render(){
 const q=queue,box=$('#feed-bulk-list');if(!box)return;box.hidden=!q?.rows.length||me?.role==='viewer';
 form().querySelector('button.primary').hidden=!!q?.rows.length;
 $('#feed-bulk-add').hidden=!!form().dataset.editId||me?.role==='viewer';$('#feed-bulk-add').textContent=t(editing===null?'feedBulkAdd':'feedBulkReplace');$('#feed-bulk-cancel-edit').hidden=editing===null;
 $('#feed-bulk-editing').textContent=editing===null?'':t('feedBulkEditing').replace('{n}',editing+1)+' · '+t('feedBulkEditHint');
 if(q?.rows.length){$('#feed-bulk-date').textContent=q.date;$('#feed-bulk-total').textContent=q.rows.length+' '+t('feedBulkCount')+' · '+amount({kg:q.rows.reduce((n,r)=>n+r.kg,0)});$('#feed-bulk-rows').innerHTML=q.rows.map((r,i)=>`<article class="feed-bulk-row"><div><strong>${i+1}. ${esc(summary(r))}</strong>${r.note?`<small>${esc(r.note)}</small>`:''}${(r.bin_allocations||[]).map(a=>`<small>${esc(feedBatchScope(a.batch_id))}：${amount(a)}</small>`).join('')}</div><div class="actions"><button type="button" data-bulk-edit="${i}">${t('feedBulkEdit')}</button><button type="button" data-bulk-remove="${i}">${t('feedBulkRemove')}</button></div></article>`).join('');}
 controls();
}
function controls(){
 const f=form();if(!f)return;
 $('#feed-bulk-add').disabled=locked();$('#feed-bulk-review').disabled=locked()||editing!==null;$('#feed-bulk-cancel-edit').disabled=locked();
 $('#feed-bulk-rows').querySelectorAll('button').forEach(b=>b.disabled=locked());$('#feed-bulk-confirm').disabled=locked();
 if(pending?.path==='/api/feed-orders/bulk-apply'&&pending.user===me?.id)f.querySelectorAll('input,select,textarea,button').forEach(e=>e.disabled=true);
}
function invalidate(){serial++;review=null;if($('#feed-bulk-dialog').open)$('#feed-bulk-dialog').close();}
function clearComposer(){const f=form();finishForm(f);f.elements.barn_id.value='';f.elements.barn_id.dispatchEvent(new Event('change'));f.elements.namedItem('item').value='';f.elements.note.value='';$('#feed-source-photo').value='';f.querySelector('.form-error').textContent='';delete f.dataset.dirty;}
function loadRow(index){
 if(locked())return;const f=form();if(val(f,'amount')!==''||editing!==null){toast(t('feedBulkFinish'));return;}
 const r=queue.rows[index];if(!r)return;clearComposer();editing=index;f.elements.date.value=queue.date;f.elements.display_unit.value=r.display_unit;f.dataset.unit=r.display_unit;f.elements.amount.value=r.display_unit==='ton'?r.kg/1000:r.kg;
 const batch=data.batches.find(b=>b.id===r.allocations?.[0]?.batch_id),bin=data.feed_bins.find(b=>b.id===r.feed_bin_id);
 f.elements.barn_id.value=bin?.barn_ids.length===1?bin.barn_ids[0]:batch?.barn_id||'';f.elements.barn_id.dispatchEvent(new Event('change'));f.elements.feed_bin_id.value=r.feed_bin_id||'';f.elements.feed_bin_id.dispatchEvent(new Event('change'));
 if(!bin&&batch)f.elements.batch_id.value=batch.id;
 $('#feed-bin-targets').querySelectorAll('[data-feed-barn]').forEach(e=>e.value=(r.target_batch_ids||[]).find(id=>data.batches.find(b=>b.id===id)?.barn_id===e.dataset.feedBarn)||'');
 const check=$('#feed-bin-targets [name=bin_split_confirmed]');if(check){check.checked=!!r.bin_allocations?.length;check.dispatchEvent(new Event('change'));$('#feed-bin-targets').querySelectorAll('[data-bin-portion-barn]').forEach(e=>{const bid=$('#feed-bin-targets').querySelector(`[data-feed-barn="${e.dataset.binPortionBarn}"]`)?.value,part=r.bin_allocations?.find(a=>a.batch_id===bid);e.value=part?part.kg/1000:'';});}
 f.elements.vendor.value=r.vendor||'';f.elements.namedItem('item').value=r.item||'';f.elements.note.value=r.note||'';if(r.target_batch_ids?.length||r.note)f.querySelector('details').open=true;render();f.scrollIntoView({block:'start'});
}
function renderReview(){
 if(!review)return;const p=review.preview,chosen=Array.from($('#feed-bulk-review-body').querySelectorAll('fieldset')).map(e=>e.querySelector('input:checked')?.value||'');
 $('#feed-bulk-review-body').innerHTML=`<p><strong>${esc(p.date)} · ${p.count} ${t('feedBulkCount')} · ${amount({kg:p.total_kg})}</strong></p>`+(p.receipt_warnings||[]).map(code=>`<p class="note">${esc(t(code))}</p>`).join('')+p.rows.map((r,i)=>{
  const choices=r.matches.map(m=>`<label class="feed-review-option"><input type="radio" name="bulk-choice-${i}" value="${esc(m.id)}" ${m.can_update?'':'disabled'}><span>${t('feedReviewUpdate')}：${amount(m)} → ${amount(r.record)}<small>${esc(m.vendor||'—')} · ${esc(m.item||'—')}</small>${parts(m)}</span></label>`).join('');
  return `<fieldset data-bulk-review-row="${i}"><legend>${i+1}. ${esc(summary(r.record))}</legend><div class="feed-bulk-portions">${parts(r.record)}${window.feedAllocationHTML?.(r.automatic_allocation)||''}</div>${r.queue_matches.length?`<p class="note">${esc(t('feedBulkRowsDuplicate').replace('{n}',r.queue_matches.map(j=>j+1).join('、')))}</p>`:''}${r.voided_matches.length?`<p>${t('feedReviewVoid')}</p>`:''}${choices}<label class="feed-review-option"><input type="radio" name="bulk-choice-${i}" value="create" ${chosen[i]==='create'||!chosen[i]&&!r.matches.length&&!r.voided_matches.length&&!r.queue_matches.length?'checked':''}><span>${t('feedReviewAdd')}</span></label></fieldset>`;
 }).join('');
 p.rows.forEach((r,i)=>{const value=chosen[i];if(value&&value!=='create'){$('#feed-bulk-review-body').querySelectorAll(`input[name="bulk-choice-${i}"]`).forEach(e=>{if(e.value===value&&!e.disabled)e.checked=true;});}});
}
build=()=>{
 base.build();const f=form();f.elements.display_unit.value='ton';f.dataset.unit='ton';f.querySelector('.actions').insertAdjacentHTML('afterbegin',`<button type="button" id="feed-bulk-add">${txt('feedBulkAdd')}</button><button type="button" id="feed-bulk-cancel-edit" hidden>${txt('feedBulkCancelEdit')}</button>`);f.insertAdjacentHTML('beforebegin',`<p class="hint">${txt('feedBulkHint')}</p>`);f.insertAdjacentHTML('afterend',`<p id="feed-bulk-editing" role="status"></p><section id="feed-bulk-list" hidden><div class="section-row"><h3>${txt('feedBulkTitle')} · <span id="feed-bulk-date"></span></h3><strong id="feed-bulk-total"></strong></div><p class="hint">${txt('feedBulkDraft')}</p><div id="feed-bulk-rows"></div><button type="button" id="feed-bulk-review" class="primary">${txt('feedBulkReview')}</button><p id="feed-bulk-error" class="form-error" role="alert"></p></section>`);
 document.body.insertAdjacentHTML('beforeend',`<dialog id="feed-bulk-dialog" aria-labelledby="feed-bulk-title"><div class="section-row"><h2 id="feed-bulk-title">${txt('feedReviewTitle')}</h2><button type="button" id="feed-bulk-close">${txt('cancel')}</button></div><div id="feed-bulk-review-body"></div><p id="feed-bulk-review-error" class="form-error" role="alert"></p><button type="button" id="feed-bulk-confirm" class="primary">${txt('feedBulkSave')}</button></dialog>`);
 $('#feed-bulk-close').onclick=()=>$('#feed-bulk-dialog').close();$('#feed-bulk-dialog').addEventListener('close',()=>{review=null;$('#feed-bulk-review-body').replaceChildren();});
 f.elements.date.addEventListener('change',()=>{if(queue?.rows.length&&!f.dataset.editId){queue.date=f.elements.date.value;queue.rows.forEach(r=>r.date=queue.date);persist();invalidate();render();}});
 $('#feed-bulk-add').onclick=async()=>{
  if(locked()||!f.reportValidity())return;if(f.dataset.editId){toast(t('feedBulkCancelSingle'));return;}if(queue.rows.length>=50&&editing===null){toast(t('feedBulkLimit'));return;}
  const r=collect(f);if(f.elements.bin_split_confirmed?.checked&&(!r.bin_allocations.length||r.bin_allocations.some(a=>!a.batch_id)||Math.abs(r.bin_allocations.reduce((n,a)=>n+a.kg,0)-r.kg)>1e-7)){f.querySelector('.form-error').textContent=t('allocation_total_mismatch');return;}
  const file=$('#feed-source-photo')?.files[0];if(file)r.note+=(r.note?'\n':'')+t('feedReviewSource')+'：'+file.name;
  const fingerprint=JSON.stringify(r),user=me.id,mine=++serial;busy=true;controls();
  try{await api('/api/feed-order-preview',{method:'POST',body:JSON.stringify({record:r})});if(me?.id!==user||mine!==serial)return;const now=collect(f);if(file)now.note+=(now.note?'\n':'')+t('feedReviewSource')+'：'+file.name;if(JSON.stringify(now)!==fingerprint){toast(t('feedReviewChanged'));return;}queue.date=r.date;if(editing===null)queue.rows.push(r);else queue.rows[editing]=r;editing=null;persist();clearComposer();render();toast(t('feedBulkStaged'));f.elements.barn_id.focus();}
  catch(err){if(me?.id===user)f.querySelector('.form-error').textContent=messageError(err);}finally{busy=false;persistPending();}
 };
 $('#feed-bulk-cancel-edit').onclick=()=>{if(locked())return;editing=null;clearComposer();render();};
 $('#feed-bulk-rows').onclick=e=>{const b=e.target.closest('button');if(!b||locked())return;if(b.hasAttribute('data-bulk-edit')){loadRow(Number(b.dataset.bulkEdit));return;}if(b.hasAttribute('data-bulk-remove')){const i=Number(b.dataset.bulkRemove);if(editing!==null){toast(t('feedBulkFinish'));return;}queue.rows.splice(i,1);persist();invalidate();render();}};
 $('#feed-bulk-review').onclick=async()=>{
  if(locked()||!queue?.rows.length)return;if(val(f,'amount')!==''||editing!==null){toast(t('feedBulkFinish'));return;}
  const request={date:queue.date,draft_id:queue.draft_id,rows:queue.rows.map(record=>({record:structuredClone(record)}))},fingerprint=JSON.stringify(queue),user=me.id,mine=++serial;busy=true;controls();$('#feed-bulk-error').textContent='';
  try{const p=await api('/api/feed-orders/bulk-preview',{method:'POST',body:JSON.stringify(request)});if(user!==me?.id||mine!==serial)return;if(fingerprint!==JSON.stringify(queue)){toast(t('feedReviewChanged'));return;}review={request,preview:p,user};$('#feed-bulk-review-error').textContent='';renderReview();$('#feed-bulk-dialog').showModal();}
  catch(err){if(user===me?.id)$('#feed-bulk-error').textContent=messageError(err);}finally{busy=false;controls();}
 };
 $('#feed-bulk-confirm').onclick=()=>{
  if(locked()||!review||review.user!==me?.id)return;const r=review,decisions=r.preview.rows.map((p,i)=>$('#feed-bulk-review-body').querySelector(`input[name="bulk-choice-${i}"]:checked`)?.value);
  if(decisions.some(v=>!v)){$('#feed-bulk-review-error').textContent=t('feedReviewChoice');return;}
  const body={...r.request,preview_token:r.preview.preview_token,rows:r.request.rows.map((row,i)=>({...row,decision:decisions[i]==='create'?'create':'update',...(decisions[i]==='create'?{new_entry_confirmed:true}:{existing_id:decisions[i]})}))};$('#feed-bulk-dialog').close();startWrite('/api/feed-orders/bulk-apply','POST',body);
 };
 document.addEventListener('pigledger:feed-bulk-saved',e=>{if(owner!==me?.id)return;if(queue?.draft_id===e.detail.draft_id){queue=fresh();editing=null;persist();clearComposer();render();}});
 document.addEventListener('pigledger:logout',()=>{persist();owner=null;queue=null;editing=null;invalidate();render();});
};
persistPending=()=>{base.persistPending();controls();};
enter=async user=>{
 if(owner!==user.id){owner=user.id;queue=fresh();try{const stored=JSON.parse(localStorage.getItem(key(owner))||'null');if(stored&&Array.isArray(stored.rows)&&stored.rows.length<=50&&stored.rows.every(r=>r&&typeof r==='object'))queue=stored;}catch(e){}editing=null;invalidate();}
 const result=await base.enter(user);if(owner===me?.id){if(queue.rows.length)form().elements.date.value=queue.date;render();}return result;
};
edit=(kind,id)=>{if(kind==='feed_orders'&&queue?.rows.length){toast(t('feedBulkSaveFirst'));return;}const result=base.edit(kind,id);if(kind==='feed_orders')render();return result;};
saveForm=e=>{if(e.target.id==='feed-order-form'&&queue?.rows.length){e.preventDefault();toast(t('feedBulkFinish'));return;}return base.saveForm(e);};
translate=()=>{base.translate();render();renderReview();};
hasUnsavedWork=()=>base.hasUnsavedWork()||!!queue?.rows.length||editing!==null;
})();
boot();
