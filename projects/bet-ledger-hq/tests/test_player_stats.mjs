import assert from 'node:assert/strict';
import {select,format,csv} from '../player-stats-core.mjs';
const rows=[{id:'a',player:'Alpha',team:'A',position:'G',stats:{points:12}},{id:'b',player:'Beta',team:'B',position:'C',stats:{points:9}},{id:'c',player:'Gamma',team:'A',position:'G',stats:{}},{id:'z',player:'Zero',team:'A',position:'G',stats:{points:0}}];
assert.deepEqual(select(rows,{sort:'points',direction:'desc'}).map(r=>r.id),['a','b','z','c']);
assert.deepEqual(select(rows,{sort:'points'}).map(r=>r.id),['z','b','a','c']);
assert.equal(select(rows,{team:'B'}).length,1);assert.equal(select(rows,{projected:true}).length,3);assert.equal(format(0),'0.0');assert.equal(format(undefined),'—');
assert.match(csv([{...rows[0],player:'=SUM(1)'}],'NBA'),/"'=SUM\(1\)"/);
console.log('NBA/NHL stat filtering, numeric ordering, zero/missing, safe CSV passed');
