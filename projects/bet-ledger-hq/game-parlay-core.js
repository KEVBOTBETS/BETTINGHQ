/* Distinct-game football research. Only observed game contracts; no player props. */
(function(root,factory){const api=factory(typeof module==='object'?require('./today-desk-core.js'):root.KevTodayDesk,typeof module==='object'?require('./value-core.js'):root.BetValue);if(typeof module==='object')module.exports=api;else root.GameParlays=api;})(typeof self!=='undefined'?self:this,function(C,V){
 'use strict';const VERSION='game-parlays-v1',TARGETS=[500,1000,2000,10000],num=V.number,dec=V.decimal,instant=v=>Date.parse(v),book=v=>String(v||'').trim().toLowerCase();
 function eligible(g,q,{now=Date.now(),sport='ncaaf',day='all',market='points',qualifiedOnly=false}={}){
  const p=num(q.probability),push=num(q.push_prob)??0,pub=instant(g.publication_at);
  return g.sport===sport&&instant(g.start)>now&&instant(g.start)<now+7*86400000&&(day==='all'||C.day(g.start)===day)&&!!q.pick&&(['ML','ATS'].includes(q.market)?['home','away'].includes(q.side):q.market==='TOTAL'&&['over','under'].includes(q.side))&&['ML','ATS','TOTAL'].includes(q.market)&&(market==='all'||market==='points'&&q.market!=='ML'||market===q.market)&&!q.player&&!q.reference_only&&q.price_source!=='model'&&(!q.quote_status||q.quote_status==='observed')&&C.fresh(g,q,now)&&pub<=now&&now-pub<=6*3600000&&!!book(q.book)&&!/unknown|unspecified|unavailable/.test(book(q.book))&&p!==null&&p>=.5&&p<1&&push>=0&&push<1&&(q.market==='ML'||num(q.line)!==null)&&(!qualifiedOnly||C.qualified(g,q,now));
 }
 function candidates(games,options={}){
  const wanted=options.book?book(options.book):null,groups=[],seen=new Set();
  for(const g of games||[]){if(seen.has(g.id))continue;seen.add(g.id);const latest=new Map();for(const q of g.selections||[]){if(!eligible(g,q,options)||wanted&&book(q.book)!==wanted)continue;const key=[q.market,q.side,q.line??'',book(q.book)].join('|'),old=latest.get(key);if(!old||instant(q.observed_at)>instant(old.observed_at))latest.set(key,q);}
   const rows=[...latest.values()].map(q=>({...q,game:g.id,event_id:g.event_id,matchup:g.matchup,sport:g.sport,start:g.start,publication_at:g.publication_at,model_version:q.model_version||g.model_version||'unversioned',source_qualified:C.qualified(g,q,options.now??Date.now()),projection:g.score_projection||null}));
   // Highest conditional win estimate in each game market/book. Opposite sides are not separate candidate evidence.
   const preferred=new Map();for(const q of rows){const key=q.market+'|'+book(q.book),old=preferred.get(key);if(!old||q.probability>old.probability||q.probability===old.probability&&dec(q.price)>dec(old.price))preferred.set(key,q);}if(preferred.size)groups.push({id:g.id,rows:[...preferred.values()]});
  }return groups.sort((a,b)=>a.id.localeCompare(b.id));
 }
 function books(games,options={}){const counts=new Map();for(const g of candidates(games,{...options,book:null})){for(const name of new Set(g.rows.map(q=>q.book))){counts.set(name,(counts.get(name)||0)+1);}}return [...counts].map(([name,games])=>({name,games})).sort((a,b)=>b.games-a.games||a.name.localeCompare(b.name));}
 function scenario(legs,stress=0){let allWin=1,noLoss=1,allPush=1,multiplier=1,conditional=1;for(const q of legs){const p=Math.max(0,Number(q.probability)-stress),push=Number(q.push_prob)||0,win=p*(1-push);allWin*=win;noLoss*=win+push;allPush*=push;conditional*=p;multiplier*=win*dec(q.price)+push;}return {all_win:allWin,profit_chance:noLoss-allPush,no_loss:noLoss,all_push:allPush,conditional_all_win:conditional,expected_multiplier:multiplier};}
 function metrics(legs){const decimal=legs.reduce((d,q)=>d*dec(q.price),1),base=scenario(legs),stress3=scenario(legs,.03),stress5=scenario(legs,.05);return {decimal,american:V.american(decimal),no_push_breakeven:1/decimal,base,stress3,stress5,weakest:[...legs].sort((a,b)=>a.probability*(1-(a.push_prob||0))-b.probability*(1-(b.push_prob||0)))[0]?.game||null,assumption:'Independent outcomes across distinct games; push legs drop to multiplier 1 under standard rules. These are unvalidated model scenarios, not a quoted parlay or qualified bet.'};}
 function build(games,options={}){
  const target=Number(options.target??500);if(!TARGETS.includes(target))return null;
  const list=books(games,options),selected=options.book||list[0]?.name;if(!selected)return null;
  const groups=candidates(games,{...options,book:selected}),targetDec=1+target/100,max=targetDec*1.25,dp=Array.from({length:9},()=>new Map());dp[0].set(0,{legs:[],decimal:1,stress:1});
  for(const group of groups){for(let n=8;n>=1;n--){const prior=[...dp[n-1].values()];for(const state of prior)for(const q of group.rows){const d=state.decimal*dec(q.price);if(d>max)continue;const key=Math.round(Math.log(d)/.035),stress=state.stress*Math.max(0,q.probability-.05)*(1-(q.push_prob||0)),candidate={legs:[...state.legs,q],decimal:d,stress},old=dp[n].get(key);if(!old||stress>old.stress||stress===old.stress&&Math.abs(Math.log(d/targetDec))<Math.abs(Math.log(old.decimal/targetDec)))dp[n].set(key,candidate);}}}
  const feasible=dp.slice(2).flatMap(m=>[...m.values()]).map(s=>({...s,distance:Math.abs(Math.log(s.decimal/targetDec))})).filter(s=>s.distance<=Math.log(1.25));if(!feasible.length)return null;const closest=Math.min(...feasible.map(s=>s.distance)),best=feasible.filter(s=>s.distance<=closest+.035).sort((a,b)=>b.stress-a.stress||a.distance-b.distance||a.legs.length-b.legs.length)[0];
  return {schema:1,version:VERSION,sport:options.sport||'ncaaf',target,book:selected,day:options.day||'all',market:options.market||'points',qualified_only:!!options.qualifiedOnly,created_at:new Date(options.now??Date.now()).toISOString(),legs:best.legs,metrics:metrics(best.legs),qualified:false};
 }
 function valid(ticket,games,now=Date.now()){
  if(!ticket?.legs?.length||ticket.legs.length>8||new Set(ticket.legs.map(q=>q.game)).size!==ticket.legs.length)return false;
  return ticket.legs.every(q=>{const g=games.find(g=>g.id===q.game);return g&&eligible(g,q,{now,sport:ticket.sport,market:'all'})&&book(q.book)===book(ticket.book)&&g.selections.some(r=>r.market===q.market&&r.side===q.side&&num(r.line)===num(q.line)&&book(r.book)===book(q.book)&&Number(r.price)===Number(q.price)&&num(r.probability)===num(q.probability)&&Number(r.push_prob||0)===Number(q.push_prob||0)&&(!ticket.qualified_only||C.qualified(g,r,now))&&C.fresh(g,r,now));});
 }
 return {VERSION,TARGETS,eligible,candidates,books,scenario,metrics,build,valid};
});
