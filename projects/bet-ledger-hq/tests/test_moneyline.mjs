import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('../moneyline-core.js');
const now=Date.parse('2026-09-19T16:00:00Z'),stamp='2026-09-19T15:00:00Z',start='2026-09-19T19:00:00Z';
const nfl={meta:{generated_at:stamp},games:[{game_id:'1',date:start,home:'KC',away:'BUF',season_type:2,status:'Scheduled'}],details:[{game_id:'1',p_home:.65,projection:{mu:4,ratings_known:true}}]};
let [card]=C.cards('nfl',nfl,now);assert.equal(card.predicted,'home');assert.equal(card.probability,.65);assert.equal(card.selectable,true);
const selected=C.choose({},card,'away',now);assert.equal(selected[card.key].team,'BUF');assert.equal(selected[card.key].predicted,'KC');
assert.equal(C.choose(selected,card,'home',Date.parse(start)),selected,'Selection must lock at kickoff even without a refresh');
assert.equal(C.choose(selected,{...card,start:'2026-09-20T19:00:00Z',when:Date.parse('2026-09-20T19:00:00Z')},'home',Date.parse(start)),selected,'A delayed schedule must not unlock an already started selection');
assert.equal(C.cards('nfl',{...nfl,error:true},now)[0].predicted,null);
assert.equal(C.cards('nfl',{...nfl,meta:{generated_at:'2026-09-18T15:00:00Z'}},now)[0].selectable,false);
assert.equal(C.cards('nfl',{...nfl,meta:{generated_at:'2026-09-20T15:00:00Z'}},now)[0].predicted,null);
assert.equal(C.cards('nfl',nfl,Date.parse(start))[0].selectable,false);
assert.equal(C.cards('nfl',{...nfl,games:[{...nfl.games[0],season_type:1}]},now).length,0);
assert.equal(C.cards('nfl',{...nfl,details:[]},now)[0].predicted,null);
const cfb={meta:{generated_at:stamp},games:[{game_id:'1',date:start,home:'ALA',away:'UGA',season_type:2,projection:{mu:-3,ratings_known:true}}]};
[card]=C.cards('ncaaf',cfb,now);assert.equal(card.predicted,'away');assert.equal(card.probability,null,'No invented probability from margin or tier');
assert.equal(C.cards('ncaaf',{...cfb,games:[{...cfb.games[0],projection:{mu:8,ratings_known:false}}]},now)[0].predicted,null);
assert.equal(C.cards('ncaaf',{...cfb,games:[{...cfb.games[0],projection:{mu:0,ratings_known:true}}]},now)[0].predicted,null);
const mlb={slate:{generated_at:stamp,games:[{gamePk:1,start,date:'2026-09-19',away:'TOR',home:'NYY',gameType:'R',sim:{p_home_final:.35},bets:[{market:'TOTAL',tier:'BEST BET',selection:'Over'}]}]}};
[card]=C.cards('mlb',mlb,now);assert.equal(card.predicted,'away','Best value/tier must never choose the winner');assert.equal(card.probability,.65);assert.equal(card.notes,'Projected lineups');
for(const state of ['In Progress','Final','Postponed','Suspended','Canceled']){
 const row=C.cards('mlb',{slate:{...mlb.slate,games:[{...mlb.slate.games[0],status:state}]}},now)[0];assert.equal(row.predicted,null);assert.equal(row.selectable,false);
}
assert.equal(C.cards('mlb',{slate:{...mlb.slate,games:[...mlb.slate.games,...mlb.slate.games]}},now).length,1);
assert.equal(C.day('2026-09-20T01:00:00Z'),'2026-09-19');
for(const p of [null,'',NaN,2,-.1,true])assert.equal(C.cards('mlb',{slate:{...mlb.slate,games:[{...mlb.slate.games[0],sim:{p_home_final:p}}]}},now)[0].predicted,null);
console.log('Moneyline: winner selection, timing, stale feeds, missing inputs, ties, duplicate games and immutable picks passed');
