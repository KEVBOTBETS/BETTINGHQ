(function(root,factory){const C=factory(typeof module==='object'?require('./value-core.js'):root.BetValue);if(typeof module==='object')module.exports=C;else root.KevDailyTickets=C;})(typeof globalThis==='undefined'?this:globalThis,function(V){
 'use strict';const sports=['nfl','ncaaf','nba','ncaab','nhl','mlb','wnba'];
 const day=t=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(t));
 const key=r=>[r.game_id,r.market,r.side,r.line??'',r.book,r.price,r.model_version,r.probability,r.push_prob,r.qualified].join('|');
 function history(evidence,g,q){const version=q.model_version||'unversioned';return (evidence?.cohorts||[]).filter(r=>r.sport===g.sport&&r.market===q.market&&r.version===version&&(!g.season||Number(r.season)===Number(g.season))).sort((a,b)=>Number(b.season)-Number(a.season))[0]||null;}
 const evidenceRank=r=>{const h=r.history?.preferred;return h?.n>=30&&h?.dates>=10?(h.roi>0?1:-1):0;};
 function options(system,evidence,{sport='all',now=Date.now(),date=day(now),allMarkets=false,quoted=false,minDecimal=1+100/150,maxDecimal=3}={}){
  const rows=[];for(const g of system?.games||[]){if(sport!=='all'&&g.sport!==sport||!sports.includes(g.sport)||Date.parse(g.start)<=now||day(g.start)!==date||!V.fresh(g.publication_at,now,['ncaaf','ncaab'].includes(g.sport)?4:6))continue;
   const unique=new Map();for(const q of g.selections||[]){const d=V.decimal(q.price),p=V.number(q.probability),push=V.number(q.push_prob)??0;
    if(!['ML','ATS','TOTAL'].includes(q.market)||q.market!=='ML'&&V.number(q.line)===null||!(['ML','ATS'].includes(q.market)?['home','away']:['over','under']).includes(q.side)||!q.fresh||!q.book||/model|unknown|unavailable|unspecified/i.test(q.book)||q.price_source==='model'||q.reference_only||q.quote_status&&q.quote_status!=='observed'||d===null||d<minDecimal-1e-9||d>maxDecimal||!V.fresh(q.observed_at,now,['nba','nhl','ncaab'].includes(g.sport)?1.5:4)||Date.parse(q.observed_at)>=Date.parse(g.start)||p===null||p<=0||(!quoted&&p<=.5)||p>=1||push<0||push>=1)continue;
    const h=history(evidence,g,q),stressed=Math.max(0,p-.03),ev=(1-push)*(p*d-1),stressEV=(1-push)*(stressed*d-1),target=stressed>0?V.american((1+.02/(1-push))/stressed):null;
    // The preferred list has model-positive research ideas, never invented offers.
    if(ev<=0&&!quoted)continue;
    const bucket=h?.buckets?.[Math.floor(p*10)+':'+Math.floor(d*4)],stamp=Date.parse(evidence?.generated_at);
    const tracked=g.sport==='ncaab'&&q.market==='ML'&&q.tier==='RESEARCH'&&q.model_version&&g.season&&g.forecast_available&&Number.isFinite(g.p_home)&&Math.abs(p-(q.side==='home'?g.p_home:1-g.p_home))<.00001&&p>.5&&Number.isFinite(stamp)&&stamp<=now&&now-stamp<=24*3600000&&bucket?.priced>=100&&bucket.n>=100&&bucket.dates>=20&&bucket.roi>0&&bucket.lower*d>=1.02&&stressEV>=.02;
    const priced=h?.preferred,qualified=tracked||!!q.qualified&&stressEV>=.02&&priced?.n>=30&&priced?.priced>=30&&priced?.dates>=10&&priced?.roi>0;
    const r={...q,game_id:g.id,event_id:g.event_id,sport:g.sport,matchup:g.matchup,start:g.start,publication_at:g.publication_at,decimal:d,push,probability:p,stressed:tracked?Math.min(stressed,bucket.lower):stressed,ev,stressEV,target,history:h,tracked:!!tracked,qualified,source_qualified:!!q.qualified};r.id=key(r);
    const contract=[q.market,q.side,q.line??''].join('|'),prior=unique.get(contract);if(!prior||d>prior.decimal)unique.set(contract,r);
   }rows.push(...unique.values());}
  rows.sort((a,b)=>Number(b.qualified)-Number(a.qualified)||evidenceRank(b)-evidenceRank(a)||(b.history?.all?.n>=30?b.history.all.lower:0)-(a.history?.all?.n>=30?a.history.all.lower:0)||b.stressEV-a.stressEV||a.start.localeCompare(b.start)||a.id.localeCompare(b.id));
  // One option per game prevents opposite sides or duplicate correlated singles.
  if(allMarkets)return rows;const seen=new Set();return rows.filter(r=>{if(seen.has(r.game_id))return false;seen.add(r.game_id);return true;});
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
 function strong(row){return !!row.qualified&&row.stressed>=.60&&row.history?.preferred?.priced>=100&&row.history?.preferred?.dates>=20&&row.history?.preferred?.roi>0&&(1-(row.push||0))*(row.stressed*row.decimal-1)>=.05;}
 function stake(row,{budget=20,remaining=budget}={}){
  if(row.bettable===false||V.decimal(row.price)===null||remaining<5||budget<5)return {amount:0,reason:'No priced single or insufficient remaining budget.'};
  return {amount:5,reason:strong(row)?'$5 standard; optional $10 for this high-confidence qualified pick.':row.qualified?'Standard $5 single.':'$5 planning amount only; this price is not a qualified recommendation.'};
 }
 function ticket(rows,amounts,{budget=20,now=Date.now()}={}){
  const seen=new Set(),errors=[];let risk=0,profit=0;
  rows.forEach(r=>{if(r.bettable===false||V.decimal(r.price)===null)errors.push('A forecast without a usable current price cannot enter a ticket.');const amount=Number(amounts[r.id]);if(amount!==5&&!(amount===10&&strong(r)))errors.push('Use $5 per single; $10 requires a high-confidence qualified pick.');else{risk+=amount;profit+=amount*(r.decimal-1);}if(seen.has(r.game_id))errors.push('Only one single per game.');seen.add(r.game_id);if(Date.parse(r.start)<=now||!V.fresh(r.observed_at,now,['nba','nhl','ncaab'].includes(r.sport)?1.5:4)||!V.fresh(r.publication_at,now,['ncaaf','ncaab'].includes(r.sport)?4:6))errors.push('A game started or its source/price expired. Refresh before exporting.');});
  if(!rows.length)errors.push('Choose at least one single.');if(!Number.isFinite(Number(budget))||risk>Number(budget))errors.push('The selected stakes exceed the daily budget.');
  return {risk,profit,returnIfAllWin:risk+profit,errors:[...new Set(errors)],kind:'Separate singles, not a parlay'};
 }
 return {sports,day,options,shortlist,strong,stake,ticket,history};
});
