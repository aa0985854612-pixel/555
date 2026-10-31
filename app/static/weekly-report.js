'use strict';
/* Entry-anchored weekly sheets use a read-only server report, never client stock deltas. */
(() => {
Object.assign(words,{
 weeklyReport:['肉豬每週紀錄表','Bảng ghi heo thịt hằng tuần'],weeklyOpen:['匯出每週紀錄表','Xuất bảng hằng tuần'],weeklyMake:['產生紀錄表','Tạo bảng'],weeklyChoose:['選擇批次與棟舍','Chọn lứa và chuồng'],weeklyAllBarns:['同批全部棟舍','Tất cả chuồng cùng lứa'],weeklyBasis:['從進場日起每7天一欄；每天登記的資料自動加總。','Mỗi cột 7 ngày kể từ ngày nhập; tự cộng dữ liệu ghi hằng ngày.'],weeklyEntryAge:['進場日齡','Tuổi ngày lúc nhập'],weeklyAgeBasis:['週齡欄從進場當日的「第幾週」起算，每7天遞增；已滿10週起標第11週。','Cột tuổi ghi tuần thứ: đủ 10 tuần là tuần thứ 11, khác số tuần đã đủ.'],weeklyCycle:['週期','Kỳ'],weeklyWeek:['第{n}週','Tuần thứ {n}'],weeklyPeriod:['第{n}期','Kỳ {n}'],weeklyStarts:['起始日','Ngày bắt đầu'],weeklyDates:['統計日期','Ngày thống kê'],weeklyDeaths:['死亡數（隻）','Số chết (con)'],weeklySales:['正常出豬（隻）','Xuất bán (con)'],weeklyCulls:['淘汰數（隻）','Loại thải (con)'],weeklyFeed:['叫料登記量（噸）','Lượng đặt đã ghi (tấn)'],weeklyNotes:['異動摘要','Tóm tắt biến động'],weeklyTotal:['選定期間合計','Tổng kỳ đã chọn'],weeklySurvival:['截至日期累計育成率','Tỷ lệ sống lũy kế đến ngày'],weeklyNone:['—＝資料待補；0＝當週無符合條件的登記；未到日期留空。','— = thiếu dữ liệu; 0 = không có bản ghi phù hợp; ngày tương lai để trống.'],weeklyFeedBasis:['叫料量只統計已指定本批／本棟的登記，不代表到料或實際耗料，也不計入FCR。未指定批次的全場叫料另外列待補，不平均分攤。','Chỉ tính lượng đặt phân bổ rõ cho lứa/chuồng này; không phải nhập hay tiêu thụ, không tính FCR. Đơn chung chưa chỉ định để riêng, không chia đều.'],weeklyPending:['待補資料','Dữ liệu cần bổ sung'],weeklyUnknownDate:['缺日期／來源合計無法分週','Thiếu ngày / tổng nguồn chưa chia tuần'],weeklyUnknownBarn:['棟舍分配待確認','Cần xác nhận phân bổ chuồng'],weeklyUnknownFeed:['全場叫料未指定批次','Đơn chung chưa chỉ định lứa'],weeklyKnown:['已知','Đã biết'],weeklyObserved:['資料統計至','Dữ liệu tính đến'],weeklyCurrent:['累計（非期間合計）','Lũy kế (khác tổng kỳ)'],weeklyLoading:['正在整理已儲存紀錄…','Đang tổng hợp bản ghi đã lưu…'],weeklyFailure:['無法產生報表，請重試。','Không tạo được bảng, hãy thử lại.'],weeklyMore:['另有{n}筆，詳見App明細','Còn {n} mục; xem chi tiết App'],weeklyScope:['匯出範圍','Phạm vi xuất']
});
Object.assign(errorWords,{weekly_choose_batch:['請先選擇一個批次；可以選整批或其中一棟。','Chọn một lứa, có thể toàn lứa hoặc một chuồng.'],weekly_period_too_long:['一次報表最多三年，請縮小日期範圍。','Mỗi bảng tối đa ba năm; thu hẹp khoảng ngày.']});
Object.assign(words,{weeklyPrintDetails:['A4直式紀錄；完整異動與待補資料也可在歷史紀錄查詢。','Bản tóm tắt A4 dọc; xem chi tiết biến động và dữ liệu cần bổ sung trong lịch sử.'],weeklyPendingCount:['待補資料：{n}筆（詳見App／App）','Cần bổ sung: {n} mục (xem App / App)']});
Object.assign(words,{weeklyPrintFeedHint:['飼料例：10/12+2(13)＝10/12、2噸、13棟；叫料不等於實耗，不計FCR。','Ví dụ cám: 10/12+2(13) = ngày 12/10, 2 tấn, chuồng 13; lượng đặt không phải tiêu thụ, không tính FCR.'],weeklyFeedShort:['叫料登記量不代表到料或實際耗料，不計入FCR。','Lượng đặt đã ghi không phải lượng nhập hay tiêu thụ thực tế, không dùng tính FCR.'],weeklyOutgoingOverflow:['出豬備註每週先列一筆；＋數字表示其餘筆數，完整內容詳App。','Ghi chú xuất heo: mỗi tuần hiện mục đầu; dấu + là số mục còn lại, xem đủ trong App.'],weeklyFeedEntries:['飼料逐筆明細','Chi tiết từng lần đặt thức ăn'],weeklyFeedNotation:['飼料寫法：10/12+2(13)＝10月12日、2噸、13棟；同日日期只寫一次，各筆換行，數量依原叫料登記。','Cách ghi: 10/12+2(13) = ngày 12/10, 2 tấn, chuồng 13; cùng ngày chỉ ghi ngày một lần, mỗi lần đặt một dòng, giữ lượng gốc.']});
Object.assign(words,{weeklyEntryFacts:['各棟進場資料','Thông tin nhập từng chuồng'],weeklyDetails:['完整異動、來源與計算說明','Chi tiết biến động, nguồn và cách tính'],weeklyShortLegend:['— 資料待補；0 無符合登記（不代表已回報無死亡）；未到日期留空。','— thiếu dữ liệu; 0 không có bản ghi (không xác nhận không chết); để trống ngày tương lai.'],weeklyPaperPeriod:['每7天一欄，依所選日期統計。','Mỗi cột 7 ngày, theo khoảng ngày đã chọn.']});
Object.assign(words,{weeklyPaperFeed:['叫料（噸）','Cám đặt (t)'],weeklyPaperOutgoing:['出豬備註','Nơi bán']});
Object.assign(words,{weeklyBrowserPrint:['瀏覽器列印','In bằng trình duyệt'],weeklyDownloadPDF:['下載 A4 PDF','Tải PDF A4'],weeklyPDFHint:['建議下載A4 PDF後再列印，避免手機重新分頁；空白只代表沒有可列資料，不代表已回報無死亡。','Nên tải PDF A4 rồi in để tránh điện thoại chia lại trang; ô trống không xác nhận không chết.'],weeklyPDFMaking:['正在產生 PDF…','Đang tạo PDF…'],weeklyPDFLegend:['空白＝未登記或資料待補；叫料不等於實耗。叫料全部列出，資料較多時自動接續下一頁。','Trống = chưa ghi hoặc thiếu dữ liệu; đặt cám không phải tiêu thụ. Hiện đầy đủ các lần đặt cám; tự sang trang khi nhiều dữ liệu.'],weeklyShortLegend:['空白＝未登記或資料待補；不代表已回報無死亡。','Trống = chưa ghi hoặc thiếu dữ liệu; không xác nhận không chết.'],weeklyNone:['空白＝未登記或資料待補；未到日期留空。','Trống = chưa ghi hoặc thiếu dữ liệu; để trống ngày tương lai.']});
Object.assign(words,{weeklyPlanned:['週期預排至32週；所選日期以外只列週次與起始日，數量留白。','Lịch dự kiến đến tuần 32; ngoài khoảng đã chọn chỉ ghi tuần và ngày bắt đầu, để trống số lượng.'],weeklyWeekShort:['{n}週','{n}W']});
Object.assign(words,{weeklyShippingMore:['另有{n}筆出豬備註，完整內容詳App。','Còn {n} ghi chú xuất heo; xem đầy đủ trong App.']});
Object.assign(words,{weeklyPaperSale:['正常出豬','Xuất bán'],weeklyPaperCull:['淘汰數（隻）','Loại (con)'],weeklyPaperDeath:['死亡數（隻）','Chết (con)'],weeklyPaperStart:['起始日','Ngày đầu']});
Object.assign(words,{
 weeklyBatch:['批號','Mã lứa'],
 weeklyBasis:['先選批號，再選棟舍；列出全部已登記資料，包含未來日期。','Chọn mã lứa trước, rồi chọn chuồng; hiện mọi bản ghi đã lưu, kể cả ngày tương lai.'],
 weeklyTotal:['全部登記合計','Tổng mọi bản ghi'],
 weeklyPaperPeriod:['每7天一欄，列出全部登記（含未來日期）。','Mỗi cột 7 ngày; hiện mọi bản ghi, kể cả ngày tương lai.'],
 weeklyPlanned:['空白週欄保留至32週；有登記就會顯示。','Giữ cột trống đến tuần 32; có bản ghi thì hiển thị.'],
 weeklyNone:['空白＝沒有登記或資料待補；已登記的未來資料照常列出。','Trống = chưa ghi hoặc thiếu dữ liệu; bản ghi ngày tương lai vẫn hiển thị.']
});
const base={build,clickAction,translate,enter,refresh};
let report=null,reportUser=null,serial=0,printing=false,title=null,pdfCache=null,pdfTask=null,previewURLs=[];
Object.assign(words,{weeklyContinue:['續','tiếp'],weeklyActualPreview:['A4列印預覽（與下載PDF相同）','Xem trước in A4 (giống PDF tải xuống)'],weeklyScreenDetails:['查看完整畫面明細','Xem chi tiết trên màn hình']});
Object.assign(words,{weeklyLatestFeedType:['料別','Loại cám'],weeklySales:['售出數（隻）','Số xuất bán (con)'],weeklyPaperSale:['售出數','Số xuất bán']});
function clearPDF(){pdfCache=null;pdfTask=null;previewURLs.forEach(u=>URL.revokeObjectURL(u));previewURLs=[];el('weekly-a4-preview')?.replaceChildren();}
async function ensurePDF(){
 if(!report||reportUser!==me?.id)return null;const original=report,user=me.id,language=lang;
 if(pdfCache?.report===original&&pdfCache.lang===language)return pdfCache.blob;
 if(pdfTask?.report===original&&pdfTask.lang===language)return pdfTask.promise;
 const task={report:original,lang:language};task.promise=(async()=>{
  const blob=await window.weeklyPdf(pdfModel());
  if(report!==original||me?.id!==user||lang!==language||!el('weekly-report-dialog').open)return null;
  pdfCache={report:original,lang:language,blob};previewURLs.forEach(u=>URL.revokeObjectURL(u));previewURLs=(blob.previewPages||[]).map(b=>URL.createObjectURL(b));
  const root=el('weekly-a4-preview');root.replaceChildren();const heading=document.createElement('h3');heading.textContent=t('weeklyActualPreview');root.append(heading);previewURLs.forEach((url,i)=>{const im=document.createElement('img');im.src=url;im.alt=t('weeklyActualPreview')+' '+(i+1)+'/'+previewURLs.length;im.width=595;im.height=842;root.append(im);});
  return blob;
 })().finally(()=>{if(pdfTask===task)pdfTask=null;});pdfTask=task;return task.promise;
}
const el=id=>document.getElementById(id),safe=esc;
function label(key,n){return t(key).replace('{n}',n);}
function resetPrint(){if(title!==null){document.title=title;title=null;}printing=false;el('weekly-print-root')?.replaceChildren();el('weekly-print-root')?.classList.remove('weekly-rendered-pages');}
function chosen(){return data?.batches.find(b=>(b._cohort_key||b.name+'|'+b.entry_date)===el('weekly-cohort').value);}
function syncCohorts(preferred=el('weekly-cohort').value){
 const cohorts=(data.cohorts||[]).filter(c=>!c.archive).sort((a,b)=>b.entry_date.localeCompare(a.entry_date)||b.name.localeCompare(a.name));
 el('weekly-cohort').innerHTML=cohorts.map(c=>`<option value="${safe(c.key)}">${safe(c.name)}｜${safe(c.barns.join('、'))}</option>`).join('');
 if(cohorts.some(c=>c.key===preferred))el('weekly-cohort').value=preferred;
}
function syncBarns(preferred=''){
 const key=el('weekly-cohort').value,ids=new Set(data.batches.filter(b=>(b._cohort_key||b.name+'|'+b.entry_date)===key).map(b=>b.barn_id));
 const barns=data.barns.filter(b=>ids.has(b.id)).sort((a,b)=>a.name.localeCompare(b.name,undefined,{numeric:true}));
 el('weekly-barn').innerHTML=`<option value="">${t('weeklyAllBarns')}</option>`+barns.map(b=>`<option value="${safe(b.id)}">${safe(b.name)}</option>`).join('');
 if(ids.has(preferred))el('weekly-barn').value=preferred;
}
function openWeekly(context={}){
 if(!data)return;serial++;clearPDF();report=null;el('weekly-sheet-body').replaceChildren();el('weekly-export-actions').hidden=true;el('weekly-error').textContent='';
 const f=current==='daily'?el('movement-form'):el('stats-filter'),b=data.batches.find(b=>b.id===(context.batch_id||val(f,'batch_id')));
 syncCohorts((context.batch_id?'':val(f,'cohort'))||(b?(b._cohort_key||b.name+'|'+b.entry_date):''));
 syncBarns(context.batch_id?b?.barn_id||'':val(f,'barn_id')||b?.barn_id||'');
 const d=el('weekly-report-dialog');if(!d.open)d.showModal();d.scrollTop=0;
 if(chosen())generate({preventDefault(){}});
}
async function generate(e){
 e.preventDefault();const f=el('weekly-report-form');if(!f.reportValidity())return;const mine=++serial,user=me?.id,button=el('weekly-generate');button.disabled=true;el('weekly-error').textContent=t('weeklyLoading');el('weekly-export-actions').hidden=true;clearPDF();report=null;el('weekly-sheet-body').replaceChildren();
 try{
  const q=new URLSearchParams({cohort:el('weekly-cohort').value,all_records:'1'});if(el('weekly-barn').value)q.set('barn_id',el('weekly-barn').value);
  const result=await api('/api/weekly-report?'+q);if(mine!==serial||me?.id!==user||!el('weekly-report-dialog').open)return;report=result;reportUser=user;render();el('weekly-error').textContent='';el('weekly-export-actions').hidden=false;ensurePDF().then(blob=>{if(blob&&e.type==='submit'&&mine===serial&&me?.id===user)el('weekly-a4-preview').scrollIntoView({block:'start',behavior:'smooth'});}).catch(()=>{});
 }catch(err){if(mine===serial)el('weekly-error').textContent=messageError(err);}finally{if(mine===serial)button.disabled=false;}
}
const metrics=['cull','death','feed_orders','sale'];
const paperMetricKey={sale:'weeklyPaperSale',cull:'weeklyPaperCull',death:'weeklyPaperDeath',feed_orders:'weeklyPaperFeed'};
const metricKey={death:'weeklyDeaths',sale:'weeklySales',cull:'weeklyCulls',feed_orders:'weeklyFeed'};
function amount(n,key){return n==null||n===0?'':key==='feed_orders'?new Intl.NumberFormat(lang==='vi'?'vi-VN':'zh-TW',{maximumFractionDigits:3}).format(n/1000):fmt(n,0);}
// Sort for display only: every original order/allocation stays a separate line.
// A date is printed on the first line of its day; spaces align later + signs.
function feedLines(details=[],shared=[]){
 const rows=[...details.map(row=>({row,pending:false})),...shared.map(row=>({row,pending:true}))].sort((a,b)=>a.row.date.localeCompare(b.row.date));
 let previous='';
 return rows.map(({row,pending})=>{
  const parts=row.date.split('-'),date=`${Number(parts[1])}/${Number(parts[2])}`;
  const barn=row.bin_label||row.barn?.match(/^(?:第)?(\d+)棟$/)?.[1]||row.barn||'';
  const prefix=row.date===previous?' '.repeat(date.length):date;previous=row.date;
  const tons=new Intl.NumberFormat('en-US',{useGrouping:false,maximumFractionDigits:12}).format(row.kg/1000);
  return `${prefix}+${tons}(${barn})${pending?' · '+t('sharedFeedPending'):''}`;
 });
}
function feedCell(w){
 if(blankWeek(w))return '';
 const lines=feedLines(w.feed_details,w.feed_shared_details).map(line=>`<span class="weekly-feed-entry">${safe(line)}</span>`).join('');
 return lines||amount(w.values.feed_orders,'feed_orders');
}
function outgoingNotation(e){
 if(e.grouped){const d=e.date.split('-');return `${Number(d[1])}/${Number(d[2])} ${e.outgoing_destination}${e.type==='cull'?' '+t('cull'):''}${e.quantity}${e.outgoing_trip?'（'+e.outgoing_trip+'）':''}`;}
 const d=e.date.split('-'),barn=e.barn?.match(/^(?:第)?(\d+)棟$/)?.[1]||e.barn||t('unassigned');
 return `${Number(d[1])}/${Number(d[2])} ${e.outgoing_destination||''}${e.type==='cull'?' '+t('cull'):''} ${e.quantity}（${barn}）${e.outgoing_trip?' · '+e.outgoing_trip:''}`;
}
// Input is already scoped to one report/cohort by the server. Unknown places
// stay separate; explicit trips, days and movement types never cross groups.
function outgoingGroups(events){
 const grouped=new Map();
 for(const [index,e] of events.entries()){
  if(!['sale','cull'].includes(e.type))continue;
  const place=e.outgoing_destination||'',trip=e.outgoing_trip||'';
  const key=JSON.stringify([e.date,e.type,place,trip,place?'':e.id||index]);
  if(!grouped.has(key))grouped.set(key,{...e,outgoing_trip:trip,quantity:0,grouped:!!place,notes:[]});
  const g=grouped.get(key);g.quantity+=e.quantity;if(e.note&&!g.notes.includes(e.note))g.notes.push(e.note);
 }
 return Array.from(grouped.values()).map(g=>({...g,note:g.notes.join('；')})).sort((a,b)=>a.date.localeCompare(b.date)||String(a.outgoing_destination||'').localeCompare(String(b.outgoing_destination||''),'zh-Hant')||a.outgoing_trip.localeCompare(b.outgoing_trip,undefined,{numeric:true})||a.type.localeCompare(b.type));
}
Object.assign(words,{weeklyShippingBasis:['出豬依同批、同日、同目的地及車次合計；分棟明細保留於App。未填車次者合計為一筆。','Gộp xuất cùng lứa, ngày, nơi đến và chuyến; App giữ chi tiết từng chuồng. Chưa ghi chuyến thì gộp thành một mục.']});

function basics(){const r=report;return [['batch',r.name],['weeklyOutgoingNotes',(r.outgoing_destinations||[]).join('、')||'—'],['barn',r.barns.join('、')],['reportEntryDate',r.entry_date],['reportEntryCount',fmt(r.cumulative.entry,0)+' '+t('heads')],['reportEntryMean',r.entry_mean_kg==null?'—':fmt(r.entry_mean_kg)+' kg'],['weeklyEntryAge',r.entry_age_days==null?t(r.age_mixed?'mixedAges':'insufficient'):fmt(r.entry_age_days,0)+' '+t('days')],['weeklyDates',r.from+' → '+r.to],['weeklyObserved',r.observed_to],['feedDefaultVendor',(r.feed_setup?.configured_vendors||[]).join('、')||'—'],['feedRecordedTypes',(r.feed_setup?.recorded_types||[]).join('、')||'—'],...((r.feed_setup?.recorded_vendors||[]).length?[['feedRecordedVendor',r.feed_setup.recorded_vendors.join('、')]]:[])];}
Object.assign(words,{weeklyReferenceCycle:['{barn}週次','Tuần {barn}'],weeklyReferenceHint:['本表週次依{barn}；其他棟依各自進場資料計齡。','Cột tuần theo {barn}; chuồng khác tính tuổi theo dữ liệu nhập riêng.']});
function cycleTitle(){return report.week_reference?t('weeklyReferenceCycle').replace('{barn}',report.week_reference.barn):t('weeklyCycle');}
function referenceHint(){return report.week_reference?t('weeklyReferenceHint').replace('{barn}',report.week_reference.barn):'';}
function shownWeek(w){return w?.age_week??w?.reference_age_week??(w&&report.week_reference?report.week_reference.start_week+w.index-1:null);}
function paperBasics(){const r=report,ws=sheetWeeks(),first=shownWeek(ws[0]),last=shownWeek(ws.at(-1));return [['batch',r.name],['barn',r.barns.join('、')],['reportEntryCount',fmt(r.cumulative.entry,0)+' '+t('heads')],['feedDefaultVendor',(r.feed_setup?.configured_vendors||[]).join('、')||''],['weeklyLatestFeedType',r.feed_setup?.latest_type||''],['weeklyCycle',first==null||last==null?'':(r.week_reference?r.week_reference.barn+' ':'')+label('weeklyWeekShort',first)+'–'+label('weeklyWeekShort',last)]];}
function entryFacts(){return `<table class="weekly-entry-facts" aria-label="${t('weeklyEntryFacts')}"><thead><tr>${['barn','reportEntryDate','reportEntryCount','weeklyEntryAge','reportEntryMean'].map(k=>`<th>${t(k)}</th>`).join('')}</tr></thead><tbody>${(report.entry_details||[]).map(e=>`<tr><th>${safe(e.barn)}</th><td>${safe(e.date)}</td><td>${e.count==null?'':fmt(e.count,0)}</td><td>${e.age_days==null?'':fmt(e.age_days,0)+' '+t('days')}</td><td>${e.mean_kg==null?'':fmt(e.mean_kg)+' kg'}${e.mean_kg!=null&&e.mean_date&&e.mean_date!==e.date?`<small>${safe(e.mean_date)}</small>`:''}</td></tr>`).join('')}</tbody></table>`;}
function notes(w){return w.events.map(e=>[e.date.slice(5),e.barn||t('unassigned'),t(e.type)+e.quantity,e.outgoing_destination,e.outgoing_trip,e.note,e.source_cell].filter(Boolean).join(' · ')).join('；');}
function pendingText(p){if(['shared_bin_unallocated','bin_batch_unknown'].includes(p.reason))return (p.date||'—')+' · '+(p.bin||'')+' · '+t(p.reason==='shared_bin_unallocated'?'sharedFeedPending':'binBatchPending')+' '+fmt(p.kg/1000,3)+' '+t('ton');return (p.date||t('dateUnknown'))+' · '+(p.reason==='unassigned_order'?t('weeklyUnknownFeed')+' '+fmt(p.kg/1000,3)+' '+t('ton'):t(p.type)+' · '+t(p.reason==='missing_barn'||p.reason==='source_allocation_incomplete'?'weeklyUnknownBarn':'weeklyUnknownDate')+(p.quantity?' · '+p.quantity+' '+t('heads'):''))+(p.source_cell?' · '+p.source_cell:'');}
function footnotes(compact){
 const r=report;
 if(compact)return `<footer class="weekly-footnotes"><p>${t('weeklyShortLegend')} ${t('weeklyPrintFeedHint')}</p><p>${t('weeklyPrintDetails')} ${t('weeklyShippingBasis')}</p></footer>`;
 return `<footer class="weekly-footnotes"><p class="weekly-print-details">${t('weeklyPrintDetails')}</p><p>${t('weeklyBasis')} ${t('weeklyAgeBasis')}</p>${r.age_mixed?`<p>${t('mixedAges')}（${r.observed_to}）：${r.barn_ages.map(b=>safe(b.barn)+' '+safe(displayAge(b.age_days))).join('；')}</p>`:''}<p>${t('coverageDisclaimer')} ${r.death_check_coverage?`${t('noDeathsChecked')} ${r.death_check_coverage.confirmed_zero_batch_days} · ${t('notReported')} ${r.death_check_coverage.awaiting_batch_days} ${t('batchDays')}。`:''}${t('weeklyNone')} * ${t('weeklyDates')}：${r.from} → ${r.to}；${t('weeklyObserved')} ${r.observed_to}</p>${compact&&r.weeks.some(w=>w.events.filter(e=>['sale','cull'].includes(e.type)&&e.outgoing_destination).length>1)?`<p>${t('weeklyOutgoingOverflow')}</p>`:''}<p>${t('weeklyFeedNotation')}</p><p>${t('weeklyFeedBasis')}</p><p>${t('cohortFormula')}</p></footer>`;
}
Object.assign(words,{weeklyPreentry:['進場前叫料','Cám đặt trước khi nhập heo'],weeklyPreentryHint:['依已指定批次列出，保留原日期，另外加總，不併入期間合計。','Theo lứa đã gán, giữ ngày gốc và cộng riêng, không gộp vào tổng kỳ.'],weeklyPreentryMore:['另有{n}筆進場前叫料，完整內容詳App。','Còn {n} lần đặt trước nhập; xem đầy đủ trong App.']});
function preentryRows(){const p=report.preentry_feed;return p?[...p.details,...p.shared_details]:[];}
function preentryTotal(){const p=report.preentry_feed;if(!p)return '';return p.total_kg!=null?fmtFeed(p.total_kg/1000)+' '+t('ton'):p.known_kg>0?t('weeklyKnown')+' '+fmtFeed(p.known_kg/1000)+' '+t('ton')+' · '+t('sharedFeedPending'):t('sharedFeedPending');}
function preentryLines(){const p=report.preentry_feed;return p?feedLines(p.details,p.shared_details):[];}
function preentryBlock(compact){const rows=preentryLines();if(!rows.length)return '';const shown=rows;return `<section class="weekly-preentry"><div class="section-row"><h2>${t('weeklyPreentry')}</h2><strong>${safe(preentryTotal())}</strong></div><p>${t('weeklyPreentryHint')}</p><div class="weekly-preentry-lines">${shown.map(n=>`<span>${safe(n)}</span>`).join('')}</div>${shown.length<rows.length?`<p>${safe(label('weeklyPreentryMore',rows.length-shown.length))}</p>`:''}</section>`;}
function sheetWeeks(){
 const ws=report.weeks.slice(),last=ws.at(-1);
 // Empty planned columns extend the paper only; saved future rows are already in report.weeks.
 const lastAge=shownWeek(last);if(!last||lastAge==null||lastAge>=32)return ws;
 for(let age=lastAge+1;age<=32;age++){
  const on=new Date(last.anchor+'T00:00:00Z');on.setUTCDate(on.getUTCDate()+(age-lastAge)*7);const anchor=on.toISOString().slice(0,10);
  ws.push({index:last.index+age-lastAge,age_week:report.week_reference?null:age,reference_age_week:report.week_reference?age:null,anchor,start:anchor,end:anchor,future:true,planned:true,values:{},known:{},feed_details:[],feed_shared_details:[],events:[]});
 }
 return ws;
}
function planningHint(){return [referenceHint(),sheetWeeks().some(w=>w.planned)?t('weeklyPlanned'):''].filter(Boolean).join(' ');}
function panels(){
 const weeks=sheetWeeks(),pages=[];for(let start=0;start<weeks.length;start+=40){const ws=weeks.slice(start,start+40).concat([null,null]),cols=Math.ceil(ws.length/2);pages.push([ws.slice(0,cols),ws.slice(cols)]);}return pages;
}
function weekHeading(w,compact){const age=shownWeek(w);return !w?'':age==null?label('weeklyPeriod',w.index):compact?label('weeklyWeekShort',age):label('weeklyWeek',age);}
function shortDate(w){if(!w)return '';const d=w.anchor.split('-');return Number(d[1])+'/'+Number(d[2]);}
function blankWeek(w){return !w||(w.future&&!w.has_records);}
function saleValues(events){return outgoingGroups(events.filter(e=>e.type==='sale')).map(e=>fmt(e.quantity,0)).join('、');}
function feedText(w){return blankWeek(w)?'':feedLines(w.feed_details,w.feed_shared_details).join('\n');}

function shippingNotes(){return outgoingGroups(report.weeks.flatMap(w=>w.events)).map(outgoingNotation);}
Object.assign(words,{weeklyDeathNotes:['死亡備註','Ghi chú heo chết'],weeklyDeathMore:['另有{n}筆死亡備註，完整內容詳App。','Còn {n} ghi chú heo chết; xem đầy đủ trong App.']});
Object.assign(words,{weeklyBarnDeathMore:['另{n}筆，詳App','Còn {n}, xem App'],weeklyBarnGroupsMore:['另有{n}棟，完整內容詳App。','Còn {n} chuồng; xem đầy đủ trong App.']});
function deathNotation(e){const d=e.date.split('-');return `${Number(d[1])}/${Number(d[2])} ${e.barn||t('unassigned')} ${t('death')}${fmt(e.quantity,0)}${t('periodHeads')}${e.note?' · '+e.note:''}`;}
function deathNotes(){return report.weeks.flatMap(w=>w.events).filter(e=>e.type==='death').sort((a,b)=>a.date.localeCompare(b.date)||String(a.barn||'').localeCompare(String(b.barn||''),undefined,{numeric:true})).map(deathNotation);}
function deathGroups(){
 const groups=new Map((report.barns||[]).map(barn=>[barn,[]]));
 for(const e of report.weeks.flatMap(w=>w.events).filter(e=>e.type==='death').sort((a,b)=>a.date.localeCompare(b.date))){const barn=e.barn||t('unassigned'),d=e.date.split('-');if(!groups.has(barn))groups.set(barn,[]);groups.get(barn).push(`${Number(d[1])}/${Number(d[2])} ${t('death')}${fmt(e.quantity,0)}${t('periodHeads')}${e.note?' · '+e.note:''}`);}
 return [...groups].sort(([a],[b])=>a.localeCompare(b,undefined,{numeric:true})).map(([barn,notes])=>{const n=barn.match(/^(?:第)?(\d+)棟$/);return {barn,title:n?(lang==='zh'?`第${n[1]}棟`:`${t('barn')} ${n[1]}`):barn,notes};});
}
function notesBlock(compact){
 const column=(notes,key,kind,more)=>{const shown=notes;return `<section class="weekly-${kind}-notes"><h2>${t(key)}</h2><div>${shown.map(n=>`<p class="weekly-${kind==='shipping'?'outgoing':'death'}-entry">${safe(n)}</p>`).join('')}${compact&&notes.length>shown.length?`<p class="weekly-${kind==='shipping'?'outgoing':'death'}-more">${safe(label(more,notes.length-shown.length))}</p>`:''}</div></section>`;};
 const groups=deathGroups(),shownGroups=groups;
 const deaths=`<section class="weekly-death-notes"><h2>${t('weeklyDeathNotes')}</h2><div class="weekly-death-groups" data-barn-columns="${Math.max(1,Math.min(3,shownGroups.length))}">${shownGroups.map(g=>{const shown=g.notes;return `<div class="weekly-death-barn" data-barn="${safe(g.barn)}"><h3>${safe(g.title)}</h3><div>${shown.map(n=>`<p class="weekly-death-entry">${safe(n)}</p>`).join('')}${shown.length<g.notes.length?`<p class="weekly-death-more">${safe(label('weeklyBarnDeathMore',g.notes.length-shown.length))}</p>`:''}</div></div>`;}).join('')}${shownGroups.length<groups.length?`<p class="weekly-death-more">${safe(label('weeklyBarnGroupsMore',groups.length-shownGroups.length))}</p>`:''}</div></section>`;
 return `<div class="weekly-notes-pair">${deaths}${column(shippingNotes(),'weeklyOutgoingNotes','shipping','weeklyShippingMore')}</div>`;
}
function pdfModel(){
 const r=report;
 return {continued:t('weeklyContinue'),preentry:preentryRows().length?{title:t('weeklyPreentry'),summary:preentryTotal(),entries:preentryLines(),hint:t('weeklyPreentryHint'),more:t('weeklyPreentryMore')}:null,title:'嘉得 · '+t('weeklyReport'),basics:paperBasics().map(([key,value])=>[t(key),value]),entryHeaders:['barn','reportEntryDate','reportEntryCount','weeklyEntryAge','reportEntryMean'].map(t),entries:(r.entry_details||[]).map(e=>[e.barn,e.date,e.count==null?'':fmt(e.count,0),e.age_days==null?'':e.age_days+' '+t('days'),e.mean_kg==null?'':fmt(e.mean_kg)+' kg'+(e.mean_date&&e.mean_date!==e.date?'\n'+e.mean_date:'')]),period:r.from+' → '+r.to+' · '+t('weeklyPaperPeriod'),cycle:cycleTitle(),pages:panels().map(page=>page.map(ws=>({headers:ws.map(w=>weekHeading(w,true)),rows:[{label:t('weeklyPaperStart'),cells:ws.map(shortDate),height:18},...metrics.map(k=>({label:t(paperMetricKey[k]),cells:ws.map(w=>blankWeek(w)?'':k==='feed_orders'?feedText(w):k==='sale'?saleValues(w.events):amount(w.values[k],k)),height:k==='feed_orders'?Math.max(46,...ws.map(w=>feedText(w).split('\n').length*10+8)):k==='death'?23:20,bold:k==='death',complete:k==='sale',left:k==='feed_orders',singleLine:k==='feed_orders',monospace:k==='feed_orders'}))]}))),death_title:t('weeklyDeathNotes'),death_notes:deathNotes(),death_groups:deathGroups(),death_more:t('weeklyBarnDeathMore'),death_groups_more:t('weeklyBarnGroupsMore'),shipping_title:t('weeklyOutgoingNotes'),shipping_notes:shippingNotes(),shipping_more:t('weeklyShippingMore'),totalLabel:t('weeklyTotal'),totals:metrics.map(k=>[t(metricKey[k]),r.totals[k]==null&&r.known_totals[k]>0?t('weeklyKnown')+' '+amount(r.known_totals[k],k):amount(r.totals[k],k)]),cumulative:t('weeklyCurrent')+' · '+r.observed_to+'  '+t('remaining')+' '+(r.cumulative.remaining==null?'':fmt(r.cumulative.remaining,0))+'  '+t('survival')+' '+(r.cumulative.survival==null?'':fmt(r.cumulative.survival)+'%'),legend:[t('weeklyPDFLegend'),planningHint(),t('weeklyShippingBasis')].filter(Boolean).join(' ')+(r.pending.length?' '+label('weeklyPendingCount',r.pending.length):'')};
}
async function downloadPDF(){
 if(!report||reportUser!==me?.id)return;const user=me.id,original=report,button=el('weekly-print'),name=filename();button.disabled=true;el('weekly-error').textContent=t('weeklyPDFMaking');
 try{const blob=await ensurePDF();if(!blob||me?.id!==user||report!==original||!el('weekly-report-dialog').open)return;const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name+'.pdf';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);el('weekly-error').textContent='';}
 catch(err){if(me?.id===user&&report===original)el('weekly-error').textContent=t('weeklyFailure');}finally{button.disabled=false;}
}
function markup(compact=false){
 const r=report,blocks=[];
 for(const page of panels())for(const ws of page){blocks.push(`<section class="weekly-block"><div class="weekly-table-wrap"><table class="weekly-table"><thead><tr><th>${safe(cycleTitle())}</th>${ws.map(w=>`<th>${safe(weekHeading(w,compact))}</th>`).join('')}</tr></thead><tbody><tr class="weekly-starts"><th>${t('weeklyStarts')}</th>${ws.map(w=>`<td>${safe(shortDate(w))}</td>`).join('')}</tr>${metrics.map(k=>`<tr class="weekly-${k}"><th>${t(compact?paperMetricKey[k]:metricKey[k])}</th>${ws.map(w=>`<td>${blankWeek(w)?'':k==='feed_orders'?feedCell(w):k==='sale'?saleValues(w.events):amount(w.values[k],k)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`);}

 const totals=metrics.map(k=>`<div><span>${t(metricKey[k])}</span><strong>${amount(r.totals[k],k)}</strong>${r.totals[k]==null&&r.known_totals[k]>0?`<small>${t('weeklyKnown')} ${amount(r.known_totals[k],k)}</small>`:''}</div>`).join('');
 const details=compact?'':`<details class="weekly-details"><summary>${t('weeklyDetails')}</summary><ul>${r.weeks.filter(w=>w.events.length).map(w=>`<li>${safe(w.start)}：${safe(notes(w))}</li>`).join('')}</ul>${footnotes(false)}</details>`;
 return `<article class="weekly-sheet${compact?' weekly-one-page':''}"><header class="weekly-heading"><h1>嘉得 · ${t('weeklyReport')}</h1></header><dl class="weekly-basics">${paperBasics().map(([k,v])=>`<div><dt>${t(k)}</dt><dd>${safe(v)}</dd></div>`).join('')}</dl>${entryFacts()}<p class="weekly-period-line">${t('weeklyDates')}：${safe(r.from)} → ${safe(r.to)} · ${t('weeklyObserved')} ${safe(r.observed_to)}<br>${t('weeklyPaperPeriod')} ${safe(planningHint())}</p>${preentryBlock(compact)}${blocks.join('')}${notesBlock(compact)}<section class="weekly-totals"><h2>${t('weeklyTotal')}</h2><div class="weekly-totals-grid">${totals}</div></section><p class="weekly-cumulative"><span>${t('weeklyCurrent')} · ${safe(r.observed_to)}</span><span>${t('remaining')} <strong>${r.cumulative.remaining==null?'—':fmt(r.cumulative.remaining,0)}</strong></span><span>${t('weeklySurvival')} <strong>${r.cumulative.survival==null?'—':fmt(r.cumulative.survival)+'%'}</strong></span></p>${r.pending.length?compact?`<p class="weekly-compact-pending">${safe(label('weeklyPendingCount',r.pending.length))}</p>`:`<details class="weekly-pending"><summary>${safe(label('weeklyPendingCount',r.pending.length))}</summary><ul>${r.pending.map(p=>`<li>${safe(pendingText(p))}</li>`).join('')}</ul></details>`:''}${footnotes(true)}${details}</article>`;
}
function fitFeedLines(root){
 const canvas=document.createElement('canvas'),c=canvas.getContext('2d'),parents=new Set([...root.querySelectorAll('.weekly-feed-entry')].map(line=>line.parentElement));
 for(const parent of parents){const lines=[...parent.querySelectorAll('.weekly-feed-entry')];let ratio=1;
  for(const line of lines){const style=getComputedStyle(line);c.font=style.font;const needed=c.measureText(line.textContent).width;if(!line.textContent.includes(' · ')&&line.clientWidth&&needed>line.clientWidth)ratio=Math.min(ratio,(line.clientWidth-1)/needed);}
  for(const line of lines){const size=parseFloat(getComputedStyle(line).fontSize);c.font=getComputedStyle(line).font;const needed=c.measureText(line.textContent).width,own=line.clientWidth&&needed?Math.min(1,(line.clientWidth-1)/needed):1;if(Math.min(ratio,own)<1)line.style.fontSize=(size*Math.min(ratio,own))+'px';}
 }
}
function render(){if(report&&reportUser===me?.id){el('weekly-sheet-body').innerHTML='<details><summary>'+t('weeklyScreenDetails')+'</summary>'+markup()+'</details>';fitFeedLines(el('weekly-sheet-body'));el('weekly-sheet-body').firstElementChild.addEventListener('toggle',()=>fitFeedLines(el('weekly-sheet-body')));ensurePDF().catch(()=>{el('weekly-error').textContent=t('weeklyFailure');});}}
function filename(){return `${t('weeklyReport')}_${report.name}_${report.barns.join('-')}_${report.from}_${report.to}`.replace(/[\\/:*?"<>|\r\n]/g,'-');}
async function printSheet(){
 if(!report||reportUser!==me?.id)return;const original=report,user=me.id;
 try{
  const blob=await ensurePDF();if(!blob||report!==original||me?.id!==user||!el('weekly-report-dialog').open)return;
  const root=el('weekly-print-root');root.replaceChildren();root.classList.add('weekly-rendered-pages');
  const pages=previewURLs.map(src=>{const img=document.createElement('img');img.src=src;img.className='weekly-print-pdf-page';root.append(img);return img;});
  await Promise.all(pages.map(img=>img.decode()));if(report!==original||me?.id!==user){resetPrint();return;}
  printing=true;title=document.title;document.title=filename();window.print();
 }catch(err){resetPrint();if(report===original&&me?.id===user)el('weekly-error').textContent=t('weeklyFailure');}
}
build=()=>{
 base.build();el('stats-filter').closest('.card').insertAdjacentHTML('beforeend',`<div class="weekly-entry"><button type="button" id="open-weekly-report">${txt('weeklyOpen')}</button><p class="hint">${txt('weeklyBasis')}</p></div>`);
 el('movement-form').insertAdjacentHTML('afterend',`<div class="weekly-entry"><button type="button" id="open-daily-weekly-report">${txt('weeklyOpen')}</button></div>`);
 document.body.insertAdjacentHTML('beforeend',`<dialog id="weekly-report-dialog" aria-labelledby="weekly-title"><div class="weekly-toolbar"><div class="section-row"><h2 id="weekly-title">${txt('weeklyReport')}</h2><button type="button" id="weekly-close">${txt('reportClose')}</button></div><form id="weekly-report-form"><div class="grid"><label>${txt('weeklyBatch')}<select id="weekly-cohort" required></select></label><label>${txt('barn')}<select id="weekly-barn"></select></label></div><p class="hint">${txt('weeklyBasis')}</p><button type="submit" id="weekly-generate" class="primary">${txt('weeklyMake')}</button><p id="weekly-error" role="status"></p></form><div id="weekly-export-actions" class="actions" hidden><button type="button" id="weekly-print" class="primary">${txt('weeklyDownloadPDF')}</button><button type="button" id="weekly-browser-print">${txt('weeklyBrowserPrint')}</button></div></div><p class="weekly-export-hint hint">${txt('weeklyPDFHint')}</p><div id="weekly-a4-preview" aria-live="polite"></div><div id="weekly-sheet-body"></div></dialog><div id="weekly-print-root"></div>`);
 el('open-weekly-report').onclick=openWeekly;el('weekly-cohort').onchange=()=>syncBarns();el('weekly-report-form').onsubmit=generate;el('weekly-print').onclick=downloadPDF;el('weekly-browser-print').onclick=printSheet;el('weekly-close').onclick=()=>el('weekly-report-dialog').close();el('weekly-report-dialog').addEventListener('close',()=>{serial++;clearPDF();report=null;reportUser=null;el('weekly-generate').disabled=false;resetPrint();});
 el('open-daily-weekly-report').onclick=openWeekly;
 for(const event of ['input','change'])el('weekly-report-form').addEventListener(event,()=>{serial++;clearPDF();report=null;reportUser=null;el('weekly-sheet-body').replaceChildren();el('weekly-export-actions').hidden=true;el('weekly-generate').disabled=false;el('weekly-error').textContent='';if(event==='change'&&chosen())queueMicrotask(()=>generate({preventDefault(){}}));});
};
document.addEventListener('pigledger:weekly-open',event=>openWeekly(event.detail||{}));
window.addEventListener('afterprint',resetPrint);
document.addEventListener('pigledger:logout',()=>{serial++;clearPDF();report=null;reportUser=null;if(el('weekly-report-dialog').open)el('weekly-report-dialog').close();el('weekly-sheet-body').replaceChildren();resetPrint();});
translate=()=>{base.translate();if(data&&el('weekly-report-dialog')?.open){syncCohorts();syncBarns(el('weekly-barn').value);}render();};
refresh=async(...args)=>{const previous=data;await base.refresh(...args);if(me&&data!==previous&&report&&el('weekly-report-dialog')?.open)await generate({preventDefault(){}});};
enter=async user=>{if(el('weekly-report-dialog')?.open)el('weekly-report-dialog').close();return base.enter(user);};
})();
