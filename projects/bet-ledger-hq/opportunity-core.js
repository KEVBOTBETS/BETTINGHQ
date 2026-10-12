/* Shared finder helpers. Watchlists are research; portfolio uses accepted receipts only. */
(function(root,factory){const api=factory(typeof module==='object'?require('./execution-core.js'):root.BetExecution);if(typeof module==='object'&&module.exports)module.exports=api;else root.KevOpportunities=api;})(typeof self!=='undefined'?self:this,function(X){
 'use strict';const KEY='kevbot-watchlist-v1';
 const number=v=>v==null||v===''||typeof v==='boolean'||!Number.isFinite(Number(v))?null:Number(v);
 function read(storage){try{const x=JSON.parse(storage.getItem(KEY)||'{}');return x.schema===1&&Array.isArray(x.games)?x:{schema:1,games:[]};}catch{return{schema:1,games:[]};}}
 function toggle(storage,id){const old=read(storage),games=old.games.includes(id)?old.games.filter(x=>x!==id):[...old.games,id];storage.setItem(KEY,JSON.stringify({schema:1,games,updated_at:new Date().toISOString()}));return games;}
 function changes(before,after){if(!before)return[];const out=[];for(const [key,label]of [['p_home','Home win estimate'],['margin','Projected margin']]){const a=number(before[key]),b=number(after[key]);if(a!==null&&b!==null&&Math.abs(a-b)>.00001)out.push({label,from:a,to:b});}const a=before.best,b=after.best;if(a&&b&&a.market===b.market&&a.side===b.side&&a.line===b.line&&a.book===b.book&&a.price!=null&&b.price!=null&&a.price!==b.price)out.push({label:'Same-book price',from:a.price,to:b.price});return out;}
 function events(row){
  const normalize=s=>({'nfl-lab':'nfl','ncaaf-lab':'ncaaf','nhl-lab':'nhl','mlb-edge':'mlb','wnba-lab':'wnba'})[String(s).toLowerCase()]||String(s).toLowerCase();
  const n=row.native||{},sport=normalize(row.sport||row.app),legs=Array.isArray(n.legs)?n.legs:[];
  const refs=legs.length?legs:[{sport,event_id:n.game_id||n.event_id,event:row.event,start_time:n.start_time||n.tipoff||row.event_date}];
  return [...new Map(refs.map(l=>{const key=normalize(l.sport||sport)+'|'+(l.event_id||l.game_id||(l.matchup||l.event||row.event)+'|'+String(l.start_time||l.date||row.event_date||'').slice(0,10));return [key,{key,event:l.matchup||l.event||row.event}];})).values()];
 }
 const eventKeys=row=>events(row).map(e=>e.key);
 function portfolio(rows,settings,limit=null){
  const map=new Map(),receipts=[];let missing=0;
  for(const row of rows){if(row.deleted)continue;const r=X.get(settings,row.id);if(!r){missing++;continue;}if(r.accepted.status!=='Pending')continue;receipts.push(r);for(const event of events(row)){const key=event.key;
   if(!map.has(key))map.set(key,{key,event:event.event,stake:0,bets:0,selections:[]});const g=map.get(key);g.stake+=r.accepted.stake;g.bets++;g.selections.push(row.selection);
  }}
  const groups=[...map.values()].sort((a,b)=>b.stake-a.stake).map(g=>({...g,over_limit:number(limit)!==null&&g.stake>limit}));
  return {receipts:receipts.length,total_stake:receipts.reduce((n,r)=>n+r.accepted.stake,0),unconfirmed:missing,groups,overlap:groups.filter(g=>g.bets>1).length,
   note:'Full ticket stake is counted against every game that can lose it. Game groups overlap and must not be added together. Correlation is not quantified.'};
 }
 return {KEY,read,toggle,changes,eventKeys,portfolio};
});
