'use strict';
/* A report contains one saved job, never a draft or a filtered subset of pens. */
(() => {
Object.assign(words,{
 exportWeighing:['匯出／列印秤重表','Xuất / in phiếu cân'],reportTitle:['嘉得肉豬秤重紀錄','Phiếu cân heo thịt Gia Đắc'],reportPreview:['秤重表預覽','Xem trước phiếu cân'],reportPrint:['列印／另存 PDF','In / lưu PDF'],reportCSV:['下載 Excel 表格（CSV）','Tải bảng Excel (CSV)'],reportClose:['關閉','Đóng'],reportSaved:['本次秤重已儲存','Đã lưu phiếu cân này'],reportLatest:['匯出本次秤重表','Xuất phiếu vừa lưu'],reportOverall:['本次總平均','Trọng lượng TB cả phiếu'],reportPen:['欄位','Ô chuồng'],reportPenMean:['欄平均（公斤）','TB ô (kg)'],reportCount:['頭數','Số con'],reportPig:['豬隻','Heo'],reportEntryCount:['進場頭數','Số con nhập'],reportEntryMean:['入場均重','TB lúc nhập'],reportEntryDate:['進場日期','Ngày nhập'],reportMeasured:['入場量測日期','Ngày cân lúc nhập'],reportEntryBasis:['進場資料依目前批次設定；不代表本次抽樣頭數。','Dữ liệu nhập theo cài đặt lứa hiện tại, không phải số con lấy mẫu.'],reportFormula:['總平均＝全部有效樣本總重量 ÷ 全部有效樣本頭數。空白不當作 0。','TB cả phiếu = tổng kg mẫu hợp lệ ÷ tổng số mẫu hợp lệ. Không tính ô trống là 0.'],reportQuick:['頭數＋總重量登記；未逐隻秤重','Ghi số con + tổng kg; không có cân từng con'],reportUnavailable:['這次秤重已作廢或沒有可匯出的有效紀錄。','Phiếu đã bị vô hiệu hoặc không còn bản ghi hợp lệ để xuất.'],reportUnit:['公斤／隻','kg/con'],reportSample:['抽樣估計；僅代表本次有效樣本。','Ước tính từ mẫu; chỉ đại diện mẫu hợp lệ của phiếu này.']
});
const base={build,clickAction,translate,selections,enter};
let latest=null,active=null,originalTitle=null;
const keyOf=r=>r.session_id||'single:'+r.id;
function job(key){
 const rows=(data?.weights||[]).filter(r=>keyOf(r)===key&&r.count>0&&r.total_kg>0);
 if(!rows.length)return null;
 const first=rows[0],batch=data.batches.find(b=>b.id===first.batch_id);
 if(!batch||rows.some(r=>r.date!==first.date||r.batch_id!==first.batch_id))return null;
 const barn=data.barns.find(b=>b.id===batch.barn_id),count=rows.reduce((n,r)=>n+r.count,0),kg=rows.reduce((n,r)=>n+r.total_kg,0);
 return {key,rows,first,batch,barn,count,kg,mean:kg/count};
}
function basics(j){
 return [['date',j.first.date],['barn',j.barn?.name||t('unassigned')],['batch',j.batch.name],['sessionNo',j.first.session_number??'—'],['sessionAge',displayAge(j.first.age_days)],['reportEntryDate',j.batch.entry_date],['reportEntryCount',j.batch.entry_count==null?'—':fmt(j.batch.entry_count,0)+' '+t('heads')],['reportEntryMean',j.batch.entry_mean_kg==null?'—':fmt(j.batch.entry_mean_kg)+' kg'],['reportMeasured',j.batch.entry_mean_date||'—']];
}
function markup(j){
 const cells=basics(j).map(([k,v])=>`<div><dt>${esc(t(k))}</dt><dd>${esc(v)}</dd></div>`).join('');
 const rows=j.rows.map(r=>`<tr><th scope="row"><strong>${esc(r.pen||'—')}</strong>${r.section?`<small>${esc(t(r.section))}</small>`:''}</th><td class="report-weight-cell">${r.individual_kg?.length?`<div class="report-weights">${r.individual_kg.map((w,i)=>`<span><small>${i+1}</small><b>${fmt(w)}</b></span>`).join('')}</div>`:`<span class="report-quick">${t('reportQuick')}<br>${t('totalWeight')} ${fmt(r.total_kg)} kg</span>`}</td><td>${fmt(r.count,0)}</td><td class="report-pen-mean">${fmt(r.total_kg/r.count)}</td></tr>`).join('');
 return `<article class="weighing-report"><header class="report-heading"><h1>${t('reportTitle')}</h1><p>${esc(j.first.date)} · ${esc(j.barn?.name||'—')} · ${esc(j.batch.name)}</p></header><dl class="report-basics">${cells}</dl><div class="report-table-wrap"><table class="report-table"><colgroup><col class="report-col-pen"><col><col class="report-col-count"><col class="report-col-mean"></colgroup><thead><tr><th scope="col">${t('reportPen')}</th><th scope="col">${t('eachKg')}</th><th scope="col">${t('reportCount')}</th><th scope="col">${t('reportPenMean')}</th></tr></thead><tbody>${rows}</tbody></table></div><section class="report-result"><div><span>${t('reportOverall')}</span><strong>${fmt(j.mean)} <small>${t('reportUnit')}</small></strong></div><p>${t('sampleCount')} <b>${fmt(j.count,0)}</b> ${t('heads')}<br>${t('totalWeight')} <b>${fmt(j.kg)}</b> kg</p></section><footer class="report-footnotes"><p>${t('reportFormula')}</p><p>${t('reportSample')}</p><p>${t('reportEntryBasis')}</p></footer></article>`;
}
function renderLatest(){
 const box=$('#weighing-saved-export');if(!box)return;
 const j=latest&&me&&latest.user===me.id&&job(latest.key);box.hidden=!j;
 if(j)box.innerHTML=`<div><strong>${t('reportSaved')}</strong><span>${esc(j.first.date)} · ${esc(j.barn?.name||'—')} · ${esc(j.batch.name)} · ${fmt(j.mean)} kg</span></div><button type="button" data-open-weighing-report="${esc(j.key)}">${t('reportLatest')}</button>`;
}
function renderPreview(){
 const j=active&&job(active);if(!j){toast(t('reportUnavailable'));return null;}
 $('#weighing-report-title').textContent=t('reportPreview');$('#weighing-report-body').innerHTML=markup(j);
 $('#print-weighing-report').textContent=t('reportPrint');$('#csv-weighing-report').textContent=t('reportCSV');$('#close-weighing-report').textContent=t('reportClose');return j;
}
function openReport(key){
 active=key;if(!renderPreview())return;
 const dialog=$('#weighing-report-dialog');if(!dialog.open)dialog.showModal();dialog.scrollTop=0;
}
function filename(j){return `${t('reportTitle')}_${j.first.date}_${j.barn?.name||'—'}_${j.batch.name}_${j.first.session_number??j.first.id.slice(0,8)}`.replace(/[\\/:*?"<>|\r\n]/g,'-');}
function printReport(){
 const j=renderPreview();if(!j)return;
 $('#weighing-print-root').innerHTML=markup(j);originalTitle=document.title;document.title=filename(j);window.print();
}
// A quoted CSV cell can still execute a spreadsheet formula; guard text inputs.
function csvCell(value){let s=String(value??'');if(/^[\s\uFEFF]*[=+\-@]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';}
function downloadCSV(){
 const j=renderPreview();if(!j)return;
 const max=Math.max(6,...j.rows.map(r=>r.individual_kg?.length||0)),lines=[[t('reportTitle')],...basics(j).map(([k,v])=>[t(k),v]),[],[t('section'),t('reportPen'),...Array.from({length:max},(_,i)=>`${t('reportPig')} ${i+1} (kg)`),t('sampleCount'),t('totalWeight')+' (kg)',t('reportPenMean')]];
 for(const r of j.rows)lines.push([r.section?t(r.section):'',r.pen||'',...Array.from({length:max},(_,i)=>r.individual_kg?.[i]??''),r.count,r.total_kg,r.total_kg/r.count]);
 lines.push([], [t('reportOverall'),j.mean,t('reportUnit')],[t('sampleCount'),j.count,t('heads')],[t('totalWeight'),j.kg,'kg'],[t('reportFormula')],[t('reportSample')],[t('reportEntryBasis')]);
 const blob=new Blob(['\ufeff'+lines.map(row=>row.map(csvCell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=filename(j)+'.csv';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);
}
build=()=>{
 base.build();$('#weighing-form').insertAdjacentHTML('afterend','<aside id="weighing-saved-export" class="weighing-saved-export" aria-live="polite" hidden></aside>');
 document.body.insertAdjacentHTML('beforeend','<dialog id="weighing-report-dialog" aria-labelledby="weighing-report-title"><div class="report-toolbar"><h2 id="weighing-report-title"></h2><div class="report-actions"><button type="button" id="print-weighing-report" class="primary"></button><button type="button" id="csv-weighing-report"></button><button type="button" id="close-weighing-report"></button></div></div><div id="weighing-report-body"></div></dialog><div id="weighing-print-root"></div>');
 $('#print-weighing-report').onclick=printReport;$('#csv-weighing-report').onclick=downloadCSV;$('#close-weighing-report').onclick=()=>$('#weighing-report-dialog').close();
 $('#weighing-report-dialog').addEventListener('close',()=>{active=null;restoreTitle();$('#weighing-print-root').replaceChildren();});
};
function restoreTitle(){if(originalTitle!==null){document.title=originalTitle;originalTitle=null;}}
window.addEventListener('beforeprint',()=>{const j=me&&active&&job(active);if(j)$('#weighing-print-root').innerHTML=markup(j);});
window.addEventListener('afterprint',()=>{restoreTitle();$('#weighing-print-root')?.replaceChildren();});
document.addEventListener('pigledger:logout',()=>{latest=null;active=null;if($('#weighing-report-dialog')?.open)$('#weighing-report-dialog').close();$('#weighing-report-body')?.replaceChildren();$('#weighing-print-root')?.replaceChildren();renderLatest();});
document.addEventListener('pigledger:weighing-saved',e=>{
 const r=data?.weights.find(r=>e.detail.session_id?r.session_id===e.detail.session_id:r.id===e.detail.id);if(!r)return;
 latest={key:keyOf(r),user:me.id};renderLatest();
});
clickAction=e=>{
 const b=e.target.closest('[data-print-weighing],[data-open-weighing-report]');if(b){openReport(b.dataset.printWeighing||b.dataset.openWeighingReport);return;}return base.clickAction(e);
};
translate=()=>{base.translate();renderLatest();if($('#weighing-report-dialog')?.open)renderPreview();};
selections=(force=false)=>{base.selections(force);renderLatest();};
enter=async user=>{if(latest?.user!==user.id){latest=null;$('#weighing-saved-export')?.replaceChildren();if($('#weighing-saved-export'))$('#weighing-saved-export').hidden=true;}if($('#weighing-report-dialog')?.open)$('#weighing-report-dialog').close();$('#weighing-print-root')?.replaceChildren();return base.enter(user);};
})();
