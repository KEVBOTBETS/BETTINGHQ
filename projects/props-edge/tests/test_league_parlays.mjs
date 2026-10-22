import assert from 'node:assert/strict';
import C from '../site/league-parlay-core.js';
const now=Date.parse('2026-10-22T20:00Z'),at='2026-10-22T19:45Z',start='2026-10-22T23:00Z';
const q=(n,extra={})=>({id:String(n),sport:'NBA',event_id:String(n),matchup:'A @ B',start_time:start,market:'ATS',side:'home',line:-2.5,pick:'Home -2.5',book:'DraftKings',price:150,price_kind:'book',model_prob:.65,qualified:true,observed_at:at,kind:'game',...extra});
const rows=[q(1),q(2),q(3),q(4)],built=C.build(rows,{target:500,now})[0];assert.ok(built);assert.equal(built.legs.length,2);assert.equal(built.actionable,false);assert.equal(built.combined_quote_verified,false);assert.ok(built.model_baseline>0);
assert.equal(C.build(rows.map(r=>({...r,qualified:false})),{target:500,profile:'core',now}).length,0);
assert.equal(C.build(rows.map(r=>({...r,book:r.event_id})),{target:500,now}).length,0);
assert.equal(C.build(rows,{target:500,scope:'game',game:'all',now}).length,0);assert.equal(C.build(rows,{target:123,now}).length,0);
for(const extra of [{observed_at:'2026-10-22T18:00Z'},{observed_at:'2026-10-22T21:00Z'},{start_time:at},{quote_status:'retained'},{reference_only:true},{price_source:'model'}])assert.equal(C.valid(q(1,extra),now),false);
assert.equal(C.compatible(q(1,{market:'ML',line:null}),[q(1)],'moonshot'),false);
assert.equal(C.compatible(q(2,{event_id:'1',kind:'player',player_id:'a'}),[q(1,{kind:'player',player_id:'a'})],'moonshot'),false);
assert.equal(C.metrics([q(1),q(2,{event_id:'1'})]).model_baseline,null);assert.equal(C.metrics([q(1),q(2,{model_prob:null})]).model_baseline,null);assert.equal(C.metrics([q(1),q(2,{push_prob:.03})]).model_baseline,null);
assert.throws(()=>C.capture({...built,legs:[q(1,{start_time:at}),q(2)]},now));assert.equal(C.profit({result:'Win',stake:10,actual_price:300}),30);assert.equal(C.profit({result:'Loss',stake:10,actual_price:300}),-10);
const system={games:[{sport:'nba',event_id:'1',start,matchup:'A @ B',publication_at:at,selections:[{market:'ML',side:'home',price:150,book:'DraftKings',pick:'A ML',observed_at:at,probability:.6}]}]};assert.equal(C.contracts(system,null,'NHL',[],now).length,0);assert.equal(C.contracts(system,null,'NBA',[],now).length,1);assert.equal(C.contracts(system,{sport:'NHL',generated_at:at,quotes:[q(1)]},'NBA',[],now).length,1);
const nhl={games:[{sport:'nhl',event_id:'nhl:1',start,matchup:'A @ B',publication_at:at,selections:[]}]},props={sport:'NHL',generated_at:at,source_model_at:at,goal_scorers:[{event_id:'nhl:1',start_time:start,matchup:'A @ B',athlete_id:'1',player:'Scorer',market:'Anytime goal',side:'yes',model_prob:.4}]};assert.equal(C.contracts(nhl,props,'NHL',[],now).length,0);
const fair=C.contracts(nhl,props,'NHL',[],now,true);assert.equal(fair.length,1);assert.equal(fair[0].price_kind,'model-fair');assert.equal(fair[0].price,150);assert.equal(C.metrics(fair).estimated,true);assert.equal(C.contracts(nhl,{...props,source_model_at:'2026-10-21T00:00Z'},'NHL',[],now,true).length,0);assert.equal(C.day('2026-10-23T01:30Z'),'2026-10-22');
console.log('NBA/NHL targets, one-book contracts, conflict guards, expiry, fair scenarios, capture and actual P&L passed.');

const crowded=Array.from({length:300},(_,i)=>q('a'+i,{event_id:'a',player_id:String(i),kind:'player',market:'Points',side:'over',line:20.5,price:5000}));crowded.push(q('z1',{event_id:'z',player_id:'z1',kind:'player',market:'Points',side:'over',line:20.5}),q('z2',{event_id:'z',player_id:'z2',kind:'player',market:'Points',side:'over',line:20.5}));assert.ok(C.build(crowded,{target:500,scope:'slate',now}).length,'A crowded earlier game must not hide later-game contracts');

const watch=[{sport:'NBA',event_id:'1',athlete_id:'p1',player:'Example Player',market:'Points',start_time:start,roster_verified:true,recent:[19,20,24,30],average:23.25}];
const milestones=C.milestones(watch,now),twenty=milestones.find(q=>q.threshold===20);
assert.equal(twenty.pick,'Example Player 20+ points');assert.equal(twenty.line,19.5);assert.equal(twenty.history_hits,3);assert.equal(twenty.history_n,4);
assert.equal(twenty.model_prob,null);assert.equal(twenty.price,null);assert.equal(C.valid(twenty,now),false);assert.equal(C.build(milestones,{target:500,now}).length,0);
assert.equal(C.milestones([...watch,...watch],now).length,milestones.length);assert.equal(C.milestones([{...watch[0],roster_verified:false}],now).length,0);assert.equal(C.milestones([{...watch[0],start_time:at}],now).length,0);
assert.equal(C.milestones([{...watch[0],recent:[]}],now)[0].history_n,0);assert.equal(C.milestones([{...watch[0],market:'Threes'}],now).find(q=>q.threshold===3).line,2.5);
console.log('NBA player milestones: exact thresholds, history counts, deduplication and unpriced exclusion passed.');
