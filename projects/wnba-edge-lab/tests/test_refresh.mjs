import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),F=require('../site/feed.js'),E=require('../site/eligibility.js');
const source=fs.readFileSync(new URL('../site/app.js',import.meta.url),'utf8');
const stamp='2026-09-16T11:00:00Z';
function payload(generated=stamp){
  const data=Object.fromEntries(F.FILES.map(name=>[name,['board','games','news','results'].includes(name)?[]:{}]));
  data.meta={generated_at:generated,source_status:'live',errors:[],odds_health:{status:'partial',upcoming_games:2,priced_games:0}};
  data.index={generated_at:generated,dates:['2026-09-16','2026-09-17','2026-09-18'],built_for:'2026-09-16'};
  data.summary={starting_bankroll:200,daily_cap:40,day_summary:{}};
  return F.FILES.map(name=>data[name]);
}
async function harness(initialFailure=false){
  let clock=Date.parse('2026-09-16T12:00:00Z'),calls=0,saveCount=0;
  const nodes=new Map(),inputs=[],events=[];
  const node=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',hidden:false,dataset:{}});return nodes.get(id);};
  const document={hidden:false,activeElement:null,documentElement:{dataset:{}},querySelector:node,querySelectorAll:sel=>sel==='[data-stake]'?inputs:[],addEventListener(){}};
  const wager={id:'confirmed-existing-wager',stake:7,result:'Pending'};
  const ledger={load:()=>[structuredClone(wager)],settleAll:entries=>({entries,changed:false}),save:()=>{saveCount++;return true;},summarise:()=>({bankroll:200,profit:0,pending:1,settled:0,at_risk:7})};
  let response=async()=>{if(initialFailure)throw new Error('offline');return payload();};
  const window={WNBALedger:ledger,QuoteEligibility:E,WNBAFeed:{...F,read:async()=>{calls++;return response();}},dispatchEvent:event=>events.push(event.type)};
  class Clock extends Date{constructor(...args){super(...(args.length?args:[clock]));}static now(){return clock;}}
  const ctx=vm.createContext({window,document,Date:Clock,URL,Intl,Event,AbortController,location:{href:'https://example.test/?date=2026-09-17'},history:{replaceState(){}},localStorage:{getItem(){throw new Error('storage disabled');}},matchMedia:()=>({matches:false}),setTimeout:()=>1,clearTimeout(){},setInterval(){},fetch(){throw new Error('unexpected network');}});
  vm.runInContext(source,ctx);await new Promise(setImmediate);
  return {ctx,node,document,inputs,events,get calls(){return calls;},get saves(){return saveCount;},advance:()=>{clock+=360000;},respond:fn=>{response=fn;},run:code=>vm.runInContext(code,ctx),refresh:()=>vm.runInContext('refreshPublishedData(true)',ctx)};
}
const h=await harness();
assert.equal(h.run('state.date'),'2026-09-17');
assert.equal(h.calls,1);assert.equal(h.saves,0);
assert.match(h.node('#stamp').textContent,/Published/);
assert.doesNotMatch(h.node('#stamp').textContent,/LIVE DATA/);
await h.refresh();assert.equal(h.calls,1,'visibility events should not flood requests');
const saved=h.run('JSON.stringify(myBets)'),board=h.run('JSON.stringify(board)');
h.advance();h.respond(async()=>{throw new Error('offline');});await h.refresh();
assert.equal(h.run('JSON.stringify(myBets)'),saved);assert.equal(h.run('JSON.stringify(board)'),board);
assert.match(h.node('#health').textContent,/previous data is retained/);
h.advance();h.respond(async()=>payload('2026-09-16T12:01:00Z'));h.run('state.tab="board"');await h.refresh();
assert.equal(h.run('state.date'),'2026-09-17');assert.equal(h.run('state.tab'),'board');
assert.equal(h.run('JSON.stringify(myBets)'),saved);assert.equal(h.saves,0);
assert.ok(h.events.includes('wnba:feed-updated'));
for(const tab of ['sim','accuracy']){h.advance();h.run(`state.tab=${JSON.stringify(tab)}`);const calls=h.calls;await h.refresh();assert.equal(h.calls,calls,`${tab} work should not be reset`);}
h.run('state.tab="plays"');h.advance();h.inputs.push({value:'7',defaultValue:'5'});let calls=h.calls;await h.refresh();assert.equal(h.calls,calls,'custom stake should survive');h.inputs.length=0;
h.document.activeElement={matches:()=>true};await h.refresh();assert.equal(h.calls,calls,'active editor should survive');h.document.activeElement=null;
h.document.hidden=true;await h.refresh();assert.equal(h.calls,calls,'hidden pages should not poll');h.document.hidden=false;
h.node('#ledgerImport').files=[{}];await h.refresh();assert.equal(h.calls,calls,'pending import should survive');h.node('#ledgerImport').files=[];
let resolve;h.respond(()=>new Promise(r=>{resolve=r;}));const inFlight=h.refresh();h.inputs.push({value:'9',defaultValue:'5'});resolve(payload('2026-09-16T12:02:00Z'));await inFlight;
assert.equal(h.run('meta.generated_at'),'2026-09-16T12:01:00Z','editing that starts during fetch must be preserved');
assert.equal(h.run('lastCheck'),0);assert.equal(h.run('refreshing'),false);h.inputs.length=0;
// Quote expiry remains enforced even when no newer publication is available.
h.run(`board=[{game_id:'expired',tier:'LEAN',stake:5,tipoff:'2026-09-17T23:00:00Z',odds_fetched_at:'2026-09-15T00:00:00Z',reasons:[]}];refreshExpiredQuotes()`);
assert.equal(h.run('board[0].stake'),0);assert.equal(h.run('board[0].tier'),'AVOID');
assert.equal(h.run('JSON.stringify(myBets)'),saved);
const retry=await harness(true);assert.match(retry.node('#view').innerHTML,/could not be loaded/);retry.advance();retry.respond(async()=>payload());await retry.refresh();assert.equal(retry.run('meta.generated_at'),stamp);
assert.equal(retry.saves,0);
console.log('automatic refresh, edit preservation, stale gates, storage resilience and manual-ledger checks passed');
