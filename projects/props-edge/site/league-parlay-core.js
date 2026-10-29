/* Research contracts shared by the NBA and NHL labs. No wagering or inferred book prices. */
(function(root){'use strict';
 const TARGETS=[300,400,500,1000,2000,5000,10000,20000,30000,50000];
 const num=x=>x!==null&&x!==''&&Number.isFinite(Number(x))?Number(x):null;
 const decimal=p=>p>0?1+p/100:1+100/Math.abs(p),american=d=>d>=2?Math.round((d-1)*100):-Math.round(100/(d-1));
 const norm=x=>String(x||'').toLowerCase().replace(/[^a-z0-9]/g,''),day=x=>Number.isFinite(Date.parse(x))?new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(x)):'';
 const fresh=(at,now,hours)=>Number.isFinite(Date.parse(at))&&Date.parse(at)<=now&&now-Date.parse(at)<=hours*3600000;
 const key=q=>[q.sport,q.event_id,q.player_id||'',q.market,q.side,q.line??'',norm(q.book)].join('|');
 function valid(q,now=Date.now()){
  return ['NBA','NHL'].includes(q.sport)&&Boolean(q.event_id)&&Date.parse(q.start_time)>now&&Boolean(q.pick)&&Boolean(norm(q.book))
   &&num(q.price)!==null&&Math.abs(Number(q.price))>=100
   &&(q.kind==='game'?(['ML','ATS'].includes(q.market)?['home','away'].includes(q.side):q.market==='TOTAL'&&['over','under'].includes(q.side)):Boolean(q.player_id)&&(['Anytime goal'].includes(q.market)?['yes','no'].includes(q.side):['over','under'].includes(q.side)))
   &&(q.price_kind!=='model-fair'||(q.sport==='NHL'&&q.market==='Anytime goal'||q.sport==='NBA'&&q.model_version==='nba-milestones-v1'&&q.samples>=10)&&num(q.model_prob)>0&&num(q.model_prob)<1)
   &&(['ML','Anytime goal'].includes(q.market)||num(q.line)!==null)
   &&fresh(q.observed_at,now,q.price_kind==='model-fair'?6:1.5)&&!q.reference_only
   &&!['out','inactive','questionable','doubtful','injured reserve','suspended'].includes(String(q.status||'').toLowerCase())&&!q.shadow?.questionable
   &&(!q.quote_status||q.quote_status==='observed')
   &&(q.price_kind==='model-fair'||!q.price_source||q.price_source!=='model');
 }
 function contracts(system,props,sport,manual=[],now=Date.now(),fair=false){
  const games=(system.games||[]).filter(g=>g.sport===sport.toLowerCase()),ids=new Set(games.map(g=>String(g.event_id))),rows=[];
  if(!fair){for(const g of games){if(!fresh(g.publication_at,now,6))continue;for(const q of g.selections||[])rows.push({...q,sport,event_id:String(g.event_id),matchup:g.matchup,start_time:g.start,price:q.price,model_prob:num(q.probability),price_kind:'book',observed_at:q.observed_at,kind:'game'});}
   if(props?.sport===sport&&fresh(props.generated_at,now,6))for(const q of props.quotes||[])if(ids.has(String(q.event_id)))rows.push({...q,sport,event_id:String(q.event_id),player_id:String(q.athlete_id),price:q.price_american,price_kind:'book',kind:'player',pick:q.market==='Anytime goal'?q.player+' anytime goal':`${q.player} ${q.side} ${q.line??''} ${q.market}`});
   for(const q of manual)if(q.sport===sport&&ids.has(String(q.event_id)))rows.push({...q,price_kind:'manual',kind:'player'});
  }else if(sport==='NHL'&&props?.sport==='NHL'&&fresh(props.generated_at,now,6)&&fresh(props.source_model_at,now,6)){
   for(const q of props.goal_scorers||[]){const p=num(q.model_prob);if(p===null||p<=0||p>=1||!ids.has(String(q.event_id)))continue;rows.push({...q,sport,event_id:String(q.event_id),player_id:String(q.athlete_id),pick:q.player+' anytime goal',price:american(1/p),book:'MODEL FAIR · NOT OFFERED',price_kind:'model-fair',observed_at:props.generated_at,kind:'player'});}
  }
  if(fair&&sport==='NBA'&&props?.sport==='NBA'&&fresh(props.generated_at,now,6)&&fresh(props.source_model_at,now,6)){
   for(const q of props.milestone_forecasts||[]){const p=num(q.model_prob);if(p===null||p<=0||p>=1||!ids.has(String(q.event_id)))continue;rows.push({...q,sport,event_id:String(q.event_id),start_time:games.find(g=>String(g.event_id)===String(q.event_id))?.start,player_id:String(q.athlete_id),price:american(1/p),book:'MODEL FAIR · NOT OFFERED',price_kind:'model-fair',observed_at:props.generated_at,kind:'player'});}
  }
  if(sport==='NBA'&&!fair){const estimates=new Map((props?.milestone_forecasts||[]).map(q=>[[String(q.event_id),String(q.athlete_id),q.market,q.side,q.line].join('|'),q]));
   for(const q of rows)if(q.kind==='player'){const estimate=estimates.get([q.event_id,q.player_id,q.market,q.side,q.line].join('|'));if(estimate&&fresh(props.generated_at,now,6)&&fresh(props.source_model_at,now,6)){q.model_prob=estimate.model_prob;q.ranking_prob=estimate.ranking_prob;q.samples=estimate.samples;q.reason=estimate.reason;}}
  }
  const latest=new Map();for(const q of rows){if(!valid(q,now))continue;const k=key(q),old=latest.get(k);if(!old||Date.parse(q.observed_at)>Date.parse(old.observed_at))latest.set(k,{...q,id:k,price:Number(q.price),price_decimal:decimal(Number(q.price)),model_prob:num(q.model_prob)});}
  return [...latest.values()];
 }
 const MILESTONES={Points:[10,15,20,25,30,35,40],Rebounds:[4,6,8,10,12,15],Assists:[4,6,8,10,12],Threes:[1,2,3,4,5,6]};
 function milestones(watch,now=Date.now()){
  const seen=new Set();return (watch||[]).filter(q=>q.sport==='NBA'&&q.athlete_id&&MILESTONES[q.market]&&Date.parse(q.start_time)>now&&q.roster_verified===true&&!['out','inactive','questionable','doubtful','suspended'].includes(String(q.status||'').toLowerCase())).flatMap(q=>{
   const id=[q.event_id,q.athlete_id,q.market].join('|');if(seen.has(id))return [];seen.add(id);
   const recent=(q.recent||[]).filter(v=>typeof v==='number'&&Number.isFinite(v)&&v>=0);
   return MILESTONES[q.market].map(n=>({...q,milestone_id:id+'|'+n,threshold:n,line:n-.5,side:'over',kind:'player',player_id:String(q.athlete_id),pick:q.player+' '+n+'+ '+q.market.toLowerCase(),history_hits:recent.filter(v=>v>=n).length,history_n:recent.length,model_prob:null,price:null,price_kind:'unpriced',qualified:false}));
  });
 }
 function compatible(q,chosen,profile){
  return !chosen.some(l=>l.id===q.id||q.sport==='NBA'&&q.player_id&&q.player_id===l.player_id||profile==='core'&&l.event_id===q.event_id
   ||q.event_id===l.event_id&&(q.player_id&&q.player_id===l.player_id
    ||!q.player_id&&!l.player_id&&(q.market==='TOTAL'&&l.market==='TOTAL'||['ML','ATS'].includes(q.market)&&['ML','ATS'].includes(l.market))));
 }
 function metrics(legs){const dec=legs.reduce((p,q)=>p*decimal(Number(q.price)),1),sameGame=new Set(legs.map(q=>q.event_id)).size<legs.length;
  const known=legs.every(q=>num(q.model_prob)!==null&&q.model_prob>0&&q.model_prob<1&&!(num(q.push_prob)>0));
  return {decimal:dec,american:american(dec),same_game:sameGame,model_baseline:!sameGame&&known?legs.reduce((p,q)=>p*q.model_prob,1):null,estimated:legs.some(q=>q.price_kind==='model-fair'),combined_quote_verified:false,actionable:false};
 }
 function build(pool,{target=500,profile='moonshot',scope='day',game='all',date='all',book='all',kind='all',now=Date.now()}={}){
  if(!TARGETS.includes(Number(target))||scope==='game'&&game==='all')return [];
  const minPlayerChance=target<=500?.60:target<=1000?.50:target<=2000?.45:target<=5000?.35:target<=20000?.25:.18;
  const eligible=pool.filter(q=>valid(q,now)&&(q.sport!=='NBA'||q.price_kind!=='model-fair'||num(q.model_prob)>=minPlayerChance)&&(profile!=='core'||q.qualified===true&&num(q.model_prob)>=.6&&q.price_kind==='book')&&(kind==='all'||q.kind===kind||q.market===kind)&&(game==='all'||q.event_id===game)&&(scope==='slate'||date==='all'||day(q.start_time)===date)&&(book==='all'||norm(q.book)===norm(book)));
  const groups=[...new Set(eligible.map(q=>norm(q.book)))],finished=[];
  for(const group of groups){const perGame=new Map(),aim=Math.pow(1+target/100,profile==='core'?0.5:1/3);
   for(const q of eligible.filter(q=>norm(q.book)===group)){if(!perGame.has(q.event_id))perGame.set(q.event_id,[]);perGame.get(q.event_id).push(q);}
   const lists=[...perGame.values()].map(rows=>rows.sort((a,b)=>Math.abs(Math.log(decimal(a.price)/aim))-Math.abs(Math.log(decimal(b.price)/aim))));
   const short=[];for(let depth=0;short.length<240;depth++){let added=false;for(const list of lists)if(list[depth]&&short.length<240){short.push(list[depth]);added=true;}if(!added)break;}
   const rows=short.sort((a,b)=>String(a.id).localeCompare(String(b.id))),maxLegs=profile==='core'?3:eligible.some(q=>q.sport==='NBA'&&q.price_kind==='model-fair')?6:8,tolerance=eligible.some(q=>q.sport==='NBA'&&q.price_kind==='model-fair')?.05:.10,min=1+Number(target)*(1-tolerance)/100,max=1+Number(target)*(1+tolerance)/100;let beam=[{legs:[],dec:1,last:-1}];
   for(let count=1;count<=maxLegs;count++){const next=[];
    for(const state of beam)for(let i=state.last+1;i<rows.length;i++){const q=rows[i];if(!compatible(q,state.legs,profile)||q.sport==='NBA'&&q.price_kind==='model-fair'&&scope!=='game'&&state.legs.some(l=>l.event_id===q.event_id))continue;const d=state.dec*decimal(Number(q.price));if(d>max)continue;const entry={legs:[...state.legs,q],dec:d,last:i};if(count>=2&&d>=min)finished.push(entry);else next.push(entry);}
    // Keep price-diverse partial combinations so small-price legs remain reachable.
    const buckets=new Map();for(const s of next){const k=Math.round(Math.log(s.dec)*70),old=buckets.get(k);if(!old||s.last<old.last)buckets.set(k,s);}beam=[...buckets.values()].sort((a,b)=>Math.abs(Math.log(a.dec/(1+target/100)))-Math.abs(Math.log(b.dec/(1+target/100)))).slice(0,160);if(!beam.length)break;
   }
  }
  const ranked=eligible.some(q=>q.sport==='NBA'&&q.price_kind==='model-fair');const rank=s=>s.legs.reduce((v,q)=>v+Math.log(Math.max(.001,num(q.ranking_prob)??num(q.model_prob)??.01)),0);
  finished.sort((a,b)=>(ranked?rank(b)-rank(a):0)||Math.abs(a.dec-(1+target/100))-Math.abs(b.dec-(1+target/100))||a.legs.length-b.legs.length);
  const picked=[];for(const s of finished){if(picked.some(t=>s.legs.filter(q=>t.legs.some(l=>l.id===q.id)).length>=Math.max(1,s.legs.length-1)))continue;
   picked.push({id:s.legs.map(q=>q.id).join('~'),sport:s.legs[0].sport,target:Number(target),profile,scope,created_at:new Date(now).toISOString(),legs:s.legs.map(q=>({...q})),...metrics(s.legs)});if(picked.length===2)break;}
  return picked;
 }
 function diagnose(pool,options,games,now=Date.now()){
  const date=options.date||'all',scope=options.scope||'day',game=options.game||'all';const upcoming=(games||[]).filter(g=>Date.parse(g.start)>now),matching=upcoming.filter(g=>(game==='all'||String(g.event_id)===game)&&(scope==='slate'||date==='all'||day(g.start)===date));
  const counts=new Map();for(const g of upcoming){const d=day(g.start);counts.set(d,(counts.get(d)||0)+1);}const next=[...counts.keys()].sort().find(d=>(date==='all'||d>date)&&counts.get(d)>=2);
  if(scope==='game'&&game==='all')return {reason:'Choose one game for same-game drafts.',next_day:null};
  if(!matching.length)return {reason:'No upcoming games remain for this date and game filter.',next_day:next};
  if(scope!=='game'&&matching.length<2)return {reason:'Only '+matching.length+' upcoming game remains on '+date+'. Multi-game parlays need at least two different games. Same-game research is available through Scope.',next_day:next};
  const eligible=pool.filter(q=>valid(q,now)&&(game==='all'||q.event_id===game)&&(scope==='slate'||date==='all'||day(q.start_time)===date)&&(options.kind==='all'||!options.kind||q.kind===options.kind||q.market===options.kind)&&(options.book==='all'||!options.book||norm(q.book)===norm(options.book)));
  if(!eligible.length)return {reason:options.fair?'No usable player estimates match these filters. Check player history, availability coverage and the selected stat.':'No current sportsbook contracts match these filters. Observed offers and model fair scenarios use separate pricing pools.',next_day:next};
  if(options.profile==='core')return {reason:'No Core combination qualifies. Research drafts remain available without becoming qualified bets.',next_day:next};
  return {reason:'Current contracts cannot reach this target after the leg-chance, player, game and single-book rules. Try another target or date; a price is never invented to fill a ticket.',next_day:next};
 }
 function capture(t,now=Date.now()){if(!t?.legs?.length||t.legs.length<2||t.legs.length>8||!t.legs.every(q=>valid(q,now))||new Set(t.legs.map(q=>norm(q.book))).size!==1)throw Error('Draft has expired or mixes books. Refresh and rebuild.');return JSON.parse(JSON.stringify({...t,captured_at:new Date(now).toISOString()}));}
 const profit=b=>b.result==='Win'?Number(b.stake)*(decimal(Number(b.actual_price))-1):b.result==='Loss'?-Number(b.stake):0;
 const api={diagnose,MILESTONES,milestones,TARGETS,num,decimal,american,norm,day,fresh,key,valid,contracts,compatible,metrics,build,capture,profit};root.LeagueParlays=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
