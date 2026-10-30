import assert from 'node:assert/strict';
import C from '../site/bands-core.js';
const now=Date.parse('2026-10-30T16:00Z'),meta={generated_at:new Date(now).toISOString()};
const game=i=>({game_id:String(i),tipoff:'2026-10-30T23:00Z',observed_at:meta.generated_at,state:'pre',home:{abbr:'H'+i},away:{abbr:'A'+i},projection:{ratings_known:true,mu:8,margin_sd:12,p_home:C.cdf(8/12)}});
for(const format of Object.keys(C.formats)){
 const g=C.candidate(game(1),format);assert.ok(Math.abs(g.bands.reduce((n,b)=>n+b.prob,0)-g.win_prob)<1e-9);assert.ok(g.bands.every(b=>b.prob<g.win_prob));
 const r=C.build(Array.from({length:6},(_,i)=>game(i)),meta,{now,format});assert.equal(r.tickets.length,4);assert.equal(new Set(r.tickets.map(t=>t.signature)).size,4);assert.ok(r.tickets.some(t=>t.legs.length===4));
 for(const t of r.tickets){assert.ok(t.legs.length>=3&&t.legs.length<=4);assert.equal(new Set(t.legs.map(g=>g.event_id)).size,t.legs.length);assert.ok(t.legs.every(g=>g.win_prob>=.6));assert.ok(Math.abs(t.prob-t.legs.reduce((p,g)=>p*g.band.prob,1))<1e-12);}
}
const away=game(1);away.projection={...away.projection,mu:-8,p_home:1-C.cdf(8/12)};assert.equal(C.candidate(away).team,'A1');assert.equal(C.candidate(away).margin,8);
const opts={now};assert.equal(C.build([game(1),game(2)],meta,opts).tickets.length,0);
for(const change of [{state:'post'},{postponed:true},{canceled:true},{source_stale:true},{tipoff:'2026-10-30T15:59Z'},{observed_at:'2026-10-30T00:00Z'},{projection:{ratings_known:false}}])assert.equal(C.eligible({...game(1),...change},meta,now),false);
assert.equal(C.eligible(game(1),{generated_at:'2026-10-30T00:00Z'},now),false);assert.equal(C.eligible(game(1),{generated_at:'2026-10-30T17:00Z'},now),false);
const weak=game(2);weak.projection={...weak.projection,p_home:.59};assert.equal(C.build([game(0),game(1),weak],meta,opts).tickets.length,0);
assert.equal(C.build([game(1),game(1),game(2)],meta,opts).pool.length,2);
assert.equal(C.day('2026-10-31T02:00Z'),'2026-10-30');
assert.throws(()=>C.build([],meta,{now,format:'fake'}));
console.log('NBA bands: probability mass, 60% filter, 3–4 distinct games, formats, Toronto dates and stale/kickoff guards passed');
