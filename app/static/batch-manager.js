'use strict';
/* Whole-batch editing and counted stock use reviewed, atomic server writes. */
(() => {
Object.assign(words,{
 manageFarm:['批次與棟舍管理','Quản lý lứa và chuồng'],manageIntro:['選批次 → 修改資料 → 核對前後數字 → 確認儲存。日後可直接在這裡修改。','Chọn lứa → sửa → đối chiếu trước/sau → xác nhận lưu. Bạn có thể tự sửa tại đây.'],manageBatch:['管理這一批','Quản lý lứa này'],manageSelect:['選擇要管理的批次','Chọn lứa cần sửa'],manageOpen:['開啟管理','Mở quản lý'],manageEntry:['修改進場資料','Sửa dữ liệu nhập đàn'],manageStock:['登記實際盤點頭數','Ghi số kiểm kê thực tế'],manageEntryHint:['修改原始進場資料；每棟分開填，整批一起儲存。棟舍改名會同步套用於這棟的其他批次。','Sửa dữ liệu nhập; điền riêng từng chuồng, lưu cả lứa cùng lúc. Đổi tên chuồng áp dụng cho các lứa khác của chuồng.'],manageStockHint:['填今天實際數到的頭數；未填的棟舍保持原值。系統登記盤點差額，原始進場總數不變。','Điền số đếm thực tế; chuồng để trống giữ nguyên. Ghi chênh lệch kiểm kê, không đổi số nhập gốc.'],manageName:['批號（各棟一起修改）','Mã lứa (sửa mọi chuồng)'],manageKeepTotal:['保持整批進場總數，只調整各棟分配','Giữ tổng nhập cả lứa, chỉ đổi phân bổ'],manageLegacyTotal:['Excel匯入批次的進場合計須維持原始總數。','Tổng nhập lứa Excel phải giữ theo nguồn gốc.'],manageTotals:['整批進場合計','Tổng nhập cả lứa'],manageCurrent:['系統存欄','Tồn theo hệ thống'],manageCounted:['實際盤點頭數（空白不調整）','Số đếm thực tế (trống: không đổi)'],manageReason:['修改原因／資料依據','Lý do / căn cứ sửa'],manageMore:['日齡、分次進場及報表設定','Tuổi, các lần nhập và phiếu tuần'],manageReview:['核對修改前後','Đối chiếu trước và sau'],manageSave:['確認無誤，儲存修改','Xác nhận đúng, lưu thay đổi'],manageStockTotal:['本批次存欄','Tồn cả lứa'],manageNew:['新增批次','Thêm lứa'],manageBarns:['新增／修改棟舍','Thêm / sửa chuồng'],manageDraft:['繼續未儲存的修改','Tiếp tục bản chưa lưu'],manageDraftHint:['輸入會暫存於這台裝置；按確認儲存後，其他手機才會同步看到。','Nội dung tạm lưu trên thiết bị này; xác nhận lưu để điện thoại khác thấy.'],manageReload:['放棄修改，重載已存資料','Bỏ sửa, tải lại dữ liệu đã lưu'],managePending:['尚未確認儲存，請重試原筆；不要重填。','Chưa xác nhận lưu; thử lại bản gốc, không nhập lại.'],manageHelp:['我想改什麼？','Bạn muốn sửa gì?'],manageHelpText:['數完豬隻想修正剩餘頭數：選「登記實際盤點頭數」。進場單上的頭數、日期或均重有誤：選「修改進場資料」。死亡、出豬、補豬與轉棟，仍到「每日登記」記錄。','Muốn sửa tồn sau khi đếm: chọn kiểm kê. Sai số nhập, ngày hoặc cân nặng: chọn sửa nhập đàn. Chết, bán, nhập bổ sung và chuyển chuồng ghi ở mục hằng ngày.'],manageAge:['基準日齡（天，選填）','Tuổi chuẩn (ngày, tùy chọn)'],manageFields:['資料變更','Dữ liệu thay đổi'],manageHistory:['查看修改紀錄','Xem lịch sử sửa'],manageChanged:['資料或輸入已改變，請重新核對。','Dữ liệu đã đổi; đối chiếu lại.'],manageUnknown:['資料不足，請先補齊來源；不以0代替。','Thiếu dữ liệu; bổ sung nguồn, không thay bằng 0.']
});
Object.assign(errorWords,{
 invalid_batch_settings:['管理資料不完整，請重新開啟這一批。','Dữ liệu thiếu; mở lại lứa.'],batch_settings_reason_required:['請填修改原因或資料依據。','Nhập lý do / căn cứ.'],batch_settings_members_changed:['批次成員已變更，請重載已存資料後重新核對。','Thành viên lứa đã đổi; tải lại và đối chiếu.'],batch_settings_total_mismatch:['整批進場合計不同，請調整其他棟的分配，或取消保持總數。','Tổng nhập khác; điều chỉnh chuồng khác hoặc bỏ giữ tổng.'],batch_settings_source_pending:['原始出豬／死亡尚未完成分棟核對，不能直接重分進場數；若要登記數到的存欄，請改用盤點頭數。','Chưa đối chiếu xuất/chết từng chuồng; không phân bổ lại nhập. Muốn ghi tồn đã đếm: dùng kiểm kê.'],batch_settings_future_stock:['盤點日期不能晚於今天。','Ngày kiểm kê không được sau hôm nay.'],batch_settings_no_changes:['沒有修改內容；請先修改資料或填入不同的盤點頭數。','Chưa thay đổi; sửa dữ liệu hoặc nhập số kiểm kê khác.'],batch_settings_legacy_date:['匯入資料的進場日不可早於原始日期；報表另有「肉豬紀錄表起始日」可調整。','Ngày nhập dữ liệu Excel không được trước nguồn gốc; có thể chỉnh ngày bắt đầu phiếu tuần.'],legacy_period_locked:['此日期屬於匯入歷史期間，請使用目前日期盤點；歷史出豬或死亡請到歷史紀錄更正。','Ngày thuộc kỳ Excel; kiểm kê ngày hiện tại. Sửa xuất/chết cũ trong lịch sử.'],invalid_text:['請填有效名稱或文字。','Nhập tên / nội dung hợp lệ.']
});
Object.assign(words,{manageBatchShort:['管理','Quản lý'],manageClose:['關閉，保留草稿','Đóng, giữ bản nháp'],manageLoading:['正在載入…','Đang tải…']});
const base={build,renderSettings,renderHome,translate,persistPending,restorePending,finishForm,hasUnsavedWork,enter};
let model=null,review=null,serial=0,stockSerial=0,previewBusy=false,dirty=false,loading=false;
const dialog=()=>$('#batch-manager-dialog'),form=()=>$('#batch-manager-form');
const key=b=>b._cohort_key||b.name+'|'+b.entry_date;
const pendingHere=()=>pending?.path==='/api/batch-settings/apply'&&pending.user===me?.id;
const draftKey=()=>me?'pig-batch-settings-draft:'+me.id:'';
const numeric=e=>e.value===''?null:Number(e.value);
const label=(k,value,type='text',attrs='')=>`<label>${txt(k)}<input data-field="${k}" type="${type}" value="${esc(value??'')}" ${attrs}></label>`;
const fieldLabels={entry_date:'entryDate',entry_count:'entry',entry_mean_kg:'entryMean',entry_mean_date:'entryMeanDate',entry_age_days:'manageAge',age_date:'ageDate',status:'status',weekly_start_date:'weeklyStartDate',report_entry_lots:'reportEntryLots',report_entry_lots_source:'entryLotsSource',note:'note',name:'batchName'};
function rowInput(k,value,type='text',attrs=''){return label(fieldLabels[k]||k,value,type,attrs).replace(`data-field="${fieldLabels[k]||k}"`,`data-field="${k}"`);}
function controls(){
 if(!form())return;const locked=!!pending||previewBusy||me?.role!=='admin';
 const stockMode=form().elements.mode.value==='stock';
 form().querySelectorAll('input,select,textarea,button').forEach(e=>e.disabled=locked||!!e.closest(stockMode?'.manager-entry,#manager-entry-options':'.manager-stock,#manager-stock-options'));
 $('#manager-keep-total').disabled=locked||!!model?.lockTotal;
 $('#manager-confirm').disabled=locked||!review;
 $('#manager-close').disabled=!!pendingHere();$('#manager-reload').disabled=!!pendingHere()||previewBusy;
 $('#manager-retry').hidden=!pendingHere();$('#manager-retry').disabled=!!retryPending.busy;
 if(pendingHere())$('#manager-error').textContent=t('managePending');
}
function body(){
 if(!model)return null;
 const mode=form().elements.mode.value;
 return {mode,batch_id:model.id,reason:form().elements.reason.value,
 ...(mode==='stock'?{date:form().elements.date.value}:{name:form().elements.batch_name.value,preserve_entry_total:$('#manager-keep-total').checked}),
 rows:Array.from($('#manager-rows').children).map(card=>{
  const old=model.members.find(b=>b.id===card.dataset.batch);
  if(mode==='stock')return {id:old.id,revision:old.revision,remaining:numeric(card.querySelector('[data-counted]'))};
  const fields={};card.querySelectorAll('[data-field]').forEach(e=>{fields[e.dataset.field]=e.type==='number'?numeric(e):e.value;});
  fields.report_entry_lots=Array.from(card.querySelectorAll('.manager-lot')).map(l=>({date:l.querySelector('[data-lot=date]').value,count:numeric(l.querySelector('[data-lot=count]')),mean_kg:numeric(l.querySelector('[data-lot=mean_kg]'))}));
  return {id:old.id,revision:old.revision,barn_revision:old.barn_revision,barn_name:card.querySelector('[data-barn-name]').value,fields};
 })};
}
function remember(){
 if(loading||!model||model.user!==me?.id)return;
 try{localStorage.setItem(draftKey(),JSON.stringify({user:me.id,request:body()}));}catch(e){}
 dirty=true;updateTotals();review=null;++serial;$('#manager-impact').replaceChildren();controls();
}
function clearDraft(){try{localStorage.removeItem(draftKey());}catch(e){}dirty=false;}
function updateTotals(){
 if(!model)return;const values=Array.from($('#manager-rows').querySelectorAll('[data-field=entry_count]')).map(numeric),old=model.members.map(b=>b.entry_count);
 const sum=a=>a.some(v=>v==null)?null:a.reduce((n,v)=>n+v,0);
 $('#manager-total').textContent=t('manageTotals')+'：'+fmt(sum(old)??model.originalEntry,0)+' → '+fmt(sum(values),0)+' '+t('heads');
}
function lotHTML(lot={}){return `<div class="manager-lot"><label>${txt('date')}<input data-lot="date" type="date" value="${esc(lot.date||'')}" required></label><label>${txt('quantity')}<input data-lot="count" type="number" min="1" step="1" value="${esc(lot.count??'')}" required></label><label>${txt('entryMeanShort')}<input data-lot="mean_kg" type="number" min="0.01" step="any" value="${esc(lot.mean_kg??'')}"></label><button type="button" data-remove-lot>${txt('removeEntryLot')}</button></div>`;}
function rowsHTML(members){return members.map(b=>`<section class="manager-barn" data-batch="${esc(b.id)}"><h3>${esc(b.barn_name)}</h3><div class="manager-stock"><p>${txt('manageCurrent')}：<strong data-current-stock>—</strong> ${txt('heads')}</p><label>${txt('manageCounted')}<input data-counted type="number" min="0" step="1" inputmode="numeric"></label></div><div class="manager-entry"><div class="grid"><label>${txt('barnName')}<input data-barn-name value="${esc(b.barn_name)}" required maxlength="80"></label>${rowInput('entry_date',b.entry_date,'date','required')}${rowInput('entry_count',b.entry_count,'number','min="0" step="1"')}${rowInput('entry_mean_kg',b.entry_mean_kg,'number','min="0.01" step="any"')}<label>${txt('status')}<select data-field="status">${['active','ended'].map(s=>`<option value="${s}" data-i="${s}" ${s===b.status?'selected':''}>${t(s)}</option>`).join('')}</select></label></div><details><summary>${txt('manageMore')}</summary><div class="grid">${rowInput('entry_age_days',b.entry_age_days,'number','min="0" step="any"')}${rowInput('age_date',b.age_date,'date')}${rowInput('entry_mean_date',b.entry_mean_date,'date')}${rowInput('weekly_start_date',b.weekly_start_date,'date')}${rowInput('note',b.note,'text','maxlength="2000"')}</div><h4>${txt('reportEntryLots')}</h4><p class="hint">${txt('reportEntryLotsHint')}</p><div class="manager-lots">${(b.report_entry_lots||[]).map(lotHTML).join('')}</div><button type="button" data-add-lot>${txt('addEntryLot')}</button>${rowInput('report_entry_lots_source',b.report_entry_lots_source,'text','maxlength="2000"')}</details></div></section>`).join('');}
async function stock(){
 if(!model||form().elements.mode.value!=='stock')return;
 const mine=++stockSerial,owner=me?.id,id=model.id,on=form().elements.date.value;
 $$('#manager-rows [data-current-stock]').forEach(e=>e.textContent='…');
 try{
  const p=await api('/api/statistics?summary=1&cohort='+encodeURIComponent(model.cohort)+'&to='+encodeURIComponent(on));
  if(mine!==stockSerial||model?.id!==id||me?.id!==owner||!dialog().open||form().elements.date.value!==on)return;
  for(const card of $('#manager-rows').children){const n=p.batches.find(b=>b.id===card.dataset.batch)?.herd.remaining;card.querySelector('[data-current-stock]').textContent=fmt(n,0);}
 }catch(e){if(mine===stockSerial&&model?.id===id&&me?.id===owner){$$('#manager-rows [data-current-stock]').forEach(el=>el.textContent='—');$('#manager-error').textContent=messageError(e);}}
}
function modeChanged(){
 const stockMode=form().elements.mode.value==='stock';
 $$('.manager-entry').forEach(e=>e.hidden=stockMode);$$('.manager-stock').forEach(e=>e.hidden=!stockMode);
 $('#manager-entry-options').hidden=stockMode;$('#manager-stock-options').hidden=!stockMode;
 $('#manager-instruction').textContent=t(stockMode?'manageStockHint':'manageEntryHint');
 // Hidden fields do not participate in the other mode's native validation.
 form().querySelectorAll('.manager-entry input,.manager-entry select,#manager-entry-options input').forEach(e=>{e.required=!stockMode&&(e.dataset.lot?e.dataset.lot!=='mean_kg':['entry_date','batch_name'].includes(e.dataset.field||e.name));});
 for(const card of $('#manager-rows').children)card.querySelector('[data-field=entry_count]').required=!stockMode&&!model.members.find(b=>b.id===card.dataset.batch)?.legacy_source;
 $$('#manager-rows [data-barn-name]').forEach(e=>e.required=!stockMode);form().elements.batch_name.required=!stockMode;form().elements.date.required=stockMode;
 updateTotals();if(stockMode)stock();controls();
}
function openManager(id,restored=null){
 if(me?.role!=='admin'||pending&&!pendingHere()){toast(t('pending'));return;}
 if(!restored){try{const saved=JSON.parse(localStorage.getItem(draftKey())||'null');if(saved?.user===me?.id){if(saved.request.batch_id!==id){toast(t('manageDraft'));return;}restored=saved.request;}}catch(e){}}
 const anchor=data?.batches.find(b=>b.id===id);if(!anchor)return;
 loading=true;++serial;++stockSerial;review=null;
 model={user:me.id,id,cohort:key(anchor),legacy:!!anchor.legacy_source,members:data.batches.filter(b=>key(b)===key(anchor)).map(b=>{const barn=data.barns.find(x=>x.id===b.barn_id);return {...b,barn_name:barn.name,barn_revision:barn.revision};}).sort((a,b)=>a.barn_name.localeCompare(b.barn_name,'zh-Hant',{numeric:true}))};
 model.lockTotal=model.legacy&&model.members.length>1;model.originalEntry=data.dashboard?.cohorts?.find(c=>c.cohort===model.cohort)?.herd.entry;
 form().reset();form().elements.mode.value=restored?.mode||'entry';form().elements.batch_name.value=restored?.name||anchor.name;form().elements.date.value=restored?.date||today();form().elements.reason.value=restored?.reason||'';$('#manager-keep-total').checked=restored?.preserve_entry_total??(model.members.length>1);
 $('#manager-legacy-hint').hidden=!model.lockTotal;$('#manager-rows').innerHTML=rowsHTML(model.members);$('#manager-impact').replaceChildren();$('#manager-error').textContent='';$('#manager-title').textContent=t('manageFarm')+' · '+anchor.name;
 if(restored){for(const row of restored.rows){const card=Array.from($('#manager-rows').children).find(c=>c.dataset.batch===row.id),member=model.members.find(b=>b.id===row.id);if(!card||!member)continue;member.revision=row.revision;if(row.barn_revision!=null)member.barn_revision=row.barn_revision;if(row.barn_name!=null)card.querySelector('[data-barn-name]').value=row.barn_name;for(const [k,v] of Object.entries(row.fields||{})){const el=card.querySelector(`[data-field="${k}"]`);if(el)el.value=v??'';}if(row.fields?.report_entry_lots)card.querySelector('.manager-lots').innerHTML=row.fields.report_entry_lots.map(lotHTML).join('');if(row.remaining!=null)card.querySelector('[data-counted]').value=row.remaining;}}
 if(!dialog().open)dialog().showModal();loading=false;dirty=!!restored;modeChanged();controls();
}
function options(){
 const select=$('#manager-select');if(!select||!data)return;const keep=select.value,groups=new Map();
 for(const b of [...data.batches].sort((a,b)=>b.entry_date.localeCompare(a.entry_date))){const k=key(b);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(b);}
 select.innerHTML=option('','choose')+Array.from(groups.values()).map(m=>`<option value="${esc(m[0].id)}">${esc(m[0].name)}｜${m.map(b=>esc(data.barns.find(x=>x.id===b.barn_id)?.name||'')).join('、')}${m.every(b=>b.status==='ended')?' · '+t('ended'):''}</option>`).join('');select.value=keep;
 let saved=null;try{saved=JSON.parse(localStorage.getItem(draftKey())||'null');}catch(e){}$('#manager-resume').hidden=!saved||saved.user!==me?.id;
}
function decorate(){
 if(!data||me?.role!=='admin')return;
 $$('#batch-settings .cohort-setting').forEach(card=>{if(card.querySelector('[data-manage-batch]'))return;const member=data.batches.find(b=>key(b)===card.dataset.cohortKey);if(member)card.querySelector('summary').insertAdjacentHTML('beforeend',`<button type="button" data-manage-batch="${esc(member.id)}">${txt('manageBatch')}</button>`);});
 $$('#barns .overview-cohort').forEach(card=>{if(card.querySelector('[data-manage-batch]'))return;const group=card.querySelector('[data-cohort-total]')?.dataset.cohortTotal,member=data.batches.find(b=>key(b)===group);if(member)card.querySelector('.overview-cohort-heading').insertAdjacentHTML('beforeend',`<button type="button" data-manage-batch="${esc(member.id)}" aria-label="${esc(t('manageBatch'))}">${txt('manageBatchShort')}</button>`);});
}
function fieldValue(value){if(value==null||value==='')return '—';if(Array.isArray(value))return value.map(l=>`${l.date} · ${l.count} ${t('heads')} · ${l.mean_kg??'—'} kg`).join('；');return typeof value==='number'?fmt(value):esc(['active','ended'].includes(value)?t(value):value);}
function renderImpact(p){
 $('#manager-impact').innerHTML=`<h3>${t('manageReview')}</h3><p>${t('asOf')} ${esc(p.as_of)}</p><div class="manager-impact-totals"><div>${t('manageTotals')}<strong>${fmt(p.before.entry,0)} → ${fmt(p.after.entry,0)}</strong></div><div>${t('manageStockTotal')}<strong>${fmt(p.before.remaining,0)} → ${fmt(p.after.remaining,0)}</strong></div></div>${p.rows.map(r=>`<article><h4>${esc(r.barn)}${r.barn!==r.barn_after?' → '+esc(r.barn_after):''}</h4><p>${t('manageCurrent')}：<strong>${fmt(r.before,0)} → ${fmt(r.after,0)} ${t('heads')}</strong></p>${r.fields.length?`<dl>${r.fields.map(c=>`<div><dt>${t(fieldLabels[c.field]||c.field)}</dt><dd>${fieldValue(c.before)} → ${fieldValue(c.after)}</dd></div>`).join('')}</dl>`:''}</article>`).join('')}`;
}
build=()=>{
 base.build();$('#page-settings').insertAdjacentHTML('afterbegin',`<section class="card admin-section" id="batch-management"><h2>${txt('manageFarm')}</h2><p>${txt('manageIntro')}</p><label>${txt('manageSelect')}<select id="manager-select"></select></label><div class="actions"><button type="button" id="manager-open" class="primary">${txt('manageOpen')}</button><button type="button" id="manager-resume" hidden>${txt('manageDraft')}</button><button type="button" id="manager-new">${txt('manageNew')}</button><button type="button" id="manager-barns">${txt('manageBarns')}</button><button type="button" id="manager-history">${txt('manageHistory')}</button></div><details><summary>${txt('manageHelp')}</summary><p>${txt('manageHelpText')}</p></details></section>`);
 document.body.insertAdjacentHTML('beforeend',`<dialog id="batch-manager-dialog" aria-labelledby="manager-title"><div class="section-row"><h2 id="manager-title"></h2><button type="button" id="manager-close">${txt('manageClose')}</button></div><form id="batch-manager-form"><label>${txt('type')}<select name="mode"><option value="entry" data-i="manageEntry">${t('manageEntry')}</option><option value="stock" data-i="manageStock">${t('manageStock')}</option></select></label><p id="manager-instruction" class="note"></p><div id="manager-entry-options"><label>${txt('manageName')}<input name="batch_name" maxlength="80" required></label><label class="check"><input type="checkbox" id="manager-keep-total">${txt('manageKeepTotal')}</label><p class="hint" id="manager-legacy-hint">${txt('manageLegacyTotal')}</p><p id="manager-total" role="status"></p></div><div id="manager-stock-options" hidden><label>${txt('date')}<input type="date" name="date"></label></div><div id="manager-rows"></div><label>${txt('manageReason')}<textarea name="reason" required maxlength="500"></textarea></label><p class="hint">${txt('manageDraftHint')}</p><button type="submit" id="manager-preview">${txt('manageReview')}</button></form><p id="manager-error" class="form-error" role="alert"></p><div id="manager-impact" aria-live="polite"></div><div class="actions"><button type="button" class="primary" id="manager-confirm" disabled>${txt('manageSave')}</button><button type="button" id="manager-retry" hidden>${txt('retry')}</button><button type="button" id="manager-reload">${txt('manageReload')}</button></div></dialog>`);
 $('#manager-open').onclick=()=>{const id=$('#manager-select').value;if(id)openManager(id);};
 $('#manager-resume').onclick=()=>{try{const saved=JSON.parse(localStorage.getItem(draftKey()));if(saved?.user===me?.id)openManager(saved.request.batch_id,saved.request);}catch(e){}};
 $('#manager-new').onclick=()=>$('#new-batch').click();$('#manager-barns').onclick=()=>{const card=$('#barn-form').closest('details');if(card)card.open=true;$('#barn-form').scrollIntoView({block:'start',behavior:'smooth'});};
 $('#manager-history').onclick=async()=>{
  const user=me?.id;let box=$('#manager-change-history');if(!box){box=document.createElement('section');box.id='manager-change-history';$('#batch-management').append(box);}box.textContent=t('manageLoading');
  try{const rows=await api('/api/audit');if(me?.id!==user)return;const seen=new Set(),changes=[];for(const row of rows){if(row.action!=='batch-settings')continue;const after=JSON.parse(row.after_value||'{}'),p=after.impact;if(!p||seen.has(p.preview_token))continue;seen.add(p.preview_token);changes.push(`<article><p><strong>${esc(new Date(row.timestamp).toLocaleString(lang==='vi'?'vi-VN':'zh-TW',{timeZone:'Asia/Taipei',hour12:false}))} · ${esc(row.username||'')}</strong></p><p>${t(p.mode==='stock'?'manageStock':'manageEntry')} · ${p.rows.map(r=>esc(r.barn_after)).join('、')} · ${t('manageStockTotal')} ${fmt(p.before.remaining,0)} → ${fmt(p.after.remaining,0)}</p><p>${esc(after.reason||'')}</p><details><summary>${t('manageFields')}</summary>${p.rows.map(r=>`<p><strong>${esc(r.barn)}${r.barn!==r.barn_after?' → '+esc(r.barn_after):''}</strong> · ${t('manageCurrent')} ${fmt(r.before,0)} → ${fmt(r.after,0)}</p>${r.fields.map(c=>`<p>${t(fieldLabels[c.field]||c.field)}：${fieldValue(c.before)} → ${fieldValue(c.after)}</p>`).join('')}`).join('')}</details></article>`);}box.innerHTML=`<h3>${t('manageHistory')}</h3>`+(changes.join('')||`<p>${t('noRecords')}</p>`);}
  catch(e){if(me?.id===user)box.textContent=messageError(e);}
 };
 $('#pages').addEventListener('click',e=>{const b=e.target.closest('[data-manage-batch]');if(b){e.preventDefault();e.stopPropagation();openManager(b.dataset.manageBatch);}});
 $('#manager-close').onclick=()=>{if(!pendingHere())dialog().close();};dialog().addEventListener('cancel',e=>{if(pendingHere())e.preventDefault();});dialog().addEventListener('close',()=>{++serial;++stockSerial;review=null;options();});
 form().addEventListener('input',remember);form().addEventListener('change',e=>{remember();if(e.target.name==='mode')modeChanged();if(e.target.name==='date')stock();});
 $('#manager-rows').addEventListener('click',e=>{if(pending)return;const remove=e.target.closest('[data-remove-lot]'),add=e.target.closest('[data-add-lot]');if(remove){remove.closest('.manager-lot').remove();remember();}if(add){add.closest('.manager-entry').querySelector('.manager-lots').insertAdjacentHTML('beforeend',lotHTML());remember();}});
 form().onsubmit=async e=>{
  e.preventDefault();if(!model||pending||previewBusy||!form().reportValidity())return;const request=body(),mine=++serial,user=me.id;previewBusy=true;controls();$('#manager-error').textContent='';
  try{const p=await api('/api/batch-settings/preview',{method:'POST',body:JSON.stringify(request)});if(mine!==serial||me?.id!==user||!dialog().open)return;if(JSON.stringify(body())!==JSON.stringify(request))throw {error:'manageChanged'};review={request,preview:p,user};renderImpact(p);}
  catch(e){if(mine===serial&&me?.id===user)$('#manager-error').textContent=messageError(e);}
  finally{previewBusy=false;controls();}
 };
 $('#manager-confirm').onclick=async()=>{
  if(!review||pending||review.user!==me?.id)return;if(JSON.stringify(body())!==JSON.stringify(review.request)){remember();return;}
  await startWrite('/api/batch-settings/apply','POST',{...review.request,preview_token:review.preview.preview_token});
  if(dialog().open){if(!pendingHere()){$('#manager-error').textContent=$('#toast').textContent;review=null;}controls();}
 };
 $('#manager-retry').onclick=async()=>{await retryPending();controls();};
 $('#manager-reload').onclick=()=>{if(model&&!pendingHere()){const id=model.id;clearDraft();openManager(id);}};
 document.addEventListener('pigledger:batch-settings-saved',()=>{clearDraft();model=null;review=null;dialog().close();form().reset();$('#manager-rows').replaceChildren();$('#manager-impact').replaceChildren();options();});
 document.addEventListener('pigledger:logout',()=>{++serial;++stockSerial;model=null;review=null;dirty=false;dialog().close();form().reset();$('#manager-rows').replaceChildren();$('#manager-impact').replaceChildren();$('#manager-title').textContent='';$('#manager-select').replaceChildren();$('#manager-change-history')?.remove();});
};
renderSettings=()=>{base.renderSettings();options();decorate();};
renderHome=async()=>{const result=await base.renderHome();decorate();return result;};
translate=()=>{base.translate();options();decorate();if(model){$('#manager-title').textContent=t('manageFarm');modeChanged();if(review)renderImpact(review.preview);}};
persistPending=()=>{base.persistPending();controls();};
restorePending=()=>{base.restorePending();if(pendingHere()&&data)openManager(pending.body.batch_id,pending.body);};
finishForm=f=>{base.finishForm(f);};
hasUnsavedWork=()=>base.hasUnsavedWork()||dirty;
enter=async user=>{await base.enter(user);if(me?.id===user.id)options();};
})();
