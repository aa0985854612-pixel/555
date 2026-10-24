const VERSION='pigledger-2.0.55';
const FILES=['/quick-record.js?v=2.0.55','/quick-record.css?v=2.0.55','/bin-stock.js?v=2.0.55','/line-feed.js?v=2.0.55','/feed-drafts.js?v=2.0.55','/batch-manager.js?v=2.0.55','/batch-manager.css?v=2.0.55','/outgoing-preview.js?v=2.0.55','/outgoing-preview.css?v=2.0.55','/','/jiade-cover.webp?v=2.0.55','/app.js?v=2.0.55','/appearance.js?v=2.0.55','/upgrade.js?v=2.0.55','/redesign.js?v=2.0.55','/order-fcr.js?v=2.0.55','/notifications.js?v=2.0.55','/growth.js?v=2.0.55','/weighing-report.js?v=2.0.55','/weekly-pdf.js?v=2.0.55','/weekly-report.js?v=2.0.55','/feed.js?v=2.0.55','/cohort-link.js?v=2.0.55','/compact.js?v=2.0.55','/review.js?v=2.0.55','/feed-review.js?v=2.0.55','/feed-setup.js?v=2.0.55','/movement-review.js?v=2.0.55','/calendar-presentation.js?v=2.0.55','/work-calendar-pdf.js?v=2.0.55','/work-calendar.js?v=2.0.55','/feed-bulk.js?v=2.0.55','/style.css?v=2.0.55','/jiade-icon-180-v1.6.3.png','/jiade-icon-192-v1.6.3.png','/jiade-icon-512-v1.6.3.png','/jiade-icon-maskable-v1.6.3.png','/manifest.webmanifest?v=2.0.55','/manifest.webmanifest'];
self.addEventListener('install',e=>e.waitUntil(caches.open(VERSION).then(c=>c.addAll(FILES))));
self.addEventListener('message',e=>{if(e.data==='activate')self.skipWaiting()});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('pigledger-')&&k!==VERSION).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
 const u=new URL(e.request.url);
 if(u.origin!==location.origin||u.pathname.startsWith('/api/')||e.request.method!=='GET')return;
 e.respondWith(fetch(e.request).then(r=>{if(r.ok){const copy=r.clone();caches.open(VERSION).then(c=>c.put(e.request,copy))}return r}).catch(()=>caches.match(e.request)));
});
const PUSH_STATE='jiade-device-state';
self.addEventListener('message',e=>{
 if(e.data?.type==='push-active')e.waitUntil(caches.open(PUSH_STATE).then(c=>e.data.enabled?c.put('/__push_enabled',new Response('1')):c.delete('/__push_enabled')));
});
self.addEventListener('push',e=>e.waitUntil((async()=>{
 const enabled=await (await caches.open(PUSH_STATE)).match('/__push_enabled');if(!enabled)return;
 let p;try{p=e.data.json();}catch(_){return;}
 const target=new URL(p.url||'/#daily',self.location.origin);if(target.origin!==self.location.origin)return;
 await self.registration.showNotification(p.title||'嘉得肉豬紀錄',{body:p.body||'',tag:p.tag,renotify:false,icon:'/jiade-icon-192-v1.6.3.png',badge:'/jiade-icon-192-v1.6.3.png',data:{url:target.href}});
})()));
self.addEventListener('notificationclick',e=>{
 e.notification.close();e.waitUntil((async()=>{const target=new URL(e.notification.data?.url||'/#daily',self.location.origin);if(target.origin!==self.location.origin)return;const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});const existing=windows.find(c=>new URL(c.url).origin===self.location.origin);if(existing){await existing.navigate(target.href);return existing.focus();}return self.clients.openWindow(target.href);})());
});
