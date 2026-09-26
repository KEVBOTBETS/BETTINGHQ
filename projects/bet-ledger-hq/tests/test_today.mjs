import assert from "node:assert/strict";
import {createRequire} from "node:module";
const require=createRequire(import.meta.url),C=require("../today-core.js");
const now=Date.parse("2026-09-14T16:00:00Z"),stamp="2026-09-14T15:00:00Z",start="2026-09-15T00:15:00Z";
let count=0;
function test(name,fn){fn();count++;console.log("ok",name);}
const base={tier:"GOOD",game_id:"1",game_date:start,matchup:"DEN @ KC",price:-110,book:"DraftKings",stake:2};
const bundle={meta:{generated_at:stamp},board:[base]};
test("Toronto dates are not UTC dates",()=>assert.equal(C.day(start),"2026-09-14"));
test("date-only ledger dates are preserved",()=>assert.equal(C.day("2026-09-14"),"2026-09-14"));
test("missing numbers remain unknown",()=>assert.equal(C.number(null),null));
test("invalid odds are rejected",()=>assert.equal(C.american(0),null));
test("future quote timestamps are unknown",()=>assert.equal(C.freshness("2026-09-14T17:00:00Z",6,now).status,"unknown"));
test("old published data is stale",()=>assert.equal(C.freshness("2026-09-13T15:00Z",6,now).status,"stale"));
test("qualified NFL play passes",()=>assert.equal(C.plays("nfl",bundle,now).length,1));
test("unknown quote time is not called live",()=>assert.ok(C.plays("nfl",bundle,now)[0].review.length));
for(const [name,change] of [["held",{held:true}],["PASS",{tier:"PASS"}],["no stake",{stake:0}],["invalid odds",{price:40}],["started",{game_date:"2026-09-14T14:00Z"}],["unverified",{odds_verified:false}]]){
  test(name+" is excluded",()=>assert.equal(C.plays("nfl",{...bundle,board:[{...base,...change}]},now).length,0));
}
test("stale bundle is excluded",()=>assert.equal(C.plays("nfl",{...bundle,meta:{generated_at:"2026-09-12T12:00Z"}},now).length,0));
test("stale quote is excluded despite fresh generation",()=>assert.equal(C.plays("nfl",{...bundle,board:[{...base,odds_observed_at:"2026-09-13T12:00Z"}]},now).length,0));
test("NCAAF does not require a server bankroll stake",()=>assert.equal(C.plays("ncaaf",{...bundle,board:[{...base,stake:undefined,odds_verified:true}]},now).length,1));
test("MLB zero-stake tier label is not a play",()=>assert.equal(C.plays("mlb",{meta:{generated_at:stamp},slate:{games:[{start,status:"Scheduled",bets:[{...base,stake:0}]}]}},now).length,0));
test("duplicate plays deduplicate",()=>assert.equal(C.plays("nfl",{...bundle,board:[base,base]},now).length,1));
test("daily ticket ranks tier before edge and caps at ten",()=>{
  const rows=Array.from({length:12},(_,i)=>({tier:i===11?"BEST BET":"GOOD",score:i,probability:.5,when:i,key:"nfl"}));
  const top=C.topPlays(rows,10);assert.equal(top.length,10);assert.equal(top[0].tier,"BEST BET");assert.equal(top[1].score,10);
});
test("incomplete availability is visible",()=>assert.ok(C.health("ncaaf",{meta:{generated_at:stamp}},now).warnings.some(x=>/Availability/.test(x))));
test("provider quota is visible without leaking errors",()=>{
  const h=C.health("props",{meta:{generated_at:stamp,source_by_sport:{NFL:{errors:["OUT_OF_USAGE_CREDITS secret test"]}}}},now);
  assert.ok(h.warnings.some(x=>/quota/.test(x)));assert.ok(!JSON.stringify(h).includes("secret"));
});
test("healthy publication is not a sheet sync status",()=>assert.equal(C.health("nfl",bundle,now).status,"recent"));
const bets=[
 {app:"nfl-lab",sport:"NFL",event:"DEN @ KC",event_date:start,status:"Pending",stake:10},
 {app:"props",sport:"NFL",event:"Denver Broncos @ Kansas City Chiefs",event_date:start,status:"Pending",stake:5},
 {app:"ladder",sport:"NFL",event:"DEN @ KC",event_date:start,status:"Win",stake:7,pnl:4},
 {app:"props",sport:"NFL",event:"Multi-game parlay",event_date:start,status:"Pending",stake:3}
];
test("same game across NFL and Props groups",()=>assert.equal(C.exposure(bets).groups[0].stake,15));
test("unmatched positions remain in total exposure",()=>{assert.equal(C.exposure(bets).total,18);assert.equal(C.exposure(bets).unmatched,1);});
test("deleted bets are not exposure",()=>assert.equal(C.exposure([{...bets[0],deleted:true}]).total,0));
test("different sports never combine",()=>assert.notEqual(C.eventKey(bets[0]),C.eventKey({...bets[0],sport:"NCAAF"})));
test("different dates never combine",()=>assert.notEqual(C.eventKey(bets[0]),C.eventKey({...bets[0],event_date:"2026-09-21"})));
test("drawdown counts settlements only",()=>assert.equal(C.drawdown([{status:"Loss",pnl:-10},{status:"Pending",pnl:-100},{status:"Win",pnl:4}],100).max,10));
test("NFL accuracy ignores legacy performance",()=>assert.equal(C.accuracy("nfl",{accuracy:{scope:{season:2026,season_type_label:"regular season"},games:{winner:{n:15,correct:11,accuracy:11/15}}},performance:{overall:{wins:95}}}).n,15));
test("props accuracy never invents betting ROI",()=>assert.equal(C.accuracy("props",{accuracy:{props:{Yards:{graded:3,mae:10}}}}).roi,undefined));
test("future or malformed supplied quote times are excluded",()=>{
  for(const stamp of ["2026-09-14T17:00Z","not-a-date"])assert.equal(C.plays("nfl",{...bundle,board:[{...base,odds_observed_at:stamp}]},now).length,0);
});
test("Ladder pushes and voids are not counted as losses",()=>{
  const a=C.accuracy("ladder",{accuracy:{overall:{settled:8,wins:4,losses:2,pushes:1,voids:1}}});
  assert.equal(a.losses,2);assert.equal(a.pushes,1);assert.equal(a.voids,1);
});
test('WNBA uses tipoff and quote timestamp, never a zero-stake pick',()=>{
 const row={...base,tipoff:start,game_date:undefined,odds_fetched_at:stamp,side:'away'};
 assert.equal(C.plays('wnba',{meta:{generated_at:stamp},board:[row]},now).length,1);
 assert.equal(C.plays('wnba',{meta:{generated_at:stamp},board:[{...row,stake:0}]},now).length,0);
});
test('away NFL and college spreads are converted from home-oriented lines',()=>{
 for(const key of ['nfl','ncaaf'])assert.equal(C.plays(key,{meta:{generated_at:stamp},board:[{...base,market:'ATS',side:'away',line:-7,pick:'DEN +7'}]},now)[0].line,7);
});
test('WNBA already stores selection-oriented spread lines',()=>assert.equal(C.plays('wnba',{meta:{generated_at:stamp},board:[{...base,market:'ATS',side:'away',line:7,pick:'SEA +7'}]},now)[0].line,7));
test('MLB selection resolves side without inventing it',()=>{
 const game={gamePk:1,home:'TB',away:'ATH',start,status:'Scheduled',odds:{fetched_at:stamp},bets:[{tier:'GOOD',stake:1,price:-110,market:'RL',line:-1.5,selection:'ATH',label:'ATH +1.5'}]};
 const row=C.plays('mlb',{meta:{generated_at:stamp},slate:{games:[game]}},now)[0];assert.equal(row.side,'away');assert.equal(row.line,1.5);
});
test('raw edge scales cannot let one sport take every place in the same tier',()=>{
 const rows=[...Array.from({length:10},(_,i)=>({key:'mlb',tier:'GOOD',score:100+i,when:i})),{key:'nfl',tier:'GOOD',score:.01,when:20}];
 assert.equal(C.topPlays(rows,2).some(r=>r.key==='nfl'),true);
});
test("tier is the default play order",()=>{
 const rows=[{key:"ncaaf",tier:"LEAN",when:1},{key:"mlb",tier:"BEST BET",when:9},{key:"nfl",tier:"GOOD",when:5}];
 assert.deepEqual(C.sortPlays(rows).map(r=>r.tier),["BEST BET","GOOD","LEAN"]);
 assert.deepEqual(C.sortPlays(rows,"time").map(r=>r.when),[1,5,9]);
});
test("fair and worst prices come from the model probability",()=>{
 assert.equal(C.fairPrice(0.5),100);
 assert.equal(C.fairPrice(0.6),-150);
 assert.equal(C.worstPrice(0.245,0.025),319);        /* 1.025/0.245 = 4.184 -> +318.4, rounded up */
 assert.equal(C.worstPrice(0.6,0.025),-141);         /* never overstates the room */
 assert.equal(C.worstPrice(null,0.025),null);
});
test("card carries win chance, fair price and the board's own minimum return",()=>{
 const r=C.plays("ncaaf",{meta:{generated_at:stamp,settings:{tiers:{lean:0.025}}},board:[{...base,market:"ML",side:"home",pick:"KC ML",price:220,model_prob:0.35,odds_observed_at:stamp}]},now)[0];
 assert.equal(r.probability,0.35);assert.equal(r.fair,186);assert.equal(r.minReturn,0.025);assert.equal(r.worstReached,false);
});
test("spread movement is read from the pick's side",()=>{
 const away=C.movement("ncaaf",{market:"ATS",line_move:{opened_spread:-13.5}},"away",11.5,-110);
 assert.deepEqual([away.opened,away.now,away.toward],[13.5,11.5,2]);   /* dog got fewer points: market backed it */
 const home=C.movement("ncaaf",{market:"ATS",line_move:{opened_spread:-7}},"home",-6,-110);
 assert.equal(home.toward,-1);                                         /* favourite got cheaper: market faded it */
});
test("totals and moneyline movement",()=>{
 assert.equal(C.movement("nfl",{market:"TOTAL",line_move:{opened_total:44.5}},"under",43,-110).toward,1.5);
 assert.ok(C.movement("ncaaf",{market:"ML",line_move:{opened_ml_away:250}},"away",null,220).toward>0);
 assert.equal(C.movement("ncaaf",{market:"ML",line_move:{opened_ml_home:-150}},"away",null,130),null);
 assert.equal(C.movement("wnba",{market:"TOTAL",open_line:155.5,open_price:-110},"over",154.5,-110).toward,-1);
 assert.equal(C.movement("mlb",{market:"ML"},"home",null,-120),null);
});
test("accuracy passes closing-line value through",()=>assert.equal(C.accuracy("ncaaf",{accuracy:{clv:{forecasts:{spread:{n:3}}},games:{}}}).clv.forecasts.spread.n,3));
console.log(count+" Today checks passed.");
