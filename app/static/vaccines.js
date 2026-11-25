'use strict';
/* One audited plan belongs to one barn's batch. */
(() => {
 Object.assign(words,{
  vaccineTitle:['疫苗施打計畫','Kế hoạch tiêm vắc-xin'],
  vaccineBatch:['批號與棟舍','Mã lứa và chuồng'],
  vaccineChoose:['請選擇批號與棟舍','Chọn lứa và chuồng'],
  vaccineFirst:['第一次','Lần thứ nhất'],
  vaccineSecond:['第二次','Lần thứ hai'],
  vaccineDate:['施打日期','Ngày tiêm'],
  vaccineBottles:['用藥瓶數（選填）','Số lọ (tùy chọn)'],
  vaccineDone:['已施打','Đã tiêm'],
  vaccineSave:['儲存疫苗資料','Lưu dữ liệu vắc-xin'],
  vaccineHint:['先選批號與棟舍，再填 PR、APP 每次施打日期；完成施打後勾選「已施打」。','Chọn lứa và chuồng, nhập ngày PR và APP; đánh dấu đã tiêm sau khi hoàn tất.'],
  vaccineDateRequired:['勾選已施打時，請先填寫該次施打日期。','Nhập ngày tiêm trước khi đánh dấu đã tiêm.']
 });
 Object.assign(errorWords,{
  invalid_vaccine_plan:['請檢查施打日期、瓶數和已施打狀態。','Kiểm tra ngày tiêm, số lọ và trạng thái đã tiêm.'],
  vaccine_plan_exists:['這個批次已有疫苗資料，請重新載入後修改。','Lứa này đã có dữ liệu vắc-xin; tải lại để sửa.']
 });
 const base={build,selections,translate};
 const keys=['pr1','app1','pr2','app2'];
 let dirty=false;
 const drafts=new Map();
 function options(){
  const select=$('#vaccine-batch');
  if(!select||!data)return;
  const selected=select.value;
  const barns=new Map(data.barns.map(b=>[b.id,b.name]));
  const batches=[...data.batches].sort((a,b)=>b.entry_date.localeCompare(a.entry_date)||String(barns.get(a.barn_id)||'').localeCompare(String(barns.get(b.barn_id)||''),undefined,{numeric:true}));
  select.innerHTML='<option value="">'+esc(t('vaccineChoose'))+'</option>'+batches.map(b=>'<option value="'+esc(b.id)+'">'+esc(b.name+'｜'+(barns.get(b.barn_id)||'')+(b.status==='ended'?' · '+t('ended'):''))+'</option>').join('');
  select.value=selected;
 }
 function populate(){
  const form=$('#vaccine-form');
  if(!form)return;
  const id=$('#vaccine-batch').value;
  const plan=(data?.vaccine_plans||[]).find(item=>item.batch_id===id);
  const doses=drafts.get(id)||plan?.doses;
  for(const key of keys){
   const dose=doses?.[key];
   form.elements[key+'_date'].value=dose?.date||'';
   form.elements[key+'_bottles'].value=dose?.bottles??'';
   form.elements[key+'_done'].checked=!!dose?.done;
  }
  form.querySelector('fieldset').disabled=!id||me?.role!=='admin'||!!pending;
  $('#vaccine-batch').disabled=!!pending;
  form.querySelector('.form-error').textContent='';
  dirty=drafts.size>0;
  form.dataset.dirty=dirty?'1':'';
 }
 function readDoses(form){
  return Object.fromEntries(keys.map(key=>[key,{
   date:form.elements[key+'_date'].value,
   bottles:form.elements[key+'_bottles'].value===''?null:Number(form.elements[key+'_bottles'].value),
   done:form.elements[key+'_done'].checked
  }]));
 }
 function doseFields(key,vaccine,round){
  return `<section class="vaccine-dose"><h4>${esc(vaccine)} · ${txt(round)}</h4>
   <label>${txt('vaccineDate')}<input type="date" name="${key}_date"></label>
   <label>${txt('vaccineBottles')}<input type="number" name="${key}_bottles" min="0" step="any" inputmode="decimal"></label>
   <label class="check"><input type="checkbox" name="${key}_done"> ${txt('vaccineDone')}</label></section>`;
 }
 build=()=>{
  base.build();
  $('#page-settings').insertAdjacentHTML('afterbegin',`<section class="card admin-section" id="vaccine-settings">
   <h2>${txt('vaccineTitle')}</h2><p class="hint">${txt('vaccineHint')}</p>
   <form id="vaccine-form"><label>${txt('vaccineBatch')}<select id="vaccine-batch" required></select></label>
   <fieldset disabled><div class="grid">
    ${doseFields('pr1','PR','vaccineFirst')}
    ${doseFields('app1','APP','vaccineFirst')}
    ${doseFields('pr2','PR','vaccineSecond')}
    ${doseFields('app2','APP','vaccineSecond')}
   </div><button type="submit" class="primary">${txt('vaccineSave')}</button></fieldset>
   <p class="form-error" role="status"></p></form></section>`);
  const form=$('#vaccine-form');
  $('#vaccine-batch').addEventListener('change',populate);
  form.addEventListener('input',event=>{
   if(event.target.id==='vaccine-batch')return;
   const id=$('#vaccine-batch').value;
   if(id)drafts.set(id,readDoses(form));
   dirty=drafts.size>0;
   form.dataset.dirty=dirty?'1':'';
  });
  form.addEventListener('submit',async event=>{
   event.preventDefault();
   if(!me||me.role!=='admin'||!form.reportValidity())return;
   if(pending){toast(t('pending'));return;}
   const batchId=$('#vaccine-batch').value,doses=readDoses(form);
   if(Object.values(doses).some(dose=>dose.done&&!dose.date)){
    form.querySelector('.form-error').textContent=t('vaccineDateRequired');return;
   }
   const current=(data.vaccine_plans||[]).find(plan=>plan.batch_id===batchId);
   const body={batch_id:batchId,doses,...(current?{revision:current.revision}:{})};
   form.querySelector('fieldset').disabled=true;
   $('#vaccine-batch').disabled=true;
   try{await startWrite('/api/vaccine_plans'+(current?'/'+current.id:''),current?'PUT':'POST',body);}
   finally{form.querySelector('fieldset').disabled=!$('#vaccine-batch').value||me?.role!=='admin'||!!pending;$('#vaccine-batch').disabled=!!pending;}
  });
  document.addEventListener('pigledger:vaccine-saved',event=>{
   drafts.delete(event.detail.batch_id);
   dirty=drafts.size>0;
   if($('#vaccine-batch').value)populate();
  });
  document.addEventListener('pigledger:logout',()=>{dirty=false;drafts.clear();delete form.dataset.dirty;form.reset();$('#vaccine-batch').replaceChildren();form.querySelector('fieldset').disabled=true;});
 };
 selections=(...args)=>{const result=base.selections(...args);options();if(!dirty&&$('#vaccine-batch')?.value)populate();return result;};
 translate=()=>{base.translate();options();};
})();
