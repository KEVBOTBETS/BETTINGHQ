/* Scorer research: conditional estimates, never offered odds or qualified bets. */
(()=>{'use strict';
const e=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=p=>(100*p).toFixed(1)+'%',fair=p=>p<.5?'+'+Math.round(100*(1/p-1)):String(-Math.round(100*p/(1-p)));
const day=v=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(v));
const probability=q=>q.market==='Anytime goal'&&String(q.side).toLowerCase()==='yes'&&Number.isFinite(q.model_prob)&&q.model_prob>0&&q.model_prob<1?q.model_prob:null;
function joint(rows){return rows.length>=2&&new Set(rows.map(q=>q.event_id)).size===rows.length&&rows.every(q=>probability(q)!=null)?rows.reduce((p,q)=>p*probability(q),1):null;}
function render(data,game,search,onOffer){
 const section=document.querySelector('#nhl-goals');if(!section||data.sport!=='NHL')return;section.hidden=false;
 const valid=(data.goal_scorers||[]).filter(q=>Date.parse(q.start_time)>Date.now()&&probability(q)!=null).sort((a,b)=>b.model_prob-a.model_prob);
 const earliest=[...valid].sort((a,b)=>Date.parse(a.start_time)-Date.parse(b.start_time))[0];
 const pool=valid.filter(q=>(game==='all'?earliest&&day(q.start_time)===day(earliest.start_time):String(q.event_id)===game)&&(!search||[q.player,q.team,q.matchup].join(' ').toLowerCase().includes(search)));
 const top=pool.slice(0,12),fresh=Date.now()>=Date.parse(data.generated_at)&&Date.now()-Date.parse(data.generated_at)<=6*3600000;
 const unique=[];for(const q of pool)if(!unique.some(x=>x.event_id===q.event_id))unique.push(q);
 const combos=[];if(fresh&&unique.length>=2)combos.push({name:'Two scorers',legs:unique.slice(0,2)});if(fresh&&unique.length>=3)combos.push({name:'Three scorers',legs:unique.slice(0,3)});
 if(fresh&&unique.length>=4)combos.push({name:'Moonshot research',legs:unique.slice(0,Math.min(6,unique.length))});
 section.innerHTML='<p class="eyebrow">NHL / ANYTIME GOAL SCORERS</p><h2>One goal changes the ticket.</h2><p class="muted">'+(game==='all'&&earliest?'Next game day · '+e(day(earliest.start_time))+' · ':'')+'Chance of at least one regulation or overtime goal, conditional on playing. Shootout goals excluded. Estimates are unvalidated; confirm participation, injuries and book rules.</p>'+(fresh?'':'<p>Forecast publication is older than six hours. Parlay suggestions are paused until refresh.</p>')+
 '<div class="goal-grid">'+top.map((q,i)=>'<article class="goal-card"><div><small>'+e(q.team)+' · '+e(q.matchup)+'</small><h3>'+e(q.player)+'</h3></div><strong>'+pct(q.model_prob)+'</strong><span>Estimated goal chance · about 1 in '+(1/q.model_prob).toFixed(1)+'</span><div class="goal-meter"><i style="width:'+(q.model_prob*100)+'%"></i></div><small>Model fair '+fair(q.model_prob)+' · not a book quote</small><small>'+e(q.current_goals)+' goals / '+e(q.current_games)+' current games · '+e(q.prior_goals)+' / '+e(q.prior_games)+' prior club games</small><button data-goal-offer="'+i+'">Enter my book’s scorer price</button></article>').join('')+'</div>'+(top.length?'':'<p>No eligible scorer forecast for this filter. Official history or a current team projection is missing.</p>')+
 '<h3>Goal-scorer parlay research</h3><p class="muted">Different games only. Chance below is the product of individual estimates under an independence assumption, not a calibrated joint forecast. Model fair odds show the probability scale; confirm the actual combined book quote.</p><div class="goal-parlays">'+combos.map(c=>{const p=joint(c.legs);return '<article class="goal-card"><small>'+e(c.name)+' · '+c.legs.length+' legs</small><h3>'+pct(p)+' estimated chance</h3><b>About 1 in '+(1/p).toFixed(1)+' · model fair '+fair(p)+'</b><ol>'+c.legs.map(q=>'<li>'+e(q.player)+' · '+e(q.matchup)+' · '+pct(q.model_prob)+'</li>').join('')+'</ol><small>No combined sportsbook price observed. Enter each real offer below to build and save a research ticket.</small></article>';}).join('')+'</div>'+(combos.length?'':'<p>Choose Every upcoming game for same-day combinations across different games. Same-game scorer probabilities are correlated; no joint estimate is claimed.</p>');
 section.querySelectorAll('[data-goal-offer]').forEach(b=>b.addEventListener('click',()=>onOffer(top[Number(b.dataset.goalOffer)])));
}
window.NHLGoals={render,probability,joint};
})();
