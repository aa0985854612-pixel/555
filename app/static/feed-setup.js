'use strict';
/* Physical bins identify shared destinations, without inventing per-barn kg. */
(() => {
Object.assign(words,{
 feedBin:['料桶','Bồn cám'],feedBinSetup:['料桶與廠商設定','Cài đặt bồn và nhà cung cấp'],feedType:['料別','Loại cám'],feedVendor:['飼料廠商','Nhà cung cấp cám'],feedDefaultVendor:['棟舍預設廠商','Nhà cung cấp mặc định'],feedRecordedVendor:['本期間登記廠商','Nhà cung cấp đã ghi trong kỳ'],feedRecordedTypes:['本期間登記料別','Loại cám đã ghi trong kỳ'],feedTypeBig:['大豬料','Cám heo lớn'],feedTypePiglet:['仔豬料','Cám heo con'],feedTypeLactation:['哺乳二期料','Cám giai đoạn bú sữa 2'],feedBinLegacy:['未指定料桶／舊紀錄','Chưa gán bồn / bản ghi cũ'],feedBinBarns:['料桶涵蓋棟舍','Các chuồng dùng bồn'],feedTargets:['對應批次（不分攤公斤）','Lứa liên quan (không chia kg)'],feedTargetUnknown:['未指定批次，保留料桶紀錄','Chưa gán lứa, giữ bản ghi bồn'],feedSharedHint:['共用桶保留整筆叫料量；跨批或只查單棟時，未分攤量另外標示，不平均分配。','Giữ lượng đặt cả bồn dùng chung; khác lứa hoặc một chuồng thì ghi riêng chưa phân bổ, không chia đều.'],feedSharedReference:['共用／批次未確認量，非單棟分配','Lượng dùng chung / chưa xác định lứa, không phân bổ riêng chuồng'],feedKnownTotal:['可歸屬叫料合計','Tổng lượng đặt xác định được'],feedReferenceTotal:['共用／待歸屬紀錄量','Lượng dùng chung / chờ phân bổ'],feedBinSetupHint:['共用棟舍由同一料桶登記；雙桶各自保存。已有叫料紀錄的料桶不能直接改棟舍歸屬，可停用後新增。','Ghi một lần cho bồn chung; bồn đôi lưu riêng. Bồn đã có lịch sử không đổi chuồng trực tiếp; có thể ngừng rồi thêm bồn mới.'],feedBinName:['料桶名稱／編號','Tên / mã bồn'],feedLegacyType:['舊紀錄料別','Loại cám cũ'],sharedFeedPending:['共用料桶未分攤','Bồn chung chưa phân bổ'],binBatchPending:['料桶批次待確認','Cần xác định lứa của bồn'],feedDisabled:['已停用','Đã ngừng'],feedConfigNote:['設定備註','Ghi chú cài đặt']
});
Object.assign(errorWords,{invalid_feed_type:['請選大豬料、仔豬料或哺乳二期料。','Chọn một trong ba loại cám.'],invalid_feed_bin:['請檢查料桶及涵蓋棟舍。','Kiểm tra bồn và các chuồng.'],duplicate_feed_bin:['料桶名稱已存在。','Tên bồn đã tồn tại.'],feed_bin_inactive:['料桶已停用，請重新選擇。','Bồn đã ngừng, chọn lại.'],feed_bin_members_locked:['此料桶已有叫料紀錄，不能直接變更涵蓋棟舍；請停用後另建料桶。','Bồn có lịch sử; không đổi chuồng trực tiếp. Ngừng rồi tạo bồn khác.'],bin_allocation_conflict:['料桶叫料不能同時填另一份分棟公斤，請重新核對。','Đặt theo bồn không kèm phân bổ kg khác; kiểm tra lại.']});
const base={build,selections,collect,edit,restorePending,finishForm,renderSettings,persistPending,query};
const types=[['大豬料','feedTypeBig'],['仔豬料','feedTypePiglet'],['哺乳二期料','feedTypeLactation']];
let binsFingerprint='';
function typeOptions(value=''){
 const select=$('#feed-order-form [name=item]');select.innerHTML=option('','choose')+types.map(([v,k])=>`<option value="${v}">${t(k)}</option>`).join('')+(value&&!types.some(([v])=>v===value)?`<option value="${esc(value)}">${t('feedLegacyType')}：${esc(value)}</option>`:'');select.value=value;
}
function binOptions(){
 if(!data)return;const f=$('#feed-order-form'),select=f.elements.feed_bin_id,value=select.value;
 select.innerHTML=option('','feedBinLegacy')+(data.feed_bins||[]).map(b=>`<option value="${b.id}">${esc(b.name)}${b.barn_ids.length>1?' · '+t('feedBinBarns')+' '+b.barn_ids.map(id=>esc(data.barns.find(x=>x.id===id)?.name||'')).join('、'):''} · ${esc(b.vendor)}${b.active?'':' · '+t('feedDisabled')}</option>`).join('');select.value=value;
}
function targets(explicit=null){
 if(!data)return;const f=$('#feed-order-form'),bin=data.feed_bins?.find(b=>b.id===val(f,'feed_bin_id')),box=$('#feed-bin-targets');
 const old=Object.fromEntries(Array.from(box.querySelectorAll('[data-feed-barn]')).map(e=>[e.dataset.feedBarn,e.value]));
 const legacy=f.querySelector('.scope');legacy.hidden=!!bin;f.elements.barn_id.required=false;f.elements.batch_id.required=!bin&&!!val(f,'barn_id');
 const scopeHint=f.querySelector('[data-i=orderScope]')?.closest('p');if(scopeHint)scopeHint.hidden=!!bin;
 box.hidden=!bin;
 if(!bin){box.replaceChildren();return;}
 const targets=[];
 box.innerHTML=`<p class="hint full">${t('feedTargets')}</p>`+bin.barn_ids.map(id=>{
  const batches=data.batches.filter(b=>b.barn_id===id&&(b.status==='active'||me?.role==='admin')).sort((a,b)=>b.entry_date.localeCompare(a.entry_date));
  let value=explicit?explicit.find(x=>batches.some(b=>b.id===x))||'':old[id];
  if(value===undefined){const candidates=batches.filter(b=>b.status==='active'&&b.entry_date<=val(f,'date'));value=candidates.length===1?candidates[0].id:'';}
  targets.push([id,value]);
  return `<label>${esc(data.barns.find(b=>b.id===id)?.name||'')}<select data-feed-barn="${id}"><option value="">${t('feedTargetUnknown')}</option>${batches.map(b=>`<option value="${b.id}">${esc(b.name)} · ${b.entry_date}${b.status==='ended'?' · '+t('ended'):''}</option>`).join('')}</select></label>`;
 }).join('')+`<p class="hint full">${t('feedSharedHint')}</p>`;
 targets.forEach(([id,value])=>box.querySelector(`[data-feed-barn="${id}"]`).value=value);
 box.querySelectorAll('select').forEach(el=>el.disabled=me?.role==='viewer'||pending?.formId===f.id);
}
build=()=>{
 base.build();const f=$('#feed-order-form'),grid=f.querySelector(':scope > .grid');
 const old=f.elements.namedItem('item').closest('label');old.outerHTML=select('feedType','item','');typeOptions();f.elements.namedItem('item').required=true;
 grid.insertAdjacentHTML('beforeend',select('feedBin','feed_bin_id',option('','feedBinLegacy')));
 grid.append(f.elements.namedItem('item').closest('label'),f.elements.vendor.closest('label'));f.elements.vendor.closest('label').querySelector('[data-i]').dataset.i='feedVendor';
 f.querySelector('details .grid').insertAdjacentHTML('afterbegin','<div id="feed-bin-targets" class="grid full" hidden></div>');
 const filter=$('#feed-filter'),oldFilter=filter.elements.namedItem('item').closest('label');oldFilter.outerHTML=select('feedType','item',option('','all'));filter.querySelector('.actions').insertAdjacentHTML('beforebegin',select('feedBin','feed_bin_id',option('','all')));
 f.elements.feed_bin_id.addEventListener('change',()=>{const b=data?.feed_bins.find(b=>b.id===val(f,'feed_bin_id'));if(b)f.elements.vendor.value=b.vendor;$('#feed-bin-targets').replaceChildren();targets();persistPending();});
 f.elements.date.addEventListener('change',()=>{targets();});
 f.elements.namedItem('item').addEventListener('change',()=>f.dataset.dirty='1');
 $('#page-settings').insertAdjacentHTML('beforeend',`<details class="card" id="feed-bin-settings"><summary>${txt('feedBinSetup')}</summary><p class="hint">${txt('feedBinSetupHint')}</p><form id="feed-bin-form" data-kind="feed_bins"><div class="grid">${input('feedBinName','name','text','required')}${select('feedVendor','vendor','<option>養全</option><option>新農科</option>')}<fieldset class="full"><legend>${txt('feedBinBarns')}</legend><div id="feed-bin-barns" class="bin-barn-options"></div></fieldset><label class="check"><input name="active" type="checkbox" checked>${txt('enabled')}</label>${input('feedConfigNote','note')}</div>${formActions()}</form><div id="feed-bin-list"></div></details>`);
 const binForm=$('#feed-bin-form');binForm.onsubmit=e=>{if(!binForm.querySelector('[name=member_barn]:checked')){e.preventDefault();binForm.querySelector('.form-error').textContent=t('invalid_feed_bin');return;}saveForm(e);};
 for(const ev of ['input','change'])binForm.addEventListener(ev,()=>binForm.dataset.dirty='1');
};
selections=(force=false)=>{
 base.selections(force);if(!data)return;
 const fingerprint=JSON.stringify([data.feed_bins,data.barns,data.batches.map(b=>[b.id,b.revision]),lang]);
 if(force||fingerprint!==binsFingerprint){binsFingerprint=fingerprint;const f=$('#feed-order-form');binOptions();typeOptions(val(f,'item'));targets();
 const filter=$('#feed-filter'),binFilter=filter.elements.feed_bin_id;replaceOptions(binFilter,option('','all')+data.feed_bins.map(b=>`<option value="${b.id}">${esc(b.name)} · ${esc(b.vendor)}</option>`).join(''));
 const itemFilter=filter.elements.namedItem('item'),legacyTypes=[...new Set(data.feed_orders.map(o=>o.item).filter(v=>v&&!types.some(([x])=>x===v)))];replaceOptions(itemFilter,option('','all')+types.map(([v,k])=>`<option value="${v}">${t(k)}</option>`).join('')+legacyTypes.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join(''));
 const old=Array.from($('#feed-bin-barns').querySelectorAll('input:checked')).map(e=>e.value);$('#feed-bin-barns').innerHTML=data.barns.map(b=>`<label class="check"><input type="checkbox" name="member_barn" value="${b.id}" ${old.includes(b.id)?'checked':''}>${esc(b.name)}</label>`).join('');}
};
query=f=>{const result=new URLSearchParams(base.query(f));if(val(f,'feed_bin_id'))result.set('feed_bin_id',val(f,'feed_bin_id'));return result.toString();};
collect=f=>{
 if(f.id==='feed-bin-form')return {name:val(f,'name'),vendor:val(f,'vendor'),barn_ids:Array.from(f.querySelectorAll('[name=member_barn]:checked')).map(e=>e.value),active:f.elements.active.checked,note:val(f,'note'),...(f.dataset.editId?{revision:Number(f.dataset.revision)}:{})};
 const body=base.collect(f);if(f.id==='feed-order-form'&&val(f,'feed_bin_id'))return {...body,allocations:[],feed_bin_id:val(f,'feed_bin_id'),target_batch_ids:Array.from($('#feed-bin-targets').querySelectorAll('select')).map(e=>e.value).filter(Boolean)};
 return body;
};
persistPending=()=>{base.persistPending();const f=$('#feed-bin-form');if(f)f.querySelectorAll('input,select,textarea,button').forEach(e=>e.disabled=me?.role!=='admin'||!!pending);};
edit=(kind,id)=>{
 if(kind==='feed_bins'){
  if(pending)return;const f=$('#feed-bin-form'),r=data.feed_bins.find(b=>b.id===id);if(!r)return;
  if(f.dataset.dirty==='1'){toast(t('saveBeforeSwitch'));return;}
  location.hash='settings';$('#feed-bin-settings').open=true;f.dataset.editId=id;f.dataset.revision=r.revision;f.elements.name.value=r.name;f.elements.vendor.value=r.vendor;f.elements.note.value=r.note;f.elements.active.checked=r.active;
  f.querySelectorAll('[name=member_barn]').forEach(e=>e.checked=r.barn_ids.includes(e.value));f.querySelector('[data-action=cancelEdit]').hidden=false;f.querySelector('.edit-label').hidden=false;f.scrollIntoView({block:'start'});return;
 }
 base.edit(kind,id);
 if(kind==='feed_orders'){const r=data.feed_orders.find(r=>r.id===id),f=$('#feed-order-form');f.elements.feed_bin_id.value=r.feed_bin_id||'';typeOptions(r.item);f.elements.namedItem('item').required=!!r.feed_bin_id||!!r.item;targets(r.target_batch_ids||null);}
};
restorePending=()=>{base.restorePending();if(!pending||pending.user!==me?.id)return;
 if(pending.formId==='feed-order-form'){const f=$('#feed-order-form');f.elements.feed_bin_id.value=pending.body.feed_bin_id||'';typeOptions(pending.body.item);targets(pending.body.target_batch_ids||null);}
 if(pending.formId==='feed-bin-form'){const r=pending.body,f=$('#feed-bin-form');$('#feed-bin-settings').open=true;f.elements.name.value=r.name;f.elements.vendor.value=r.vendor;f.elements.note.value=r.note;f.elements.active.checked=r.active;f.querySelectorAll('[name=member_barn]').forEach(e=>e.checked=r.barn_ids.includes(e.value));if(pending.method==='PUT'){f.dataset.editId=pending.path.split('/').pop();f.dataset.revision=r.revision;}}
 persistPending();
};
finishForm=f=>{base.finishForm(f);if(f.id==='feed-bin-form'){f.querySelectorAll('[name=member_barn]').forEach(e=>e.checked=false);f.elements.active.checked=true;}if(f.id==='feed-order-form')f.elements.namedItem('item').required=true;};
renderSettings=()=>{
 base.renderSettings();$('#feed-bin-form').hidden=me?.role!=='admin';
 preserveBox('feed-bin-list',(data.feed_bins||[]).map(b=>`<article class="feed-bin-row"><div><strong>${esc(b.name)}</strong><span>${esc(b.vendor)} · ${b.barn_ids.map(id=>esc(data.barns.find(x=>x.id===id)?.name||'')).join('、')}${b.active?'':' · '+t('feedDisabled')}</span></div>${me?.role==='admin'?`<button type="button" data-edit="feed_bins" data-id="${b.id}">${t('edit')}</button>`:''}</article>`).join('')||empty());persistPending();
};
})();
boot();
