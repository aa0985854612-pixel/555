'use strict';
/* Daily acknowledgements use the existing durable, idempotent write queue. */
(() => {
Object.assign(words,{
 dailyReview:['當日核對','Đối chiếu trong ngày'],reviewHint:['以下是已登記數量；沒有紀錄不代表零死亡。','Số đã ghi; không có bản ghi không có nghĩa là không chết.'],patrolReview:['巡場確認','Xác nhận kiểm tra'],noDeathsChecked:['已巡場、無死亡','Đã kiểm tra, không chết'],notReported:['尚未回報','Chưa báo cáo'],deathRecorded:['已登記死亡','Đã ghi heo chết'],unresolvedDaily:['來源待核對','Cần đối chiếu nguồn'],confirmNoDeaths:['確認無死亡','Xác nhận không chết'],cancelCheck:['撤銷確認','Hủy xác nhận'],cancelCheckReason:['撤銷無死亡確認的原因','Lý do hủy xác nhận không chết'],confirmCheckLabel:['請確認已巡查此棟，當日確實沒有死亡。','Xác nhận đã kiểm tra chuồng và ngày này không có heo chết.'],checkNote:['只確認所選日期、棟舍及批次；不會更動頭數。','Chỉ xác nhận ngày, chuồng và lứa này; không đổi tồn đàn.'],recordedToday:['當日已登記','Đã ghi trong ngày'],noDailyRecords:['這天尚無異動紀錄','Chưa ghi biến động ngày này'],moreDaily:['其他當日紀錄','Các bản ghi khác trong ngày'],checkSuperseded:['已補登死亡，原無死亡確認已失效','Đã bổ sung heo chết; xác nhận không chết trước đây hết hiệu lực'],qualityTitle:['待補／待核對資料','Dữ liệu cần bổ sung / đối chiếu'],qualityHint:['依可靠資料列出缺項，不會自動猜填或更動存欄。','Liệt kê thiếu sót từ dữ liệu đáng tin; không đoán hay tự đổi tồn đàn.'],qualityActive:['目前在養批次','Lứa đang nuôi'],qualitySources:['來源與歸屬待核對','Nguồn và phân bổ cần đối chiếu'],qualityNoGaps:['目前沒有列出的待補項目','Hiện không có mục cần bổ sung'],qualityGoEdit:['前往補正','Bổ sung'],qualityGoHistory:['查看來源歷史','Xem lịch sử nguồn'],qualityReason:['待補原因','Lý do cần bổ sung'],missing_entry_count:['單棟進場頭數待補','Thiếu số nhập riêng chuồng'],missing_entry_mean:['入場均重待補','Thiếu cân nặng TB lúc nhập'],missing_age:['日齡／週齡基準待補','Thiếu căn cứ tuổi'],missing_death_allocation:['單棟累計死亡分配待補','Thiếu phân bổ chết lũy kế theo chuồng'],missing_stock:['存欄依據待核對','Cần đối chiếu tồn đàn'],stock_exceeds_entry:['存欄大於已知進場分母，需核對進場、轉入或盤點','Tồn đàn vượt mẫu số nhập đã biết; đối chiếu nhập, chuyển hoặc kiểm kê'],missing_date:['缺日期','Thiếu ngày'],missing_barn_allocation:['缺可靠棟舍／批次分配','Thiếu phân bổ chuồng / lứa đáng tin'],source_mean_only:['只有來源均重，缺樣本頭數','Chỉ có TB nguồn, thiếu số mẫu'],source_conflict:['新版來源與App有待核對差異','Nguồn mới khác App, cần đối chiếu'],unassigned_feed:['叫料尚未指定棟舍／批次','Đặt cám chưa gán chuồng / lứa'],coverageDisclaimer:['未回報不代表無死亡；死亡數僅表示已登記數量。','Chưa báo cáo không có nghĩa là không chết; số chết chỉ là số đã ghi.'],coverageTitle:['巡場回報涵蓋','Phạm vi báo cáo kiểm tra'],coverageHint:['僅計目前在養批次、來源基準日之後的棟批日；有死亡紀錄不等於已完成整日巡場。歷史未確認的零值不能當作無死亡證明。','Chỉ tính ngày-chuồng-lứa đang nuôi sau mốc nguồn; có bản ghi chết không đồng nghĩa đã kiểm tra cả ngày. Số 0 lịch sử chưa xác nhận không chứng minh không chết.'],batchDays:['棟批日','ngày-chuồng-lứa'],checkConfirm:['確認巡場結果','Xác nhận kết quả kiểm tra'],checkCancelHeading:['撤銷巡場確認','Hủy xác nhận kiểm tra']
});
Object.assign(words,{
 bulkNoDeaths:['全部回報無死豬','Báo cáo tất cả không có heo chết'],bulkCheckHeading:['確認全部回報範圍','Xác nhận phạm vi báo cáo tất cả'],bulkCheckHint:['請確認已巡查以下全部棟舍，所選日期確實無死亡；已有死亡、已確認或資料待核對的棟批會略過。','Xác nhận đã kiểm tra tất cả chuồng dưới đây và không chết trong ngày đã chọn; bỏ qua chuồng-lứa có heo chết, đã xác nhận hoặc cần đối chiếu.'],bulkIncluded:['本次回報','Báo cáo lần này'],bulkSkipped:['自動略過','Tự bỏ qua'],bulkEmpty:['目前沒有可回報的棟批','Hiện không có chuồng-lứa có thể báo cáo'],bulkScopeCount:['棟批','chuồng-lứa'],other_owner:['原確認需由本人或管理員處理','Xác nhận cũ cần người tạo hoặc quản trị xử lý'],outside_check_period:['非可確認日期／批次','Không thuộc ngày / lứa có thể xác nhận']
});
Object.assign(errorWords,{daily_preview_changed:['資料已更新，請重新按「全部回報無死豬」核對範圍。','Dữ liệu đã đổi; nhấn báo cáo tất cả lần nữa để đối chiếu.'],
 daily_death_conflict:['已有死亡或未分配死亡資料，不能確認無死亡；請重新核對。','Đã có dữ liệu chết hoặc chưa phân bổ; không thể xác nhận không chết.'],daily_check_exists:['此棟這天已有確認紀錄，請重新讀取。','Chuồng này đã có xác nhận ngày này; tải lại.'],future_daily_check:['不能預先確認未來日期的巡場。','Không thể xác nhận kiểm tra ngày tương lai.'],check_legacy_period:['此日屬於來源基準期間，請核對原始歷史。','Ngày thuộc kỳ nguồn; đối chiếu lịch sử gốc.'],check_reason_required:['請填寫撤銷原因。','Nhập lý do hủy.'],daily_check_identity_locked:['巡場確認的日期與批次不可直接改動；請撤銷後另行確認。','Không đổi trực tiếp ngày / lứa xác nhận; hủy rồi xác nhận lại.']
});
const base={build,renderHome,renderSettings,persistPending,statHTML,renderCurrent};
let requestNo=0,checkDraft=null;
const editable=r=>me?.role==='admin'||(me?.role==='staff'&&r.created_by===me.id);
const statusWord=s=>({no_deaths:'noDeathsChecked',death_recorded:'deathRecorded',not_reported:'notReported',unresolved:'unresolvedDaily'}[s]);
function pendingButtons(){
 $$('#daily-review button[data-bulk-check],#daily-review button[data-cancel-check],#check-save').forEach(b=>b.disabled=!!pending||me?.role==='viewer'||(b.hasAttribute('data-bulk-check')&&!renderDaily.latest?.rows.some(r=>r.can_confirm&&(!r.check||editable(r.check)))));
}
persistPending=()=>{base.persistPending();pendingButtons();};
build=()=>{
 base.build();
 $('#daily-entry').insertAdjacentHTML('afterend',`<section class="card daily-review" id="daily-review"><div class="review-heading"><h2>${txt('dailyReview')}</h2><label><span class="sr-only">${txt('date')}</span><input type="date" id="review-date" value="${today()}" aria-label="${esc(t('date'))}"></label></div><div id="review-body" aria-live="polite"></div></section>`);
 $('#page-settings').insertAdjacentHTML('afterbegin',`<details class="card quality-panel" id="quality-panel" data-key="quality-panel"><summary><span>${txt('qualityTitle')}</span> <span id="quality-count" class="pill"></span></summary><p class="hint">${txt('qualityHint')}</p><div id="quality-body"></div></details>`);
 document.body.insertAdjacentHTML('beforeend',`<dialog id="check-dialog"><h2 id="check-heading"></h2><p id="check-scope"></p><p id="check-instruction"></p><div id="check-bulk-scope"></div><label id="check-reason-label" hidden>${txt('cancelCheckReason')}<input id="check-reason" maxlength="500" autocomplete="off"></label><p class="hint">${txt('checkNote')}</p><div class="actions"><button type="button" id="check-close">${txt('cancel')}</button><button type="button" class="primary" id="check-save">${txt('confirmNoDeaths')}</button></div></dialog>`);
 $('#review-date').onchange=()=>{if(!$('#review-date').value)return;renderDaily();};
 $('#movement-form [name=date]').addEventListener('change',()=>{$('#review-date').value=val($('#movement-form'),'date');renderDaily();});
 document.addEventListener('pigledger:logout',()=>{$('#check-dialog').close();checkDraft=null;renderDaily.latest=null;++requestNo;});
 $('#check-close').onclick=()=>$('#check-dialog').close();
 $('#check-save').onclick=()=>{
  if(!checkDraft||pending)return;
  if(checkDraft.bulk){const body={date:checkDraft.date,preview_token:checkDraft.preview_token};$('#check-dialog').close();startWrite('/api/daily-checks/bulk','POST',body);return;}
  const body={date:checkDraft.date,batch_id:checkDraft.batch_id,status:checkDraft.cancel?'cancelled':'no_deaths',note:checkDraft.cancel?$('#check-reason').value.trim():''};
  if(checkDraft.cancel&&!body.note){$('#check-reason').reportValidity();return;}
  if(checkDraft.check)body.revision=checkDraft.check.revision;
  const path='/api/daily_checks'+(checkDraft.check?'/'+checkDraft.check.id:'');$('#check-dialog').close();startWrite(path,checkDraft.check?'PUT':'POST',body);
 };
 $('#daily-review').addEventListener('click',async e=>{
  const bulk=e.target.closest('[data-bulk-check]');if(bulk){
   if(pending||me?.role==='viewer')return;bulk.disabled=true;
   const on=$('#review-date').value,user=me?.id;
   try{
    const preview=await api('/api/daily-checks/preview?date='+encodeURIComponent(on));
    if(user!==me?.id||on!==$('#review-date').value)return;
    if(!preview.eligible.length){toast(t('bulkEmpty'));return;}
    checkDraft={...preview,bulk:true};$('#check-heading').textContent=t('bulkCheckHeading');$('#check-scope').textContent=`${preview.date} · ${t('bulkIncluded')} ${preview.eligible.length} ${t('bulkScopeCount')}`;
    $('#check-instruction').textContent=t('bulkCheckHint');$('#check-reason-label').hidden=true;$('#check-reason').required=false;
    const label=r=>`${esc(r.barn)} · ${esc(r.batch)}`;
    $('#check-bulk-scope').innerHTML=`<ul>${preview.eligible.map(r=>`<li>${label(r)}</li>`).join('')}</ul>${preview.skipped.length?`<details><summary>${t('bulkSkipped')} ${preview.skipped.length} ${t('bulkScopeCount')}</summary><ul>${preview.skipped.map(r=>`<li>${label(r)} — ${t(statusWord(r.reason)||r.reason)}</li>`).join('')}</ul></details>`:''}`;
    $('#check-save').textContent=t('bulkNoDeaths');$('#check-dialog').showModal();
   }catch(err){toast(messageError(err));}finally{pendingButtons();}return;
  }

  const confirm=e.target.closest('[data-check]'),cancel=e.target.closest('[data-cancel-check]');if(!confirm&&!cancel)return;
  const row=renderDaily.latest?.rows.find(r=>r.batch_id===(confirm?.dataset.check||cancel?.dataset.cancelCheck));if(!row)return;
  checkDraft={...row,date:renderDaily.latest.date,cancel:!!cancel};$('#check-bulk-scope').replaceChildren();
  $('#check-heading').textContent=t(cancel?'checkCancelHeading':'checkConfirm');$('#check-scope').textContent=`${checkDraft.date} · ${row.barn} · ${row.batch}`;
  $('#check-instruction').textContent=cancel?'':t('confirmCheckLabel');$('#check-reason-label').hidden=!cancel;$('#check-reason').required=!!cancel;$('#check-reason').value='';$('#check-save').textContent=t(cancel?'cancelCheck':'confirmNoDeaths');$('#check-dialog').showModal();
 });
 $('#quality-body').addEventListener('click',e=>{
  const b=e.target.closest('[data-quality-edit]');if(b){edit('batches',b.dataset.qualityEdit);$('#batch-form details').open=true;return;}
  const h=e.target.closest('[data-quality-source]');if(!h)return;
  const kind=h.dataset.qualitySource;if(kind==='feed_orders'){location.hash='feed';return;}if(kind==='workbooks'){const fold=$('#workbook-form').closest('details');if(fold)fold.open=true;fold?.scrollIntoView({block:'start'});return;}
  const f=$('#history-filter');f.reset();f.elements.record_kind.value=kind;syncFilters(f);location.hash='history';renderCurrent();
 });
};
function recordLine(r){
 const batch=data.batches.find(b=>b.id===r.batch_id),barn=r.barn_number?String(r.barn_number)+t('barn'):data.barns.find(b=>b.id===batch?.barn_id)?.name||t('unassigned');
 return `<article class="review-event"><div><strong>${esc(barn)}</strong><span>${esc(batch?.name||r.legacy_batch||t('unassigned'))}</span>${r.note?`<small>${esc(r.note)}</small>`:''}</div><strong class="${r.type==='death'?'warning-text':''}">${esc(t(r.type))} ${fmt(r.quantity,0)}</strong><div class="review-actions">${recordActions('movements',r)}</div></article>`;
}
async function renderDaily(){
 const on=$('#review-date')?.value||today(),ticket=++requestNo;if(!data)return;
 try{
  if(on!==data.daily_review?.date){renderDaily.latest=null;preserveBox('review-body',`<p>${t('weeklyLoading')}</p>`);}
  const report=on===data.daily_review?.date?data.daily_review:await api('/api/daily-review?date='+encodeURIComponent(on));if(ticket!==requestNo||!data)return;
  renderDaily.latest=report;
  const counts=report.counts,events=report.events;
  preserveBox('review-body',`<div class="review-totals">${['death','sale','cull'].map(k=>`<div><span>${t(k)}</span><strong>${fmt(report.totals[k],0)}</strong></div>`).join('')}</div><p class="hint">${t('reviewHint')}</p><div class="bulk-patrol-action">${me?.role!=='viewer'?`<button type="button" class="primary" data-bulk-check ${report.rows.some(r=>r.can_confirm&&(!r.check||editable(r.check)))?'':'disabled'}>${t('bulkNoDeaths')}</button>`:''}<p class="hint">${t('noDeathsChecked')} ${counts.no_deaths} · ${t('notReported')} ${counts.not_reported}</p></div><details data-key="daily-events"><summary>${t('recordedToday')} · ${events.length}</summary>${events.map(recordLine).join('')||`<p>${t('noDailyRecords')}</p>`}</details><details data-key="patrol-list"><summary>${t('patrolReview')}</summary><div class="patrol-list">${report.rows.map(r=>`<article class="patrol-row"><div><strong>${esc(r.barn)}</strong><span>${esc(r.batch)}</span><small class="patrol-status ${r.status==='death_recorded'?'warning-text':''}">${t(statusWord(r.status))}${r.status==='death_recorded'?' '+fmt(r.deaths,0)+' '+t('heads'):''}</small>${r.check_superseded?`<small>${t('checkSuperseded')}</small>`:''}</div><div>${r.check?.status==='no_deaths'&&editable(r.check)?`<button type="button" data-cancel-check="${r.batch_id}">${t('cancelCheck')}</button>`:''}</div></article>`).join('')}</div></details>`);
  pendingButtons();
 }catch(e){if(ticket===requestNo){preserveBox('review-body',`<p class="form-error">${esc(messageError(e))}</p>`);renderDaily.latest=null;}}
}
function renderQuality(){
 if(!data?.data_quality)return;const q=data.data_quality;$('#quality-count').textContent=q.count;
 const group=(items,key)=>`<details data-key="quality-${key}" ${key==='active'?'open':''}><summary>${t(key==='active'?'qualityActive':'qualitySources')} · ${items.length}</summary>${items.map(i=>`<article class="quality-item"><div><strong>${esc(i.barn||i.source_cell||i.date||t('unassigned'))}</strong><span>${esc(i.name||'')}${i.entry_date?' · '+esc(i.entry_date):''}</span></div><p>${i.fields.map(k=>esc(t(k))).join('；')}</p>${i.fields.includes('stock_exceeds_entry')?`<p>${t('remaining')} ${fmt(i.remaining,0)} · ${t('denominator')} ${fmt(i.denominator,0)}</p>`:''}${i.note?`<details data-key="quality-note-${esc(i.id)}"><summary>${t('note')}</summary><p>${esc(i.note)}</p></details>`:''}${i.kind==='batches'?(me?.role==='admin'?`<button type="button" data-quality-edit="${i.batch_id}">${t('qualityGoEdit')}</button>`:''):`<button type="button" data-quality-source="${i.kind}">${t('qualityGoHistory')}</button>`}</article>`).join('')}</details>`;
 const first=!$('#quality-body').hasChildNodes();
 preserveBox('quality-body',q.count?group(q.items.filter(i=>i.kind==='batches'),'active')+group(q.items.filter(i=>i.kind!=='batches'),'source'):`<p>${t('qualityNoGaps')}</p>`);
 if(first&&$('#quality-body [data-key=quality-active]'))$('#quality-body [data-key=quality-active]').open=true;
}
renderHome=async()=>{const result=await base.renderHome();await renderDaily();return result;};
renderSettings=()=>{base.renderSettings();renderQuality();};
statHTML=s=>{
 const html=base.statHTML(s),c=s.death_check_coverage;if(!c)return html;
 const coverage=`<div class="coverage-card"><h3>${t('coverageTitle')}</h3><p><strong>${t('noDeathsChecked')} ${c.confirmed_zero_batch_days}</strong> · ${t('deathRecorded')} ${c.death_recorded_batch_days} · ${t('notReported')} ${c.awaiting_batch_days} ${t('batchDays')}</p><details data-key="coverage-basis"><summary>${t('qualityReason')}</summary><p>${t('coverageHint')}</p></details><p class="hint">${t('coverageDisclaimer')}</p></div>`;
 return html.replace('</section>',coverage+'</section>');
};
})();
