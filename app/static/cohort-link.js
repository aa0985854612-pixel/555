'use strict';
/* An explicit same-batch link never changes physical entry dates or headcounts. */
(() => {
Object.assign(words,{sameBatchAs:['同批歸組（選填）','Gộp cùng lứa (tùy chọn)'],ownBatch:['獨立批次，不歸組','Lứa độc lập, không gộp'],sameBatchHelp:['分次進場也可同批：選已建立的那一批，保留這棟的實際進場日及頭數。Excel舊批次不改歸屬；新一批請另外新增。','Có thể cùng lứa dù nhập khác ngày: chọn lứa đã có, giữ ngày nhập và số con thực tế. Không đổi lứa Excel cũ; tạo bản mới cho đàn mới.'],mixedAges:['週齡依棟舍','Tuổi khác theo chuồng']});
Object.assign(errorWords,{cohort_link_cycle:['同批歸組不可互相循環。','Không được gộp lứa theo vòng.'],cohort_link_same_barn:['請選另一棟的同批資料；同棟不同批不能直接合併。','Chọn bản cùng lứa ở chuồng khác.'],cohort_link_earlier_entry:['請以最早進場的那一筆作為同批基準。','Chọn bản nhập sớm nhất làm gốc lứa.']});
const base={build,selections,edit,finishForm};
function options(){
 const f=$('#batch-form');if(!f||!data)return;const r=data.batches.find(b=>b.id===f.dataset.editId),select=f.elements.same_batch_as,keep=select.value;
 const roots=data.batches.filter(b=>b.id!==r?.id&&!b.same_batch_as&&b.barn_id!==val(f,'barn_id')).sort((a,b)=>b.entry_date.localeCompare(a.entry_date));
 select.innerHTML=`<option value="">${t('ownBatch')}</option>`+roots.map(b=>`<option value="${esc(b.id)}">${esc(b.name)}｜${esc(data.barns.find(x=>x.id===b.barn_id)?.name||'')} · ${esc(b.entry_date)}${b.status==='ended'?' · '+t('ended'):''}</option>`).join('');
 if(roots.some(b=>b.id===keep))select.value=keep;
 select.closest('label').hidden=!!r?.legacy_source;select.disabled=me?.role!=='admin'||!!r?.legacy_source||pending?.formId===f.id;
 f.elements.name.readOnly=!!select.value;
}
build=()=>{
 base.build();const f=$('#batch-form');f.querySelector(':scope > .grid').insertAdjacentHTML('beforeend',`<label class="full">${txt('sameBatchAs')}<select name="same_batch_as"><option value="">${t('ownBatch')}</option></select><small class="hint">${txt('sameBatchHelp')}</small></label>`);
 f.elements.same_batch_as.addEventListener('change',()=>{const b=data?.batches.find(b=>b.id===val(f,'same_batch_as'));if(b)f.elements.name.value=b.name;f.elements.name.readOnly=!!b;f.dataset.dirty='1';});f.elements.barn_id.addEventListener('change',options);
};
selections=(force=false)=>{base.selections(force);options();};
edit=(kind,id)=>{base.edit(kind,id);if(kind==='batches'){options();const f=$('#batch-form'),r=data.batches.find(b=>b.id===id);f.elements.same_batch_as.value=r.same_batch_as||'';f.elements.name.readOnly=!!r.same_batch_as;}};
finishForm=f=>{base.finishForm(f);if(f.id==='batch-form'){f.elements.same_batch_as.value='';f.elements.name.readOnly=false;options();}};
})();
