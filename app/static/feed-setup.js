'use strict';
/* Physical bins identify shared destinations, without inventing per-barn kg. */
(() => {
Object.assign(words,{
 feedVendorHint:['選棟帶入上次料別與廠商，可自行更改；雙料桶請選桶號。可先叫料，再於進階項目指定預計進場批次，日期照實填寫。','Chọn chuồng để điền loại cám lần trước và nhà cung cấp; có thể sửa, chọn mã nếu có hai bồn. Có thể đặt trước rồi gán lứa sắp nhập trong mục nâng cao; giữ ngày thật.'],feedBinChoose:['請選料桶','Chọn bồn'],feedBinDefaultVendor:['料桶備用廠商（未指定棟舍時）','Nhà cung cấp dự phòng của bồn (chưa chọn chuồng)'],feedVendorMismatch:['共用桶各棟預設廠商不同，請核對本次廠商。','Các chuồng dùng chung bồn có nhà cung cấp mặc định khác nhau; kiểm tra lần đặt này.'],feedBin:['料桶','Bồn cám'],feedBinSetup:['料桶與廠商設定','Cài đặt bồn và nhà cung cấp'],feedType:['料別（選填）','Loại cám (tùy chọn)'],feedTypeUnknown:['暫不填料別','Chưa điền loại cám'],feedVendor:['飼料廠商','Nhà cung cấp cám'],feedDefaultVendor:['棟舍預設廠商','Nhà cung cấp mặc định'],feedRecordedVendor:['本期間登記廠商','Nhà cung cấp đã ghi trong kỳ'],feedRecordedTypes:['本期間登記料別','Loại cám đã ghi trong kỳ'],feedTypeBig:['大豬料','Cám heo lớn'],feedTypePiglet:['仔豬料','Cám heo con'],feedTypeLactation:['哺乳二期料','Cám giai đoạn bú sữa 2'],feedBinLegacy:['未指定料桶／舊紀錄','Chưa gán bồn / bản ghi cũ'],feedBinBarns:['料桶涵蓋棟舍','Các chuồng dùng bồn'],feedTargets:['各棟所屬批次／紀錄表','Lứa / báo cáo của từng chuồng'],feedTargetUnknown:['未指定批次，保留料桶紀錄','Chưa gán lứa, giữ bản ghi bồn'],feedSharedHint:['共用桶保留整筆叫料量；跨批或只查單棟時，未分攤量另外標示，不平均分配。','Giữ lượng đặt cả bồn dùng chung; khác lứa hoặc một chuồng thì ghi riêng chưa phân bổ, không chia đều.'],feedSharedReference:['共用／批次未確認量，非單棟分配','Lượng dùng chung / chưa xác định lứa, không phân bổ riêng chuồng'],feedKnownTotal:['可歸屬叫料合計','Tổng lượng đặt xác định được'],feedReferenceTotal:['共用／待歸屬紀錄量','Lượng dùng chung / chờ phân bổ'],feedBinSetupHint:['共用棟舍由同一料桶登記；雙桶各自保存。已有叫料紀錄的料桶不能直接改棟舍歸屬，可停用後新增。','Ghi một lần cho bồn chung; bồn đôi lưu riêng. Bồn đã có lịch sử không đổi chuồng trực tiếp; có thể ngừng rồi thêm bồn mới.'],feedBinName:['料桶名稱／編號','Tên / mã bồn'],feedLegacyType:['舊紀錄料別','Loại cám cũ'],sharedFeedPending:['共用料桶未分攤','Bồn chung chưa phân bổ'],binBatchPending:['料桶批次待確認','Cần xác định lứa của bồn'],feedDisabled:['已停用','Đã ngừng'],feedConfigNote:['設定備註','Ghi chú cài đặt']
});
Object.assign(errorWords,{invalid_feed_type:['請選大豬料、仔豬料或哺乳二期料。','Chọn một trong ba loại cám.'],invalid_feed_bin:['請檢查料桶及涵蓋棟舍。','Kiểm tra bồn và các chuồng.'],duplicate_feed_bin:['料桶名稱已存在。','Tên bồn đã tồn tại.'],feed_bin_inactive:['料桶已停用，請重新選擇。','Bồn đã ngừng, chọn lại.'],feed_bin_members_locked:['此料桶已有叫料紀錄，不能直接變更涵蓋棟舍；請停用後另建料桶。','Bồn có lịch sử; không đổi chuồng trực tiếp. Ngừng rồi tạo bồn khác.'],bin_allocation_conflict:['料桶叫料不能同時填另一份分棟公斤，請重新核對。','Đặt theo bồn không kèm phân bổ kg khác; kiểm tra lại.']});
const base={build,selections,collect,edit,restorePending,finishForm,renderSettings,persistPending,query,saveForm};
const types=[['大豬料','feedTypeBig'],['仔豬料','feedTypePiglet'],['哺乳二期料','feedTypeLactation']];
Object.assign(words,{feedSplit:['已確認各棟分量','Đã xác nhận lượng từng chuồng'],feedSplitAmount:['分配噸數','Số tấn phân bổ'],feedSplitHint:['只填實際確認的分量，合計須等於整桶叫料量；不自動平分。各棟依指定批次進入其整批紀錄表。','Chỉ nhập lượng đã xác nhận; tổng phải bằng lượng cả bồn, không chia đều. Mỗi phần vào báo cáo lứa đã chọn.'],feedBinTotal:['整桶','Cả bồn']});
Object.assign(errorWords,{allocation_total_mismatch:['各棟分量合計須等於整桶叫料量。','Tổng từng chuồng phải bằng lượng cả bồn.'],feed_split_required:['請填各棟分量，並指定有分量的棟舍批次。','Nhập lượng từng chuồng và chọn lứa cho phần đã phân bổ.']});
let binsFingerprint='';
function typeOptions(value=''){
 const select=$('#feed-order-form [name=item]');select.innerHTML=option('','feedTypeUnknown')+types.map(([v,k])=>`<option value="${v}">${t(k)}</option>`).join('')+(value&&!types.some(([v])=>v===value)?`<option value="${esc(value)}">${t('feedLegacyType')}：${esc(value)}</option>`:'');select.value=value;
}
// Read the synced, confirmed ledger, never another tab's unsaved selection.
function rememberType(){
 if(!data)return;const f=$('#feed-order-form');if(f.dataset.editId||pending?.formId===f.id)return;
 const barn=val(f,'barn_id'),bin=val(f,'feed_bin_id');if(!barn&&!bin){typeOptions();return;}
 const batches=new Map(data.batches.map(b=>[b.id,b.barn_id]));
 const orders=data.feed_orders||[],seen=new Set(orders.map(r=>r.id));
 const rows=[...orders,...(data.deliveries||[]).filter(r=>!seen.has(r.id))].filter(r=>{
  if(!r.item||r.deleted)return false;
  if(bin&&r.feed_bin_id)return r.feed_bin_id===bin;
  if(!barn)return false;
  return r.feed_bin_snapshot?.barn_ids?.includes(barn)||
   (r.target_batch_ids||[]).some(id=>batches.get(id)===barn)||
   (r.allocations||[]).some(a=>batches.get(a.batch_id)===barn);
 }).sort((a,b)=>b.date.localeCompare(a.date)||(b.created_at||'').localeCompare(a.created_at||'')||b.id.localeCompare(a.id));
 typeOptions(rows[0]?.item||'');
}
function binOptions(){
 if(!data)return;const f=$('#feed-order-form'),select=f.elements.feed_bin_id,value=select.value,barn=val(f,'barn_id');
 select.innerHTML=option('',barn?'feedBinChoose':'feedBinLegacy')+(data.feed_bins||[]).filter(b=>!barn||b.barn_ids.includes(barn)||b.id===value&&f.dataset.editId).map(b=>`<option value="${b.id}">${esc(feedBinLabel(b))} · ${esc(data.barns.find(x=>x.id===barn)?.feed_vendor||b.vendor)}${b.active?'':' · '+t('feedDisabled')}</option>`).join('');select.value=value;
}
function portionControls(){const f=$('#feed-order-form'),checked=f?.elements.bin_split_confirmed?.checked;$('#feed-bin-targets')?.querySelectorAll('[data-bin-portion-barn]').forEach(e=>e.disabled=!checked||me?.role==='viewer'||pending?.formId===f.id);}
function targets(explicit=null,allocations=null){
 if(!data)return;const f=$('#feed-order-form'),bin=data.feed_bins?.find(b=>b.id===val(f,'feed_bin_id')),box=$('#feed-bin-targets');
 const active=box.contains(document.activeElement)?document.activeElement:null,focusKey=active?.dataset.feedBarn?'data-feed-barn':active?.dataset.binPortionBarn?'data-bin-portion-barn':null,focusValue=focusKey?active.getAttribute(focusKey):null;
 const old=Object.fromEntries(Array.from(box.querySelectorAll('[data-feed-barn]')).map(e=>[e.dataset.feedBarn,e.value]));
 const checked=allocations!==null?allocations.length>0:!!box.querySelector('[name=bin_split_confirmed]:checked');
 const quantities=Object.fromEntries(Array.from(box.querySelectorAll('[data-bin-portion-barn]')).map(e=>[e.dataset.binPortionBarn,e.value]));
 const legacy=f.querySelector('.scope');legacy.hidden=false;f.elements.batch_id.closest('label').hidden=!!bin;
 f.elements.feed_bin_id.required=!!val(f,'barn_id')&&data.feed_bins.some(b=>b.active&&b.barn_ids.includes(val(f,'barn_id')))&&(!f.dataset.editId||!!data.feed_orders.find(o=>o.id===f.dataset.editId)?.feed_bin_id);f.elements.barn_id.required=false;f.elements.batch_id.required=!bin&&!!val(f,'barn_id');
 const scopeHint=f.querySelector('[data-i=orderScope]')?.closest('p');if(scopeHint)scopeHint.hidden=!!bin;
 box.hidden=!bin;
 const vendors=new Set((bin?.barn_ids||[]).map(id=>data.barns.find(b=>b.id===id)?.feed_vendor).filter(Boolean));
 $('#feed-vendor-warning').hidden=vendors.size<2;
 if(!bin){box.replaceChildren();return;}
 const targets=[];
 box.innerHTML=`<p class="hint full">${t('feedTargets')}</p>`+bin.barn_ids.map(id=>{
  const batches=data.batches.filter(b=>b.barn_id===id&&(b.status==='active'||me?.role==='admin')).sort((a,b)=>b.entry_date.localeCompare(a.entry_date));
  let value=explicit?explicit.find(x=>batches.some(b=>b.id===x))||'':old[id];
  if(value===undefined){const candidates=batches.filter(b=>b.status==='active'&&b.entry_date<=val(f,'date'));value=candidates.length===1?candidates[0].id:'';}
  targets.push([id,value]);
  return `<label>${esc(data.barns.find(b=>b.id===id)?.name||'')}<select data-feed-barn="${id}"><option value="">${t('feedTargetUnknown')}</option>${batches.map(b=>`<option value="${b.id}">${esc(feedBatchScope(b.id))}${b.status==='ended'?' · '+t('ended'):''}</option>`).join('')}</select></label>`;
 }).join('')+`<p class="hint full">${t('feedSharedHint')}</p>`;
 targets.forEach(([id,value])=>box.querySelector(`[data-feed-barn="${id}"]`).value=value);
 box.insertAdjacentHTML('beforeend',`<label class="check full"><input type="checkbox" name="bin_split_confirmed" ${checked?'checked':''}>${t('feedSplit')}</label><div class="grid full feed-bin-portions" ${checked?'':'hidden'}>${bin.barn_ids.map(id=>{const batch=targets.find(x=>x[0]===id)?.[1],part=allocations?.find(a=>a.batch_id===batch),value=allocations!==null?(part?part.kg/1000:''):quantities[id]||'';return `<label>${esc(data.barns.find(b=>b.id===id)?.name||'')} · ${t('feedSplitAmount')}<input type="number" min="0" step="any" inputmode="decimal" data-bin-portion-barn="${id}" value="${esc(value)}"></label>`;}).join('')}<p class="hint full">${t('feedSplitHint')}</p></div>`);
 box.querySelector('[name=bin_split_confirmed]').addEventListener('change',e=>{box.querySelector('.feed-bin-portions').hidden=!e.target.checked;portionControls();});
 box.querySelectorAll('select,input').forEach(el=>el.disabled=me?.role==='viewer'||pending?.formId===f.id);portionControls();if(focusKey){const next=box.querySelector(`[${focusKey}="${focusValue}"]`);if(next&&!next.disabled)next.focus({preventScroll:true});}
}
build=()=>{
 base.build();const f=$('#feed-order-form'),grid=f.querySelector(':scope > .grid');
 const old=f.elements.namedItem('item').closest('label');old.outerHTML=select('feedType','item','');typeOptions();f.elements.namedItem('item').required=false;
 grid.insertAdjacentHTML('beforeend',select('feedBin','feed_bin_id',option('','feedBinLegacy')));
 grid.append(f.querySelector('.scope'));
 grid.append(f.elements.feed_bin_id.closest('label'),f.elements.namedItem('item').closest('label'),f.elements.vendor.closest('label'));
 grid.insertAdjacentHTML('beforeend',`<p class="hint full">${txt('feedVendorHint')}</p><p class="hint full" id="feed-vendor-warning" hidden>${txt('feedVendorMismatch')}</p>`);
 $('#barn-form > .grid').insertAdjacentHTML('beforeend',select('feedDefaultVendor','feed_vendor',option('','choose')+'<option>養全</option><option>新農科</option>'));
 f.elements.vendor.closest('label').querySelector('[data-i]').dataset.i='feedVendor';
 f.querySelector('details .grid').insertAdjacentHTML('afterbegin','<div id="feed-bin-targets" class="grid full" hidden></div>');
 const filter=$('#feed-filter'),oldFilter=filter.elements.namedItem('item').closest('label');oldFilter.outerHTML=select('feedType','item',option('','all'));filter.querySelector('.actions').insertAdjacentHTML('beforebegin',select('feedBin','feed_bin_id',option('','all')));
 f.elements.feed_bin_id.addEventListener('change',()=>{const b=data?.feed_bins.find(b=>b.id===val(f,'feed_bin_id'));if(b){const barn=data.barns.find(x=>x.id===val(f,'barn_id'));f.elements.vendor.value=barn?.feed_vendor||b.vendor;}$('#feed-bin-targets').replaceChildren();targets();rememberType();persistPending();});
 f.elements.barn_id.addEventListener('change',()=>{
  const barn=data.barns.find(b=>b.id===val(f,'barn_id'));f.elements.feed_bin_id.value='';binOptions();
  const matches=data.feed_bins.filter(b=>b.active&&b.barn_ids.includes(barn?.id));
  if(matches.length===1)f.elements.feed_bin_id.value=matches[0].id;
  f.elements.vendor.value=barn?.feed_vendor||(matches.length&&new Set(matches.map(b=>b.vendor)).size===1?matches[0].vendor:'');
  $('#feed-bin-targets').replaceChildren();targets();rememberType();persistPending();
 });
 f.elements.date.addEventListener('change',()=>{targets();});
 f.elements.namedItem('item').addEventListener('change',()=>f.dataset.dirty='1');
 $('#page-settings').insertAdjacentHTML('beforeend',`<details class="card" id="feed-bin-settings"><summary>${txt('feedBinSetup')}</summary><p class="hint">${txt('feedBinSetupHint')}</p><form id="feed-bin-form" data-kind="feed_bins"><div class="grid">${input('feedBinName','name','text','required')}${select('feedBinDefaultVendor','vendor','<option>養全</option><option>新農科</option>')}<fieldset class="full"><legend>${txt('feedBinBarns')}</legend><div id="feed-bin-barns" class="bin-barn-options"></div></fieldset><label class="check"><input name="active" type="checkbox" checked>${txt('enabled')}</label>${input('feedConfigNote','note')}</div>${formActions()}</form><div id="feed-bin-list"></div></details>`);
 const binForm=$('#feed-bin-form');binForm.onsubmit=e=>{if(!binForm.querySelector('[name=member_barn]:checked')){e.preventDefault();binForm.querySelector('.form-error').textContent=t('invalid_feed_bin');return;}saveForm(e);};
 for(const ev of ['input','change'])binForm.addEventListener(ev,()=>binForm.dataset.dirty='1');
};
selections=(force=false)=>{
 base.selections(force);if(!data)return;
 const fingerprint=JSON.stringify([data.feed_bins,data.barns,data.batches.map(b=>[b.id,b.revision]),lang]);
 if(force||fingerprint!==binsFingerprint){binsFingerprint=fingerprint;const f=$('#feed-order-form');binOptions();typeOptions(val(f,'item'));targets();
 const filter=$('#feed-filter'),binFilter=filter.elements.feed_bin_id;replaceOptions(binFilter,option('','all')+data.feed_bins.map(b=>`<option value="${b.id}">${esc(feedBinLabel(b))} · ${esc(b.vendor)}</option>`).join(''));
 const itemFilter=filter.elements.namedItem('item'),legacyTypes=[...new Set(data.feed_orders.map(o=>o.item).filter(v=>v&&!types.some(([x])=>x===v)))];replaceOptions(itemFilter,option('','all')+types.map(([v,k])=>`<option value="${v}">${t(k)}</option>`).join('')+legacyTypes.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join(''));
 const old=Array.from($('#feed-bin-barns').querySelectorAll('input:checked')).map(e=>e.value);$('#feed-bin-barns').innerHTML=data.barns.map(b=>`<label class="check"><input type="checkbox" name="member_barn" value="${b.id}" ${old.includes(b.id)?'checked':''}>${esc(b.name)}</label>`).join('');}
};
query=f=>{const result=new URLSearchParams(base.query(f));if(val(f,'feed_bin_id'))result.set('feed_bin_id',val(f,'feed_bin_id'));return result.toString();};
collect=f=>{
 if(f.id==='feed-bin-form')return {name:val(f,'name'),vendor:val(f,'vendor'),barn_ids:Array.from(f.querySelectorAll('[name=member_barn]:checked')).map(e=>e.value),active:f.elements.active.checked,note:val(f,'note'),...(f.dataset.editId?{revision:Number(f.dataset.revision)}:{})};
 const body=base.collect(f);if(f.id==='feed-order-form'&&val(f,'feed_bin_id'))return {...body,...(val(f,'barn_id')?{requested_barn_id:val(f,'barn_id')}:{}),allocations:[],feed_bin_id:val(f,'feed_bin_id'),target_batch_ids:Array.from($('#feed-bin-targets').querySelectorAll('select')).map(e=>e.value).filter(Boolean),bin_allocations:val(f,'bin_split_confirmed')&&f.elements.bin_split_confirmed.checked?Array.from($('#feed-bin-targets').querySelectorAll('[data-bin-portion-barn]')).filter(e=>Number(e.value)>0).map(e=>({batch_id:$('#feed-bin-targets').querySelector(`[data-feed-barn="${e.dataset.binPortionBarn}"]`).value,kg:Number(e.value)*1000})):[]};
 return body;
};
persistPending=()=>{base.persistPending();portionControls();const f=$('#feed-bin-form');if(f)f.querySelectorAll('input,select,textarea,button').forEach(e=>e.disabled=me?.role!=='admin'||!!pending);};
edit=(kind,id)=>{
 if(kind==='feed_bins'){
  if(pending)return;const f=$('#feed-bin-form'),r=data.feed_bins.find(b=>b.id===id);if(!r)return;
  if(f.dataset.dirty==='1'){toast(t('saveBeforeSwitch'));return;}
  location.hash='settings';$('#feed-bin-settings').open=true;f.dataset.editId=id;f.dataset.revision=r.revision;f.elements.name.value=r.name;f.elements.vendor.value=r.vendor;f.elements.note.value=r.note;f.elements.active.checked=r.active;
  f.querySelectorAll('[name=member_barn]').forEach(e=>e.checked=r.barn_ids.includes(e.value));f.querySelector('[data-action=cancelEdit]').hidden=false;f.querySelector('.edit-label').hidden=false;f.scrollIntoView({block:'start'});return;
 }
 base.edit(kind,id);
 if(kind==='barns'&&$('#barn-form').dataset.editId===id){const r=data.barns.find(b=>b.id===id);if(r)$('#barn-form').elements.feed_vendor.value=r.feed_vendor||'';}
 if(kind==='feed_orders'&&$('#feed-order-form').dataset.editId===id){const r=data.feed_orders.find(r=>r.id===id),f=$('#feed-order-form');if(r.feed_bin_id){const bin=data.feed_bins.find(b=>b.id===r.feed_bin_id);f.elements.barn_id.value=bin?.barn_ids.length===1?bin.barn_ids[0]:'';}binOptions();f.elements.feed_bin_id.value=r.feed_bin_id||'';typeOptions(r.item);f.elements.namedItem('item').required=false;targets(r.target_batch_ids||null,r.bin_allocations||[]);}
};
restorePending=()=>{base.restorePending();if(!pending||pending.user!==me?.id)return;
 if(pending.formId==='feed-order-form'){const f=$('#feed-order-form');const body=pending.body.record||pending.body;if(body.feed_bin_id){const bin=data.feed_bins.find(b=>b.id===body.feed_bin_id);f.elements.barn_id.value=bin?.barn_ids.length===1?bin.barn_ids[0]:'';}binOptions();f.elements.feed_bin_id.value=body.feed_bin_id||'';typeOptions(body.item);targets(body.target_batch_ids||null,body.bin_allocations||[]);}
 if(pending.formId==='feed-bin-form'){const r=pending.body,f=$('#feed-bin-form');$('#feed-bin-settings').open=true;f.elements.name.value=r.name;f.elements.vendor.value=r.vendor;f.elements.note.value=r.note;f.elements.active.checked=r.active;f.querySelectorAll('[name=member_barn]').forEach(e=>e.checked=r.barn_ids.includes(e.value));if(pending.method==='PUT'){f.dataset.editId=pending.path.split('/').pop();f.dataset.revision=r.revision;}}
 persistPending();
};
finishForm=f=>{base.finishForm(f);if(f.id==='barn-form')f.elements.feed_vendor.value='';if(f.id==='feed-bin-form'){f.querySelectorAll('[name=member_barn]').forEach(e=>e.checked=false);f.elements.active.checked=true;}if(f.id==='feed-order-form'){f.elements.namedItem('item').required=false;$('#feed-bin-targets [name=bin_split_confirmed]')?.removeAttribute('checked');const checkbox=$('#feed-bin-targets [name=bin_split_confirmed]');if(checkbox)checkbox.checked=false;$('#feed-bin-targets').querySelectorAll('[data-bin-portion-barn]').forEach(e=>e.value='');const box=$('#feed-bin-targets .feed-bin-portions');if(box)box.hidden=true;}};
saveForm=e=>{
 const f=e.target;if(f.id==='feed-order-form'&&f.elements.bin_split_confirmed?.checked){
  const body=collect(f);if(!body.bin_allocations.length||body.bin_allocations.some(r=>!r.batch_id)){e.preventDefault();f.querySelector('.form-error').textContent=t('feed_split_required');return;}
  if(Math.abs(body.bin_allocations.reduce((n,r)=>n+r.kg,0)-body.kg)>1e-7){e.preventDefault();f.querySelector('.form-error').textContent=t('allocation_total_mismatch');return;}
 }
 return base.saveForm(e);
};
renderSettings=()=>{
 base.renderSettings();$('#feed-bin-form').hidden=me?.role!=='admin';
 preserveBox('feed-bin-list',(data.feed_bins||[]).map(b=>`<article class="feed-bin-row"><div><strong>${esc(feedBinLabel(b))}</strong><span>${esc(b.vendor)} · ${b.barn_ids.map(id=>esc(data.barns.find(x=>x.id===id)?.name||'')).join('、')}${b.active?'':' · '+t('feedDisabled')}</span></div>${me?.role==='admin'?`<button type="button" data-edit="feed_bins" data-id="${b.id}">${t('edit')}</button>`:''}</article>`).join('')||empty());persistPending();
};
})();
