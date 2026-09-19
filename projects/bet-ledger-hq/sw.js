/* Only static code and artwork are cached. Live and private data always use the network. */
const CACHE='kevbot-shell-portable-20260919-3',BASE=new URL('./',self.location.href);
const FILES=['./','index.html','hub.css','hub-extras.css','hub.js','pwa.js','offline.html','manifest.webmanifest','icon.svg','icon-192.png','icon-512.png','apple-touch-icon.png','kevbot-logo.jpg','football.html','football-core.js','football.js','moneyline.html','moneyline.css','moneyline-core.js','moneyline.js','moneyline-card.js','today.html','today.css','today-extras.css','today-core.js','today.js','ticket-core.js','ticket-renderer.js','ticket-store.js','betsync.js','archive.html','archive.js','alerts-core.js','alerts-view.js','ledger.html','hq.js','ledger-details.js'];
const ALLOWED=new Set(FILES.map(f=>new URL(f,BASE).href));
for(const file of ['pick-history-view.js','ledger-recovery.js','ledger-recovery-view.js']){FILES.push(file);ALLOWED.add(new URL(file,BASE).href);}
for(const name of ['baseball','hockey','football'])ALLOWED.add(new URL('assets/tickets/'+name+'.webp',BASE).href);
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(FILES.map(f=>new URL(f,BASE).href)))));
self.addEventListener('activate',event=>event.waitUntil((async()=>{for(const key of await caches.keys())if(key.startsWith('kevbot-shell-')&&key!==CACHE)await caches.delete(key);await self.clients.claim();})()));
self.addEventListener('message',event=>{if(event.data?.type==='ACTIVATE')self.skipWaiting();});
self.addEventListener('fetch',event=>{
  const request=event.request,url=new URL(request.url);url.search='';url.hash='';
  if(request.method!=='GET'||url.origin!==BASE.origin||!ALLOWED.has(url.href))return;
  event.respondWith((async()=>{const cache=await caches.open(CACHE);try{const response=await fetch(request);if(response.ok)await cache.put(url.href,response.clone());return response;}catch(_){const saved=await cache.match(url.href);if(saved)return saved;if(request.mode==='navigate')return cache.match(new URL('offline.html',BASE).href);return Response.error();}})());
});
