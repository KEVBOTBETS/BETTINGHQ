/* Private accepted receipts only. Date-clustered intervals do not establish future profit. */
(function(root,factory){const api=factory(typeof module==='object'?require('./execution-core.js'):root.BetExecution);if(typeof module==='object'&&module.exports)module.exports=api;else root.BetEvidence=api;})(typeof self!=='undefined'?self:this,function(X){
 'use strict';
 function interval(entries){
  const days=new Map();let missing=false;for(const e of entries){const day=String(e.row.event_date||'').slice(0,10);if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Number.isFinite(Date.parse(day))){missing=true;continue;}const g=days.get(day)||{pnl:0,stake:0};g.pnl+=X.pnl(e.receipt);g.stake+=e.receipt.accepted.stake;days.set(day,g);}
  if(missing||entries.length<100||days.size<28)return {range:null,days:days.size};
  const groups=[...days.values()],samples=[];let seed=123456789;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
  for(let k=0;k<1000;k++){let pnl=0,stake=0;for(let j=0;j<groups.length;j++){const g=groups[Math.floor(random()*groups.length)];pnl+=g.pnl;stake+=g.stake;}if(stake)samples.push(pnl/stake);}
  samples.sort((a,b)=>a-b);return {range:[samples[Math.floor(samples.length*.025)],samples[Math.floor(samples.length*.975)]],days:days.size};
 }
 function score(rows,settings){
  const groups=new Map();for(const row of rows.filter(r=>!r.deleted)){const receipt=X.get(settings,row.id);if(!receipt)continue;const label=[row.sport||row.app||'Unknown',row.market||'Unknown'].join(' / '),a=groups.get(label)||[];a.push({row,receipt});groups.set(label,a);}
  return [...groups].map(([label,entries])=>{const settled=entries.filter(e=>!['Pending','Void'].includes(e.receipt.accepted.status)),stake=settled.reduce((n,e)=>n+e.receipt.accepted.stake,0),pnl=settled.reduce((n,e)=>n+X.pnl(e.receipt),0),uncertainty=interval(settled),closes=entries.map(e=>X.closeComparison(e.receipt,X.closing(settings,e.row.id))).filter(c=>c.comparable);
   return {label,confirmed:entries.length,settled:settled.length,pending:entries.filter(e=>e.receipt.accepted.status==='Pending').length,voids:entries.filter(e=>e.receipt.accepted.status==='Void').length,stake,pnl,roi:stake?pnl/stake:null,...uncertainty,closes:closes.length,movement:closes.length?closes.reduce((n,c)=>n+c.movement,0)/closes.length:null};
  }).sort((a,b)=>a.label.localeCompare(b.label));
 }
 return {score,interval};
});
