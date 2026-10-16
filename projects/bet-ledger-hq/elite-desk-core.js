/* Read-only decision tools. No inferred odds, automatic wagers or model promotion. */
(function(root,factory){const api=factory(typeof module==='object'&&module.exports?require('./today-desk-core.js'):root.KevTodayDesk,typeof module==='object'&&module.exports?require('./value-core.js'):root.BetValue);if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KevEliteDesk=api;})(typeof window!=='undefined'?window:null,function(C,V){
 'use strict';
 const num=V.number,dec=V.decimal,at=v=>Date.parse(v),book=v=>String(v||'').trim().toLowerCase();
 const same=(a,b)=>a.market===b.market&&a.side===b.side&&num(a.line)===num(b.line);
 const publicationFresh=(g,now)=>Number.isFinite(at(g.publication_at))&&at(g.publication_at)<=now&&now-at(g.publication_at)<=6*3600000;
 function sensitivity(g,q,now=Date.now()){
  if(!q||!publicationFresh(g,now))return null;
  return V.evaluate({...q,model_prob:q.probability,odds_observed_at:q.observed_at,start:g.start},{sport:g.sport,publication:g.publication_at,now});
 }
 function decision(g,q,{now=Date.now(),failed=false}={}){
  const reasons=(q?.reasons||[]).flatMap(x=>String(x).split(';').map(x=>x.trim())).filter(Boolean);
  if(failed)reasons.unshift('Latest publication reload failed; retained information is research only');
  if(!publicationFresh(g,now))reasons.push('Forecast publication stale or unavailable');
  if(!q||!C.fresh(g,q,now))reasons.push('No fresh observed price for this selection');
  if(!C.qualified(g,q,now)&&!reasons.length)reasons.push('Source model has not qualified this selection');
  return {qualified:!failed&&C.qualified(g,q,now),reasons:[...new Set(reasons)],value:failed?null:sensitivity(g,q,now)};
 }
 function prices(g,q,now=Date.now()){
  const latest=new Map();
  for(const row of g.selections||[]){if(!same(row,q)||!C.fresh(g,row,now)||row.reference_only||row.price_source==='model'||row.quote_status&&row.quote_status!=='observed')continue;const key=book(row.book),prior=latest.get(key);if(!prior||at(row.observed_at)>at(prior.observed_at))latest.set(key,row);}
  return [...latest.values()].sort((a,b)=>dec(b.price)-dec(a.price)||String(a.book).localeCompare(String(b.book)));
 }
 function compare(g,now=Date.now()){
  const quotes=(g.selections||[]).filter(q=>q.market==='ML'&&C.fresh(g,q,now)&&!q.reference_only&&q.price_source!=='model'&&(!q.quote_status||q.quote_status==='observed')),pairs=[];
  for(const h of quotes.filter(q=>q.side==='home')){const a=quotes.find(q=>q.side==='away'&&book(q.book)===book(h.book)&&at(q.observed_at)===at(h.observed_at));if(a){const ph=1/dec(h.price),pa=1/dec(a.price);pairs.push({p:ph/(ph+pa),book:h.book,observed_at:h.observed_at,overround:ph+pa-1});}}
  pairs.sort((a,b)=>at(b.observed_at)-at(a.observed_at));const market=pairs[0]||null,p=publicationFresh(g,now)?num(g.p_home):null;
  const model=p!==null&&p>0&&p<1?p:null;return {model,market,gap:model!==null&&market?model-market.p:null,margin:publicationFresh(g,now)?num(g.margin):null};
 }
 function filter(rows,{query='',view='all',order='time',now=Date.now()}={}){
  const priced=g=>(g.selections||[]).some(q=>C.fresh(g,q,now));
  return rows.filter(g=>(!query.trim()||[g.matchup,g.home,g.away,g.sport].join(' ').toLowerCase().includes(query.trim().toLowerCase()))&&(view==='all'||view==='priced'&&priced(g)||view==='confirm'&&!priced(g))).sort((a,b)=>(order==='coverage'?Number(priced(b))-Number(priced(a)):0)||at(a.start)-at(b.start)||String(a.id).localeCompare(String(b.id)));
 }
 function preferences(raw){
  const r=raw&&typeof raw==='object'?raw:{};
  return {sport:['all','nfl','ncaaf','nhl'].includes(r.sport)?r.sport:'all',period:['week','today'].includes(r.period)?r.period:'week',query:typeof r.query==='string'?r.query.slice(0,80):'',view:['all','priced','confirm'].includes(r.view)?r.view:'all',order:r.order==='coverage'?'coverage':'time',compared:Array.isArray(r.compared)?[...new Set(r.compared.filter(x=>typeof x==='string'&&x.length<120))].slice(0,3):[]};
 }
 function review(rows,data,{now=Date.now(),failed=false}={}){
  return rows.map(r=>{const g=data?.games?.find(g=>g.id===r.game),base={id:r.id,pick:r.pick};
   if(failed)return {...base,state:'unavailable',message:'Publication reload failed; reconfirm this selection.'};
   if(!(at(r.start)>now))return {...base,state:'started',message:'Game has started; remove this pregame selection.'};
   if(!Number.isFinite(at(r.observed_at))||at(r.observed_at)>now||now-at(r.observed_at)>(r.sport==='nhl'?90:180)*60000)return {...base,state:'expired',message:'Saved quote expired; remove and reconfirm.'};
   if(r.origin==='User-confirmed sportsbook offer')return {...base,state:'manual',message:'User-confirmed price retained; not independently verified by the publication.'};
   if(!g)return {...base,state:'unavailable',message:'Game missing from the current publication; reconfirm.'};
   const offers=prices(g,r,now).filter(q=>book(q.book)===book(r.book)),q=offers[0];
   if(!q)return {...base,state:'unavailable',message:'No fresh quote at this exact book, side and line; reconfirm.'};
   if(Number(q.price)!==Number(r.price))return {...base,state:'changed',price:q.price,observed_at:q.observed_at,message:'Published price changed; the original draft was preserved. Remove and reconfirm.'};
   return {...base,state:'matched',message:'Same price observed at the same book and exact line. Confirmation is still needed at the sportsbook.'};
  });
 }
 return {same,sensitivity,decision,prices,compare,filter,preferences,review};
});
