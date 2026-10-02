/* Frozen spread forecasts and simulated one-unit returns. */
(function(root){
 'use strict';
 function side(r){if(r.side)return r.side;const gap=r.home_spread==null?null:r.model_margin+r.home_spread;return gap>0?'home':gap<0?'away':null;}
 function metrics(rows){
  const n=s=>rows.filter(r=>r.status===s).length,w=n('Win'),l=n('Loss'),push=n('Push');
  const scored=rows.filter(r=>Number.isFinite(r.margin_error));
  const priced=rows.filter(r=>Number.isFinite(r.unit_profit)&&['Win','Loss','Push'].includes(r.status));
  const profit=priced.reduce((s,r)=>s+r.unit_profit,0),total=w+l;
  let interval=null;if(total){const p=w/total,z=1.96,d=1+z*z/total,c=(p+z*z/(2*total))/d,h=z*Math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d;interval=[c-h,c+h];}
  return {rows:rows.length,w,l,push,pending:n('Pending'),noLine:rows.filter(r=>r.home_spread==null).length,rate:total?w/total:null,interval,mae:scored.length?scored.reduce((s,r)=>s+r.margin_error,0)/scored.length:null,marginGames:scored.length,priced:priced.length,profit:priced.length?profit:null,roi:priced.length?profit/priced.length:null};
 }
 const api={side,metrics};if(typeof module==='object')module.exports=api;else root.SpreadAudit=api;
})(typeof window==='object'?window:globalThis);
