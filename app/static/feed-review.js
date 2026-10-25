'use strict';
/* Compare a transcribed quantity with saved history; images stay in this tab. */
(() => {
Object.assign(words,{
 feedReviewChanged:['輸入已變更，請重新核對後儲存。','Dữ liệu đã đổi; đối chiếu lại trước khi lưu.'],feedReviewTitle:['核對飼料紀錄','Đối chiếu bản ghi cám'],feedReviewIncoming:['本次填入','Dữ liệu lần này'],feedReviewOld:['已有紀錄','Bản ghi hiện có'],feedReviewNone:['沒有相同日期與料桶的紀錄。','Không có bản ghi cùng ngày và bồn.'],feedReviewUpdate:['更正這筆原紀錄','Sửa bản ghi này'],feedReviewAdd:['確認為另外一筆，新增','Xác nhận là lần khác, thêm mới'],feedReviewSave:['確認儲存','Xác nhận lưu'],feedReviewChoice:['請先選擇更正哪一筆，或確認是另外新增。','Chọn bản ghi cần sửa hoặc xác nhận là lần mới.'],feedReviewVoid:['找到已作廢紀錄，將保留作廢狀態；只有確定是另一次叫料才新增。','Có bản ghi đã hủy; không khôi phục. Chỉ thêm nếu là lần đặt khác.'],feedReviewCannot:['此筆由其他人建立，請管理員更正。','Bản ghi do người khác tạo; cần quản trị viên sửa.'],feedPhoto:['照片對照（選填）','Ảnh đối chiếu (tùy chọn)'],feedPhotoHint:['照片供本次對照，請填妥日期、料桶、料別與數量；儲存前會核對原紀錄。照片不自動辨識、不上傳，保留檔名與登記文字。','Ảnh chỉ để đối chiếu lần này; điền ngày, bồn, loại và lượng rồi đối chiếu trước khi lưu. Không tự nhận dạng hay tải ảnh lên; giữ tên tệp và nội dung đã ghi.'],feedReviewSource:['來源照片','Ảnh nguồn']
});
Object.assign(errorWords,{invalid_feed_review:['請重新核對飼料資料。','Đối chiếu lại dữ liệu cám.'],feed_review_decision_required:['請選擇更正原紀錄或另筆新增。','Chọn sửa bản ghi cũ hoặc thêm lần mới.']});
const base={build,saveForm,translate,restorePending,finishForm,enter};
let draft=null,photoURL=null,previewing=false,previewSerial=0,reviewUser=null;
const photo=()=>$('#feed-source-photo');
function clearPhoto(){if(photoURL)URL.revokeObjectURL(photoURL);photoURL=null;if(photo())photo().value='';}
function render(){
 if(!draft)return;const d=draft.preview,selected=$('#feed-review-options input:checked')?.value||'',record=d.record,quantity=r=>fmtFeed(r.kg/1000)+' '+t('ton'),parts=r=>(r.bin_allocations||[]).map(a=>`<p>${esc(feedBatchScope(a.batch_id))}：${fmtFeed(a.kg/1000)} ${t('ton')}</p>`).join('');
 $('#feed-review-body').innerHTML=`${photoURL?`<img class="feed-reference-photo" src="${photoURL}" alt="${t('feedReviewSource')}">`:''}<div class="feed-incoming"><span>${t('feedReviewIncoming')}</span><strong>${esc(record.date)} · ${quantity(record)}</strong><p>${esc(record.feed_bin_id?feedBinLabel(data.feed_bins.find(b=>b.id===record.feed_bin_id)):t('allFarm'))} · ${esc(record.item||'—')} · ${esc(record.vendor||'—')}</p>${parts(record)}</div>${(d.receipt_warnings||[]).map(code=>`<p class="note">${esc(t(code))}</p>`).join('')}<h3>${t('feedReviewOld')}</h3>${d.matches.length?'':`<p>${t('feedReviewNone')}</p>`}<div id="feed-review-options">${d.matches.map(r=>`<label class="feed-review-option"><input type="radio" name="feed-review-decision" value="${esc(r.id)}" ${r.can_update&&(!d.rid||d.rid===r.id)?'':'disabled'}><span><strong>${quantity(r)} → ${quantity(record)}</strong><small>${esc(r.date)} · ${esc(r.item||'—')} · ${esc(r.vendor||'—')}</small>${parts(r)}${r.can_update? t('feedReviewUpdate'):t('feedReviewCannot')}</span></label>`).join('')}${d.rid?'':`<label class="feed-review-option"><input type="radio" name="feed-review-decision" value="create"><span>${t('feedReviewAdd')}</span></label>`}</div>${d.voided_matches.length?`<p class="note">${t('feedReviewVoid')}</p>`:''}`;
 const choice=selected||(d.rid?d.rid:!d.matches.length&&!d.voided_matches.length?'create':'');if(choice){const radio=Array.from($('#feed-review-options').querySelectorAll('input')).find(i=>i.value===choice&&!i.disabled);if(radio)radio.checked=true;}
}
build=()=>{
 base.build();const f=$('#feed-order-form');f.querySelector('details .grid').insertAdjacentHTML('beforeend',`<label class="full">${txt('feedPhoto')}<input id="feed-source-photo" type="file" accept="image/*"><small>${txt('feedPhotoHint')}</small></label>`);
 photo().addEventListener('change',()=>{if(photoURL)URL.revokeObjectURL(photoURL);const file=photo().files[0];photoURL=file?URL.createObjectURL(file):null;});
 document.body.insertAdjacentHTML('beforeend',`<dialog id="feed-review-dialog" aria-labelledby="feed-review-title"><div class="section-row"><h2 id="feed-review-title">${txt('feedReviewTitle')}</h2><button type="button" id="feed-review-close">${txt('cancel')}</button></div><div id="feed-review-body"></div><p id="feed-review-error" role="alert"></p><button type="button" id="feed-review-confirm" class="primary">${txt('feedReviewSave')}</button></dialog>`);
 $('#logout').addEventListener('click',()=>{previewSerial++;draft=null;$('#feed-review-dialog').close();clearPhoto();});
 $('#feed-review-close').onclick=()=>$('#feed-review-dialog').close();$('#feed-review-dialog').addEventListener('close',()=>{draft=null;$('#feed-review-body').replaceChildren();});
 $('#feed-review-confirm').onclick=()=>{
  if(!draft||pending||me?.id!==reviewUser)return;const choice=$('#feed-review-options input:checked')?.value;if(!choice){$('#feed-review-error').textContent=t('feedReviewChoice');return;}
  const request={...draft.request,preview_token:draft.preview.preview_token,decision:choice==='create'?'create':'update',...(choice==='create'?{new_entry_confirmed:true}:{existing_id:choice})};$('#feed-review-dialog').close();startWrite('/api/feed-order-apply','POST',request,'feed-order-form');
 };
};
saveForm=async e=>{
 if(e.target.id!=='feed-order-form')return base.saveForm(e);e.preventDefault();const f=e.target;if(pending||previewing||!f.reportValidity()||me.role==='viewer')return;
 f.querySelector('.form-error').textContent='';const request={record:collect(f),rid:f.dataset.editId||null},file=photo()?.files[0];if(file){const source=t('feedReviewSource')+'：'+file.name;if(!request.record.note.includes(source))request.record.note+=(request.record.note?'\n':'')+source;}
 const formFingerprint=JSON.stringify(collect(f)),serial=++previewSerial,user=me.id;previewing=true;f.querySelector('.primary').disabled=true;
 try{const preview=await api('/api/feed-order-preview',{method:'POST',body:JSON.stringify(request)});if(serial!==previewSerial||me?.id!==user)return;if(formFingerprint!==JSON.stringify(collect(f))){f.querySelector('.form-error').textContent=t('feedReviewChanged');return;}draft={request,preview};reviewUser=user;$('#feed-review-error').textContent='';render();$('#feed-review-dialog').showModal();}
 catch(err){if(me?.id===user)f.querySelector('.form-error').textContent=messageError(err);}
 finally{previewing=false;persistPending();}
};
translate=()=>{base.translate();render();};
restorePending=()=>{base.restorePending();if(pending?.path==='/api/feed-order-apply'&&pending.user===me?.id){const f=$('#feed-order-form');if(pending.body.rid){f.dataset.editId=pending.body.rid;f.dataset.revision=pending.body.record.revision;}}};
finishForm=f=>{base.finishForm(f);if(f.id==='feed-order-form')clearPhoto();};
enter=async user=>{if(reviewUser!==user.id){previewSerial++;draft=null;$('#feed-review-dialog')?.close();clearPhoto();reviewUser=user.id;}return base.enter(user);};
})();
