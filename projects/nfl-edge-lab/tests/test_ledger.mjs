import assert from "node:assert/strict";
import {createRequire} from "node:module";
const require=createRequire(import.meta.url);const L=require("../site/ledger.js");
const row={game_id:"1",game_date:"2026-09-10T00:00Z",week:1,season_type:2,matchup:"BUF @ NYJ",market:"ATS",side:"home",pick:"NYJ -3",line:-3,price:-110,book:"DraftKings",model_prob:.57,market_fair_prob:.5,breakeven:.5238,edge:.035,edge_raw:.07,tier:"GOOD",confidence:.8,stake:8};
const entry=L.entryFrom(row,10);assert.equal(entry.stake,10);assert.equal(L.keyOf(entry),"1|ATS|home");
assert.equal(L.merge([entry],[entry]).entries.length,1);
let settled=L.settleAll([entry],[{game_id:"1",completed:true,away:"BUF",home:"NYJ",away_score:20,home_score:24}]);assert.equal(settled.entries[0].result,"Win");assert.equal(settled.entries[0].pnl,9.09);
const sum=L.summarise(settled.entries,500);assert.equal(sum.current_bankroll,509.09);assert.equal(sum.settled,1);assert.match(L.toCSV(settled.entries),/BUF @ NYJ/);
console.log("NFL manual ledger tests passed");
