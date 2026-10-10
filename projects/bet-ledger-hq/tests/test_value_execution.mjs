import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),V=require('../value-core.js'),X=require('../execution-core.js'),N=require('../night-football-core.js'),T=require('../today-core.js');
const now=Date.parse('2026-10-10T04:00:00Z'),publication='2026-10-10T03:30:00Z';
const row={id:'nfl:1',sport:'NFL',game_id:'1',game_date:'2026-10-11T20:00:00Z',market:'ATS',side:'home',line:-3.5,price:-110,book:'Book',model_prob:.58,push_prob:0,tier:'GOOD',stake:5,odds_observed_at:publication};
const q=V.evaluate(row,{sport:'nfl',now,publication});
assert(q.passes);assert.equal(q.worst,-117);assert(Math.abs(q.stressEV-.05)<1e-10);
assert(!V.evaluate(row,{sport:'nfl',now,price:-120}).passes);
assert(!V.evaluate(row,{sport:'nfl',now,line:-4}).passes);
for(const change of [{quote_status:'retained'},{reference_only:true},{model_prob:null},{model_prob:true},{model_prob:1},{price:50},{book:''},{price_source:'model'},{held:true},{odds_verified:false},{push_prob:1},{game_date:'2026-10-09T00:00Z'},{odds_observed_at:null},{odds_observed_at:'2026-10-10T05:00Z'}])assert(!V.evaluate({...row,...change},{sport:'nfl',now}).passes,JSON.stringify(change));
assert(!V.evaluate(row,{sport:'nfl',now,publication:'2026-10-09T03:00Z'}).passes);
// Minimum price must survive integer rounding on either side of even money.
for(const p of [.2,.4,.53,.55,.7,.9]){
 const r={...row,model_prob:p,push_prob:.07};const v=V.evaluate(r,{sport:'nfl',now});
 assert(V.evaluate(r,{sport:'nfl',now,price:v.worst}).stressEV>=.02-1e-10);
 const worse=v.worst===100?-101:v.worst-1;
 assert(V.evaluate(r,{sport:'nfl',now,price:worse}).stressEV<.02+1e-10);
}
// Football conditional and prop unconditional probabilities give the same EV.
const football={...row,model_prob:.58,push_prob:.1},prop={...row,player:'Player',model_prob:.522,model_prob_no_push:.58,push_prob:.1};
assert(Math.abs(V.evaluate(football,{sport:'nfl',now}).stressEV-V.evaluate(prop,{sport:'props',now}).stressEV)<1e-10);
assert(!V.evaluate({...prop,model_prob_no_push:.7},{sport:'props',now}).passes);
assert.equal(V.probabilities({...row,push_prob:.1},'unknown'),null);
assert.equal(V.annotate({...row,price:-120},'nfl',publication,now).stake,0);
const passed=V.annotate({...row,tier:'PASS'},'nfl',publication,now);assert.equal(passed.tier,'PASS');
const blocked=V.annotate({...row,price:-120},'nfl',publication,now);assert.equal(blocked.source_tier,'GOOD');assert.equal(blocked.model_prob,.58);
assert.equal(N.qualified(blocked,{generated_at:publication},now),false);
assert.equal(T.plays('nfl',{meta:{generated_at:publication},board:[blocked]},now).length,0);
assert.equal(T.plays('nfl',{meta:{generated_at:publication},board:[V.annotate(row,'nfl',publication,now)]},now).length,1);
const input={price:-120,line:-3.5,stake:10,book:'Actual Book',placed_at:'2026-10-10T03:00:00Z',status:'Pending'};
const r=X.confirm(row,input,null,'2026-10-10T04:00:00Z'),settings={[X.key(row.id)]:JSON.stringify(r)};
assert.equal(X.summary([row],{}).count,0);assert.equal(X.summary([row],settings).exposure,10);
assert.equal(X.comparison(r),'Worse accepted price');
const settled=X.confirm({...row,price:-150,model_prob:.7},{...input,status:'Win'},r,'2026-10-10T04:01:00Z');
assert.deepEqual(settled.reference,r.reference);assert(Math.abs(X.pnl(settled)-8.333333333333334)<1e-10);
settings[X.key(row.id)]=JSON.stringify(settled);assert(Math.abs(X.summary([row],settings).roi-5/6)<1e-10);
const push=X.confirm(row,{...input,status:'Push'},r,'2026-10-10T04:00:00Z');settings[X.key(row.id)]=JSON.stringify(push);assert.equal(X.summary([row],settings).staked,10);assert.equal(X.summary([row],settings).pnl,0);
const voided=X.confirm(row,{...input,status:'Void'},r,'2026-10-10T04:00:00Z');settings[X.key(row.id)]=JSON.stringify(voided);assert.equal(X.summary([row],settings).roi,null);
assert.equal(X.comparison(X.confirm(row,{...input,line:-4},r,'2026-10-10T04:00:00Z')),'Different line; forecast EV unavailable');
assert(X.csv([row],settings).includes('accepted_price'));assert.equal(X.summary([{...row,deleted:true}],settings).count,0);
for(const change of [{price:50},{stake:-1},{book:''},{line:'bad'},{placed_at:'2026-10-11T03:00Z'},{status:'Winner'}])assert.throws(()=>X.confirm(row,{...input,...change},null,'2026-10-10T04:00:00Z'));
assert.equal(X.get({[X.key(row.id)]:JSON.stringify({schema:1,id:row.id,confirmed:true})},row.id),null);assert.equal(X.snapshot({...row,app:'nfl-lab',side:'away'},'2026-10-10').line,3.5);assert.equal(V.selectionLine({...row,side:'away'},'nfl'),3.5);assert.equal(row.price,-110);console.log('Price stress, rounded minimum odds, push probability bases, source tier retention, runtime gates, frozen receipts, actual P/L, void/push ROI and receipt validation passed');
// Deployment counters must match the recommendation rows, while retaining source counts.
const {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync}=require('node:fs'),{tmpdir}=require('node:os'),path=require('node:path'),{execFileSync}=require('node:child_process');
const temp=mkdtempSync(path.join(tmpdir(),'price-policy-'));
try{
 for(const repo of ['nfl-edge-lab','ncaaf-edge-lab','props-edge','nhl-edge-lab','wnba-edge-lab']){
  const dir=path.join(temp,repo,'data');mkdirSync(dir,{recursive:true});
  const at=new Date().toISOString(),bad={...row,game_date:new Date(Date.now()+86400000).toISOString(),odds_observed_at:at,price:-150};
  writeFileSync(path.join(dir,'meta.json'),JSON.stringify({generated_at:at,counts:{qualified:1,actionable:1},quote_health:{markets:{ATS:{qualified:1}},board_reasons:{qualified:1}}}));
  writeFileSync(path.join(dir,'board.json'),JSON.stringify([bad]));if(repo==='props-edge')writeFileSync(path.join(dir,'legs.json'),'[]');
 }
 execFileSync(process.execPath,[new URL('../../../tools/apply_value_policy.mjs',import.meta.url).pathname,temp]);
 const meta=JSON.parse(readFileSync(path.join(temp,'nfl-edge-lab/data/meta.json')));assert.equal(meta.counts.qualified,0);assert.equal(meta.source_counts.qualified,1);assert.equal(meta.value_policy.source_qualified,1);assert.equal(meta.quote_health.markets.ATS.qualified,0);assert.equal(meta.quote_health.board_reasons.qualified,0);assert.equal(meta.quote_health.board_reasons['additional price stress failures'],1);
}finally{rmSync(temp,{recursive:true,force:true});}
console.log('Public qualification counters match stress-gated rows and preserve source counters');
