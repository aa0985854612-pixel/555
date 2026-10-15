'use strict';
/* Shared UI for source history, compact filters and account security. */
(() => {
Object.assign(words,{
 scopeType:['查詢範圍','Phạm vi'],allFarm:['全場','Toàn trại'],cohort:['跨棟批次','Lứa qua các chuồng'],oneBarn:['單棟','Một chuồng'],organization:['整組','Nhóm'],singleBatch:['單棟批次','Lứa tại chuồng'],recordKind:['紀錄類別','Loại bản ghi'],movements:['豬隻異動','Biến động đàn'],deliveries:['飼料到料','Nhập thức ăn'],usages:['實際用料','Tiêu thụ'],sourceStatus:['資料狀態','Trạng thái dữ liệu'],missingOnly:['待補日期／資料','Cần bổ sung ngày/dữ liệu'],sourceMean:['來源提供的均重（樣本頭數未知）','TB từ nguồn (chưa rõ số mẫu)'],sourceMeanShort:['來源均重','TB từ nguồn'],wholeCohort:['整批來源，未分棟','Nguồn cả lứa, chưa chia chuồng'],archive:['歷史舊表','Bảng lịch sử'],dateUnknown:['日期待補','Cần bổ sung ngày'],sourceCell:['來源位置','Ô nguồn'],entryMean:['入場均重公斤／隻（選填）','TB khi nhập kg/con (tùy chọn)'],entryMeanDate:['均重量測日期（空白用進場日）','Ngày đo TB (trống: ngày nhập)'],entryMeanSource:['入場均重資料來源','Nguồn TB khi nhập'],entryMeanNote:['入場均重備註','Ghi chú TB khi nhập'],entryCountSource:['分棟進場頭數的可靠來源','Nguồn đáng tin số nhập từng chuồng'],entryUnknownHint:['缺單棟進場頭數或歷史死亡時，育成率顯示 —；不從暫定存欄反推。可在批次進階設定補入有來源的進場頭數。','Thiếu số nhập hoặc chết từng chuồng: hiển thị —; không suy từ tồn tạm tính. Bổ sung số nhập có nguồn trong cài đặt lứa.'],periodDeaths:['查詢期間死亡','Chết trong kỳ lọc'],cohortDetails:['批次與各棟明細','Chi tiết lứa và chuồng'],sourceAdg:['來源均重的估計平均日增重','Tăng trọng ngày ước tính từ TB nguồn'],sourceMeanHint:['未提供樣本頭數的來源均重，不參與加權抽樣合計；跨棟來源也不當成單棟實測。','TB thiếu số mẫu không gộp theo số con; nguồn nhiều chuồng không coi là đo riêng từng chuồng.'],sourcePending:['來源有差異，保留 App 紀錄','Nguồn khác biệt; giữ bản App'],sourceLoad:['展開查看來源與匯入結果','Mở xem nguồn và kết quả nhập'],updateSummary:['更新核對結果','Kết quả đối chiếu cập nhật'],matchedManual:['與 App 對上，未重複新增','Khớp App, không thêm trùng'],keptManual:['保留 App，來源差異留存','Giữ App, lưu khác biệt nguồn'],unchanged:['相同來源明細','Chi tiết nguồn không đổi'],pendingSource:['待核對批次','Lứa cần đối chiếu'],passwordChange:['修改自己的密碼','Đổi mật khẩu của mình'],currentPassword:['目前密碼','Mật khẩu hiện tại'],newPassword:['新密碼（至少12字元）','Mật khẩu mới (ít nhất 12 ký tự)'],confirmPassword:['再次輸入新密碼','Nhập lại mật khẩu mới'],passwordMismatch:['兩次新密碼不一致','Hai mật khẩu mới không khớp'],passwordChanged:['密碼已變更，請重新登入','Đã đổi mật khẩu; đăng nhập lại'],passwordRequired:['首次登入請先修改密碼，再使用其他功能。','Lần đầu đăng nhập: đổi mật khẩu trước khi dùng.'],setupLink:['產生一次性設定連結（舊密碼失效）','Tạo liên kết đặt mật khẩu một lần (hủy mật khẩu cũ)'],setupHint:['連結有效48小時、使用一次即失效。請私下交給對應使用者；重發會使舊連結失效。','Liên kết dùng một lần trong 48 giờ. Gửi riêng đúng người; cấp lại sẽ hủy liên kết cũ.'],copyLink:['複製設定連結','Sao chép liên kết'],copied:['已複製，請私下分享','Đã sao chép; chia sẻ riêng'],activateAccount:['設定帳號密碼','Đặt mật khẩu tài khoản'],activateHint:['設定完成後，以自己的帳號密碼登入。','Sau khi đặt, đăng nhập bằng tài khoản của bạn.'],setupComplete:['密碼已設定，請登入','Đã đặt mật khẩu; hãy đăng nhập'],firstChange:['首次登入需更換密碼','Cần đổi mật khẩu khi đăng nhập lần đầu'],adminHint:['每人使用自己的帳號。唯讀可查看；編輯人員可新增及更正自己登記的日常資料；管理員管理設定及重要更正。','Dùng tài khoản riêng. Chỉ xem: đọc; nhân viên: thêm/sửa bản ghi hằng ngày của mình; quản trị: cài đặt và sửa quan trọng.'],workbookHint:['新版 Excel 會與既有來源及 App 紀錄比對，先預覽再匯入。只有第一次建立來源時才需填分棟盤點；有衝突保留 App。','Excel mới được đối chiếu với nguồn và App; xem trước rồi nhập. Chỉ nguồn đầu cần kiểm kê từng chuồng; xung đột giữ App.'],dailySub:['先登記今天的異動，現況往下查看。','Ghi biến động hôm nay; xem tình trạng bên dưới.']
});
Object.assign(errorWords,{
 password_change_required:['請先更換自己的密碼','Hãy đổi mật khẩu trước'],invalid_setup_link:['設定連結無效、已使用或已過期，請管理員重發','Liên kết không hợp lệ, đã dùng hoặc hết hạn; nhờ quản trị cấp lại'],use_own_password_form:['請使用「修改自己的密碼」','Dùng mục đổi mật khẩu của mình'],entry_source_required:['補入分棟進場頭數時，請填可靠來源','Khi bổ sung số nhập từng chuồng, nhập nguồn đáng tin'],legacy_entry_total_mismatch:['各棟進場合計與來源批次不符，尚未儲存','Tổng nhập từng chuồng không khớp nguồn; chưa lưu']
});
Object.assign(errorWords,{invalid_current_password:['目前密碼不正確，請重新輸入','Mật khẩu hiện tại không đúng'],heads_unknown:['這棟的來源異動尚未分配，請先核對頭數','Biến động nguồn chưa phân chuồng; đối chiếu số con trước']});
Object.assign(words,{recorded:['使用者登記','Ghi trong App']});
const base={build,collect,finishForm,edit,selections,renderCurrent,renderSettings,clickAction,rowsHTML,workbookHTML,renderWorkbookSources,filterBox};
const sourceCache=new Map(), setupLinks=new Map();
let cohortFingerprint='', activationToken='';
const fragment=new URLSearchParams(location.hash.slice(1));
if(fragment.has('activate')){activationToken=fragment.get('activate')||'';history.replaceState(null,'',location.pathname);}
const rowBarn=r=>data.barns.find(b=>b.id===(r.barn_id||data.batches.find(b=>b.id===r.batch_id)?.barn_id))?.name||(r.barn_number!=null?r.barn_number+' '+t('barn'):t('wholeCohort'));
const meanOf=r=>r.source_mean?r.mean_kg:(r.count&&r.total_kg!=null?r.total_kg/r.count:null);

filterBox=(id,extras='')=>{
 if(id==='stats-filter'||id==='weight-filter')extras='';
 if(id==='history-filter')extras=select('recordKind','record_kind',['movements','weights','deliveries','usages'].map(k=>option(k,k)).join(''))+extras+select('sourceStatus','missing',option('','all')+option('1','missingOnly'));
 return `<form class="filters" id="${id}">${input('from','from','date')}${input('to','to','date')}${select('scopeType','scope_type',option('all','allFarm')+option('cohort','cohort')+option('barn','oneBarn')+option('group','organization'))}${select('cohort','cohort',option('','all'))}${select('group','group',option('','all'))}${select('barn','barn_id',option('','all'))}${select('singleBatch','batch_id',option('','all'))}${extras}<div class="actions"><button data-i="query">${t('query')}</button><button type="button" data-action="clear" data-i="clear">${t('clear')}</button></div></form>`;
};
function filterScope(f,clear=false){
 const mode=val(f,'scope_type')||'all';
 const shown={cohort:mode==='cohort',group:mode==='group',barn_id:mode==='barn'||mode==='cohort',batch_id:mode==='barn'};
 for(const [name,visible] of Object.entries(shown)){const el=f.elements.namedItem(name);el.closest('label').hidden=!visible;if(clear&&!visible)el.value='';}
 if(f.id==='history-filter'){const type=f.elements.type;type.closest('label').hidden=val(f,'record_kind')!=='movements';if(type.closest('label').hidden)type.value='';}
 updateFilterBatch(f);
}
build=()=>{
 base.build();
 const daily=$('#page-daily');daily.prepend($('#movement-form').closest('.split'));
 const batch=$('#batch-form');batch.querySelector('details .grid').insertAdjacentHTML('beforeend',input('entryMean','entry_mean_kg','number','min="0.000001" step="any"')+input('entryMeanDate','entry_mean_date','date')+input('entryMeanSource','entry_mean_source')+input('entryMeanNote','entry_mean_note')+input('entryCountSource','entry_count_source'));
 const settings=$('#page-settings');settings.insertAdjacentHTML('afterbegin',`<div class="card" id="password-card"><h2>${txt('passwordChange')}</h2><p id="password-required" class="note" hidden>${txt('passwordRequired')}</p><form id="password-form"><div class="grid">${input('currentPassword','current_password','password','required autocomplete="current-password"')}${input('newPassword','new_password','password','minlength="12" required autocomplete="new-password"')}${input('confirmPassword','confirm_password','password','minlength="12" required autocomplete="new-password"')}</div><p class="form-error" role="status"></p><button class="primary">${txt('saveSettings')}</button></form></div>`);
 $('#password-form').onsubmit=changeOwnPassword;
 const workbook=$('#workbook-form');workbook.elements.counts_text.required=false;workbook.elements.counts_as_of.required=false;
 $$('.filters').forEach(f=>{
  f.elements.scope_type.addEventListener('change',()=>{filterScope(f,true);syncFilters(f);});
  f.elements.cohort.addEventListener('change',()=>{f.elements.batch_id.value='';updateFilterBatch(f);});
  f.elements.record_kind?.addEventListener('change',()=>filterScope(f));filterScope(f);
 });
 $('#user-form').insertAdjacentHTML('beforebegin',`<p class="hint">${txt('adminHint')}</p><p class="hint">${txt('setupHint')}</p>`);
 $('#login-view').insertAdjacentHTML('beforeend',`<form id="activation-form" class="card" hidden><h2>${txt('activateAccount')}</h2><p>${txt('activateHint')}</p>${input('username','username','text','required autocomplete="username"')}${input('newPassword','password','password','minlength="12" required autocomplete="new-password"')}${input('confirmPassword','confirm','password','minlength="12" required autocomplete="new-password"')}<p class="form-error" role="status"></p><button class="primary">${txt('activateAccount')}</button></form>`);
 $('#activation-form').onsubmit=activateAccount;
 if(activationToken){$('#login-form').hidden=true;$('#activation-form').hidden=false;$('#activation-form').elements.username.value=fragment.get('user')||'';}
};
collect=f=>{
 const d=base.collect(f);
 if(f.id==='batch-form'){d.entry_mean_kg=val(f,'entry_mean_kg')===''?null:Number(val(f,'entry_mean_kg'));d.entry_mean_date=val(f,'entry_mean_date')||null;}
 return d;
};
finishForm=f=>{base.finishForm(f);if(f.id==='batch-form')for(const name of ['entry_mean_kg','entry_mean_date','entry_mean_source','entry_mean_note','entry_count_source'])f.elements[name].value='';};
edit=(kind,id)=>{base.edit(kind,id);if(kind==='batches'){const r=data.batches.find(b=>b.id===id),f=$('#batch-form');if(r.legacy_source&&(r.legacy_group?.expected_members>1||r.entry_count==null)){f.elements.entry_count.readOnly=false;f.elements.entry_count.required=false;}for(const name of ['entry_mean_kg','entry_mean_date','entry_mean_source','entry_mean_note','entry_count_source'])f.elements[name].value=r[name]??'';}};
updateFilterBatch=(f,reset=false)=>{const el=f.elements.batch_id;if(!el||!data)return;replaceOptions(el,option('','all')+data.batches.filter(b=>(!val(f,'barn_id')||b.barn_id===val(f,'barn_id'))&&(!val(f,'cohort')||(b._cohort_key||b.name+'|'+b.entry_date)===val(f,'cohort'))).map(b=>`<option value="${b.id}">${esc(batchName(b.id))}</option>`).join(''));};
selections=(force=false)=>{
 base.selections(force);const fp=JSON.stringify([data.cohorts,lang]);
 if(force||fp!==cohortFingerprint){cohortFingerprint=fp;$$('.filters [name=cohort]').forEach(el=>replaceOptions(el,option('','all')+(data.cohorts||[]).map(c=>`<option value="${esc(c.key)}">${esc(c.name)} · ${esc(c.entry_date)}${c.archive?' · '+esc(t('archive')):''}</option>`).join('')));}
 $$('.filters').forEach(f=>filterScope(f));
};
syncFilters=source=>{
 for(const key of ['from','to','scope_type','cohort','group','barn_id','batch_id'])sharedFilters[key]=val(source,key);
 localStorage.setItem('pig-filters',JSON.stringify(sharedFilters));
 $$('.filters').forEach(f=>{if(f===source)return;for(const key of ['from','to','scope_type','cohort','group','barn_id'])f.elements[key].value=sharedFilters[key]|| (key==='scope_type'?'all':'');updateFilterBatch(f);f.elements.batch_id.value=sharedFilters.batch_id||'';filterScope(f);});
};
query=f=>{const p=new URLSearchParams();for(const key of ['from','to','barn_id','batch_id','cohort','group','type','vendor','item','missing'])if(val(f,key))p.set(key,val(f,key));return p.toString();};
recordActions=(kind,r)=>{
 if((r.legacy_source&&!['batches','barns'].includes(kind))||r.source_mean||r._source_derived)return esc(t('legacyReadonly'));
 const edit=me.role==='admin'||(me.role==='staff'&&r.created_by===me.id&&['movements','deliveries','usages','weights'].includes(kind));
 return (edit?`<button data-edit="${kind}" data-id="${r.id}">${esc(t('edit'))}</button>`:'')+(me.role==='admin'?`<button class="danger" data-delete="${kind}" data-id="${r.id}">${esc(t('delete'))}</button>`:'');
};
rowsHTML=(kind,rows)=>{
 if(!rows.length)return empty();
 if(kind==='movements')return table(['date','barn','batch','type','quantity','note','sourceCell','edit'],rows.map(r=>`<tr><td>${esc(r.date||t('dateUnknown'))}</td><td>${esc(rowBarn(r))}</td><td>${esc(r.legacy_batch||data.batches.find(b=>b.id===r.batch_id)?.name||t('unassigned'))}${r.archive?'<br>'+esc(t('archive')):''}</td><td>${esc(t(r.type))}</td><td>${fmt(r.quantity,0)}</td><td>${esc(r.note)}</td><td>${esc(r.source_cell||t('recorded'))}</td><td>${recordActions(kind,r)}</td></tr>`));
 if(kind==='weights')return table(['date','barn','batch','weightCount','totalWeight','mean','sourceCell','edit'],rows.map(r=>`<tr><td>${esc(r.date||t('dateUnknown'))}${r.age_weeks_hint?'<br>'+esc(r.age_weeks_hint):''}</td><td>${esc(rowBarn(r))}</td><td>${esc(r.legacy_batch||data.batches.find(b=>b.id===r.batch_id)?.name||'')}<br><small>${esc(r.pen||'')}</small></td><td>${fmt(r.count,0)}</td><td>${fmt(r.total_kg)}</td><td>${fmt(meanOf(r))}<br><small>${esc(t(r.source_mean?'sourceMean':'sample'))}</small></td><td>${esc(r.source_cell||'')}<br><small>${esc(r.note||'')}</small></td><td>${recordActions(kind,r)}</td></tr>`));
 return base.rowsHTML(kind,rows);
};
renderCurrent=async()=>{
 if(current!=='history'&&current!=='weights')return base.renderCurrent();
 const ticket=++renderTicket,page=current,f=$('#'+(page==='history'?'history-filter':'weight-filter')),kind=page==='history'?val(f,'record_kind'):'weights';
 try{
  const rows=await api('/api/'+kind+'?'+query(f));if(ticket!==renderTicket||current!==page)return;
  if(page==='history'){$('#history-results').innerHTML=(kind==='weights'?'<p class="hint">'+esc(t('sourceMeanHint'))+'</p>':'')+rowsHTML(kind,rows);return;}
  $('#weight-results').innerHTML=rowsHTML('weights',rows);
  const valid=rows.filter(r=>r.count>0&&r.total_kg>0),grouped={};
  valid.forEach(r=>{const key=r.batch_id+'|'+r.date,g=grouped[key]||={date:r.date,batch_id:r.batch_id,count:0,total:0};g.count+=r.count;g.total+=r.total_kg;});
  const html=Object.values(grouped).length?table(['date','batch','weightCount','mean'],Object.values(grouped).map(g=>`<tr><td>${g.date}</td><td>${esc(batchName(g.batch_id))}</td><td>${fmt(g.count,0)}</td><td>${fmt(g.total/g.count)}</td></tr>`)):'';
  preserveBox('weight-summary',html+sampleSummary(valid)+`<p class="hint">${esc(t('sourceMeanHint'))}</p>`);
 }catch(e){toast(messageError(e));}
};
statHTML=s=>{
 const c=s.cumulative;
 let html=`<h2>${t('asOf')} · ${esc(s.as_of)}</h2><div class="metrics">${metric('remaining',fmt(c.remaining,0),t('heads'),true)}${metric('outgoing',fmt(c.outgoing,0),t('saleAndCull'))}${metric('dead',fmt(c.dead,0),t('heads'))}${metric('survival',c.survival==null?'—':fmt(c.survival)+'%',t('deathOnly'))}</div>`;
 if(s.interval)html+=`<div class="card"><h2>${t('interval')}</h2>${table(['entry','sale','cull','death'],['<tr>'+['entry','sale','cull','death'].map(k=>'<td>'+fmt(s.interval[k],0)+'</td>').join('')+'</tr>'])}</div>`;
 html+=`<div class="card"><h2>${t('cohortDetails')}</h2><p class="hint">${t('entryUnknownHint')}</p>${(s.cohorts||[]).map(cohort=>{
  const p=cohort.source_performance;
  return `<details data-key="cohort-${esc(cohort.cohort)}"><summary>${esc(cohort.name)} · ${esc(displayAge(cohort.age_days))} · ${t('periodDeaths')} ${fmt(cohort.period_deaths,0)} · ${t('survival')} ${cohort.herd.survival==null?'—':fmt(cohort.herd.survival)+'%'}</summary>${table(['barn','remaining','entry','dead','survival','periodDeaths'],cohort.barns.map(b=>`<tr><td>${esc(data.barns.find(x=>x.id===b.barn_id)?.name||'')}</td><td>${fmt(b.herd.remaining,0)}</td><td>${fmt(b.herd.entry,0)}</td><td>${fmt(b.herd.dead,0)}</td><td>${b.herd.survival==null?'—':fmt(b.herd.survival)+'%'}</td><td>${fmt(b.period_deaths,0)}</td></tr>`))}${p?`<p>${t('sourceAdg')}: <strong>${fmt(p.adg)}</strong> ${t('kgPerDay')}</p><p class="hint">${p.first.date} → ${p.last.date} · ${p.days} ${t('days')} · ${fmt(p.first.mean)} → ${fmt(p.last.mean)} kg · ${t('gainPerPig')}: ${fmt(p.delta)} kg</p>${p.composition_changed?'<p class="note">'+t('composition')+'</p>':''}${p.delta<0?'<p class="warning-text">'+t('weight_decreased')+'</p>':''}<p class="hint">${t('sourceMeanHint')}</p>`:''}${s.batches.filter(b=>cohort.barns.some(x=>x.id===b.id)&&b.performance.last).map(perfHTML).join('')}</details>`;
 }).join('')||empty()}</div>`;
 html+=`<details class="card" data-key="feed-performance"><summary>${t('feed')} · ${t('estimatedFcr')}: ${s.aggregate_fcr==null?t('insufficient'):fmt(s.aggregate_fcr)}</summary><div class="performance"><div>${t('delivered')}<strong>${fmt(s.delivery_kg)}</strong></div><div>${t('consumed')}<strong>${fmt(s.consumption_kg)}</strong></div></div><p class="hint">${t('feedPartial')}</p><p class="hint">${t('aggregateHint')}</p></details>`;
 return html;
};
workbookHTML=book=>{
 if(!book.update_summary)return base.workbookHTML(book);
 const s=book.update_summary;
 return `<h3>${t('updateSummary')}</h3><p>${t('importedCount')}: ${s.added} · ${t('matchedManual')}: ${s.matched_manual} · ${t('unchanged')}: ${s.unchanged}</p>${s.pending_cohorts.length?`<p class="note">${t('sourcePending')}: ${s.pending_cohorts.map(c=>esc(c.name)).join('、')}</p>`:''}${table(['batch','importedCount','unchanged','pendingSource'],s.changes.map(c=>`<tr><td>${esc(c.name)}</td><td>${c.added}</td><td>${c.unchanged}</td><td>${c.pending.length?esc(t('keptManual')):'—'}</td></tr>`))}<p class="hint">${t('sourceMeanHint')}</p>`;
};
renderWorkbookSources=()=>{
 if(!data)return;if(workbookDraft)preserveBox('workbook-preview',workbookHTML(workbookDraft.preview));
 const box=$('#workbook-sources');if(box.contains(document.activeElement))return;
 const fp=JSON.stringify([data.workbooks,lang]);if(box.dataset.fingerprint===fp)return;box.dataset.fingerprint=fp;
 box.innerHTML=data.workbooks.map(b=>`<details data-key="book-${b.id}"><summary>${esc(b.filename)} · ${esc(b.as_of||'')}</summary><button data-download-source="${b.id}">${t('originalFile')}</button><p class="hint">${t('sourceLoad')}</p><div data-book-details="${b.id}"></div></details>`).join('');
 box.querySelectorAll('details').forEach(el=>el.addEventListener('toggle',async()=>{
  if(!el.open)return;const id=el.querySelector('[data-book-details]').dataset.bookDetails;
  try{if(!sourceCache.has(id))sourceCache.set(id,await api('/api/workbooks/'+id+'/details'));el.querySelector('[data-book-details]').innerHTML=workbookHTML(sourceCache.get(id));}catch(e){toast(messageError(e));}
 }));
};
renderSettings=()=>{
 if(!data)return;base.renderSettings();
 $('#batch-settings').innerHTML=table(['barn','batch','entryDate','entry','entryMean','entryMeanDate','status','edit'],data.batches.map(r=>`<tr><td>${esc(data.barns.find(b=>b.id===r.barn_id)?.name||'')}</td><td>${esc(r.name)}</td><td>${r.entry_date}</td><td>${fmt(r.entry_count,0)}</td><td>${fmt(r.entry_mean_kg)}</td><td>${esc(r.entry_mean_date||'—')}</td><td>${t(r.status)}</td><td>${recordActions('batches',r)}</td></tr>`));
};
previewWorkbook=async event=>{
 event.preventDefault();const f=event.target,b=f.querySelector('[type=submit]');if(!f.reportValidity())return;b.disabled=true;$('#apply-workbook').disabled=true;
 try{const payload=await workbookPayload(),preview=await api('/api/workbook/preview',{method:'POST',body:JSON.stringify(payload)});if(preview.update_summary)payload.preview_token=preview.update_summary.preview_token;workbookDraft={payload,preview,key:crypto.randomUUID(),user:me.id};$('#workbook-preview').innerHTML=workbookHTML(preview);f.querySelector('.form-error').textContent='';$('#apply-workbook').disabled=false;}catch(e){f.querySelector('.form-error').textContent=messageError(e);}finally{b.disabled=false;}
};
clickAction=e=>{
 const b=e.target.closest('button');if(!b)return;
 if(b.dataset.action==='clear'){const f=b.closest('form');f.reset();filterScope(f,true);syncFilters(f);renderCurrent();return;}
 if(b.dataset.export&&b.dataset.filter==='history-filter'){download('/api/export?kind='+val($('#history-filter'),'record_kind')+'&'+query($('#history-filter')));return;}
 if(b.dataset.setupUser){issueSetup(b);return;}
 if(b.dataset.copySetup){const value=setupLinks.get(b.dataset.copySetup);if(value)navigator.clipboard.writeText(value).then(()=>toast(t('copied'))).catch(()=>{const input=b.parentElement.querySelector('.setup-link');input.focus();input.select();});return;}
 base.clickAction(e);
};
loadAdmin=async()=>{
 if(me?.role!=='admin'||document.activeElement?.closest('#user-results'))return;
 try{
  const [users,audit]=await Promise.all([api('/api/users'),api('/api/audit')]);if(document.activeElement?.closest('#user-results'))return;
  $('#user-results').innerHTML=users.map(u=>`<div class="user-row" data-user="${u.id}"><input class="account-name" aria-label="${t('username')}" value="${esc(u.username)}"><select aria-label="${t('role')}">${['admin','staff','viewer'].map(k=>`<option value="${k}" ${u.role===k?'selected':''}>${t(k)}</option>`).join('')}</select><label class="check"><input type="checkbox" ${u.active?'checked':''}>${t('enabled')}</label><button data-update-user="${u.id}">${t('saveSettings')}</button><input type="password" autocomplete="new-password" minlength="12" aria-label="${t('resetPassword')}" placeholder="${t('resetPassword')}"><input type="hidden" value="${esc(JSON.stringify({role:u.role,active:u.active,revision:u.revision}))}"><button type="button" data-setup-user="${u.id}" data-revision="${u.revision}" ${u.id===me.id?'disabled':''}>${t('setupLink')}</button>${u.must_change?'<small>'+t('firstChange')+'</small>':''}${setupLinks.has(u.id)?`<div class="full"><input class="setup-link" readonly aria-label="${t('setupLink')}" value="${esc(setupLinks.get(u.id))}"><button type="button" data-copy-setup="${u.id}">${t('copyLink')}</button></div>`:''}</div>`).join('');
  preserveBox('audit-results',audit.map(a=>`<details data-key="audit-${a.seq}"><summary>${esc(a.timestamp)} · ${esc(a.username||a.user_id)} · ${esc(a.action)} / ${esc(a.kind)}</summary><p>${t('before')}</p><pre>${esc(a.before_value||'—')}</pre><p>${t('after')}</p><pre>${esc(a.after_value||'—')}</pre></details>`).join(''));
 }catch(e){toast(messageError(e));}
};
updateUser=async row=>{
 try{await api('/api/users/'+row.dataset.user,{method:'PUT',body:JSON.stringify({username:row.querySelector('.account-name').value,role:row.querySelector('select').value,active:row.querySelector('[type=checkbox]').checked,password:row.querySelector('[type=password]').value,before:JSON.parse(row.querySelector('[type=hidden]').value)})});toast(t('saved'));if(row.dataset.user===me.id)showLogin();else loadAdmin();}catch(e){toast(messageError(e));}
};
async function issueSetup(button){
 button.disabled=true;
 try{const result=await api('/api/users/'+button.dataset.setupUser+'/setup',{method:'POST',body:JSON.stringify({revision:Number(button.dataset.revision)})});const fragment=new URLSearchParams({activate:result.token,user:result.username});setupLinks.set(button.dataset.setupUser,location.origin+'/#'+fragment.toString());await loadAdmin();}catch(e){toast(messageError(e));button.disabled=false;}
}
function showLogin(){me=null;data=null;$('#workspace').hidden=true;$('#login-view').hidden=false;$('#logout').hidden=true;$('#user-name').textContent='';}
async function changeOwnPassword(event){
 event.preventDefault();const f=event.target,error=f.querySelector('.form-error');if(val(f,'new_password')!==val(f,'confirm_password')){error.textContent=t('passwordMismatch');return;}
 const b=f.querySelector('button');b.disabled=true;
 try{await api('/api/password',{method:'POST',body:JSON.stringify({current_password:val(f,'current_password'),new_password:val(f,'new_password')})});f.reset();showLogin();toast(t('passwordChanged'));}catch(e){error.textContent=messageError(e);}finally{b.disabled=false;}
}
async function activateAccount(event){
 event.preventDefault();const f=event.target,error=f.querySelector('.form-error');if(val(f,'password')!==val(f,'confirm')){error.textContent=t('passwordMismatch');return;}
 const b=f.querySelector('button');b.disabled=true;
 try{await api('/api/activate',{method:'POST',body:JSON.stringify({username:val(f,'username'),token:activationToken,password:val(f,'password')})});activationToken='';$('#login-form').elements.username.value=val(f,'username');f.reset();f.hidden=true;$('#login-form').hidden=false;toast(t('setupComplete'));}catch(e){error.textContent=messageError(e);}finally{b.disabled=false;}
}
refresh=async(options={})=>{
 if(refreshing||!me||me.must_change)return;refreshing=true;
 try{
  const incoming=await api('/api/snapshot'+(data?.cursor?'?since='+encodeURIComponent(data.cursor):''));
  if(!incoming.unchanged){data=incoming;if(data.version!==VERSION){$('#connection').textContent=t('update');$('#connection').hidden=false;return;}selections();if(options.render!==false)await renderCurrent();}
  if(navigator.onLine&&!registration?.waiting)$('#connection').hidden=true;
 }catch(e){$('#connection').textContent=t('syncError');$('#connection').hidden=false;}finally{refreshing=false;}
};
enter=async user=>{
 if(activationToken)return;
 me=user;data=null;selectionFingerprint='';cohortFingerprint='';$('#login-view').hidden=true;$('#workspace').hidden=false;$('#logout').hidden=false;$('#user-name').textContent=user.username+' · '+t(user.role);
 $$('#nav a').forEach(el=>el.hidden=!!user.must_change&&el.dataset.page!=='settings');
 $$('#page-settings > *').forEach(el=>{if(el.id==='password-card')return;if(user.must_change){el.dataset.forcedHidden='1';el.hidden=true;}else if(el.dataset.forcedHidden){delete el.dataset.forcedHidden;el.hidden=false;}});
 $('#password-required').hidden=!user.must_change;
 if(user.must_change){setPage('settings',false);return;}
 history.replaceState(null,'',location.pathname+'#daily');setPage('daily',false);await refresh({render:false});
 if(!data)return;
 $$('.filters').forEach(f=>{for(const key of ['from','to','scope_type','cohort','group','barn_id'])if(sharedFilters[key])f.elements[key].value=sharedFilters[key];if(!sharedFilters.scope_type&&sharedFilters.barn_id)f.elements.scope_type.value='barn';updateFilterBatch(f);if(sharedFilters.batch_id)f.elements.batch_id.value=sharedFilters.batch_id;filterScope(f);});
 await renderCurrent();restorePending();persistPending();
};
boot();
})();
