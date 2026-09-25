import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

// Execute the actual template functions without a browser or network requests.
const source = readFileSync(new URL('../ladder/webledger.py', import.meta.url), 'utf8');
const start = source.indexOf('  function reflow(){');
const end = source.indexOf('  // Self-settlement', start);
const ctx = {entries:[], CFG:{base_stake:5, max_rung:1, stake_increment:.01}};
vm.createContext(ctx);
vm.runInContext(source.slice(start, end), ctx);
for (const [league, side, expected] of [['nfl','home','push'],['nfl','away','push'],['epl','home','loss'],['epl','draw','win']]) {
  const entry = {league, side};
  ctx.settleFrom(entry, {winner:'draw', date:'2026-09-06'});
  assert.equal(entry.result, expected);
}
ctx.entries = [{added:'1',stake:10,stake_edited:true,decimal:2,result:'win'}];
assert.equal(ctx.reflow().net,10);
ctx.CFG.max_rung = 4;
ctx.entries.push({added:'2',stake:7,stake_edited:true,decimal:2,result:'loss'});
assert.equal(ctx.reflow().net,3);
ctx.entries = [{added:'1',stake:10,stake_edited:true,decimal:2,result:'push'}];
assert.equal(ctx.reflow().stake,10);
ctx.CFG.reset_at = '2026-09-14T22:00:00+00:00';
ctx.entries = [
  {added:'2026-09-05T12:00:00+00:00',stake:5,stake_edited:true,decimal:2,result:'win'},
  {added:'2026-09-14T22:01:00+00:00',stake:5,stake_edited:true,decimal:1.5,result:'win'}
];
assert.equal(ctx.reflow().rung,1);
assert.equal(ctx.reflow().stake,7.5);
console.log('browser tie settlement and actual-stake accounting passed');
