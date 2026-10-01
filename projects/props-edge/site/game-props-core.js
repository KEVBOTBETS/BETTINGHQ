/* Individual prop rankings. Never a combined same-game betting ticket. */
(function(root){
  'use strict';
  const norm=x=>String(x??'').toLowerCase().replace(/[^a-z0-9]/g,'');
  const number=x=>x!==null&&x!==''&&Number.isFinite(Number(x));
  const tier={'BEST BET':0,GOOD:1,LEAN:2};
  const weekKey=g=>`${Number(g.season_type)||2}:${Number(g.week)}`;
  function rank(game,legs,{now=Date.now(),generatedAt,maxAgeHours=12}={}){
    if(game.completed||Date.parse(game.date)<=now)return [];
    const rows=legs.filter(l=>{
      const at=Date.parse(l.updated_at||generatedAt),start=Date.parse(l.start_time);
      return String(l.event_id)===String(game.game_id)&&l.sport==='NFL'&&start>now
        &&Number.isFinite(at)&&at<=now&&now-at<=maxAgeHours*3600000
        &&number(l.model_prob)&&Number(l.model_prob)>0&&Number(l.model_prob)<1
        &&Number(l.samples)>=3&&l.roster_verified!==false
        &&!['out','inactive','injured reserve','suspended','doubtful'].includes(String(l.status||'').toLowerCase())
        &&(l.line_source||l.price_source==='book'||l.imported)
        &&['over','under','yes','no'].includes(l.side)
        &&(['yes','no'].includes(l.side)||number(l.line));
    }).map(l=>{
      const qualified=l.price_source==='book'&&!l.held&&tier[l.tier]!==undefined
        &&number(l.action_edge??l.edge)&&Number(l.action_edge??l.edge)>0
        &&number(l.price_american)&&Math.abs(Number(l.price_american))>=100;
      return {...l,game_prop_qualified:qualified};
    });
    rows.sort((a,b)=>Number(b.game_prop_qualified)-Number(a.game_prop_qualified)
      ||(a.game_prop_qualified?((tier[a.tier]??9)-(tier[b.tier]??9))||Number(b.action_edge??b.edge)-Number(a.action_edge??a.edge):0)
      ||Number(b.model_prob)-Number(a.model_prob)||Number(b.confidence||0)-Number(a.confidence||0)
      ||String(a.id).localeCompare(String(b.id)));
    const seen=new Set();
    return rows.filter(l=>{const key=norm(l.player)+'|'+norm(l.market);if(seen.has(key))return false;seen.add(key);return true;}).slice(0,10);
  }
  function weeks(games,meta={}){
    const map=new Map();
    for(const w of meta.calendar||[])map.set(weekKey(w),{...w,key:weekKey(w)});
    for(const g of games){const key=weekKey(g);if(!map.has(key))map.set(key,{key,season_type:Number(g.season_type)||2,week:Number(g.week),label:`${Number(g.season_type)===1?'Preseason ':Number(g.season_type)===3?'Postseason ':''}Week ${g.week}`});}
    for(let w=1;w<=18;w++){const key=`2:${w}`;if(!map.has(key))map.set(key,{key,season_type:2,week:w,label:`Week ${w}`});}
    return [...map.values()].sort((a,b)=>a.season_type-b.season_type||a.week-b.week);
  }
  function capture(game,legs,now=Date.now()){
    if(!legs.length||legs.length>10||Date.parse(game.date)<=now||!Number.isFinite(Date.parse(game.date))||game.completed)throw Error('Only a current pregame list can be saved.');
    if(legs.some(l=>String(l.event_id)!==String(game.game_id)||!l.player||!l.market||Date.parse(l.start_time)<=now||!Number.isFinite(Date.parse(l.start_time))))throw Error('Selections must belong to this game and be saved before kickoff.');
    const keys=legs.map(l=>norm(l.player)+'|'+norm(l.market));if(new Set(keys).size!==keys.length)throw Error('Duplicate player markets cannot be saved.');
    return JSON.parse(JSON.stringify({schema:1,id:'game-'+game.game_id,game,captured_at:new Date(now).toISOString(),legs,manual:{}}));
  }
  function grade(ticket,results,settler,now=Date.now()){
    const evidence=settler.settle(ticket,results,now);
    const legs=evidence.legs.map(l=>{const manual=ticket.manual?.[settler.key(l)];return manual&&['Win','Loss','Pending','Push','Void'].includes(manual.result)?{...l,result:manual.result,actual:null,result_source:'Manual',manual_at:manual.at}:{...l,result_source:l.graded_at?'Verified final result':'Awaiting result'};});
    const counts=Object.fromEntries(['Win','Loss','Pending','Push','Void','Review'].map(s=>[s,legs.filter(l=>l.result===s).length]));
    return {legs,counts,result:settler.outcome(legs)};
  }
  const api={rank,weeks,weekKey,capture,grade};root.GameProps=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
