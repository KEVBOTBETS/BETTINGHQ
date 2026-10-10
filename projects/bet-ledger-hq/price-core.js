/* Source-scoped exact contracts. Observations are never certified live or closing prices. */
(function(root,factory){const api=factory(typeof module==='object'?require('./value-core.js'):root.BetValue);if(typeof module==='object'&&module.exports)module.exports=api;else root.BetPrices=api;})(typeof self!=='undefined'?self:this,function(V){
 'use strict';
 const contract=r=>JSON.stringify([r.key,String(r.eventId),r.start,r.market,r.playerId||r.player||'',r.side||r.pick,V.number(r.line)]);
 const identity=r=>contract(r)+'|'+String(r.book).trim().toLowerCase();
 function valid(r,now){return !!r.eventId&&!!r.book&&!/unspecified|unknown|model/i.test(r.book)&&V.decimal(r.price)!==null&&V.fresh(r.quote,now,4)&&V.instant(r.quote)<V.instant(r.start)&&V.instant(r.start)>now;}
 function compare(pick,quotes,now=Date.now()){
  const byBook=new Map();for(const q of quotes||[]){if(contract(q)!==contract(pick)||!valid(q,now))continue;const k=String(q.book).trim().toLowerCase(),old=byBook.get(k);if(!old||Date.parse(q.quote)>Date.parse(old.quote))byBook.set(k,q);}
  const rows=[...byBook.values()].sort((a,b)=>V.decimal(b.price)-V.decimal(a.price));return {rows,best:rows[0]||null,coverage:rows.length};
 }
 function observe(previous,quotes,at){
  const now=Date.parse(at),last={...(previous?.last||{})};
  for(const q of quotes||[]){if(!valid(q,now))continue;const id=identity(q),old=last[id];if(!old||Date.parse(q.quote)>Date.parse(old.quote))last[id]={...q,observed_at:at};}
  const kept=Object.entries(last).filter(([,q])=>Date.parse(q.start)>now-90*86400000).sort((a,b)=>Date.parse(b[1].start)-Date.parse(a[1].start)).slice(0,50000);
  return {schema:1,checked_at:at,description:'Last observed pregame price by exact source contract and book. Not a certified closing price; gaps remain visible.',last:Object.fromEntries(kept)};
 }
 function crossing(pick,before,after){
  if(contract(pick)!==contract(before)||contract(pick)!==contract(after)||before.book!==after.book)return null;
  const limit=V.decimal(pick.value?.worst??pick.worst);if(limit===null)return null;
  const was=V.decimal(before.price),next=V.decimal(after.price);if(was===null||next===null)return null;
  return was>=limit&&next<limit?'lost':was<limit&&next>=limit?'recovered':null;
 }
 function latest(quotes,now=Date.now()){const map=new Map();for(const q of quotes||[]){if(!valid(q,now))continue;const id=identity(q),old=map.get(id);if(!old||Date.parse(q.quote)>Date.parse(old.quote))map.set(id,q);}return [...map.values()];}
 function collect(C,key,bundle,now=Date.now()){return C.plays(key,{...bundle,board:Array.isArray(bundle.quotes)?bundle.quotes:bundle.board},now,{quotes:true});}
 return {contract,identity,valid,compare,observe,crossing,latest,collect};
});
