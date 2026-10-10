(function(root){
 'use strict';
 const number=v=>v==null||v===''||!Number.isFinite(Number(v))?null:Number(v);
 function rows(sport,bundle,now=Date.now()){
  const details=new Map((bundle.details||[]).map(g=>[String(g.game_id),g]));
  const outlook=new Map((bundle.outlook||[]).map(g=>[String(g.game_id),g]));
  return (bundle.games||[]).map(g=>{
   const key=sport+':'+g.game_id,d=details.get(String(g.game_id)),o=outlook.get(String(g.game_id));
   const p=d?.projection||g.projection,mu=(p?.ratings_known===false?null:number(p?.mu))??(number(o?.model_spread)==null?null:-number(o.model_spread));
   const quote=d?.odds||g.odds||{},line=number(quote.spread_home),gap=mu==null||line==null?null:mu+line;
   const side=gap>0?'home':gap<0?'away':null,board=(bundle.board||[]).filter(r=>String(r.game_id)===String(g.game_id)&&r.market==='ATS');
   const preferred=board.find(r=>r.side===side),stamp=Date.parse(bundle.meta?.generated_at),start=Date.parse(g.date);
   const fresh=!bundle.error&&Number.isFinite(stamp)&&stamp<=now+300000&&now-stamp<24*3600000;
   const locked=!Number.isFinite(start)||start<=now||g.completed||g.canceled||g.postponed||/in progress|final|postponed|canceled/i.test(g.status||'');
   const paused=preferred?.validation_policy?.paused===true||bundle.meta?.validation?.markets?.some(m=>m.market==='ATS'&&m.recommendations_paused&&m.baseline_version===(bundle.meta?.model_version||preferred?.tier_version||'current-v1'));
   const reason=paused?'Market validation paused recommendations; manual game options remain available':preferred?.filtered||preferred?.hold_note||preferred?.warning||preferred?.qualification||(!fresh?'Forecast stale':mu==null?'Model projection unavailable':line==null?'Enter your book’s spread and price':'Below model qualification threshold');
   const tier=preferred&&!preferred.filtered&&!preferred.held?preferred.tier:null;
   const rating=paused||!fresh||mu==null||line==null||preferred?.filtered||preferred?.held?'AVOID':['BEST BET','GOOD','LEAN'].includes(tier)?tier:preferred?.ev<0?'BAD':'LEAN';
   return {...g,key,sport,validationPaused:paused,optionSide:side||(mu===null||mu===0?null:mu>0?'home':'away'),optionBasis:side?'Spread research lean':mu===null?'Choose either side; model unavailable':mu===0?'No model preference; choose either side':'Model winner direction; enter a spread to reassess',forecast_at:bundle.meta?.generated_at,mu,line,gap,side,rating,reason,fresh,locked,quote,board};
  }).sort((a,b)=>Date.parse(a.date)-Date.parse(b.date));
 }
 function selection(row,side,line,price,book,now=Date.now()){
  line=number(line);price=number(price);
  if(row.locked||Date.parse(row.date)<=now||!['home','away'].includes(side)||line==null||Math.abs(line)>100||price==null||Math.abs(price)<100||!String(book||'').trim())return null;
  // Display lines are from the chosen team's perspective, not the home line.
  return {key:row.key,sport:row.sport,game_id:row.game_id,start:row.date,day:row.date.slice(0,10),event:row.away+' @ '+row.home,source:row.sport.toUpperCase(),side,line,price,book:String(book).trim(),pick:row[side]+' '+(line>0?'+':'')+line,tier:'MANUAL',model_margin:row.mu,forecast_rating:row.rating,model_side:row.side,agrees_with_model:row.side?row.side===side:null,forecast_at:row.forecast_at||null,selected_at:new Date(now).toISOString(),probability:null};
 }
 // Prefer the league calendar; college feeds without one use Toronto Monday–Sunday weeks.
 function weeks(bundle,now=Date.now()){
  const phase=g=>Number(g.season_type||2),key=g=>phase(g)+':'+g.week;
  const calendar=(bundle.meta?.calendar||[]).map(w=>({...w,key:key(w)})).filter(w=>Number.isFinite(Date.parse(w.start))&&Number.isFinite(Date.parse(w.end))).sort((a,b)=>Date.parse(a.start)-Date.parse(b.start));
  if(calendar.length){const active=calendar.findIndex(w=>Date.parse(w.start)<=now&&now<=Date.parse(w.end));return calendar.slice(active>=0?active:calendar.findIndex(w=>Date.parse(w.start)>now)).filter(w=>Date.parse(w.end)>=now);}
  const groups=new Map();for(const g of bundle.games||[]){if(g.week==null||!Number.isFinite(Date.parse(g.date)))continue;const k=key(g),date=Date.parse(g.date);if(!groups.has(k))groups.set(k,{key:k,week:g.week,season_type:phase(g),first:date,last:date});else{const w=groups.get(k);w.first=Math.min(w.first,date);w.last=Math.max(w.last,date);}}
  const monday=t=>{const d=new Date(new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(t)+'T00:00Z');d.setUTCDate(d.getUTCDate()-(d.getUTCDay()+6)%7);return d.getTime();};
  return [...groups.values()].sort((a,b)=>a.first-b.first).filter(w=>monday(w.last)>=monday(now)).map(w=>({...w,label:(w.season_type===3?'Postseason ': '')+'Week '+w.week}));
 }
 function weekChoices(bundles,league,now=Date.now()){
  const lists=Object.entries(bundles).filter(([s])=>league==='all'||s===league).map(([sport,b])=>({sport,weeks:weeks(b,now)}));
  return Array.from({length:Math.max(0,...lists.map(l=>l.weeks.length))},(_,offset)=>{const members=lists.filter(l=>l.weeks[offset]).map(l=>({sport:l.sport,...l.weeks[offset]}));return {offset,members,label:(offset===0?'Current · ': '')+members.map(w=>w.sport.toUpperCase()+' '+(w.label||'Week '+w.week)).join(' / ')};});
 }
 function inWeek(row,choice){return !!choice?.members.some(w=>w.sport===row.sport&&w.key===Number(row.season_type||2)+':'+row.week);}
 const api={rows,selection,number,weeks,weekChoices,inWeek};if(typeof module==='object')module.exports=api;else root.AllSpreads=api;
})(typeof window==='object'?window:globalThis);
