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
   const fresh=Number.isFinite(stamp)&&stamp<=now+300000&&now-stamp<24*3600000;
   const locked=!Number.isFinite(start)||start<=now||g.completed||g.canceled||g.postponed||/in progress|final|postponed|canceled/i.test(g.status||'');
   const reason=preferred?.filtered||preferred?.hold_note||preferred?.warning||preferred?.qualification||(!fresh?'Forecast stale':mu==null?'Model projection unavailable':line==null?'Enter your book’s spread and price':'Below model qualification threshold');
   const tier=preferred&&!preferred.filtered&&!preferred.held?preferred.tier:null;
   const rating=!fresh||mu==null||line==null||preferred?.filtered||preferred?.held?'AVOID':['BEST BET','GOOD','LEAN'].includes(tier)?tier:preferred?.ev<0?'BAD':'LEAN';
   return {...g,key,sport,forecast_at:bundle.meta?.generated_at,mu,line,gap,side,rating,reason,fresh,locked,quote,board};
  }).sort((a,b)=>Date.parse(a.date)-Date.parse(b.date));
 }
 function selection(row,side,line,price,book,now=Date.now()){
  line=number(line);price=number(price);
  if(row.locked||Date.parse(row.date)<=now||!['home','away'].includes(side)||line==null||Math.abs(line)>100||price==null||Math.abs(price)<100||!String(book||'').trim())return null;
  // Display lines are from the chosen team's perspective, not the home line.
  return {key:row.key,sport:row.sport,game_id:row.game_id,start:row.date,day:row.date.slice(0,10),event:row.away+' @ '+row.home,source:row.sport.toUpperCase(),side,line,price,book:String(book).trim(),pick:row[side]+' '+(line>0?'+':'')+line,tier:'MANUAL · '+row.rating,model_margin:row.mu,forecast_rating:row.rating,forecast_at:row.forecast_at||null,selected_at:new Date(now).toISOString(),probability:null};
 }
 const api={rows,selection,number};if(typeof module==='object')module.exports=api;else root.AllSpreads=api;
})(typeof window==='object'?window:globalThis);
