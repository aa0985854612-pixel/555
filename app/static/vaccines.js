'use strict';
/* Vaccination plans are shared by the selected cohort. */
(() => {
 Object.assign(words,{
  vaccineTitle:['疫苗施打計畫','Kế hoạch tiêm vắc-xin'],
  vaccineBatch:['批號','Mã lứa'],
  vaccineChoose:['請選擇批號','Chọn mã lứa'],
  vaccineFirst:['第一次','Lần thứ nhất'],
  vaccineSecond:['第二次','Lần thứ hai'],
  vaccineDate:['施打日期','Ngày tiêm'],
  vaccineBottles:['用藥瓶數（選填）','Số lọ (tùy chọn)'],
  vaccineBottleUnit:['瓶','lọ'],
  vaccineDone:['已施打','Đã tiêm'],
  vaccineSave:['儲存疫苗資料','Lưu dữ liệu vắc-xin'],
  vaccineHint:['選批號後填寫 PR、APP 日期與整批瓶數，同批棟舍共用；施打後勾選「已施打」。','Chọn mã lứa, nhập ngày và tổng số lọ PR, APP cho cả lứa; đánh dấu đã tiêm sau khi hoàn tất.'],
  vaccinePrevious:['原先各棟疫苗資料','Dữ liệu tiêm cũ theo chuồng'],
  vaccineConflicting:['各棟原有資料不同，請參考下方明細後填寫整批資料。','Dữ liệu cũ giữa các chuồng khác nhau; xem chi tiết bên dưới trước khi nhập cho cả lứa.'],
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
 function cohortKey(batch){return batch._cohort_key||batch.name+'|'+batch.entry_date;}
 function members(key){return (data?.batches||[]).filter(batch=>cohortKey(batch)===key);}
 function cohortPlans(key){
  const ids=new Set(members(key).map(batch=>batch.id));
  return (data?.vaccine_plans||[]).filter(plan=>ids.has(plan.batch_id));
 }
 function options(){
  const select=$('#vaccine-batch');
  if(!select||!data)return;
  const selected=select.value;
  const groups=(data.cohorts||[]).filter(group=>!group.archive&&members(group.key).length)
   .sort((a,b)=>b.entry_date.localeCompare(a.entry_date)||b.name.localeCompare(a.name));
  select.innerHTML='<option value="">'+esc(t('vaccineChoose'))+'</option>'+groups.map(group=>{
   const groupBatches=members(group.key);
   const barns=orderedBarns(data.barns.filter(barn=>groupBatches.some(batch=>batch.barn_id===barn.id))).map(barn=>barn.name);
   const ended=groupBatches.every(batch=>batch.status==='ended')?' · '+t('ended'):'';
   return '<option value="'+esc(group.key)+'">'+esc(group.name+'｜'+barns.join('、')+ended)+'</option>';
  }).join('');
  select.value=selected;
 }
 function populate(){
  const form=$('#vaccine-form');
  if(!form)return;
  const key=$('#vaccine-batch').value,plans=cohortPlans(key);
  const shared=plans.filter(plan=>plan.scope==='cohort');
  const previous=plans.filter(plan=>plan.scope!=='cohort');
  const signatures=new Set(previous.map(plan=>JSON.stringify(keys.map(name=>plan.doses[name]))));
  const conflict=shared.length>1||(!shared.length&&signatures.size>1);
  const plan=shared.length===1?shared[0]:(!shared.length&&signatures.size===1?previous[0]:null);
  const doses=drafts.get(key)||plan?.doses;
  for(const name of keys){
   const dose=doses?.[name];
   form.elements[name+'_date'].value=dose?.date||'';
   form.elements[name+'_bottles'].value=dose?.bottles??'';
   form.elements[name+'_done'].checked=!!dose?.done;
  }
  const barnName=id=>{
   const batch=data.batches.find(item=>item.id===id);
   return data.barns.find(barn=>barn.id===batch?.barn_id)?.name||'';
  };
  const previousBox=$('#vaccine-previous');
  const visible=previous.concat(shared.length>1?shared:[]);
  previousBox.hidden=!visible.length;
  previousBox.innerHTML=visible.length?'<summary>'+esc(t('vaccinePrevious'))+'</summary>'+visible.map(plan=>{
   const lines=keys.map(name=>{
    const dose=plan.doses[name];
    if(!dose.date&&dose.bottles==null&&!dose.done)return '';
    return name.toUpperCase()+' '+(dose.date||'—')+' '+(dose.bottles==null?'':dose.bottles+' '+t('vaccineBottleUnit'))+' '+(dose.done?t('vaccineDone'):'');
   }).filter(Boolean);
   return '<p><strong>'+esc(barnName(plan.batch_id))+'</strong> '+esc(lines.join('；'))+'</p>';
  }).join(''):'';
  form.querySelector('fieldset').disabled=!key||me?.role!=='admin'||!!pending;
  $('#vaccine-batch').disabled=!!pending;
  form.querySelector('.form-error').textContent=conflict?t('vaccineConflicting'):'';
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
   <p class="form-error" role="status"></p><details id="vaccine-previous" hidden></details></form></section>`);
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
   const key=$('#vaccine-batch').value,doses=readDoses(form);
   if(Object.values(doses).some(dose=>dose.done&&!dose.date)){
    form.querySelector('.form-error').textContent=t('vaccineDateRequired');return;
   }
   const shared=cohortPlans(key).filter(plan=>plan.scope==='cohort');
   if(shared.length>1){form.querySelector('.form-error').textContent=t('vaccineConflicting');return;}
   const current=shared[0];
   const batchId=current?.batch_id||members(key).map(batch=>batch.id).sort()[0];
   const body={batch_id:batchId,scope:'cohort',doses,...(current?{revision:current.revision}:{})};
   form.querySelector('fieldset').disabled=true;
   $('#vaccine-batch').disabled=true;
   try{await startWrite('/api/vaccine_plans'+(current?'/'+current.id:''),current?'PUT':'POST',body);}
   finally{form.querySelector('fieldset').disabled=!$('#vaccine-batch').value||me?.role!=='admin'||!!pending;$('#vaccine-batch').disabled=!!pending;}
  });
  document.addEventListener('pigledger:vaccine-saved',event=>{
   const batch=data?.batches.find(item=>item.id===event.detail.batch_id);
   if(batch)drafts.delete(cohortKey(batch));
   dirty=drafts.size>0;
   if($('#vaccine-batch').value)populate();
  });
  document.addEventListener('pigledger:logout',()=>{dirty=false;drafts.clear();delete form.dataset.dirty;form.reset();$('#vaccine-batch').replaceChildren();form.querySelector('fieldset').disabled=true;});
 };
 selections=(...args)=>{const result=base.selections(...args);options();if(!dirty&&$('#vaccine-batch')?.value)populate();return result;};
 translate=()=>{base.translate();options();};
})();
