/* Exact frozen ticket identities. Actual book terms/returns are never inferred. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.PropsParlays=api;})(typeof window!=='undefined'?window:null,function(){
 'use strict';
 const clone=v=>JSON.parse(JSON.stringify(v));
 const key=l=>JSON.stringify([String(l.result_event_id||l.event_id||''),String(l.player||''),String(l.team||''),String(l.market||''),String(l.side||''),l.line==null?null:Number(l.line)]);
 const time=v=>typeof v==='string'&&/(?:Z|[+-]\d\d:\d\d)$/.test(v)?Date.parse(v):NaN;
 function snapshot(ticket,legs,stamp=new Date().toISOString()){
   if(!Array.isArray(legs)||legs.length<2||legs.some(l=>!l.player||!l.market||!/^\d+$/.test(String(l.result_event_id||l.event_id||''))||!Number.isFinite(time(l.start_time))))throw Error('This ticket lacks the structured event details needed for tracking.');
   if(new Set(legs.map(key)).size!==legs.length)throw Error('Duplicate selections cannot form a tracked parlay.');
   return {schema:1,source_ticket_id:ticket.id,scope:ticket.scope,label:ticket.label,target:ticket.target,captured_at:stamp,
     start_time:legs.map(l=>l.start_time).sort((a,b)=>time(a)-time(b))[0],legs:clone(legs),leg_count:legs.length};
 }
 function outcome(legs){
   const states=legs.map(l=>l.result||'Pending');
   if(!states.length)return 'Pending';
   if(states.every(s=>s==='Void'))return 'Void';
   if(states.some(s=>['Push','Void','Review'].includes(s)))return 'Review';
   if(states.includes('Loss'))return 'Loss';
   return states.every(s=>s==='Win')?'Win':'Pending';
 }
 function settle(ticket,results,now=Date.now()){
   const index=new Map();
   for(const r of results||[]){
     const at=time(r.graded_at),start=time(r.start_time);
     if(!['Win','Loss','Push','Void'].includes(r.result)||!Number.isFinite(at)||!Number.isFinite(start)||start>at||at>now)continue;
     if(r.result!=='Void'&&(r.actual==null||typeof r.actual!=='number'||!Number.isFinite(r.actual)))continue;
     const k=key(r),old=index.get(k);
     if(old&&(old.result!==r.result||old.actual!==r.actual)){index.set(k,{result:'Review',conflict:true});continue;}
     if(!old?.conflict)index.set(k,r);
   }
   const legs=(ticket?.legs||[]).map(l=>{
     const r=index.get(key(l));
     if(!r||time(l.start_time)>now)return {...clone(l),result:'Pending',actual:null};
     return {...clone(l),result:r.result,actual:r.actual??null,graded_at:r.graded_at||null};
   });
   return {result:outcome(legs),legs};
 }
 function settleEntries(entries,results,now=Date.now()){
   let changed=false;
   const next=entries.map(e=>{
     if(e.kind!=='parlay'||!e.parlay_snapshot||e.result!=='Pending'||e.settlement_mode==='manual')return e;
     const evidence=settle(e.parlay_snapshot,results,now);
     const completed=['Win','Loss'].includes(evidence.result)&&evidence.legs.every(l=>['Win','Loss'].includes(l.result));
     // Even all-void actual tickets require the book's confirmed settlement.
     const result=completed?evidence.result:'Pending';
     const status=['Void','Review'].includes(evidence.result)?'Review':completed?evidence.result:'Pending';
     if(JSON.stringify(e.parlay_evidence)===JSON.stringify(evidence)&&e.result===result&&e.parlay_status===status)return e;
     changed=true;return {...e,result,parlay_status:status,parlay_evidence:evidence,settlement_mode:'auto',
       ...(completed?{settled_at:new Date(now).toISOString(),settlement_source:'Verified final published leg results'}:{})};
   });
   return {entries:next,changed};
 }
 return {key,snapshot,outcome,settle,settleEntries};
});
