/* Research contracts shared by the NBA and NHL labs. No wagering or inferred book prices. */
(function(root){'use strict';
 const TARGETS=[300,400,500,1000,2000,5000,10000,30000,50000];
 const num=x=>x!==null&&x!==''&&Number.isFinite(Number(x))?Number(x):null;
 const decimal=p=>p>0?1+p/100:1+100/Math.abs(p),american=d=>d>=2?Math.round((d-1)*100):-Math.round(100/(d-1));
 const norm=x=>String(x||'').toLowerCase().replace(/[^a-z0-9]/g,''),day=x=>Number.isFinite(Date.parse(x))?new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(x)):'';
 const fresh=(at,now,hours)=>Number.isFinite(Date.parse(at))&&Date.parse(at)<=now&&now-Date.parse(at)<=hours*3600000;
 const key=q=>[q.sport,q.event_id,q.player_id||'',q.market,q.side,q.line??'',norm(q.book)].join('|');
 function valid(q,now=Date.now()){
  return ['NBA','NHL'].includes(q.sport)&&Boolean(q.event_id)&&Date.parse(q.start_time)>now&&Boolean(q.pick)&&Boolean(norm(q.book))
   &&num(q.price)!==null&&Math.abs(Number(q.price))>=100
   &&(q.kind==='game'?(['ML','ATS'].includes(q.market)?['home','away'].includes(q.side):q.market==='TOTAL'&&['over','under'].includes(q.side)):Boolean(q.player_id)&&(['Anytime goal'].includes(q.market)?['yes','no'].includes(q.side):['over','under'].includes(q.side)))
   &&(q.price_kind!=='model-fair'||q.sport==='NHL'&&q.market==='Anytime goal'&&num(q.model_prob)>0&&num(q.model_prob)<1)
   &&(['ML','Anytime goal'].includes(q.market)||num(q.line)!==null)
   &&fresh(q.observed_at,now,q.price_kind==='model-fair'?6:1.5)&&!q.reference_only
   &&!['out','inactive','doubtful','injured reserve','suspended'].includes(String(q.status||'').toLowerCase())&&!q.shadow?.questionable
   &&(!q.quote_status||q.quote_status==='observed')
   &&(q.price_kind==='model-fair'||!q.price_source||q.price_source!=='model');
 }
 function contracts(system,props,sport,manual=[],now=Date.now(),fair=false){
  const games=(system.games||[]).filter(g=>g.sport===sport.toLowerCase()),ids=new Set(games.map(g=>String(g.event_id))),rows=[];
  if(!fair){for(const g of games){if(!fresh(g.publication_at,now,6))continue;for(const q of g.selections||[])rows.push({...q,sport,event_id:String(g.event_id),matchup:g.matchup,start_time:g.start,price:q.price,model_prob:num(q.probability),price_kind:'book',observed_at:q.observed_at,kind:'game'});}
   if(props?.sport===sport&&fresh(props.generated_at,now,6))for(const q of props.quotes||[])if(ids.has(String(q.event_id)))rows.push({...q,sport,event_id:String(q.event_id),player_id:String(q.athlete_id),price:q.price_american,price_kind:'book',kind:'player',pick:`${q.player} ${q.side} ${q.line??''} ${q.market}`});
   for(const q of manual)if(q.sport===sport&&ids.has(String(q.event_id)))rows.push({...q,price_kind:'manual',kind:'player'});
  }else if(sport==='NHL'&&props?.sport==='NHL'&&fresh(props.generated_at,now,6)&&fresh(props.source_model_at,now,6)){
   for(const q of props.goal_scorers||[]){const p=num(q.model_prob);if(p===null||p<=0||p>=1||!ids.has(String(q.event_id)))continue;rows.push({...q,sport,event_id:String(q.event_id),player_id:String(q.athlete_id),pick:q.player+' anytime goal',price:american(1/p),book:'MODEL FAIR · NOT OFFERED',price_kind:'model-fair',observed_at:props.generated_at,kind:'player'});}
  }
  const latest=new Map();for(const q of rows){if(!valid(q,now))continue;const k=key(q),old=latest.get(k);if(!old||Date.parse(q.observed_at)>Date.parse(old.observed_at))latest.set(k,{...q,id:k,price:Number(q.price),price_decimal:decimal(Number(q.price)),model_prob:num(q.model_prob)});}
  return [...latest.values()];
 }
 function compatible(q,chosen,profile){
  return !chosen.some(l=>l.id===q.id||profile==='core'&&l.event_id===q.event_id
   ||q.event_id===l.event_id&&(q.player_id&&q.player_id===l.player_id
    ||!q.player_id&&!l.player_id&&(q.market==='TOTAL'&&l.market==='TOTAL'||['ML','ATS'].includes(q.market)&&['ML','ATS'].includes(l.market))));
 }
 function metrics(legs){const dec=legs.reduce((p,q)=>p*decimal(Number(q.price)),1),sameGame=new Set(legs.map(q=>q.event_id)).size<legs.length;
  const known=legs.every(q=>num(q.model_prob)!==null&&q.model_prob>0&&q.model_prob<1&&!(num(q.push_prob)>0));
  return {decimal:dec,american:american(dec),same_game:sameGame,model_baseline:!sameGame&&known?legs.reduce((p,q)=>p*q.model_prob,1):null,estimated:legs.some(q=>q.price_kind==='model-fair'),combined_quote_verified:false,actionable:false};
 }
 function build(pool,{target=500,profile='moonshot',scope='day',game='all',date='all',book='all',kind='all',now=Date.now()}={}){
  if(!TARGETS.includes(Number(target))||scope==='game'&&game==='all')return [];
  const eligible=pool.filter(q=>valid(q,now)&&(profile!=='core'||q.qualified===true&&num(q.model_prob)>=.6&&q.price_kind==='book')&&(kind==='all'||q.kind===kind||q.market===kind)&&(game==='all'||q.event_id===game)&&(scope==='slate'||date==='all'||day(q.start_time)===date)&&(book==='all'||norm(q.book)===norm(book)));
  const groups=[...new Set(eligible.map(q=>norm(q.book)))],finished=[];
  for(const group of groups){const perGame=new Map(),aim=Math.pow(1+target/100,profile==='core'?0.5:1/3);
   for(const q of eligible.filter(q=>norm(q.book)===group)){if(!perGame.has(q.event_id))perGame.set(q.event_id,[]);perGame.get(q.event_id).push(q);}
   const lists=[...perGame.values()].map(rows=>rows.sort((a,b)=>Math.abs(Math.log(decimal(a.price)/aim))-Math.abs(Math.log(decimal(b.price)/aim))));
   const short=[];for(let depth=0;short.length<240;depth++){let added=false;for(const list of lists)if(list[depth]&&short.length<240){short.push(list[depth]);added=true;}if(!added)break;}
   const rows=short.sort((a,b)=>String(a.id).localeCompare(String(b.id))),maxLegs=profile==='core'?3:8,min=1+Number(target)*.9/100,max=1+Number(target)*1.1/100;let beam=[{legs:[],dec:1,last:-1}];
   for(let count=1;count<=maxLegs;count++){const next=[];
    for(const state of beam)for(let i=state.last+1;i<rows.length;i++){const q=rows[i];if(!compatible(q,state.legs,profile))continue;const d=state.dec*decimal(Number(q.price));if(d>max)continue;const entry={legs:[...state.legs,q],dec:d,last:i};if(count>=2&&d>=min)finished.push(entry);else next.push(entry);}
    // Keep price-diverse partial combinations so small-price legs remain reachable.
    const buckets=new Map();for(const s of next){const k=Math.round(Math.log(s.dec)*70),old=buckets.get(k);if(!old||s.last<old.last)buckets.set(k,s);}beam=[...buckets.values()].sort((a,b)=>Math.abs(Math.log(a.dec/(1+target/100)))-Math.abs(Math.log(b.dec/(1+target/100)))).slice(0,160);if(!beam.length)break;
   }
  }
  finished.sort((a,b)=>Math.abs(a.dec-(1+target/100))-Math.abs(b.dec-(1+target/100))||a.legs.length-b.legs.length);
  const picked=[];for(const s of finished){if(picked.some(t=>s.legs.filter(q=>t.legs.some(l=>l.id===q.id)).length>=Math.max(1,s.legs.length-1)))continue;
   picked.push({id:s.legs.map(q=>q.id).join('~'),sport:s.legs[0].sport,target:Number(target),profile,scope,created_at:new Date(now).toISOString(),legs:s.legs.map(q=>({...q})),...metrics(s.legs)});if(picked.length===2)break;}
  return picked;
 }
 function capture(t,now=Date.now()){if(!t?.legs?.length||t.legs.length<2||t.legs.length>8||!t.legs.every(q=>valid(q,now))||new Set(t.legs.map(q=>norm(q.book))).size!==1)throw Error('Draft has expired or mixes books. Refresh and rebuild.');return JSON.parse(JSON.stringify({...t,captured_at:new Date(now).toISOString()}));}
 const profit=b=>b.result==='Win'?Number(b.stake)*(decimal(Number(b.actual_price))-1):b.result==='Loss'?-Number(b.stake):0;
 const api={TARGETS,num,decimal,american,norm,day,fresh,key,valid,contracts,compatible,metrics,build,capture,profit};root.LeagueParlays=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
