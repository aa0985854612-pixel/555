const VERSION='pigledger-1.7.0';
const FILES=['/','/jiade-cover.webp?v=1.7.0','/app.js?v=1.7.0','/appearance.js?v=1.7.0','/upgrade.js?v=1.7.0','/redesign.js?v=1.7.0','/compact.js?v=1.7.0','/style.css?v=1.7.0','/jiade-icon-180-v1.6.3.png','/jiade-icon-192-v1.6.3.png','/jiade-icon-512-v1.6.3.png','/jiade-icon-maskable-v1.6.3.png','/manifest.webmanifest?v=1.7.0','/manifest.webmanifest'];
self.addEventListener('install',e=>e.waitUntil(caches.open(VERSION).then(c=>c.addAll(FILES))));
self.addEventListener('message',e=>{if(e.data==='activate')self.skipWaiting()});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('pigledger-')&&k!==VERSION).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
 const u=new URL(e.request.url);
 if(u.origin!==location.origin||u.pathname.startsWith('/api/')||e.request.method!=='GET')return;
 e.respondWith(fetch(e.request).then(r=>{if(r.ok){const copy=r.clone();caches.open(VERSION).then(c=>c.put(e.request,copy))}return r}).catch(()=>caches.match(e.request)));
});
