/* Pure scoring functions. One home-win probability per verified game. */
(function(root){
'use strict';
const mean=a=>a.length?a.reduce((s,n)=>s+n,0)/a.length:null;
const finite=n=>typeof n==='number'&&Number.isFinite(n);
function wilson(w,n){if(!n)return null;const z=1.959964,p=w/n,d=1+z*z/n,c=(p+z*z/(2*n))/d,h=z*Math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;return [c-h,c+h];}
function score(rows,key='p'){
 const r=rows.filter(x=>finite(x[key])&&x[key]>=0&&x[key]<=1&&(x.y===0||x.y===1));
 const picks=r.filter(x=>x[key]!==.5),correct=picks.filter(x=>(x[key]>.5)===(x.y===1)).length;
 return {n:r.length,picks:picks.length,correct,accuracy:picks.length?correct/picks.length:null,interval:wilson(correct,picks.length),brier:mean(r.map(x=>(x[key]-x.y)**2)),logloss:mean(r.map(x=>{const p=Math.max(1e-6,Math.min(1-1e-6,x[key]));return -x.y*Math.log(p)-(1-x.y)*Math.log(1-p);} ))};
}
function summarize(rows){
 const paired=rows.filter(x=>finite(x.market)&&x.market>0&&x.market<1),m=score(paired),b=score(paired,'market');
 const comparison=(model,market,actual)=>{const r=rows.filter(x=>[model,market,actual].every(k=>finite(x[k])));return {n:r.length,model:mean(r.map(x=>Math.abs(x[model]-x[actual]))),market:mean(r.map(x=>Math.abs(x[market]-x[actual])))};};
 return {...score(rows),paired:{n:paired.length,model:m,market:b,skill:b.brier>0?1-m.brier/b.brier:null},margin:comparison('margin','market_margin','actual_margin'),total:comparison('total','market_total','actual_total'),calibration:Array.from({length:5},(_,i)=>{const r=rows.filter(x=>Math.min(4,Math.floor(x.p*5))===i),wins=r.reduce((s,x)=>s+x.y,0);return {bucket:`${i*20}–${(i+1)*20}%`,n:r.length,predicted:mean(r.map(x=>x.p)),actual:r.length?wins/r.length:null,interval:wilson(wins,r.length)};})};
}
root.KevPerformance={score,summarize,wilson};
})(typeof window==='undefined'?globalThis:window);
