'use strict';
/* Projections are read-only and separate from saved weighing samples. */
(() => {
Object.assign(words,{
 growthEstimateTitle:['體重估算','Ước tính cân nặng'],growthEstimateIntro:['依最近秤重推估到今天；日期更新時會自動重算。','Ước tính đến hôm nay từ lần cân gần nhất; tự tính lại khi sang ngày.'],
 growthEstimateSelect:['選擇棟舍／批次','Chọn chuồng / lứa'],growthEstimateAll:['全部飼養中棟舍','Tất cả chuồng đang nuôi'],growthEstimateToday:['今日估計均重','TB ước tính hôm nay'],growthEstimateDate:['估算日期','Ngày ước tính'],
 growthEstimateLatest:['最近秤重','Cân gần nhất'],growthEstimateUnit:['公斤／隻','kg/con'],growthEstimateRate:['估計每日增重','Tăng trọng ngày ước tính'],growthEstimateRateUnit:['公斤／隻／日','kg/con/ngày'],growthEstimateGain:['期間平均增重','Tăng TB giữa hai mốc'],
 growthEstimateTwo:['依最近兩個秤重日估算','Theo hai ngày cân gần nhất'],growthEstimateOne:['依進場均重＋一次秤重估算','Theo TB lúc nhập + một lần cân'],growthEstimateEntry:['進場均重','TB lúc nhập'],growthEstimateWeighed:['秤重均重','TB khi cân'],
 growthEstimateFormula:['今日估重＝最近均重＋每日增重 × 經過天數。','TB hôm nay = TB gần nhất + tăng trọng/ngày × số ngày đã qua.'],growthEstimateSample:['抽樣與固定增重速度的估算，實際體重以重新秤重為準。','Ước tính từ mẫu và tốc độ tăng cố định; cân lại để biết thực tế.'],
 growthEstimateMissing:['尚無秤重，登記一次後即可搭配進場均重估算。','Chưa cân; ghi một lần để ước tính cùng TB lúc nhập.'],growthEstimateNeedEntry:['已有一次秤重；請補進場均重與日期，或再秤一次。','Đã cân một lần; bổ sung TB và ngày nhập, hoặc cân lần nữa.'],growthEstimateNeedDate:['需要兩個不同日期的均重；請再登記另一日秤重。','Cần TB ở hai ngày khác nhau; ghi lần cân vào ngày khác.'],
 growthEstimateDecreased:['後次均重較低，暫停推估今日體重；請核對抽樣與豬群。','TB lần sau thấp hơn; tạm dừng dự đoán hôm nay. Kiểm tra mẫu và đàn.'],growthEstimateMovement:['比較後有出豬、死亡或其他頭數異動，現存豬群均重可能不同。','Có xuất, chết hoặc biến động số con; TB đàn hiện tại có thể khác.'],
 growthEstimateElapsed:['距最近秤重','Từ lần cân gần nhất'],growthEstimateStale:['距上次秤重較久，建議再秤一次更新估算。','Đã lâu chưa cân; nên cân lại để cập nhật ước tính.'],growthEstimateLoading:['正在讀取秤重估算…','Đang tải ước tính…'],growthEstimateFailed:['估算尚未更新，請重新整理；下方日期為上次成功計算日。','Chưa cập nhật; hãy tải lại. Ngày bên dưới là ngày tính thành công gần nhất.']
});
const base={build,renderCurrent,translate,refresh};
let model=null,serial=0,owner=null;
const farmDate=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const box=()=>$('#growth-estimates');
function render(){
 if(!box()||!me||owner!==me.id||!model)return;
 const selector=$('#growth-estimate-batch'),selected=selector.value;
 const rows=[...model.batches].sort((a,b)=>batchName(a.batch_id).localeCompare(batchName(b.batch_id),'zh-Hant',{numeric:true}));
 selector.innerHTML=`<option value="*">${t('growthEstimateAll')}</option>`+rows.map(r=>`<option value="${esc(r.batch_id)}">${esc(batchName(r.batch_id))}</option>`).join('');
 selector.value=selected==='*'?'*':rows.some(r=>r.batch_id===selected)?selected:(rows.find(r=>Number.isFinite(r.growth.estimated_mean_kg))||rows[0])?.batch_id||'*';
 const shown=rows.filter(r=>selector.value==='*'||r.batch_id===selector.value);
 $('#growth-estimate-date').textContent=t('growthEstimateDate')+'：'+model.as_of;
 $('#growth-estimate-results').innerHTML=shown.map(r=>{
  const b=data.batches.find(b=>b.id===r.batch_id),barn=data.barns.find(x=>x.id===r.barn_id),g=r.growth;
  const hasRate=Number.isFinite(g.adg_kg),hasEstimate=Number.isFinite(g.estimated_mean_kg);
  const missing=g.reasons.includes('no_weighing')?'growthEstimateMissing':g.reasons.includes('entry_mean_required')?'growthEstimateNeedEntry':g.reasons.includes('different_dates_required')?'growthEstimateNeedDate':null;
  return `<article class="growth-item" data-estimate-batch="${esc(r.batch_id)}"><div class="growth-heading"><strong>${esc(barn?.name||t('unassigned'))}</strong><span>${esc(b?.name||'')}</span></div><div class="growth-estimate-hero"><span>${t('growthEstimateToday')}</span><strong class="growth-estimate-kg">${hasEstimate?fmtWeight(g.estimated_mean_kg):'—'}</strong><small>${t('growthEstimateUnit')}</small></div>${g.last?`<p class="growth-estimate-last">${t('growthEstimateLatest')}：${esc(g.last.date)} · <b>${fmtWeight(g.last.mean)} kg</b></p>`:''}${hasRate?`<p class="growth-estimate-method">${t(g.method==='two_weighings'?'growthEstimateTwo':'growthEstimateOne')}</p><p class="growth-period">${esc(g.first.date)} → ${esc(g.last.date)} · ${g.interval_days} ${t('days')}</p><p class="growth-means">${t(g.method==='entry_and_weighing'?'growthEstimateEntry':'growthEstimateWeighed')} <b>${fmtWeight(g.first.mean)}</b> → <b>${fmtWeight(g.last.mean)}</b> kg</p><div class="growth-values"><div><span>${t('growthEstimateRate')}</span><strong class="growth-estimate-adg">${fmtWeight(g.adg_kg)}</strong><small>${t('growthEstimateRateUnit')}</small></div><div><span>${t('growthEstimateGain')}</span><strong class="growth-estimate-gain">${fmtWeight(g.gain_kg)}</strong><small>${t('growthEstimateUnit')}</small></div></div><p class="hint">${t('growthEstimateElapsed')} ${g.days_since_last} ${t('days')}</p>`:''}${missing?`<p class="growth-missing">${t(missing)}</p>`:''}${g.reasons.includes('weight_decreased')?`<p class="note">${t('growthEstimateDecreased')}</p>`:''}${g.composition_changed?`<p class="hint">${t('growthEstimateMovement')}</p>`:''}${g.days_since_last>28?`<p class="hint">${t('growthEstimateStale')}</p>`:''}${orderFcrMarkup(r.order_estimate)}</article>`;
 }).join('')||`<p class="empty">${t('noActive')}</p>`;
}
async function load(){
 if(!me||!data||current!=='weights')return;
 const ticket=++serial,user=me.id;
 try{
  const next=await api('/api/growth-estimates');
  if(ticket!==serial||me?.id!==user||current!=='weights')return;
  model=next;owner=user;$('#growth-estimate-error').textContent='';render();
 }catch(e){if(ticket===serial&&me?.id===user&&current==='weights')$('#growth-estimate-error').textContent=t('growthEstimateFailed');}
}
build=()=>{
 base.build();$('#page-weights').insertAdjacentHTML('afterbegin',`<section class="card growth-overview" id="growth-estimates" aria-labelledby="growth-estimate-title"><h2 id="growth-estimate-title" data-i="growthEstimateTitle">${t('growthEstimateTitle')}</h2><p class="hint" data-i="growthEstimateIntro">${t('growthEstimateIntro')}</p><label><span data-i="growthEstimateSelect">${t('growthEstimateSelect')}</span><select id="growth-estimate-batch"></select></label><p id="growth-estimate-error" class="form-error" role="status"></p><p id="growth-estimate-date" class="growth-period"></p><div id="growth-estimate-results"><p class="hint" data-i="growthEstimateLoading">${t('growthEstimateLoading')}</p></div><details data-key="growth-estimate-method"><summary data-i="source">${t('source')}</summary><p data-i="growthEstimateFormula">${t('growthEstimateFormula')}</p><p data-i="growthEstimateSample">${t('growthEstimateSample')}</p></details><p class="hint" data-i="growthEstimateSample">${t('growthEstimateSample')}</p></section>`);
 $('#growth-estimate-batch').onchange=render;
};
renderCurrent=async()=>{const task=base.renderCurrent();if(current==='weights')await load();return task;};
translate=()=>{base.translate();render();};
refresh=async(...args)=>{await base.refresh(...args);if(current==='weights'&&me&&model?.as_of!==farmDate())await load();};
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&me&&current==='weights'&&model?.as_of!==farmDate())load();});
document.addEventListener('pigledger:logout',()=>{serial++;owner=null;model=null;$('#growth-estimate-results')?.replaceChildren();if($('#growth-estimate-batch'))$('#growth-estimate-batch').innerHTML='';if($('#growth-estimate-date'))$('#growth-estimate-date').textContent='';if($('#growth-estimate-error'))$('#growth-estimate-error').textContent='';});
})();
