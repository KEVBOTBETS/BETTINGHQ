/* Apply execution policy to the public artifact only; frozen forecasts stay intact. */
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),V=require('../projects/bet-ledger-hq/value-core.js');
const root=path.resolve(process.argv[2]),now=Date.now();
for(const [repo,sport] of [['nfl-edge-lab','nfl'],['ncaaf-edge-lab','ncaaf'],['props-edge','props'],['nhl-edge-lab','nhl'],['wnba-edge-lab','wnba']]){
  const data=path.join(root,repo,'data'),meta=JSON.parse(await readFile(path.join(data,'meta.json'),'utf8'));
  let board=[];
  for(const name of sport==='props'?['board','legs']:['board']){
    const file=path.join(data,name+'.json'),rows=JSON.parse(await readFile(file,'utf8'));
    if(!Array.isArray(rows))throw Error('Invalid board '+file);
    const annotated=rows.map(r=>V.annotate(r,sport,meta.generated_at,now));
    if(name==='board')board=annotated;
    await writeFile(file,JSON.stringify(annotated)+'\n');
  }
  const qualified=board.filter(r=>['LEAN','GOOD','BEST','BEST BET'].includes(r.tier)&&!r.held&&!r.filtered);
  meta.value_policy={...V.POLICY,qualified:qualified.length,source_qualified:board.filter(r=>['LEAN','GOOD','BEST','BEST BET'].includes(r.source_tier)).length,
    note:'Additional price sensitivity gate. Original model counts retained in source_counts; not a confidence interval.'};
  meta.source_counts=meta.counts?{...meta.counts}:undefined;
  if(meta.counts){
    for(const k of ['qualified','qualified_options','actionable'])if(k in meta.counts)meta.counts[k]=qualified.length;
    for(const [k,tiers] of [['best',['BEST','BEST BET']],['good',['GOOD']],['leans',['LEAN']]])if(k in meta.counts)meta.counts[k]=qualified.filter(r=>tiers.includes(r.tier)).length;
    if('held' in meta.counts)meta.counts.held=0;
    if('held_options' in meta.counts)meta.counts.held_options=0;
  }
  if(meta.board_diagnosis){
    meta.source_board_diagnosis=meta.board_diagnosis;
    meta.board_diagnosis={...meta.board_diagnosis,qualified:qualified.length,headline:qualified.length+' play(s) cleared model and price stress checks',
      reasons:{...meta.board_diagnosis.reasons,'Additional price stress failures':board.filter(r=>!r.value_policy.passes&&['LEAN','GOOD','BEST','BEST BET'].includes(r.source_tier)).length}};
  }
  await writeFile(path.join(data,'meta.json'),JSON.stringify(meta)+'\n');
}
