import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
import {webcrypto} from 'node:crypto';
const require=createRequire(import.meta.url),A=require('../alerts-core.js'),T=require('../ticket-store.js');
const tests=[],test=(name,fn)=>tests.push([name,fn]);
const at='2026-09-15T18:00:00Z',now=Date.parse(at),start='2026-09-15T23:00:00Z';
const pick={key:'mlb',eventId:'123',start,market:'total',side:'Over',pick:'Over 8.5',line:8.5,price:-110,book:'Example',event:'A @ B',source:'MLB'};
const ticket=(id='local-12345678',time=at)=>({schema:1,id,day:'2026-09-15',published_at:time,picks:[pick]});
test('availability alerts establish a baseline and never treat missing reports as recovery',()=>{
 const reports={p:{sport:'nfl',team:'Example',player:'Player',status:'Questionable',detail:'knee',report_at:at}};
 const baseline=A.scan(null,{injuries:{nfl:reports}},at);assert.equal(baseline.events.length,0);
 const missing=A.scan(baseline.state,{injuries:{nfl:null}},at);assert.deepEqual(missing.state.injuries.nfl,reports);assert.equal(missing.events.length,0);
 assert.equal(A.scan(baseline.state,{injuries:{nfl:{}}},at).events.length,0);
 const changed=A.scan(baseline.state,{injuries:{nfl:{p:{...reports.p,status:'Out'}}}},at);assert.equal(changed.events[0].kind,'injury');assert.match(changed.events[0].after,/Out/);
});
test('only dated recent reports are accepted; missing injury data stays unavailable',()=>{
 const row={status:'Out',date:at,athlete:{id:'1',displayName:'Player'}};
 assert.equal(A.injuries({},'nfl',now),null);
 assert.equal(Object.keys(A.injuries({injuries:[{id:'1',injuries:[row,{...row,date:'2025-01-01',athlete:{id:'2',displayName:'Old'}}]}]},'nfl',now)).length,1);
});
test('MLB alerts compare fresh lineup and starter observations',()=>{
 const game={gamePk:1,start,away:'A',home:'B',away_sp:{name:'Pitcher A'},lineups_confirmed:false};
 assert.deepEqual(A.lineups({slate:{generated_at:'2020-01-01',games:[game]}},now),{});
 const first=A.scan(null,{lineups:A.lineups({slate:{generated_at:at,games:[game]}},now)},at);assert.equal(first.events.length,0);
 const next=A.scan(first.state,{lineups:A.lineups({slate:{generated_at:at,games:[{...game,lineups_confirmed:true,away_sp:{name:'Pitcher B'}}]}},now)},at);
 assert.deepEqual(next.events.map(e=>e.kind),['lineup','starter']);
});
test('odds warnings require a future archived pick and the same book; snapshots remain unchanged',()=>{
 const original=JSON.stringify(pick),q={...pick,price:-125};
 const first=A.scan(null,{tracked:[pick],quotes:[q]},at);assert.equal(first.events.length,1);assert.equal(first.events[0].before,'-110 · line 8.5');
 assert.equal(A.scan(first.state,{tracked:[pick],quotes:[q]},at).events.length,0);
 assert.equal(A.scan(null,{tracked:[pick],quotes:[{...q,book:'Other'}]},at).events.length,0);
 assert.equal(A.scan(null,{tracked:[pick],quotes:[{...q,price:0}]},at).events.length,0);
 assert.equal(A.scan(null,{tracked:[pick],quotes:[q]},'2026-09-16T00:00:00Z').events.length,0);
 assert.equal(JSON.stringify(pick),original);
});
test('backup snapshots exclude credentials, ledger state, and images and reject conflicting IDs',()=>{
 const clean=T.clean({...ticket(),token:'private',image:'blob:',rows:[{stake:99}]});
 assert.equal(clean.token,undefined);assert.equal(clean.rows,undefined);assert.equal(clean.image,undefined);
 const settings={[T.PREFIX+clean.id]:JSON.stringify(clean)};assert.deepEqual(T.patch([clean],settings).settings,{});
 assert.throws(()=>T.patch([{...clean,picks:[{...pick,price:-115}]}],settings),/different picks/);
 assert.throws(()=>T.clean({...ticket(),picks:[{...pick,price:0}]}),/Invalid/);
});
test('latest 100 backups are retained without rewriting kept originals',()=>{
 const rows=Array.from({length:101},(_,i)=>T.clean(ticket('local-ticket-'+String(i).padStart(8,'0'),new Date(now+i*1000).toISOString())));
 const settings=Object.fromEntries(rows.map(t=>[T.PREFIX+t.id,JSON.stringify(t)]));const plan=T.patch(rows,settings);
 assert.equal(plan.combined.length,100);assert.deepEqual(plan.settings,{[T.PREFIX+rows[0].id]:''});
});
function backupDevice(shared){
 const data=new Map(),ctx={TextEncoder,Uint8Array,crypto:webcrypto,navigator:{onLine:true},localStorage:{getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v)},config:{url:'https://script.google.com/macros/s/test/exec',token:'secret'}};
 ctx.BetSync={loadConfig:()=>ctx.config,pullAll:async()=>({settings:{...shared}}),pushRows:async(c,rows,patch)=>{assert.equal(rows.length,0,'backups never write wagers');Object.assign(shared,patch);return {settings:{...shared}};}};
 ctx.window=ctx;vm.runInNewContext(fs.readFileSync('ticket-store.js','utf8'),ctx);return {ctx,store:ctx.KevTicketStore,data};
}
test('two independent devices back up and restore exact originals without changing wagers',async()=>{
 const shared={},a=backupDevice(shared),b=backupDevice(shared);a.store.save(ticket());await a.store.sync();await b.store.sync();
 assert.equal(JSON.stringify(b.store.list()),JSON.stringify(a.store.list()));
 b.store.save(ticket('local-87654321','2026-09-15T19:00:00Z'));await b.store.sync();await a.store.sync();assert.equal(a.store.list().length,2);
 assert.ok(!JSON.stringify(shared).includes('secret'));
});
test('failed and offline backups preserve local originals and retry on next sync',async()=>{
 const d=backupDevice({});d.store.save(ticket());d.ctx.navigator.onLine=false;assert.equal((await d.store.sync()).state,'offline');assert.equal(d.store.list().length,1);
 d.ctx.navigator.onLine=true;const pull=d.ctx.BetSync.pullAll;d.ctx.BetSync.pullAll=async()=>{throw Error('offline');};await assert.rejects(d.store.sync(),/offline/);assert.equal(d.store.list().length,1);
 d.ctx.BetSync.pullAll=pull;assert.equal((await d.store.sync()).state,'synced');
});
test('switching a sheet connection does not upload the previous connection’s pending tickets',async()=>{
 const shared={},d=backupDevice(shared);d.store.save(ticket());const pull=d.ctx.BetSync.pullAll;d.ctx.BetSync.pullAll=async()=>{throw Error('offline');};await assert.rejects(d.store.sync());
 d.ctx.config={...d.ctx.config,token:'another-account'};d.ctx.BetSync.pullAll=pull;await d.store.sync();assert.deepEqual(shared,{});assert.equal(d.store.list().length,1);
});
test('service worker only caches explicit static files, never scores, prices, or private requests',async()=>{
 const events={},files=[],puts=[],responses=[];
 const cache={addAll:async urls=>files.push(...urls),put:async(...args)=>puts.push(args),match:async url=>({cached:url})};
 const ctx={URL,Set,Response,fetch:async()=>({ok:true,clone:()=>({static:true})}),caches:{open:async()=>cache,keys:async()=>[]},self:{location:{href:'https://example.com/bet-ledger-hq/sw.js'},addEventListener:(kind,fn)=>events[kind]=fn,clients:{claim:async()=>{}}}};
 vm.runInNewContext(fs.readFileSync('sw.js','utf8'),ctx);let installed;events.install({waitUntil:p=>installed=p});await installed;
 for(const url of files)assert.ok(fs.existsSync(new URL(url).pathname.replace('/bet-ledger-hq/','')||'index.html'),url);
 const request=(url,method='GET')=>events.fetch({request:{url,method,mode:'cors'},respondWith:p=>responses.push(p)});
 request('https://example.com/bet-ledger-hq/data/tickets/results.json');request('https://example.com/bet-ledger-hq/data/slate.json');request('https://script.google.com/macros/s/private/exec');request('https://example.com/bet-ledger-hq/today.html','POST');assert.equal(responses.length,0);
 request('https://example.com/bet-ledger-hq/today.html');await responses[0];assert.equal(puts.length,1);
 ctx.fetch=async()=>{throw Error('offline');};request('https://example.com/bet-ledger-hq/archive.html');assert.equal((await responses[1]).cached,'https://example.com/bet-ledger-hq/archive.html');
});
let passed=0;for(const [name,fn] of tests){try{await fn();passed++;}catch(err){console.error('FAIL '+name,err);process.exitCode=1;}}console.log(`${passed}/${tests.length} alerts, backups and offline tests passed`);
