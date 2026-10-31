'use strict';
/* Group the existing records for display; never merge IDs or infer missing counts. */
(() => {
Object.assign(words,{
 newMovement:['豬隻登記','Ghi đàn heo'],movementExtras:['備註與其他資料（選填）','Ghi chú và thông tin khác (tùy chọn)'],
 cumulativeCulledShort:['淘汰','Loại'],
 openReportForm:['線上維修單','Phiếu sửa chữa trực tuyến'],
 groupedSetup:['按批次設定','Cài đặt theo lứa'],groupedHint:['同批各棟集中在一起；點批次展開，再選棟舍編輯。','Các chuồng cùng lứa nằm chung; mở lứa rồi chọn chuồng để sửa.'],findBatch:['找批次／棟舍','Tìm lứa / chuồng'],newBatch:['新增單棟批次','Thêm lứa tại chuồng'],batchDetailsShort:['其他批次資料','Thông tin lứa khác'],entryMeanShort:['入場均重（kg／隻）','TB nhập (kg/con)'],knownEntry:['已填進場','Số nhập đã ghi'],missingBarns:['棟待補','chuồng cần bổ sung'],barnCount:['棟','chuồng'],editHere:['正在編輯','Đang sửa'],saveBeforeSwitch:['請先儲存或取消目前修改，再切換棟舍。','Lưu hoặc hủy thay đổi hiện tại trước khi chuyển chuồng.'],otherSettings:['其他設定','Cài đặt khác'],dailyOverview:['全場總覽','Tổng quan trại'],dailyEntry:['登記','Ghi chép'],currentHeadsShort:['存欄','Tồn đàn'],cumulativeDeadShort:['死亡','Chết'],cumulativeSoldShort:['出豬','Xuất'],survivalShort:['育成率','Tỷ lệ sống'],overviewHint:['每列一棟；點棟舍即可登記。死亡、出豬與淘汰為該批進場至今日累計；出豬只計正常出豬，淘汰另外列出。未知資料顯示 —。','Mỗi dòng một chuồng; chạm tên để ghi. Chết, xuất bán và loại thải lũy kế từ ngày nhập lứa đến hôm nay; xuất bán chỉ tính bán thường, loại thải ghi riêng. Chưa rõ hiển thị —.'],noMatchingBatch:['沒有符合的批次，可改選全部或搜尋其他棟舍。','Không có lứa phù hợp; chọn tất cả hoặc tìm chuồng khác.'],createBarnShort:['新增／編輯棟舍','Thêm / sửa chuồng'],batchSavedHint:['每棟分別儲存；不會連帶更改同批其他棟。','Lưu riêng từng chuồng; không thay đổi các chuồng khác cùng lứa.'],queryConditions:['查詢條件','Điều kiện lọc']
});
Object.assign(words,{
 movementDestination:['出豬地點','Nơi xuất heo'],
 cohortRemaining:['本批次剩餘總頭數','Tổng heo còn lại của lứa'],
 cohortRemainingShort:['剩餘','Còn lại'],
 cohortSurvival:['整批育成率','Tỷ lệ sống cả lứa'],cohortBasis:['查看整批計算依據','Xem căn cứ tính cả lứa'],cohortIncludes:['涵蓋全部棟舍（含已出清）','Tất cả chuồng, gồm chuồng đã xuất hết'],cohortMissingEntry:['整批可靠進場分母待補','Cần bổ sung mẫu số nhập đáng tin của cả lứa'],cohortMissingDead:['整批累計死亡待補','Cần bổ sung số chết lũy kế cả lứa'],cohortZeroEntry:['尚無正的進場分母','Chưa có mẫu số nhập lớn hơn 0'],cohortFormula:['（可靠進場分母－累計死亡）÷可靠進場分母 × 100%；淘汰不降低育成率。','(Mẫu số nhập đáng tin − chết lũy kế) ÷ mẫu số nhập × 100%; loại thải không giảm tỷ lệ sống.'],customBarnGroup:['自訂組別（選填，非批號）','Nhóm tự đặt (tùy chọn, không phải mã lứa)'],barnSetupHelp:['這裡管理棟舍名稱與自訂分區；不需要分區時，組別可留空。同批豬的資料請到上方「按批次設定」。','Quản lý tên chuồng và khu vực tự đặt; có thể để trống nhóm. Sửa thông tin đàn cùng lứa ở mục cài đặt theo lứa phía trên.']
});
Object.assign(words,{
 currentFarmSold:['現養批次出豬','Xuất bán của lứa đang nuôi'],currentFarmBasis:['僅合計仍有豬的飼養中批次','Chỉ cộng lứa đang nuôi còn heo'],
 clearedRecords:['已清空／已結束紀錄','Lịch sử chuồng trống / lứa kết thúc'],cleared:['已清空','Đã trống'],viewHistory:['查看紀錄','Xem lịch sử'],
 clearedHint:['清空與結束的紀錄仍完整保留，可查看異動或下載肉豬紀錄表。','Giữ đầy đủ dữ liệu chuồng trống và lứa kết thúc; xem biến động hoặc tải bảng heo thịt.']
});
const base={build,renderHome,edit,finishForm,clickAction,enter,restorePending};
const keyOf=b=>b._cohort_key||b.name+'|'+b.entry_date;
const barnOf=b=>data.barns.find(x=>x.id===b.barn_id)?.name||t('unassigned');
const compareBarn=(a,b)=>barnOf(a).localeCompare(barnOf(b),'zh-Hant',{numeric:true});
const entryMeans=b=>b.report_entry_lots?.length?b.report_entry_lots.map(lot=>lot.mean_kg):[b.entry_mean_kg];
const entryMeanText=values=>[...new Set(values)].map(value=>value==null?'—':fmt(value)).join('／');
let dailyView='entry';
function groups(){
 const grouped=new Map();for(const b of data.batches){const key=keyOf(b);if(!grouped.has(key))grouped.set(key,{key,name:b.name,date:b.entry_date,members:[]});grouped.get(key).members.push(b);}
 return Array.from(grouped.values()).sort((a,b)=>b.date.localeCompare(a.date)||a.name.localeCompare(b.name,'zh-Hant',{numeric:true})).map(g=>({...g,members:g.members.sort(compareBarn)}));
}
function fold(card,label){
 const panel=document.createElement('details');panel.className='card settings-fold';const summary=document.createElement('summary');summary.innerHTML=txt(label);panel.append(summary);while(card.firstChild)panel.append(card.firstChild);card.replaceWith(panel);return panel;
}
function showDaily(view,scroll=false){
 dailyView=view;$('#daily-entry').hidden=view==='overview';
 if($('#daily-review'))$('#daily-review').hidden=view==='overview';
 if($('#daily-overview'))$('#daily-overview').hidden=view!=='overview';
 $$('#daily-switch button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.dailyView===view)));
 if(scroll)$('#daily-switch').scrollIntoView({block:'start',behavior:'smooth'});
}
function editorFields(record){
 const f=$('#batch-form'),grid=f.querySelector(':scope > .grid'),extra=f.querySelector(':scope > details .grid');
 for(const name of ['barn_id','name'])(record?extra:grid).append(f.elements[name].closest('label'));
 for(const name of ['entry_count','entry_mean_kg','entry_date'])grid.append(f.elements[name].closest('label'));
 f.elements.entry_count_source.closest('label').hidden=true;
}
build=()=>{
 base.build();
 const page=$('#page-settings'),list=$('#batch-settings'),listCard=list.closest('.card'),editor=$('#batch-form').closest('.card'),barnCard=$('#barn-form').closest('.card'),oldSplit=barnCard.parentElement;
 listCard.id='batch-workspace';listCard.classList.add('admin-section');page.prepend(listCard);
 listCard.querySelector('h2').dataset.i='groupedSetup';listCard.querySelector('h2').textContent=t('groupedSetup');listCard.insertAdjacentHTML('afterbegin',`<div class="batch-tools"><label>${txt('findBatch')}<input type="search" id="batch-search" autocomplete="off"></label><label>${txt('status')}<select id="batch-status">${option('active','active')+option('','all')+option('ended','ended')}</select></label></div>`);
 listCard.querySelector('h2').after(Object.assign(document.createElement('p'),{className:'hint',innerHTML:txt('groupedHint')}));
 listCard.querySelector('.batch-tools').before(listCard.querySelector('h2'),listCard.querySelector('p'));
 listCard.querySelector('.batch-tools').insertAdjacentHTML('afterend',`<div class="actions batch-create"><button type="button" id="new-batch">${txt('newBatch')}</button></div>`);
 editor.id='batch-editor';editor.hidden=true;editor.classList.add('batch-editor');listCard.append(editor);oldSplit.before(barnCard);oldSplit.remove();
 const form=$('#batch-form'),main=form.querySelector('.grid'),advancedGrid=form.querySelector('details .grid');
 for(const name of ['entry_age','age_unit','status','group'])advancedGrid.append(form.elements[name].closest('label'));
 main.append(form.elements.entry_mean_kg.closest('label'));form.elements.entry_mean_kg.closest('label').querySelector('[data-i]').dataset.i='entryMeanShort';form.elements.entry_mean_kg.closest('label').querySelector('[data-i]').textContent=t('entryMeanShort');
 main.after(form.elements.entry_count_source.closest('label'));
 form.querySelector('details summary').dataset.i='batchDetailsShort';form.querySelector('details summary').textContent=t('batchDetailsShort');
 form.querySelector('details').append(form.querySelector('[data-i="transferBatchHint"]'));
 editor.querySelector('h2').id='batch-editor-title';delete editor.querySelector('h2').dataset.i;editor.querySelector('h2').after(Object.assign(document.createElement('p'),{className:'hint',innerHTML:txt('batchSavedHint')}));
 $('#batch-search').addEventListener('input',filterGroups);$('#batch-status').addEventListener('change',filterGroups);
 $('#new-batch').onclick=()=>{if(!canSwitch())return;finishForm(form);form.reset();form.elements.entry_date.value=today();editorFields(null);$('#batch-workspace').append(editor);editor.hidden=false;editor.querySelector('h2').textContent=t('newBatch');const cancel=form.querySelector('[data-action=cancelEdit]');cancel.hidden=false;cancel.dataset.i='cancel';cancel.textContent=t('cancel');form.querySelectorAll('details').forEach(d=>d.open=false);editor.scrollIntoView({block:'start',behavior:'smooth'});};
 const barnGroup=$('#barn-form [name=group]').closest('label').querySelector('[data-i]');barnGroup.dataset.i='customBarnGroup';barnGroup.textContent=t('customBarnGroup');$('#barn-form').before(Object.assign(document.createElement('p'),{className:'hint',innerHTML:txt('barnSetupHelp')}));
 fold(barnCard,'createBarnShort');fold($('#workbook-form').closest('.card'),'workbook');fold($('#download-backup').closest('.card'),'backup');fold($('#user-form').closest('.card'),'users');fold($('#audit-results').closest('.card'),'audit');
 // Password remains a direct child so forced first-login changes still isolate it.
 const password=$('#password-card'),passwordFold=fold(password,'passwordChange');passwordFold.id='password-card';
 page.append(passwordFold);
 const daily=$('#page-daily'),split=$('#movement-form').closest('.split'),entry=$('#movement-form').closest('.card'),recent=$('#recent').closest('.card');
 $$('input[type="date"]').forEach(el=>el.closest('label')?.classList.add('date-field'));
 const movement=$('#movement-form'),typeField=movement.elements.type.closest('label'),quantityField=movement.elements.quantity.closest('label');
 typeField.classList.add('movement-type');quantityField.classList.add('movement-quantity');typeField.after(quantityField);
 const extras=movement.querySelector('details'),extraGrid=extras.querySelector('.grid');
 const destinationField=movement.elements.outgoing_destination.closest('label');quantityField.after(destinationField);
 const destinationLabel=destinationField.querySelector('[data-i]');destinationLabel.dataset.i='movementDestination';destinationLabel.textContent=t('movementDestination');
 extraGrid.prepend(movement.elements.outgoing_trip.closest('label'));
 const extraSummary=extras.querySelector('summary');extraSummary.dataset.i='movementExtras';extraSummary.textContent=t('movementExtras');
 movement.querySelector('details').append(movement.querySelector('[data-i="movementHint"]'));
 entry.id='daily-entry';split.before(entry);split.remove();daily.append(recent);const recentFold=fold(recent,'recent');recentFold.classList.add('recent-fold');
 daily.insertAdjacentHTML('afterbegin',`<div class="view-switch" id="daily-switch" role="group" aria-label="${esc(t('daily'))}"><button type="button" data-daily-view="entry" aria-pressed="true">${txt('dailyEntry')}</button><button type="button" data-daily-view="overview" aria-pressed="false">${txt('dailyOverview')}</button></div>`);
 $('#daily-switch').onclick=e=>{const button=e.target.closest('[data-daily-view]');if(button)showDaily(button.dataset.dailyView,true);};
 const overview=document.createElement('section');overview.id='daily-overview';overview.hidden=true;
 for(const child of Array.from(daily.children)){if(child.id!=='daily-switch'&&child.id!=='daily-entry')overview.append(child);}
 daily.append(overview);
 daily.insertAdjacentHTML('afterbegin',`<div class="home-report-shortcut"><a href="https://docs.google.com/forms/d/e/1FAIpQLSezmKVeQHdtyOB4mSTq0LgRAq2Pf_on9ZVsc6Kpl3HjU-1fUQ/viewform" target="_blank" rel="noopener noreferrer">${txt('openReportForm')}<span aria-hidden="true">↗</span></a></div>`);
 $$('.filters').forEach(f=>f.classList.add('compact-filter'));
};
function canSwitch(id){
 const f=$('#batch-form');if(pending){toast(t('pending'));return false;}
 if(f.dataset.dirty==='1'){f.querySelector('.form-error').textContent=t('saveBeforeSwitch');$('#batch-editor').scrollIntoView({block:'start',behavior:'smooth'});return false;}return true;
}
function filterGroups(){
 const search=$('#batch-search').value.trim().toLocaleLowerCase(),status=$('#batch-status').value;let shown=0;
 const byKey=new Map(groups().map(g=>[g.key,g]));
 $$('#batch-settings .cohort-setting').forEach(card=>{const group=byKey.get(card.dataset.cohortKey);const matches=(card.contains($('#batch-editor'))&&!$('#batch-editor').hidden)||group&&(!status||group.members.some(b=>b.status===status))&&(!search||[group.name,group.date,...group.members.map(barnOf)].join(' ').toLocaleLowerCase().includes(search));card.hidden=!matches;if(matches)shown++;});
 $('#batch-no-match').hidden=shown>0;
}
function attachEditor(){
 const f=$('#batch-form'),r=data?.batches.find(b=>b.id===f.dataset.editId);if(!r)return;
 const group=$$('#batch-settings .cohort-setting').find(el=>el.dataset.cohortKey===keyOf(r));if(group){group.open=true;group.hidden=false;group.append($('#batch-editor'));}
 editorFields(r);const cancel=f.querySelector('[data-action=cancelEdit]');cancel.dataset.i='cancelEdit';cancel.textContent=t('cancelEdit');
 $('#batch-editor').hidden=false;$('#batch-editor-title').textContent=`${t('editHere')}：${r.name}｜${barnOf(r)}`;
}
renderSettings=()=>{
 if(!data)return;
 renderWorkbookSources();
 preserveBox('barn-settings',table(['barn','feedVendor','edit'],data.barns.map(r=>`<tr><td><strong>${esc(r.name)}</strong>${r.group?`<small>${esc(r.group)}</small>`:''}</td><td>${esc(r.feed_vendor||'—')}</td><td>${recordActions('barns',r)}</td></tr>`)));
 // Do not detach/rebuild the active editor: IME, keyboard focus and unsaved values stay intact.
 const editor=$('#batch-editor'),editing=editor.contains(document.activeElement);
 if(!editing){
  $('#batch-workspace').append(editor);
  preserveBox('batch-settings',groups().map(g=>{
   const known=g.members.filter(b=>b.entry_count!=null),missing=g.members.length-known.length,means=[...new Set(g.members.flatMap(entryMeans))];
   const mean=entryMeanText(means)+' kg';
   return `<details class="cohort-setting" data-cohort-key="${esc(g.key)}" data-key="setup-${esc(g.key)}"><summary><span class="cohort-title">${esc(g.name)}<span class="cohort-date">${g.date}</span></span><span class="cohort-barns">${g.members.map(b=>esc(barnOf(b))).join('、')}</span><span class="cohort-meta">${t('knownEntry')} ${fmt(known.reduce((n,b)=>n+b.entry_count,0),0)} ${t('heads')}${missing?' · '+missing+' '+t('missingBarns'):''} · ${t('entryMeanShort')} ${mean}</span></summary><div class="cohort-members">${g.members.map(b=>`<article class="member-row" data-member="${b.id}"><div class="member-name"><strong>${esc(barnOf(b))}</strong><span class="pill">${t(b.status)}</span></div><div><span class="compact-label">${t('entry')}</span><strong>${fmt(b.entry_count,0)}</strong></div><div><span class="compact-label">${t('entryMeanShort')}</span><strong>${entryMeanText(entryMeans(b))} <small>kg</small></strong></div><div class="member-actions">${recordActions('batches',b)}</div></article>`).join('')}</div></details>`;
  }).join('')+`<p id="batch-no-match" class="hint" hidden>${t('noMatchingBatch')}</p>`);
  filterGroups();attachEditor();
 }
 if(me?.role==='admin'&&!document.activeElement?.closest('#user-results'))loadAdmin();
};
edit=(kind,id)=>{
 if(kind==='batches'&&!canSwitch(id))return;
 base.edit(kind,id);
 if(kind==='movements'){const r=data.movements.find(r=>r.id===id);if(r?.outgoing_destination||r?.outgoing_trip)$('#movement-form details').open=true;}
 if(kind==='batches'){attachEditor();$('#batch-form').querySelectorAll('details').forEach(d=>d.open=false);$('#batch-editor').scrollIntoView({block:'start',behavior:'smooth'});}
 if(kind==='barns'){const fold=$('#barn-form').closest('.settings-fold');if(fold)fold.open=true;$('#barn-form').scrollIntoView({block:'start',behavior:'smooth'});}
};
finishForm=f=>{base.finishForm(f);if(f.id==='batch-form'){$('#batch-editor').hidden=true;$('#batch-workspace').append($('#batch-editor'));}};
restorePending=()=>{base.restorePending();if(pending?.formId==='batch-form'){const f=$('#batch-form');const id=pending.path.split('/').at(-1);if(data?.batches.some(b=>b.id===id)){f.dataset.editId=id;f.dataset.revision=pending.body.revision;attachEditor();}else $('#batch-editor').hidden=false;}};
enter=async user=>{
 dailyView='entry';await base.enter(user);showDaily('entry');
 $('#password-card').open=!!user.must_change;
};
renderHome=async()=>{
 const openDetails=new Set($$('#barns details[data-key][open]').map(el=>el.dataset.key));
 const dashboard=await base.renderHome();if(!data||!dashboard)return;
 const result=b=>dashboard?.batches.find(x=>x.id===b.id);
 const currentIds=new Set(dashboard.current_farm?.ids||data.batches.filter(b=>b.status==='active').map(b=>b.id));
 const row=b=>{const r=result(b),h=r?.herd;return `<article class="barn-card overview-barn"><button class="overview-barn-link" data-add-barn="${b.barn_id}" data-add-batch="${b.id}"><strong>${esc(barnOf(b))}</strong><small>${esc(displayAge(r?.age_days))}</small></button><strong class="overview-heads">${fmt(h?.remaining,0)}</strong><strong class="overview-dead">${fmt(h?.dead,0)}</strong><strong class="overview-sold">${fmt(h?.sold,0)}</strong><strong class="overview-culled">${fmt(h?.culled,0)}</strong><div class="barn-survival">${h?.survival==null?`<details><summary aria-label="${esc(t('sourceLimit'))}">— ⓘ</summary><p>${t('sourceLimit')}</p></details>`:`<strong>${fmt(h.survival)}%</strong>`}</div></article>`;};
 const total=g=>{
  const h=(dashboard.current_farm?.cohorts||dashboard.cohorts)?.find(c=>c.cohort===g.key)?.herd;
  const missing=[h?.denominator==null?t('cohortMissingEntry'):h.denominator<=0?t('cohortZeroEntry'):'',h?.dead==null?t('cohortMissingDead'):''].filter(Boolean);
  return `<div class="cohort-total" data-cohort-total="${esc(g.key)}"><div class="cohort-total-head cohort-remaining"><span title="${esc(t('cohortRemaining'))}">${t('cohortRemainingShort')}</span><strong>${fmt(h?.remaining,0)} <small>${t('heads')}</small></strong></div><details data-key="cohort-basis-${esc(g.key)}"><summary class="cohort-total-head" aria-label="${esc(t('cohortBasis'))}"><span>${t('survivalShort')}</span><strong>${h?.survival==null?'—':fmt(h.survival)+'%'} <small aria-hidden="true">ⓘ</small></strong></summary><p>${t('asOf')} ${esc(dashboard.as_of)}</p><p>${t('currentFarmBasis')}：${g.members.filter(b=>currentIds.has(b.id)).map(b=>esc(barnOf(b))).join('、')}</p><dl><div><dt>${t('denominator')}</dt><dd>${fmt(h?.denominator,0)} ${t('heads')}</dd></div><div><dt>${t('dead')}</dt><dd>${fmt(h?.dead,0)} ${t('heads')}</dd></div></dl><p>${t('cohortFormula')}</p>${missing.length?`<p class="warning-text">${missing.map(esc).join('；')}</p>`:''}</details></div>`;
 };
 preserveBox('barns',groups().filter(g=>g.members.some(b=>currentIds.has(b.id))).map(g=>`<section class="overview-cohort"><div class="overview-cohort-heading"><h3>${esc(g.name)}</h3><span>${g.date}</span></div>${total(g)}<div class="overview-columns"><span>${t('barn')}</span><span>${t('currentHeadsShort')}</span><span>${t('cumulativeDeadShort')}</span><span>${t('cumulativeSoldShort')}</span><span>${t('cumulativeCulledShort')}</span><span>${t('survivalShort')}</span></div>${g.members.filter(b=>currentIds.has(b.id)).map(row).join('')}</section>`).join('')||empty());
 $$('#barns details[data-key]').forEach(el=>el.open=openDetails.has(el.dataset.key));
 $('#barns').classList.add('compact-barns');
 let archive=$('#cleared-records');if(!archive){archive=document.createElement('details');archive.id='cleared-records';archive.className='card';$('#barns').after(archive);}
 const cleared=data.batches.filter(b=>b.entry_date<=dashboard.as_of&&(b.status==='ended'||result(b)?.herd.remaining===0)).sort((a,b)=>b.entry_date.localeCompare(a.entry_date)||compareBarn(a,b));
 preserveBox('cleared-records',`<summary>${t('clearedRecords')} ${cleared.length}</summary><p class="hint">${t('clearedHint')}</p>${cleared.map(b=>`<article class="cleared-record"><strong>${esc(b.name)} · ${esc(barnOf(b))}</strong><small>${t(b.status==='ended'?'ended':'cleared')}</small><div class="actions"><button type="button" data-cleared-history="${b.id}">${t('viewHistory')}</button><button type="button" data-cleared-report="${b.id}">${t('weeklyReport')}</button></div></article>`).join('')||empty()}`);
 archive.hidden=!cleared.length;

 let hint=$('#overview-hint');if(!hint){hint=document.createElement('p');hint.id='overview-hint';hint.className='hint';$('#barns').before(hint);}hint.textContent=t('currentFarmBasis')+'。'+t('overviewHint');
 showDaily(dailyView);
};
clickAction=e=>{
 const archiveButton=e.target.closest('[data-cleared-history],[data-cleared-report]');
 if(archiveButton){
  const record=data.batches.find(b=>b.id===(archiveButton.dataset.clearedHistory||archiveButton.dataset.clearedReport));if(!record)return;
  if(archiveButton.dataset.clearedReport){document.dispatchEvent(new CustomEvent('pigledger:weekly-open',{detail:{batch_id:record.id}}));return;}
  const f=$('#history-filter');f.reset();if(f.elements.scope_type){f.elements.scope_type.value='barn';f.elements.scope_type.dispatchEvent(new Event('change'));}f.elements.barn_id.value=record.barn_id;updateFilterBatch(f);f.elements.batch_id.value=record.id;syncFilters(f);location.hash='history';setPage('history',false);renderCurrent();return;
 }
 const b=e.target.closest('button');if(b?.dataset.addBatch){const f=$('#movement-form');showDaily('entry');f.elements.barn_id.value=b.dataset.addBarn;updateScope(f.querySelector('.scope'));f.elements.batch_id.value=b.dataset.addBatch;f.scrollIntoView({block:'start',behavior:'smooth'});return;}
 return base.clickAction(e);
};
})();
