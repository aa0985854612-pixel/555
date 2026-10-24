'use strict';
/* LINE credentials stay server-side. Only admins can bind or disconnect. */
(() => {
Object.assign(words,{
 lineFeedTitle:['LINE 群組收圖設定','Cài nhận ảnh từ nhóm LINE'],lineFeedHint:['綁定後，在群組傳叫料照片會自動整理成待確認。核對後才正式登記。','Sau khi liên kết, ảnh đặt cám trong nhóm thành bản chờ duyệt. Chỉ ghi chính thức sau khi bạn xác nhận.'],
 lineFeedLoading:['讀取設定中…','Đang tải…'],lineFeedReady:['連線資料已填，可綁定群組','Đã có cấu hình, có thể liên kết nhóm'],lineFeedMissing:['尚缺連線資料，暫時不能收圖','Thiếu cấu hình, chưa nhận được ảnh'],lineFeedBound:['已綁定群組','Đã liên kết nhóm'],lineFeedUnbound:['尚未綁定群組','Chưa liên kết nhóm'],lineFeedOperator:['原管理員帳號已停用或變更權限，請重新綁定','Tài khoản quản trị cũ đã tắt hoặc đổi quyền; liên kết lại'],
 lineFeedRefresh:['更新連線狀態','Làm mới trạng thái'],lineFeedPair:['產生群組綁定碼','Tạo mã liên kết nhóm'],lineFeedDisconnect:['解除群組綁定','Hủy liên kết nhóm'],lineFeedDisconnectAsk:['解除後將停止接收這個群組的照片；已建立的待確認清單會保留。確定解除？','Ngừng nhận ảnh nhóm; giữ danh sách chờ duyệt. Hủy liên kết?'],lineFeedPairHint:['10分鐘內，把以下指令傳到已加入機器人的LINE群組。新群組綁定成功後，原群組會停止收圖。','Trong 10 phút, gửi lệnh dưới vào nhóm có bot. Liên kết nhóm mới sẽ ngừng nhận ảnh từ nhóm cũ.'],lineFeedNoCode:['尚未產生綁定碼','Chưa có mã'],lineFeedWebhook:['LINE Webhook 網址','Địa chỉ LINE Webhook'],
 lineFeedSetupTitle:['第一次怎麼設定','Cách thiết lập lần đầu'],lineFeedSetup1:['建立LINE官方帳號並開啟Messaging API；允許加入群組。','Tạo tài khoản LINE Official và bật Messaging API; cho phép vào nhóm.'],lineFeedSetup2:['在Vercel專案的環境變數填入下方三項，再重新部署。權杖與金鑰不需要傳給群組或貼在對話。','Điền ba biến môi trường dưới đây vào dự án Vercel rồi triển khai lại. Không gửi khóa trong nhóm hoặc cuộc trò chuyện.'],lineFeedSetup3:['到LINE Developers貼上Webhook網址，驗證並開啟Use webhook及Webhook redelivery；關閉內建自動回應。','Dán URL Webhook trong LINE Developers, xác minh và bật Use webhook / Webhook redelivery; tắt trả lời tự động.'],lineFeedSetup4:['把機器人邀進群組，再按「產生群組綁定碼」，把指令傳到該群組。','Mời bot vào nhóm, tạo mã rồi gửi lệnh vào nhóm đó.'],lineFeedPrivacy:['綁定群組內的圖片會交給OpenAI辨識，會使用API額度；每小時最多30張。只處理圖片，不匯入一般聊天；網站保留轉錄與來源雜湊，不保存圖片檔案。','Ảnh trong nhóm liên kết được gửi tới OpenAI để nhận dạng, có phí API; tối đa 30 ảnh/giờ. Không nhập trò chuyện thường; lưu bản chép và mã ảnh, không lưu tệp ảnh.'],lineFeedReviewHint:['群組只會建立待確認；請到網站核對並按正式登記。群組打「確認」不會入帳。','Nhóm chỉ tạo bản chờ duyệt; kiểm tra và ghi chính thức trên web. Nhắn xác nhận trong nhóm không ghi sổ.'],lineFeedRecent:['最近收圖狀態','Ảnh nhận gần đây'],lineFeedNone:['尚未收到照片','Chưa nhận ảnh'],lineFeedDone:['已整理，請到待確認核對','Đã chép, hãy đối chiếu danh sách'],lineFeedIgnored:['非叫料圖片，未登記','Không phải ảnh đặt cám, chưa ghi'],lineFeedRetry:['等待LINE重新傳送','Đợi LINE gửi lại'],lineFeedFailed:['未完成，請重新傳清楚的照片或手動新增','Chưa xong, gửi lại ảnh rõ hoặc thêm thủ công'],lineFeedProcessing:['辨識中','Đang nhận dạng'],lineFeedSet:['已填入','Đã điền'],lineFeedUnset:['尚未填入','Chưa điền'],lineFeedOpen:['開啟待確認清單','Mở danh sách chờ duyệt'],lineFeedCopied:['已複製','Đã sao chép'],lineFeedCopy:['複製','Sao chép']
});
Object.assign(errorWords,{
 line_configuration_required:['請先填妥LINE與圖片辨識的環境變數，並重新部署。','Điền cấu hình LINE và nhận ảnh rồi triển khai lại.'],line_operator_unavailable:['請以有效管理員重新綁定群組。','Liên kết lại bằng quản trị viên đang hoạt động.'],line_configuration_conflict:['群組設定衝突，請聯絡系統管理員核對。','Cấu hình nhóm xung đột; liên hệ quản trị viên kiểm tra.']
});
const base={build,enter,translate},box=()=>$('#line-feed-settings');
let state=null,busy=false,owner=null,serial=0;
function controls(){
 if(!box())return;box().hidden=me?.role!=='admin'||!(state?.ready||state?.bound);
 $('#line-feed-refresh').disabled=busy;$('#line-feed-pair').disabled=busy||!state?.ready;
 $('#line-feed-disconnect').disabled=busy||!state?.bound;
}
function render(){
 if(!box())return;controls();if(!state)return;
 $('#line-feed-connection').textContent=t(state.ready?'lineFeedReady':'lineFeedMissing');
 $('#line-feed-binding').textContent=t(state.bound?'lineFeedBound':'lineFeedUnbound')+(state.bound?' · …'+state.group_suffix:'')+(state.bound&&!state.operator_active?' · '+t('lineFeedOperator'):'');
 $('#line-feed-keys').innerHTML=Object.entries(state.configured).map(([k,v])=>`<li><code>${esc(k)}</code>：${t(v?'lineFeedSet':'lineFeedUnset')}</li>`).join('');
 $('#line-feed-recent').innerHTML=state.recent.map(r=>`<li><time>${esc(new Date(r.updated_at).toLocaleString(lang==='vi'?'vi-VN':'zh-TW',{timeZone:'Asia/Taipei'}))}</time> · ${t(({done:'lineFeedDone',ignored:'lineFeedIgnored',retry:'lineFeedRetry',failed:'lineFeedFailed',processing:'lineFeedProcessing'})[r.status]||'lineFeedFailed')}${r.error==='line_reply_failed'?' · LINE回覆失敗，待確認已保留':''}${r.draft_id?` <a href="/?feed_draft=${encodeURIComponent(r.draft_id)}#feed">${t('lineFeedOpen')}</a>`:''}</li>`).join('')||`<li>${t('lineFeedNone')}</li>`;
}
async function load(){
 if(me?.role!=='admin'||busy)return;const mine=++serial,user=me.id;busy=true;controls();$('#line-feed-error').textContent='';
 try{const value=await api('/api/line/status');if(mine!==serial||me?.id!==user)return;state=value;render();}
 catch(e){if(mine===serial&&me?.id===user)$('#line-feed-error').textContent=messageError(e);}
 finally{if(mine===serial){busy=false;controls();}}
}
async function action(name){
 if(busy||!state||me?.role!=='admin')return;if(name==='disconnect'&&!window.confirm(t('lineFeedDisconnectAsk')))return;
 const mine=++serial,user=me.id;let failure=null;busy=true;controls();$('#line-feed-error').textContent='';
 try{
  const result=await api('/api/line/configure',{method:'POST',body:JSON.stringify({action:name,revision:state.revision})});
  if(mine!==serial||me?.id!==user)return;
  $('#line-feed-command').textContent=result.command||'';$('#line-feed-code').hidden=!result.command;
 }catch(e){failure=e;}
 finally{if(mine===serial){busy=false;controls();await load();if(failure&&me?.id===user)$('#line-feed-error').textContent=messageError(failure);}}
}
build=()=>{
 base.build();$('#feed-drafts').insertAdjacentHTML('beforeend',`<details id="line-feed-settings" hidden><summary>${txt('lineFeedTitle')}</summary><p>${txt('lineFeedHint')}</p><p id="line-feed-connection" role="status">${txt('lineFeedLoading')}</p><p id="line-feed-binding"></p><div class="actions"><button type="button" id="line-feed-refresh">${txt('lineFeedRefresh')}</button><button type="button" id="line-feed-pair">${txt('lineFeedPair')}</button><button type="button" id="line-feed-disconnect">${txt('lineFeedDisconnect')}</button></div><section id="line-feed-code" hidden><p>${txt('lineFeedPairHint')}</p><code id="line-feed-command"></code><button type="button" id="line-feed-copy-command">${txt('lineFeedCopy')}</button></section><p id="line-feed-error" class="form-error" role="alert"></p><details><summary>${txt('lineFeedSetupTitle')}</summary><ol><li>${txt('lineFeedSetup1')} <a href="https://manager.line.biz/" target="_blank" rel="noopener noreferrer">LINE Official Account Manager</a></li><li>${txt('lineFeedSetup2')}<ul id="line-feed-keys"></ul></li><li>${txt('lineFeedSetup3')}<p>${txt('lineFeedWebhook')}</p><code id="line-feed-webhook"></code> <button type="button" id="line-feed-copy-url">${txt('lineFeedCopy')}</button> <a href="https://developers.line.biz/console/" target="_blank" rel="noopener noreferrer">LINE Developers</a></li><li>${txt('lineFeedSetup4')}</li></ol><p>${txt('lineFeedPrivacy')}</p><p>${txt('lineFeedReviewHint')}</p></details><details><summary>${txt('lineFeedRecent')}</summary><ul id="line-feed-recent"></ul></details></details>`);
 $('#line-feed-webhook').textContent=location.origin+'/api/line/webhook';$('#line-feed-refresh').onclick=load;$('#line-feed-pair').onclick=()=>action('pair');$('#line-feed-disconnect').onclick=()=>action('disconnect');
 for(const [id,target] of [['line-feed-copy-url','line-feed-webhook'],['line-feed-copy-command','line-feed-command']])$('#'+id).onclick=async()=>{try{await navigator.clipboard.writeText($('#'+target).textContent);toast(t('lineFeedCopied'));}catch(e){toast($('#'+target).textContent);}};
 box().addEventListener('toggle',()=>{if(box().open)load();});
 document.addEventListener('pigledger:logout',()=>{serial++;state=null;owner=null;busy=false;$('#line-feed-command').textContent='';$('#line-feed-code').hidden=true;$('#line-feed-keys').replaceChildren();$('#line-feed-recent').replaceChildren();box().open=false;box().hidden=true;});
};
enter=async user=>{if(owner!==user.id){serial++;owner=user.id;state=null;busy=false;}const result=await base.enter(user);controls();if(user.role==='admin')await load();return result;};
translate=()=>{base.translate();render();};
})();
