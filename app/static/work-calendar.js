'use strict';
/* Shared tasks use the normal audited, revision-checked pending write queue. */
(() => {
Object.assign(words,{
 calDaily:['每日固定工作','Việc cố định mỗi ngày'],calendar:['工作行事曆','Lịch công việc'],calendarSub:['每週固定與臨時工作；星期一至星期日，一週一張A4。','Việc hằng tuần và phát sinh; từ thứ Hai đến Chủ nhật, xuất A4.'],
 calImage:['匯出圖片','Xuất ảnh'],calImagePreparing:['正在準備圖片…','Đang chuẩn bị ảnh…'],calImageReady:['可點「匯出圖片」，在手機分享選單選擇「儲存影像／儲存圖片」。','Nhấn Xuất ảnh, rồi chọn lưu ảnh trong menu chia sẻ của điện thoại.'],calImageFallback:['也可長按下方圖片儲存到相簿，或按下載圖片。','Có thể nhấn giữ ảnh bên dưới để lưu vào thư viện, hoặc tải ảnh.'],calImageCancelled:['已取消分享；仍可長按下方圖片儲存。','Đã hủy chia sẻ; vẫn có thể nhấn giữ ảnh bên dưới để lưu.'],calImageDownload:['下載圖片','Tải ảnh'],calImageOpen:['開啟完整圖片','Mở ảnh đầy đủ'],
 calWeekly:['每週固定工作','Việc hằng tuần'],calOnce:['臨時工作','Việc phát sinh'],calTitle:['工作內容','Nội dung công việc'],calMode:['工作類型','Loại công việc'],calDay:['星期','Thứ'],calStart:['開始生效日','Ngày bắt đầu'],calEnd:['結束日（選填）','Ngày kết thúc (tùy chọn)'],calTime:['時間（選填）','Giờ (tùy chọn)'],calNote:['棟舍／備註（選填）','Chuồng / ghi chú (tùy chọn)'],calActive:['啟用這項工作','Bật công việc này'],calAdd:['登記工作','Ghi công việc'],calWeek:['選擇這週的任一天','Chọn ngày bất kỳ trong tuần'],calPrev:['上一週','Tuần trước'],calNext:['下一週','Tuần sau'],calThis:['本週','Tuần này'],calPDF:['匯出A4 PDF','Xuất PDF A4'],calPreview:['A4預覽','Xem trước A4'],calManage:['管理工作','Quản lý công việc'],calEmpty:['這一天還沒有安排工作。','Chưa có việc cho ngày này.'],calNoTasks:['目前沒有登記工作。','Chưa có công việc.'],calInactive:['已停用','Đã tắt'],calEditHint:['更正固定工作會套用至其生效期間；臨時工作只影響指定日期。取消工作可取消勾選「啟用這項工作」。','Sửa việc hằng tuần áp dụng trong kỳ hiệu lực; việc phát sinh chỉ ngày đã chọn. Bỏ chọn để tắt.'],calLoading:['正在載入這週工作…','Đang tải công việc…'],calMorePages:['工作較多，已完整列在同一週的續頁。','Nhiều công việc; đã ghi đầy đủ trong các trang tiếp cùng tuần.'],calFailed:['無法產生行事曆，請重新載入後再試。','Không tạo được lịch, hãy tải lại và thử.'],calPermission:['可登記新工作，並更正自己登記的工作。','Có thể thêm và sửa công việc do mình ghi.'],calFull:['整天／未指定時間','Cả ngày / chưa đặt giờ']
});
Object.assign(errorWords,{invalid_calendar_task:['請填寫工作內容、星期及有效時間，並檢查日期。','Nhập nội dung, thứ, giờ và ngày hợp lệ.']});
const weekdays=()=>lang==='vi'?['Thứ Hai','Thứ Ba','Thứ Tư','Thứ Năm','Thứ Sáu','Thứ Bảy','Chủ nhật']:['星期一','星期二','星期三','星期四','星期五','星期六','星期日'];
const base={build,collect,finishForm,renderCurrent,enter,restorePending,translate};
let model=null,serial=0,owner=null,pdf=null,pdfKey='',urls=[],pdfBuild=null,exportBusy=false;
const form=()=>$('#calendar-form');
const editable=r=>me&&me.role!=='viewer'&&(me.role==='admin'||r.created_by===me.id);
function exportControls(){if($('#calendar-pdf'))$('#calendar-pdf').disabled=exportBusy||!model;if($('#calendar-image'))$('#calendar-image').disabled=exportBusy||!model||!!pdfBuild;}
function clearAssets(){urls.forEach(u=>URL.revokeObjectURL(u));urls=[];pdf=null;pdfKey='';$('#calendar-preview')?.replaceChildren();$('#calendar-image-pages')?.replaceChildren();if($('#calendar-image-gallery'))$('#calendar-image-gallery').hidden=true;}
function release(){pdfBuild=null;clearAssets();if($('#calendar-image-status'))$('#calendar-image-status').textContent='';exportControls();}
function reset(){const f=form();f.reset();f.elements.date.value=today();f.elements.start_date.value=today();delete f.dataset.editId;delete f.dataset.revision;delete f.dataset.dirty;f.querySelector('[data-action=cancelEdit]').hidden=true;f.querySelector('.edit-label').hidden=true;f.querySelector('.form-error').textContent='';conditionalTask();}
function conditionalTask(){const weekly=val(form(),'mode')==='weekly';$$('#calendar-form .calendar-weekly').forEach(e=>e.hidden=!weekly);$('#calendar-form .calendar-once').hidden=weekly;for(const k of ['weekday','start_date'])form().elements[k].required=weekly;form().elements.date.required=!weekly;}
function error(message){$('#calendar-error').textContent=message;}
function taskHTML(r,actions=true){return `<article class="calendar-task"><div><strong>${esc(r.time?r.time+' · ':'')}${esc(r.title)}</strong>${r.note?`<p>${esc(r.note)}</p>`:''}</div>${actions&&editable(r)?`<button type="button" data-calendar-edit="${esc(r.id)}">${txt('edit')}</button>`:''}</article>`;}
function manage(){const rows=data?.work_tasks||[];$('#calendar-tasks').innerHTML=rows.length?rows.slice().sort((a,b)=>Number(b.active)-Number(a.active)||a.title.localeCompare(b.title)).map(r=>`<div class="calendar-managed"><p class="hint">${esc(r.mode==='weekly'?t('calWeekly')+' · '+weekdays()[r.weekday]+' · '+r.start_date+(r.end_date?' → '+r.end_date:''):t('calOnce')+' · '+r.date)}${r.active?'':' · '+esc(t('calInactive'))}</p>${taskHTML(r)}</div>`).join(''):`<p class="muted">${t('calNoTasks')}</p>`;}
async function loadWeek(){
 const mine=++serial,user=me?.id,date=$('#calendar-week').value||today();release();model=null;error('');$('#calendar-range').textContent=t('calLoading');exportControls();$('#calendar-days').replaceChildren();manage();
 try{const result=await api('/api/work-calendar?week='+encodeURIComponent(date));if(mine!==serial||me?.id!==user||current!=='calendar')return;model=result;$('#calendar-week').value=result.from;$('#calendar-range').textContent=result.from+' → '+result.to;$('#calendar-days').innerHTML=result.days.map(d=>`<section class="calendar-day"><h3>${esc(weekdays()[d.weekday])}<small>${d.date}</small></h3><div><h4>${t('calWeekly')}</h4>${d.tasks.filter(r=>r.mode==='weekly').map(r=>taskHTML(r)).join('')||'<p class="calendar-blank">—</p>'}<h4>${t('calOnce')}</h4>${d.tasks.filter(r=>r.mode==='once').map(r=>taskHTML(r)).join('')||'<p class="calendar-blank">—</p>'}</div></section>`).join('');exportControls();$('#calendar-image-status').textContent=t('calImagePreparing');ensurePDF().catch(()=>{if(mine===serial&&me?.id===user)error(t('calFailed'));});
 }catch(e){if(mine===serial){$('#calendar-range').textContent='';error(messageError(e));}}
}
function editTask(id){if(pending){toast(t('pending'));return;}if(form().dataset.dirty||form().dataset.editId){toast(t('saveBeforeSwitch'));return;}const r=data.work_tasks.find(x=>x.id===id);if(!r||!editable(r))return;reset();const f=form();for(const k of ['title','mode','weekday','date','start_date','end_date','time','note'])if(k in r)f.elements[k].value=r[k];f.elements.active.checked=r.active;f.dataset.editId=r.id;f.dataset.revision=r.revision;f.querySelector('[data-action=cancelEdit]').hidden=false;f.querySelector('.edit-label').hidden=false;conditionalTask();f.scrollIntoView({block:'center',behavior:'smooth'});}
build=()=>{base.build();$('#page-settings').insertAdjacentHTML('beforebegin',`<section class="page" id="page-calendar" hidden>
 <div class="card"><label>${txt('calWeek')}<input type="date" id="calendar-week" value="${today()}"></label><div class="actions calendar-week-tools"><button type="button" id="calendar-prev">${txt('calPrev')}</button><button type="button" id="calendar-this">${txt('calThis')}</button><button type="button" id="calendar-next">${txt('calNext')}</button></div><h2 id="calendar-range" aria-live="polite"></h2><div class="actions"><button type="button" class="primary" id="calendar-image" disabled>${txt('calImage')}</button><button type="button" id="calendar-pdf" disabled>${txt('calPDF')}</button></div><p id="calendar-image-status" class="hint" role="status"></p><section id="calendar-image-gallery" class="calendar-image-gallery" hidden><p class="hint">${txt('calImageFallback')}</p><div id="calendar-image-pages"></div></section><p id="calendar-error" class="form-error" role="alert"></p><details id="calendar-preview-box"><summary>${txt('calPreview')}</summary><div id="calendar-preview"></div></details></div>
 <div id="calendar-days"></div>
 <div class="card"><h2>${txt('calAdd')}</h2><p class="hint">${txt('calEditHint')}</p><form id="calendar-form" data-kind="work_tasks"><div class="grid">${select('calMode','mode',option('weekly','calWeekly')+option('once','calOnce'))}<label class="full">${txt('calTitle')}<input name="title" maxlength="120" required></label><label class="calendar-weekly">${txt('calDay')}<select name="weekday">${weekdays().map((s,i)=>`<option value="${i}">${s}</option>`).join('')}</select></label><label class="calendar-once" hidden>${txt('date')}<input type="date" name="date"></label><label class="calendar-weekly">${txt('calStart')}<input type="date" name="start_date"></label><label class="calendar-weekly">${txt('calEnd')}<input type="date" name="end_date"></label>${input('calTime','time','time')}<label class="full">${txt('calNote')}<textarea name="note" maxlength="1000"></textarea></label><label class="check full"><input type="checkbox" name="active" checked>${txt('calActive')}</label></div>${formActions()}</form></div>
 <details class="card"><summary>${txt('calManage')}</summary><div id="calendar-tasks"></div></details></section>`);
 const f=form();f.addEventListener('submit',e=>saveForm(e));for(const type of ['input','change'])f.addEventListener(type,()=>f.dataset.dirty='1');f.elements.mode.addEventListener('change',conditionalTask);reset();
 $('#calendar-week').onchange=loadWeek;$('#calendar-this').onclick=()=>{$('#calendar-week').value=today();loadWeek();};
 for(const [id,days] of [['prev',-7],['next',7]])$('#calendar-'+id).onclick=()=>{const d=new Date(($('#calendar-week').value||today())+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+days);$('#calendar-week').value=d.toISOString().slice(0,10);loadWeek();};
 $('#page-calendar').addEventListener('click',e=>{const b=e.target.closest('[data-calendar-edit]');if(b)editTask(b.dataset.calendarEdit);});$('#calendar-pdf').onclick=exportPDF;$('#calendar-image').onclick=exportImages;$('#calendar-preview-box').ontoggle=()=>{if($('#calendar-preview-box').open&&model)ensurePDF().catch(()=>error(t('calFailed')));};
 document.addEventListener('pigledger:logout',()=>{owner=null;++serial;model=null;release();reset();$('#calendar-days').replaceChildren();$('#calendar-tasks').replaceChildren();});
};
collect=f=>{if(f.id!=='calendar-form')return base.collect(f);const d=Object.fromEntries(new FormData(f));d.active=f.elements.active.checked;if(d.mode==='weekly'){d.weekday=Number(d.weekday);delete d.date;}else for(const k of ['weekday','start_date','end_date'])delete d[k];if(f.dataset.editId)d.revision=Number(f.dataset.revision);return d;};
finishForm=f=>{if(f.id!=='calendar-form')return base.finishForm(f);reset();};
restorePending=()=>{base.restorePending();if(pending?.formId==='calendar-form')conditionalTask();};
enter=async user=>{const reopen=location.hash==='#calendar';if(owner!==user.id){owner=user.id;reset();release();++serial;model=null;$('#calendar-week').value=today();}const result=await base.enter(user);if(reopen&&!user.must_change){history.replaceState(null,'',location.pathname+'#calendar');setPage('calendar');}return result;};
renderCurrent=async()=>{await base.renderCurrent();if(current==='calendar'&&data)await loadWeek();};
translate=()=>{base.translate();const old=form()?.elements.weekday.value;if(form()){form().elements.weekday.innerHTML=weekdays().map((s,i)=>`<option value="${i}">${s}</option>`).join('');form().elements.weekday.value=old;}release();};
async function ensurePDF(){
 if(!model)return null;const source=model,user=me?.id,language=lang,key=JSON.stringify([source,language]);if(pdf&&pdfKey===key)return pdf;
 if(pdfBuild?.key===key&&pdfBuild.user===user)return pdfBuild.promise;
 const job={key,user,promise:null};pdfBuild=job;exportControls();
 job.promise=(async()=>{try{
  const result=await window.workCalendarPDF({title:(language==='vi'?'Gia Đắc · ':'嘉得 · ')+t('calendar'),range:source.from+' → '+source.to,dailyTitle:t('calDaily'),headers:[t('calDay'),t('calWeekly'),t('calOnce')],weekdays:weekdays(),days:source.days,more:t('calMorePages')});
  if(model!==source||me?.id!==user||lang!==language||pdfBuild!==job)return null;
  clearAssets();pdf=result;pdfKey=key;urls=(result.previewPages||[]).map(b=>URL.createObjectURL(b));$('#calendar-preview').innerHTML=urls.map((url,i)=>`<img src="${url}" alt="${esc(t('calPreview'))} ${i+1}" width="595" height="842">`).join('');
  $('#calendar-image-status').textContent=t('calImageReady');if(urls.length>1)error(t('calMorePages'));return result;
 }finally{if(pdfBuild===job)pdfBuild=null;exportControls();}})();return job.promise;
}
function imageName(source,index,count){return '工作行事曆_'+source.from+'_'+source.to+(count>1?'_'+(index+1):'')+'.jpg';}
function showImages(source){
 const count=urls.length;$('#calendar-image-pages').innerHTML=urls.map((url,i)=>`<figure><img src="${url}" alt="${esc(t('calPreview'))} ${i+1}" width="595" height="842"><figcaption>${count>1?`${i+1} / ${count}`:''}<div class="actions"><a href="${url}" download="${esc(imageName(source,i,count))}" data-calendar-image-download>${txt('calImageDownload')}</a><a href="${url}" target="_blank" rel="noopener">${txt('calImageOpen')}</a></div></figcaption></figure>`).join('');$('#calendar-image-gallery').hidden=false;
}
function saveFile(url,name){const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();}
async function exportImages(){
 if(!model||!me||exportBusy)return;const source=model,user=me.id;
 // Prepare before the next click: native file sharing needs the tap's activation.
 if(!pdf?.previewPages?.length||pdfKey!==JSON.stringify([source,lang])){try{await ensurePDF();}catch(e){if(model===source&&me?.id===user)error(t('calFailed'));}return;}
 const files=pdf.previewPages.map((blob,i)=>new File([blob],imageName(source,i,pdf.previewPages.length),{type:'image/jpeg'}));
 showImages(source);exportBusy=true;exportControls();let canShare=false;
 try{canShare=typeof navigator.share==='function'&&typeof navigator.canShare==='function'&&navigator.canShare({files});}catch(e){}
 try{
  if(canShare){
   // No asynchronous work precedes this call, so iPhone/Android keep the tap.
   await navigator.share({files,title:t('calendar')+' '+source.from+' → '+source.to});
   if(model===source&&me?.id===user)$('#calendar-image-status').textContent=t('calImageFallback');
  }else{
   if(files.length===1)saveFile(urls[0],files[0].name);
   if(model===source&&me?.id===user)$('#calendar-image-status').textContent=t('calImageFallback');
  }
 }catch(e){if(model===source&&me?.id===user)$('#calendar-image-status').textContent=t(e.name==='AbortError'?'calImageCancelled':'calImageFallback');}
 finally{exportBusy=false;exportControls();}
}
async function exportPDF(){if(exportBusy||!model)return;const source=model,user=me?.id;exportBusy=true;exportControls();try{const blob=await ensurePDF();if(!blob||source!==model||user!==me?.id)return;const url=URL.createObjectURL(blob);saveFile(url,'工作行事曆_'+source.from+'_'+source.to+'.pdf');setTimeout(()=>URL.revokeObjectURL(url),60000);}catch(e){error(t('calFailed'));}finally{exportBusy=false;exportControls();}}
})();
