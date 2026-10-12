/* Shared pace + conserved team shots. Hypothesis, not calibrated ticket confidence. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.NHLSimulation=api;})(typeof self!=='undefined'?self:this,function(){
 'use strict';
 function random(seed){let a=seed>>>0;return()=>{a+=0x6D2B79F5;let t=Math.imul(a^(a>>>15),1|a);t^=t+Math.imul(t^(t>>>7),61|t);return((t^(t>>>14))>>>0)/4294967296;};}
 function hash(s){let h=2166136261;for(const c of s)h=Math.imul(h^c.charCodeAt(0),16777619);return h>>>0;}
 function poisson(lambda,rng){if(!(lambda>=0&&lambda<=120))throw Error('Invalid shot mean');const l=Math.exp(-lambda);let p=1,k=0;do{k++;p*=Math.max(1e-12,rng());}while(p>l&&k<500);return k-1;}
 function prepare(rows){
  if(rows.length<2||rows.length>8)return null;const events=new Map(),seen=new Set();
  for(const q of rows){const s=q.shadow?.simulation,key=[q.event_id,q.athlete_id,q.market,q.side,q.line].join('|');
   if(!s||!q.shadow?.version||!['Anytime goal','Shots on goal'].includes(q.market)||seen.has(key)||![s.goals,s.shots,s.team_shots].every(Number.isFinite)||s.goals<=0||s.shots<s.goals||s.team_shots<s.shots)return null;
   if(q.market==='Anytime goal'&&String(q.side).toLowerCase()!=='yes')return null;
   if(q.market==='Shots on goal'&&(!['over','under'].includes(String(q.side).toLowerCase())||!Number.isFinite(q.line)||q.line%1!==.5))return null;
   seen.add(key);if(!events.has(q.event_id))events.set(q.event_id,new Map());const teams=events.get(q.event_id);if(!teams.has(q.team))teams.set(q.team,new Map());const players=teams.get(q.team),old=players.get(q.athlete_id);
   if(old&&JSON.stringify(old.s)!==JSON.stringify(s))return null;
   if(!old)players.set(q.athlete_id,{s,legs:[]});players.get(q.athlete_id).legs.push(q);
  }
  for(const teams of events.values())for(const players of teams.values()){
   const all=[...players.values()],total=all[0].s.team_shots;if(all.some(p=>p.s.team_shots!==total)||all.reduce((n,p)=>n+p.s.shots,0)>total+1e-6)return null;
   for(const p of all){if(p.legs.some(a=>p.legs.some(b=>a!==b&&a.market===b.market&&a.side!==b.side)))return null;}
  }
  return events;
 }
 function simulate(rows,{draws=6000,shape=20}={}){
  const events=prepare(rows);if(!events||!Number.isInteger(draws)||draws<1000||draws>30000||![10,20,40].includes(shape))return null;
  const rng=random(hash(rows.map(q=>[q.event_id,q.athlete_id,q.market,q.side,q.line,q.shadow.version].join('|')).sort().join(';')+'|'+shape));let wins=0;
  for(let n=0;n<draws;n++){
   let hit=true;
   for(const teams of events.values()){
    let pace=0;for(let k=0;k<shape;k++)pace-=Math.log(Math.max(1e-12,rng()));pace/=shape;
    for(const players of teams.values()){
     const all=[...players.values()],total=all[0].s.team_shots,shots=Array(all.length).fill(0),goals=Array(all.length).fill(0),volume=poisson(total*pace,rng);
     for(let k=0;k<volume;k++){
      const u=rng()*total;let cumulative=0;
      for(let i=0;i<all.length;i++){cumulative+=all[i].s.shots;if(u<cumulative){shots[i]++;if(rng()<all[i].s.goals/all[i].s.shots)goals[i]++;break;}}
     }
     for(let i=0;i<all.length;i++)for(const q of all[i].legs){const pass=q.market==='Anytime goal'?goals[i]>0:String(q.side).toLowerCase()==='over'?shots[i]>q.line:shots[i]<q.line;if(!pass)hit=false;}
    }
   }
   if(hit)wins++;
  }
  const probability=wins/draws,z2=1.96**2,center=(probability+z2/(2*draws))/(1+z2/draws),error=1.96*Math.sqrt(probability*(1-probability)/draws+z2/(4*draws**2))/(1+z2/draws);
  const independent=rows.every(q=>q.market==='Anytime goal')?rows.reduce((p,q)=>p*q.shadow.model_prob,1):null;
  return {probability,independent,draws,shape,wins,monte_carlo_interval:[Math.max(0,center-error),Math.min(1,center+error)],research_only:true,validated:false,
   basis:'Conditional on participation and projected roles. Shared game pace; conserved team shots; goals are a subset of shots. Monte Carlo interval measures simulation precision only.'};
 }
 return {prepare,simulate};
});
