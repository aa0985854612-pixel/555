const VERSION='pigledger-2.0.11';
const FILES=['/','/jiade-cover.webp?v=2.0.11','/app.js?v=2.0.11','/appearance.js?v=2.0.11','/upgrade.js?v=2.0.11','/redesign.js?v=2.0.11','/weighing-report.js?v=2.0.11','/weekly-pdf.js?v=2.0.11','/weekly-report.js?v=2.0.11','/feed.js?v=2.0.11','/cohort-link.js?v=2.0.11','/compact.js?v=2.0.11','/review.js?v=2.0.11','/feed-setup.js?v=2.0.11','/style.css?v=2.0.11','/jiade-icon-180-v1.6.3.png','/jiade-icon-192-v1.6.3.png','/jiade-icon-512-v1.6.3.png','/jiade-icon-maskable-v1.6.3.png','/manifest.webmanifest?v=2.0.11','/manifest.webmanifest'];
self.addEventListener('install',e=>e.waitUntil(caches.open(VERSION).then(c=>c.addAll(FILES))));
self.addEventListener('message',e=>{if(e.data==='activate')self.skipWaiting()});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('pigledger-')&&k!==VERSION).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
 const u=new URL(e.request.url);
 if(u.origin!==location.origin||u.pathname.startsWith('/api/')||e.request.method!=='GET')return;
 e.respondWith(fetch(e.request).then(r=>{if(r.ok){const copy=r.clone();caches.open(VERSION).then(c=>c.put(e.request,copy))}return r}).catch(()=>caches.match(e.request)));
});
