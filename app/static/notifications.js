'use strict';
/* Permission is requested only from an explicit tap on this device. */
(() => {
Object.assign(words,{
 pushUpdateFirst:['有新版本待套用，請先儲存手上的資料並按「套用更新」，再啟用通知。','Có bản cập nhật; lưu dữ liệu đang nhập và cập nhật ứng dụng trước khi bật thông báo.'],pushTitle:['通知設定','Cài đặt thông báo'],pushIntro:['每台手機分別啟用；登出會關閉這台裝置的通知。','Bật riêng trên từng điện thoại; đăng xuất sẽ tắt thông báo của thiết bị này.'],pushRecords:['有人新增紀錄時通知我','Báo khi người khác thêm bản ghi'],pushDaily:['每天上午10點提醒輸入（台灣時間）','Nhắc ghi chép lúc 10:00 mỗi ngày (giờ Đài Loan)'],pushEnable:['啟用此裝置通知','Bật thông báo thiết bị này'],pushSave:['儲存通知選擇','Lưu lựa chọn'],pushDisable:['關閉此裝置通知','Tắt thông báo thiết bị này'],pushTest:['測試通知','Thử thông báo'],pushOn:['此裝置已啟用通知。','Thiết bị này đã bật thông báo.'],pushOff:['此裝置尚未啟用通知。','Thiết bị này chưa bật thông báo.'],pushPermission:['請在手機或瀏覽器設定允許此網站的通知。','Cho phép thông báo của trang này trong cài đặt điện thoại / trình duyệt.'],pushUnsupported:['此瀏覽器尚不支援推播。iPhone請先將網站加入主畫面，再從主畫面開啟。','Trình duyệt chưa hỗ trợ push. Trên iPhone, thêm trang vào màn hình chính rồi mở từ đó.'],pushNotReady:['通知服務尚未設定完成，請稍後再試。','Dịch vụ thông báo chưa sẵn sàng; thử lại sau.'],pushFailed:['通知設定未完成，請檢查連線後再試。','Chưa lưu được cài đặt; kiểm tra kết nối và thử lại.'],pushTestSent:['測試通知已交給推播服務，請查看手機通知。','Đã gửi đến dịch vụ push; kiểm tra thông báo điện thoại.'],pushTestFailed:['推播尚未送出，請稍後再試或重新啟用此裝置。','Chưa gửi được push; thử lại sau hoặc bật lại thiết bị.'],pushReminderHint:['每日提醒從下一個上午10點開始；自己新增的紀錄不會重複通知自己。','Nhắc hằng ngày từ 10:00 kế tiếp; không tự báo lại bản ghi do mình thêm.']
});
const base={build,enter,translate};let model=null,device=null,busy=false,owner=null;
const storage='pig-push-device';
const supported=()=>('Notification' in window)&&('serviceWorker' in navigator)&&('PushManager' in window)&&window.isSecureContext;
const active=()=>device&&owner===me?.id&&model?.devices?.some(d=>d.id===device.id);
function render(){
 if(!$('#notification-card'))return;
 const on=active();$('#push-status').textContent=!supported()?t('pushUnsupported'):Notification.permission==='denied'?t('pushPermission'):model&&!model.configured?t('pushNotReady'):on?t('pushOn'):t('pushOff');
 $('#push-enable').hidden=!!on;$('#push-save').hidden=!on;$('#push-disable').hidden=!on;$('#push-test').hidden=!on;
 $$('#notification-card button').forEach(b=>b.disabled=busy||!supported()||!model?.configured);
}
async function state(enabled){
 if(!('serviceWorker' in navigator))return;
 const r=await navigator.serviceWorker.getRegistration();(r?.active||navigator.serviceWorker.controller)?.postMessage({type:'push-active',enabled});
}
async function disable(){
 const old=device;
 try{if(old&&owner===me?.id)await api('/api/notifications/unsubscribe',{method:'POST',body:JSON.stringify({id:old.id})});}
 finally{
  await state(false);
  if('serviceWorker' in navigator){const r=await navigator.serviceWorker.getRegistration();const sub=await r?.pushManager?.getSubscription();if(sub)await sub.unsubscribe();}
  localStorage.removeItem(storage);device=null;if(model)model.devices=[];render();
 }
}
async function enable(){
 if(busy||!supported()||!model?.configured)return;busy=true;$('#push-error').textContent='';render();
 try{
  let permission=Notification.permission;if(permission==='default')permission=await Notification.requestPermission();
  if(permission!=='granted'){$('#push-error').textContent=t('pushPermission');return;}
  const r=await Promise.race([navigator.serviceWorker.ready,new Promise((_,reject)=>setTimeout(()=>reject(new Error('not_ready')),20000))]);
  if(r.waiting||(r.installing&&r.active)){$('#push-error').textContent=t('pushUpdateFirst');return;}
  const key=model.public_key.replaceAll('-','+').replaceAll('_','/'),bytes=Uint8Array.from(atob(key+'='.repeat((4-key.length%4)%4)),c=>c.charCodeAt(0));
  const sub=await r.pushManager.getSubscription()||await r.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:bytes});
  const user=me.id;const result=await api('/api/notifications/subscribe',{method:'POST',body:JSON.stringify({subscription:sub.toJSON(),new_records:$('#push-records').checked,daily_reminder:$('#push-daily').checked,language:lang})});
  if(me?.id!==user){await sub.unsubscribe();return;}
  owner=user;device={id:result.id,user};localStorage.setItem(storage,JSON.stringify(device));model.devices=[result];await state(true);render();
 }catch(e){$('#push-error').textContent=t('pushFailed');}finally{busy=false;render();}
}
async function load(){
 if(!me)return;const user=me.id;owner=user;model=null;device=null;
 try{
  const saved=JSON.parse(localStorage.getItem(storage)||'null');
  if(saved&&saved.user!==user){await state(false);const r=await navigator.serviceWorker?.getRegistration();const sub=await r?.pushManager?.getSubscription();if(sub)await sub.unsubscribe();localStorage.removeItem(storage);}
  const result=await api('/api/notifications');if(me?.id!==user)return;model=result;device=saved?.user===user?saved:null;
  const pref=model.devices.find(d=>d.id===device?.id);$('#push-records').checked=pref?!!pref.new_records:true;$('#push-daily').checked=pref?!!pref.daily_reminder:true;
  if(!pref)await state(false);
 }catch(e){if(me?.id===user)$('#push-error').textContent=t('pushFailed');}finally{render();}
}
build=()=>{
 base.build();$('#page-settings').insertAdjacentHTML('afterbegin',`<section class="card" id="notification-card"><h2 data-i="pushTitle">${t('pushTitle')}</h2><p class="hint" data-i="pushIntro">${t('pushIntro')}</p><label class="check"><input type="checkbox" id="push-records" checked><span data-i="pushRecords">${t('pushRecords')}</span></label><label class="check"><input type="checkbox" id="push-daily" checked><span data-i="pushDaily">${t('pushDaily')}</span></label><p class="hint" data-i="pushReminderHint">${t('pushReminderHint')}</p><p id="push-status" role="status"></p><p id="push-error" class="form-error" role="status"></p><div class="actions"><button type="button" id="push-enable" class="primary" data-i="pushEnable">${t('pushEnable')}</button><button type="button" id="push-save" data-i="pushSave" hidden>${t('pushSave')}</button><button type="button" id="push-test" data-i="pushTest" hidden>${t('pushTest')}</button><button type="button" id="push-disable" data-i="pushDisable" hidden>${t('pushDisable')}</button></div></section>`);
 $('#push-enable').onclick=enable;$('#push-save').onclick=enable;
 $('#push-disable').onclick=async()=>{try{await disable();}catch(e){$('#push-error').textContent=t('pushFailed');}};
 $('#push-test').onclick=async()=>{if(!active()||busy)return;busy=true;render();try{const r=await api('/api/notifications/test',{method:'POST',body:JSON.stringify({id:device.id})});$('#push-error').textContent=t(r.sent?'pushTestSent':'pushTestFailed');}catch(e){$('#push-error').textContent=t('pushTestFailed');}finally{busy=false;render();}};
 const logout=$('#logout').onclick;$('#logout').onclick=async e=>{try{await disable();}catch(e){}return logout(e);};render();
};
enter=async user=>{await base.enter(user);if(me?.id===user.id&&!me.must_change)await load();};
translate=()=>{base.translate();render();};
document.addEventListener('pigledger:logout',()=>{state(false);owner=null;device=null;model=null;render();});
})();
