(function(root,factory){const C=factory(typeof module==='object'?require('./value-core.js'):root.BetValue);if(typeof module==='object')module.exports=C;else root.KevDailyTickets=C;})(typeof globalThis==='undefined'?this:globalThis,function(V){
 'use strict';const sports=['nfl','ncaaf','nba','ncaab','nhl','mlb','wnba'];
 const day=t=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(t));
 const key=r=>[r.game_id,r.market,r.side,r.line??'',r.book,r.price,r.model_version,r.probability,r.push_prob,r.qualified].join('|');
 function history(evidence,g,q){const version=q.model_version||'unversioned';return (evidence?.cohorts||[]).filter(r=>r.sport===g.sport&&r.market===q.market&&r.version===version&&(!g.season||Number(r.season)===Number(g.season))).sort((a,b)=>Number(b.season)-Number(a.season))[0]||null;}
 const evidenceRank=r=>{const h=r.history?.preferred;return h?.n>=30&&h?.dates>=10?(h.roi>0?1:-1):0;};
 function options(system,evidence,{sport='all',date=day(Date.now()),now=Date.now(),minDecimal=1+100/150,maxDecimal=3}={}){
  const rows=[];for(const g of system?.games||[]){if(sport!=='all'&&g.sport!==sport||!sports.includes(g.sport)||Date.parse(g.start)<=now||day(g.start)!==date||!V.fresh(g.publication_at,now,['ncaaf','ncaab'].includes(g.sport)?4:6))continue;
   const unique=new Map();for(const q of g.selections||[]){const d=V.decimal(q.price),p=V.number(q.probability),push=V.number(q.push_prob)??0;
    if(!['ML','ATS','TOTAL'].includes(q.market)||q.market!=='ML'&&V.number(q.line)===null||!(['ML','ATS'].includes(q.market)?['home','away']:['over','under']).includes(q.side)||!q.fresh||!q.book||/model|unknown|unavailable|unspecified/i.test(q.book)||q.price_source==='model'||q.reference_only||q.quote_status&&q.quote_status!=='observed'||d===null||d<minDecimal-1e-9||d>maxDecimal||!V.fresh(q.observed_at,now,['nba','nhl','ncaab'].includes(g.sport)?1.5:4)||Date.parse(q.observed_at)>=Date.parse(g.start)||p===null||p<=.5||p>=1||push<0||push>=1)continue;
    const h=history(evidence,g,q),stressed=Math.max(0,p-.03),ev=(1-push)*(p*d-1),stressEV=(1-push)*(stressed*d-1),target=stressed>0?V.american((1+.02/(1-push))/stressed):null;
    // The preferred list has model-positive research ideas, never invented offers.
    if(ev<=0)continue;
    const priced=h?.preferred,qualified=!!q.qualified&&stressEV>=.02&&priced?.n>=30&&priced?.priced>=30&&priced?.dates>=10&&priced?.roi>0;
    const r={...q,game_id:g.id,event_id:g.event_id,sport:g.sport,matchup:g.matchup,start:g.start,publication_at:g.publication_at,decimal:d,push,probability:p,stressed,ev,stressEV,target,history:h,qualified,source_qualified:!!q.qualified};r.id=key(r);
    const contract=[q.market,q.side,q.line??''].join('|'),prior=unique.get(contract);if(!prior||d>prior.decimal)unique.set(contract,r);
   }rows.push(...unique.values());}
  rows.sort((a,b)=>Number(b.qualified)-Number(a.qualified)||evidenceRank(b)-evidenceRank(a)||(b.history?.all?.n>=30?b.history.all.lower:0)-(a.history?.all?.n>=30?a.history.all.lower:0)||b.stressEV-a.stressEV||a.start.localeCompare(b.start)||a.id.localeCompare(b.id));
  // One option per game prevents opposite sides or duplicate correlated singles.
  const seen=new Set();return rows.filter(r=>{if(seen.has(r.game_id))return false;seen.add(r.game_id);return true;});
 }
 function shortlist(system,evidence,config={}){
  const now=config.now??Date.now(),date=config.date||day(now),sport=config.sport||'all',limit=config.limit??10;
  const current=options(system,evidence,{...config,now,date,sport}).map(r=>({...r,bettable:true})),seen=new Set(current.map(r=>r.game_id)),forecasts=[];
  for(const g of system?.games||[]){const p=V.number(g.p_home);
   if(seen.has(g.id)||!sports.includes(g.sport)||sport!=='all'&&g.sport!==sport||!Number.isFinite(Date.parse(g.start))||Date.parse(g.start)<=now||day(g.start)!==date||!g.forecast_available||p===null||p<=0||p>=1||!V.fresh(g.publication_at,now,['ncaaf','ncaab'].includes(g.sport)?4:6))continue;
   const side=p>=.5?'home':'away',probability=side==='home'?p:1-p,stressed=Math.max(0,probability-.03),row={game_id:g.id,event_id:g.event_id,sport:g.sport,matchup:g.matchup,start:g.start,publication_at:g.publication_at,market:'ML',side,pick:(g[side+'_name']||g[side]||side)+' to win',probability,stressed,price:null,book:null,decimal:null,qualified:false,bettable:false,model_version:g.model_version,target:V.american(1.02/stressed),reason:'Forecast only — no fresh preferred-price positive-value offer. Confirm a current price before building a ticket.'};
   row.history=history(evidence,g,row);row.id='forecast|'+g.id;forecasts.push(row);
  }
  forecasts.sort((a,b)=>b.probability-a.probability||a.start.localeCompare(b.start)||a.game_id.localeCompare(b.game_id));
  return [...current,...forecasts].slice(0,limit);
 }
 function stake(row,{bankroll,budget=20,remaining=budget}={}){
  if(row.bettable===false||!row.qualified)return {amount:0,reason:'Research only: no evidence-backed stake recommendation. A $5 preview is a planning amount.'};
  bankroll=V.number(bankroll);budget=V.number(budget);remaining=V.number(remaining);
  if(!(bankroll>0)||!(budget>=5)||!(remaining>=5))return {amount:0,reason:'Enter a bankroll and remaining daily budget of at least $5.'};
  const k=Math.max(0,(row.stressed*row.decimal-1)/(row.decimal-1))*.25;
  const cap=Math.min(20,budget,remaining,bankroll*.01,bankroll*k),amount=Math.floor(cap/5)*5;
  return amount>=5?{amount,reason:'Quarter-Kelly planning cap, at most 1% of bankroll and $20; assumes the model estimate is usable.'}:{amount:0,reason:'The bankroll-based cap is below $5. Pass; do not round risk up to the minimum.'};
 }
 function ticket(rows,amounts,{budget=20,now=Date.now()}={}){
  const seen=new Set(),errors=[];let risk=0,profit=0;
  rows.forEach(r=>{if(r.bettable===false||V.decimal(r.price)===null)errors.push('A forecast without a usable current price cannot enter a ticket.');const amount=Number(amounts[r.id]);if(!Number.isFinite(amount)||amount<5||amount>20)errors.push('Each single must be $5–$20.');else{risk+=amount;profit+=amount*(r.decimal-1);}if(seen.has(r.game_id))errors.push('Only one single per game.');seen.add(r.game_id);if(Date.parse(r.start)<=now||!V.fresh(r.observed_at,now,['nba','nhl','ncaab'].includes(r.sport)?1.5:4)||!V.fresh(r.publication_at,now,['ncaaf','ncaab'].includes(r.sport)?4:6))errors.push('A game started or its source/price expired. Refresh before exporting.');});
  if(!rows.length)errors.push('Choose at least one single.');if(!Number.isFinite(Number(budget))||risk>Number(budget))errors.push('The selected stakes exceed the daily budget.');
  return {risk,profit,returnIfAllWin:risk+profit,errors:[...new Set(errors)],kind:'Separate singles, not a parlay'};
 }
 return {sports,day,options,shortlist,stake,ticket,history};
});
