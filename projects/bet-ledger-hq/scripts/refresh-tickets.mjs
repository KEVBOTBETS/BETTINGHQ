/* Public, keyless, forward-only archive. Never reads or writes the personal ledger. */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('../today-core.js'),T=require('../ticket-core.js');
const A=require('../alerts-core.js');
const H=require('../pick-history.js');
const root=path.resolve(new URL('..',import.meta.url).pathname),dir=path.join(root,'data/tickets');
const now=Date.now(),stamp=new Date(now).toISOString(),base=new URL('bet-ledger-hq/', 'file://'+path.resolve(process.env.LOCAL_SITE_ROOT||path.join(root,'../../_site'))+'/').href;
const registry=JSON.parse(await fs.readFile(path.join(root,'sports.json'),'utf8'));
await fs.mkdir(dir,{recursive:true});
async function read(file,fallback){try{return JSON.parse(await fs.readFile(path.join(dir,file),'utf8'));}catch(e){if(e.code==='ENOENT')return fallback;throw e;}}
async function write(file,value){const dest=path.join(dir,file);await fs.mkdir(path.dirname(dest),{recursive:true});await fs.writeFile(dest+'.tmp',JSON.stringify(value,null,2)+'\n');await fs.rename(dest+'.tmp',dest);}
async function get(url){if(String(url).startsWith('file:'))return JSON.parse(await fs.readFile(new URL(url),'utf8'));const response=await fetch(url,{signal:AbortSignal.timeout(15000),headers:{'User-Agent':'KEVBOT-public-ticket-archive/1.0'}});if(!response.ok)throw Error('HTTP '+response.status);return response.json();}
const index=await read('index.json',{schema:1,started_at:stamp,tickets:[]});
const state=await read('results.json',{schema:1,entries:{}}),cache=await read('feeds.json',{}),health={checked_at:stamp,feeds:{},result_failures:[]};
const bundles={};
await Promise.all(registry.filter(s=>s.active).map(async sport=>{
  const bundle={};let failed=false;const failures=[];
  await Promise.all(Object.entries(sport.feeds).map(async([field,file])=>{try{
    const data=await get(new URL(sport.path+'data/'+file+'.json',base));
    if(field==='board'&&!Array.isArray(data))throw Error('Board schema');if(field==='slate'&&!Array.isArray(data.games))throw Error('Slate schema');
    bundle[field]=data;
  }catch(e){failures.push(field);if(field!=='accuracy'||sport.key==='ladder')failed=true;}}));
  const previous=cache[sport.key];
  if(failed)bundles[sport.key]={...(previous||{}),error:true};else {bundle.lastGoodAt=stamp;bundles[sport.key]=bundle;cache[sport.key]=bundle;}
  const h=C.health(sport.key,bundles[sport.key],now);health.feeds[sport.key]={status:h.status,failed_fields:failures,published_at:h.stamp,last_good_at:cache[sport.key]?.lastGoodAt||null,warnings:h.warnings};
}));
// A missing source quote timestamp stays null and cannot become a closing quote.
// The archive records when we observed the published price, without inventing its age.
const rows=Object.entries(bundles).flatMap(([k,b])=>C.plays(k,b,now)).filter(r=>r.eventId);
await write('changes.json',H.observe(await read('changes.json',null),bundles,stamp));
const days=[...new Set(rows.map(r=>r.day))].sort().slice(0,8);
for(const day of days){
  const picks=C.topPlays(rows.filter(r=>r.day===day),10);
  const signature=JSON.stringify(picks.map(r=>[T.selectionKey(r),r.line,r.price,r.tier,r.book]));
  const id=crypto.createHash('sha256').update(day+signature).digest('hex').slice(0,16);
  if(!index.tickets.some(t=>t.id===id)){
    const ticket={schema:1,id,day,published_at:stamp,title:'DAILY TOP PICKS',ranking:'Tier, then sport rotation; within-source edge. No calibrated cross-model claim.',picks};
    await write(day+'/'+id+'.json',ticket);index.tickets.push({id,day,published_at:stamp,count:picks.length,path:day+'/'+id+'.json'});
    for(const pick of picks){const key=T.outcomeKey(pick);if(!state.entries[key])state.entries[key]={pick,first_ticket:id,published_at:stamp,result:{status:'Pending'},history:[]};}
  }
}
// Quote tracking includes a previously published pick even when its tier later drops.
const quotes=Object.entries(bundles).flatMap(([key,b])=>{
  const force=r=>({...r,tier:'GOOD',stake:1,recommended_stake:1,held:false});
  const all={...b,board:b.board?.map(force),slate:b.slate?{...b.slate,games:b.slate.games?.map(g=>({...g,bets:g.bets?.map(force)}))}:undefined};
  return C.plays(key,all,now);
});
for(const e of Object.values(state.entries)){
  if(Date.parse(e.pick.start)<=now)continue;
  const candidates=quotes.filter(q=>T.selectionKey(q)===T.selectionKey(e.pick)&&q.book===e.pick.book).sort((a,b)=>Date.parse(b.quote)-Date.parse(a.quote));
  const close=T.closing(e.pick,candidates[0]);if(close&&(!e.closing||Date.parse(close.observed_at)>Date.parse(e.closing.observed_at)))e.closing=close;
}
const paths={nfl:'football/nfl',props:'football/nfl',ncaaf:'football/college-football',wnba:'basketball/wnba'};
const tasks=new Map();
for(const entry of Object.values(state.entries)){
  if(!registry.some(s=>s.active&&s.key===entry.pick.key))continue;
  const age=now-Date.parse(entry.pick.start);if(age<0||age>14*86400000)continue;
  const r=entry.pick,key=(r.key==='props'?'nfl':r.key)+':'+r.eventId;
  if(!tasks.has(key))tasks.set(key,{r,entries:[]});tasks.get(key).entries.push(entry);
}
// Limit concurrent public calls, recheck finals for official stat corrections.
const work=[...tasks.values()];
async function worker(){while(work.length){const task=work.shift(),r=task.r;let summary,game,url;
  try{if(r.key==='mlb'){
    url='https://statsapi.mlb.com/api/v1.1/game/'+encodeURIComponent(r.eventId)+'/feed/live';summary=await get(url);
    game={id:String(summary.gamePk),completed:['Final','Game Over','Completed Early'].includes(summary.gameData?.status?.detailedState),home:summary.liveData?.linescore?.teams?.home?.runs,away:summary.liveData?.linescore?.teams?.away?.runs,start:summary.gameData?.datetime?.dateTime};
  }else if(paths[r.key]){
    url='https://site.api.espn.com/apis/site/v2/sports/'+paths[r.key]+'/summary?event='+encodeURIComponent(r.eventId);summary=await get(url);
    const c=summary.header?.competitions?.[0],team=side=>c?.competitors?.find(t=>t.homeAway===side);
    game={id:String(summary.header?.id),completed:c?.status?.type?.completed===true,home:C.number(team('home')?.score),away:C.number(team('away')?.score),start:c?.date};
  }else continue;
  for(const e of task.entries){const status=e.pick.key==='props'?T.gradeProp(e.pick,summary):T.gradeScore(e.pick,game);
    e.checked_at=stamp;
    if(status){if(e.result.status!==status){e.history.push({at:stamp,from:e.result.status,to:status,source:url});e.result={status,verified_at:stamp,source:url,score:game?.completed?game.away+'–'+game.home:null};}}
    else if(game?.completed)e.review='Final score available; selection/stat needs verification. Pending until verified.';
  }
  }catch(e){health.result_failures.push({sport:r.key,event_id:r.eventId,error:'Official result feed unavailable'});}
}}
await Promise.all(Array.from({length:4},worker));
const injuryPaths={mlb:'baseball/mlb',nfl:'football/nfl',ncaaf:'football/college-football'};
const injuryData={},coverage={};
await Promise.all(Object.entries(injuryPaths).map(async([sport,league])=>{try{const raw=await get('https://site.api.espn.com/apis/site/v2/sports/'+league+'/injuries');const reports=A.injuries(raw,sport,now);if(reports===null)throw Error('schema');injuryData[sport]=reports;coverage[sport]={status:Object.keys(reports).length?'available':'empty',reports:Object.keys(reports).length,checked_at:stamp};}catch(_){injuryData[sport]=null;coverage[sport]={status:'unavailable',reports:0,checked_at:stamp};}}));
const previousAlerts=await read('alerts.json',{events:[]}),previousAlertState=await read('alerts-state.json',{});
const alerts=A.scan(previousAlertState,{quotes,tracked:Object.values(state.entries).map(e=>e.pick),lineups:A.lineups(bundles.mlb,now),injuries:injuryData},stamp);
const events=[...alerts.events,...previousAlerts.events].filter(e=>now-Date.parse(e.observed_at)<7*86400000).slice(0,200);
await write('alerts-state.json',alerts.state);await write('alerts.json',{schema:1,checked_at:stamp,coverage,events});
index.checked_at=stamp;index.tickets.sort((a,b)=>b.published_at.localeCompare(a.published_at));state.checked_at=stamp;
const pickFields=['tier','stake','recommended_stake','held','odds_verified','start_time','game_date','tipoff','game_id','event_id','result_event_id','player','player_id','matchup','market','side','home','away','pick','label','selection','line','price','price_american','book','action_edge','edge_real','edge','model_prob','p_final','updated_at','odds_observed_at','odds_fetched_at','current_season_samples','roster_verified','model_version'];
const slim=r=>Object.fromEntries(pickFields.filter(k=>r[k]!==undefined).map(k=>[k,r[k]]));
for(const b of Object.values(cache)){
 if(b.board)b.board=b.board.map(slim);
 if(b.accuracy)b.accuracy={generated_at:b.accuracy.generated_at};
 if(b.slate)b.slate={generated_at:b.slate.generated_at,games:b.slate.games.map(g=>({gamePk:g.gamePk,home:g.home,away:g.away,start:g.start,status:g.status,lineups_confirmed:g.lineups_confirmed,odds:{fetched_at:g.odds?.fetched_at},bets:(g.bets||[]).map(slim)}))};
}
await write('index.json',index);await write('results.json',state);await write('feeds.json',cache);await write('health.json',health);
console.log(JSON.stringify({snapshots:index.tickets.length,unique_picks:Object.keys(state.entries).length,feeds:health.feeds,result_failures:health.result_failures.length}));
if(Object.values(health.feeds).some(f=>f.failed_fields.some(x=>x!=='accuracy'))||health.result_failures.length){process.exitCode=2;}
