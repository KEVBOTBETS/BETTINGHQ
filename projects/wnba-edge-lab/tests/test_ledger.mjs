import assert from "node:assert/strict";
import {createRequire} from "node:module";
const require = createRequire(import.meta.url);
const L = require("../site/ledger.js");

const candidate = {
  candidate_id:"1:TOTAL:over", game_id:"1", date:"2026-08-26",
  tipoff:"2026-08-26T23:00Z", matchup:"SEA @ NY", market:"TOTAL", side:"over",
  pick:"Over 160.5", line:160.5, price:-110, book:"DraftKings",
  model_prob:.57, market_fair_prob:.5, breakeven:.5238, edge:.035, tier:"BEST BET", stake:10,
};

const entry = L.entryFrom(candidate, 12.5);
assert.equal(entry.stake, 12.5);
assert.equal(L.keyOf(entry), "1|TOTAL|over");

const merged = L.merge([entry], [entry]);
assert.equal(merged.entries.length, 1);
assert.equal(merged.added, 0);

const final = {game_id:"1", completed:true, away:{score:82}, home:{score:85}};
const settled = L.settleAll([entry], [final]);
assert.equal(settled.changed, 1);
assert.equal(settled.entries[0].result, "Win");
assert.equal(settled.entries[0].profit, 11.36);

const summary = L.summarise(settled.entries, 200);
assert.equal(summary.bankroll, 211.36);
assert.equal(summary.settled, 1);
assert.match(L.toCSV(settled.entries), /SEA @ NY/);

console.log("WNBA manual ledger tests passed");

// An archived final settles a wager even when the displayed slate is empty.
const oldBet={game_id:"old",market:"ML",side:"home",price:-110,stake:10};
const oldFinal={game_id:"old",completed:true,away:{score:71},home:{score:97}};
const archiveResult=L.settleAll([oldBet],[oldFinal]);
assert.equal(archiveResult.changed,1);
assert.equal(archiveResult.entries[0].result,"Win");
assert.equal(L.settleAll(archiveResult.entries,[]).changed,0);
