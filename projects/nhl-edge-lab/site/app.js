(() => {
  'use strict';
  const $=s=>document.querySelector(s),L=window.NHLLedger;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safe=u=>typeof u==='string'&&u.startsWith('https://')?esc(u):'';
  const fmt=(v,n=1)=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toFixed(n);
  const pct=v=>v==null?'—':fmt(v*100)+'%';
  const odd=v=>v==null?'—':(v>0?'+':'')+v;
  const day=v=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(v));
  const time=v=>v&&!Number.isNaN(Date.parse(v))?new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(v)):'Unknown';
  const metric=(value,label,note='')=>'<div class="metric"><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong><small>'+esc(note)+'</small></div>';
  let data={},loading=false,failed=false,pending=null;
  const recent=()=>data.meta&&Date.now()-Date.parse(data.meta.generated_at)<6*3600000&&Date.now()>=Date.parse(data.meta.generated_at)-300000&&!failed;
  const open=g=>g.state==='pre'&&Date.parse(g.date)>Date.now();
  const actionable=r=>recent()&&r.odds_verified&&Number.isFinite(Date.parse(r.odds_observed_at))&&Date.now()-Date.parse(r.odds_observed_at)<=90*60000&&Date.now()>=Date.parse(r.odds_observed_at)-300000&&Date.parse(r.start_time)>Date.now()&&data.games?.some(g=>g.game_id===r.game_id&&open(g));
  const qualified=r=>actionable(r)&&!r.held&&r.stake>0;
  const image=(src,alt,cls='')=>safe(src)?'<img class="'+cls+'" src="'+safe(src)+'" alt="'+esc(alt)+'" loading="lazy" onerror="this.remove()">':'';
  function card(g){
    const p=g.projection||{},known=p.ratings_known,rows=data.board.filter(r=>r.game_id===g.game_id);
    const pick=rows.find(qualified),locked=!open(g),ph=g.p_home;
    const score=g.state==='pre'?(known?fmt(p.away_goals)+' : '+fmt(p.home_goals):'— : —'):fmt(g.away_score,0)+' : '+fmt(g.home_score,0);
    const pairs=['ML','ATS','TOTAL'].map(m=>rows.filter(r=>r.market===m)).filter(r=>r.length);
    const stats=side=>{const t=g[side+'_stats']||{};return t.current?.gp?t.current:t.prior||{};};
    const extra=side=>g[side+'_stats']?.extra||{};
    const comparisons=[['Goals / game',stats('away').gf_pg,stats('home').gf_pg],['Allowed / game',stats('away').ga_pg,stats('home').ga_pg],['Shots / game',extra('away').shots_pg,extra('home').shots_pg],['Shots allowed / game',extra('away').shots_against_pg,extra('home').shots_against_pg],['Save %',extra('away').save_pct==null?null:extra('away').save_pct*100,extra('home').save_pct==null?null:extra('home').save_pct*100],['Shooting %',extra('away').shooting_pct,extra('home').shooting_pct],['Faceoff %',extra('away').faceoff_pct,extra('home').faceoff_pct],['Power-play %',extra('away').pp_pct==null?null:extra('away').pp_pct*100,extra('home').pp_pct==null?null:extra('home').pp_pct*100],['Penalty kill %',extra('away').pk_pct==null?null:extra('away').pk_pct*100,extra('home').pk_pct==null?null:extra('home').pk_pct*100],['Power-play goals',extra('away').pp_goals,extra('home').pp_goals],['Short-handed goals',extra('away').sh_goals,extra('home').sh_goals],['Penalty min / game',extra('away').penalty_minutes_pg,extra('home').penalty_minutes_pg]];
    return '<article class="game-card" data-game="'+esc(g.game_id)+'"><div class="game-top"><span>'+esc(time(g.date))+'</span><span class="pill '+(pick?'gold':'')+'">'+esc(pick?pick.tier:g.season_type===1?'PRESEASON':g.status_detail||g.status)+'</span></div><div class="faceoff">'+team('away')+'<div class="score"><strong>'+esc(score)+'</strong><small>'+esc(g.state==='pre'?'projected goals':g.status)+'</small></div>'+team('home')+'</div>'+
    (known?'<div class="win-chance" role="img" aria-label="Model win probability '+esc(g.away)+' '+pct(1-ph)+', '+esc(g.home)+' '+pct(ph)+'"><div class="win-label"><span>'+esc(g.away)+' '+pct(1-ph)+'</span><span>'+pct(ph)+' '+esc(g.home)+'</span></div><div class="bar"><i style="width:'+((1-ph)*100)+'%"></i><i style="width:'+(ph*100)+'%"></i></div></div>':'<p class="note" style="padding:0 18px">Forecast unavailable: '+esc(p.reason||'insufficient data')+'</p>')+
    '<div class="context-row">'+['away','home'].map(side=>{const q=g[side+'_goalie']||{};return '<div class="goalie">'+image(q.headshot,'')+'<div><small>'+esc(g[side])+' · GOALIE</small><b>'+esc(q.name||'Not announced')+'</b><small>'+esc(q.confirmed?'Confirmed':q.status||'Unknown')+' · '+esc(g[side+'_rest']==null?'Rest unknown':g[side+'_rest']===0?'Back-to-back':g[side+'_rest']+' rest days')+'</small></div></div>';}).join('')+'</div><div class="markets">'+
    (pairs.length?pairs.map(pair=>'<div class="market-row">'+pair.slice(0,2).map(r=>'<div class="market '+(qualified(r)?'qualifies':'')+'"><div><b>'+esc(r.pick)+'</b><strong>'+odd(r.price)+'</strong></div><small>'+esc(r.book)+' · '+esc(r.market==='ATS'?'Puck line':r.market==='TOTAL'?'Total':'Moneyline')+'</small><small class="edge">Blended '+pct(r.model_prob)+' · EV '+pct(r.edge)+'</small><small>'+esc(qualified(r)?r.tier:(r.reasons||[])[0]||'Price check required')+'</small><button data-bet="'+esc(data.board.indexOf(r))+'" '+(!actionable(r)?'disabled':'')+'>Add my wager</button></div>').join('')+'</div>').join(''):'<p class="note">No complete two-sided prices published. Winner forecasts can still appear on Moneyline.</p>')+'</div><details><summary>Matchup lab · stats, scoring map & context</summary><div class="deep-dive"><p class="note">'+esc(g.venue||'Venue unavailable')+(g.broadcast?' · '+esc(g.broadcast):'')+'</p><p class="note">Goal rates: '+['away','home'].map(side=>esc(g[side])+' '+(g[side+'_stats']?.current?.gp?'current season':'prior season')+' ('+fmt(stats(side).gp,0)+' games)').join(' · ')+'</p><div class="comparison"><b>'+esc(g.away)+'</b><span>TEAM COMPARISON</span><b>'+esc(g.home)+'</b></div>'+comparisons.map(([label,a,h])=>'<div class="comparison"><b>'+fmt(a)+'</b><span>'+esc(label)+'</span><b>'+fmt(h)+'</b></div>').join('')+
    (known?'<p class="note">Most likely final scores · away–home. Goal-rate estimate; not shot-based xG.</p><div class="scorelines">'+p.scores.slice(0,5).map(s=>'<span>'+s.away+'–'+s.home+' <b>'+pct(s.probability)+'</b></span>').join('')+'</div><p class="note">Score map: columns '+esc(g.home)+' 0–7 · rows '+esc(g.away)+' 0–7. Darker means less likely. Outcomes of 8+ goals are outside this view.</p><div class="distribution" role="img" aria-label="Final score probability grid">'+p.matrix.flatMap((row,a)=>row.map((value,h)=>'<span title="'+esc(g.away)+' '+a+'–'+h+' '+esc(g.home)+': '+pct(value)+'" style="background:rgba(72,211,219,'+Math.min(.85,value*12)+')">'+(value>=.005?Math.round(value*100)+'%':'·')+'</span>')).join('')+'</div><p class="note">Projected final total '+fmt(p.total)+' · Regulation tie '+pct(p.overtime_prob)+' · Prior-season blend '+pct(p.prior_weight)+'</p>':'')+
    (safe(g.source_url)?'<a href="'+safe(g.source_url)+'" target="_blank" rel="noopener">ESPN game centre ↗</a>':'')+'</div></details></article>';
    function team(side){return '<div class="team">'+image(g[side+'_logo'],g[side+'_name'])+'<strong>'+esc(g[side])+'</strong><small>'+esc(g[side+'_name'])+'</small><small>'+esc(g[side+'_record']||'Record unavailable')+'</small></div>';}
  }
  function render(){
    if(!data.meta)return;
    const upcoming=data.games.filter(open),picks=data.board.filter(qualified),goalies=upcoming.reduce((n,g)=>n+['home','away'].filter(s=>g[s+'_goalie']?.confirmed).length,0);
    $('#health').textContent=(failed?'Refresh failed · retained publication; picks paused. ':!recent()?'Publication stale · picks paused. ':'Observed public data · ')+time(data.meta.generated_at);
    $('#health').classList.toggle('bad',!recent());
    $('#metrics').innerHTML=metric(upcoming.length,'Upcoming games','Rolling 8-day slate')+metric(picks.length,'Qualified picks','Fresh prices + model edge')+metric(goalies,'Confirmed goalies','Across upcoming games')+metric(data.standings.teams.length,'Teams tracked',data.meta.season-1+'–'+String(data.meta.season).slice(-2)+' season');
    let games=data.games.filter(g=>g.day===$('#date').value);
    const filter=$('#filter').value;
    if(filter==='qualified')games=games.filter(g=>picks.some(r=>r.game_id===g.game_id));
    if(filter==='open')games=games.filter(open);
    if(filter==='final')games=games.filter(g=>g.completed);
    const expanded=new Set([...document.querySelectorAll('.game-card details[open]')].map(d=>d.closest('[data-game]').dataset.game));
    $('#games').innerHTML=games.length?games.map(card).join(''):'<div class="empty">'+(filter==='qualified'?'No NHL picks meet every qualification check for this date. Switch to All matchups to inspect forecasts and the reasons.':'No games in this published date window. Choose another date or use Next game day.')+'</div>';
    document.querySelectorAll('.game-card').forEach(c=>{if(expanded.has(c.dataset.game))c.querySelector('details').open=true;});
    const teams=data.standings.teams.filter(t=>$('#conference').value==='all'||t.conference===$('#conference').value).sort((a,b)=>(b.points||0)-(a.points||0)||(b.goal_diff||0)-(a.goal_diff||0)||a.abbr.localeCompare(b.abbr));
    $('#standings-note').textContent='Current-season standings. Matchup comparisons use clearly labelled prior-season rates when the current season has no sample.';
    $('#standings-rows').innerHTML=teams.map(t=>'<tr><td>'+image(t.logo,'')+'<b>'+esc(t.abbr)+'</b></td><td>'+fmt(t.gp,0)+'</td><td>'+[t.wins,t.losses,t.otl].map(x=>fmt(x,0)).join('–')+'</td><td><b>'+fmt(t.points,0)+'</b></td><td>'+pct(t.points_pct)+'</td><td>'+fmt(t.gf_pg,2)+'</td><td>'+fmt(t.ga_pg,2)+'</td><td>'+fmt(t.goal_diff,0)+'</td><td>'+esc(t.last10||'—')+'</td><td>'+esc(t.home_record||'—')+'</td><td>'+esc(t.away_record||'—')+'</td></tr>').join('');
    $('#news-list').innerHTML=data.news.length?data.news.map(n=>'<article class="news-card">'+image(n.image,'')+'<div><a href="'+safe(n.url)+'" target="_blank" rel="noopener">'+esc(n.title)+'</a><small>ESPN · '+esc(time(n.published))+'</small></div></article>').join(''):'<p class="empty">News feed unavailable.</p>';
    $('#injury-list').innerHTML=table(['Team','Player','Status','Report date','Details'],data.injuries.slice(0,150).map(r=>[r.team,r.player,r.status,time(r.date),r.detail]),'No injury reports supplied; this does not confirm full availability.');
    const a=data.accuracy,w=a.games?.winner||{};
    $('#accuracy-metrics').innerHTML=metric(w.n||0,'Settled forecasts','Frozen before puck drop')+metric(pct(w.accuracy),'Winner accuracy','All tracked predictions')+metric(fmt(w.brier,3),'Brier score','Lower is better')+metric(a.pending||0,'Awaiting result','Official finals only');
    $('#accuracy-list').innerHTML=table(['Matchup','Start','Frozen pick','Model probability','Final'],[...(a.records||[])].reverse().slice(0,80).map(r=>[r.away+' @ '+r.home,time(r.start),r.p_home>.5?r.home:r.away,pct(Math.max(r.p_home,1-r.p_home)),r.result?r.result.away+'–'+r.result.home:'Pending']),'Tracking begins with real pregame forecasts. No results yet.');
    $('#source-list').innerHTML=table(['Source','Status','Observed'],Object.entries(data.meta.sources||{}).map(([k,v])=>[k,v.status,time(v.observed_at)]));
    renderLedger();
  }
  function table(headers,rows,empty='No data available.'){
    return rows.length?'<table><thead><tr>'+headers.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(c=>'<td>'+esc(c??'—')+'</td>').join('')+'</tr>').join('')+'</tbody></table>':'<p class="empty">'+esc(empty)+'</p>';
  }
  function renderLedger(){
    const rows=L.load(),s=L.summarise(rows,0);
    $('#ledger-metrics').innerHTML=metric('$'+fmt(s.profit,2),'Settled P/L')+metric(s.wins+'–'+s.losses,'Win–loss',s.pushes+' pushes')+metric(s.pending,'Open wagers','$'+fmt(s.at_risk,2)+' at risk')+metric(pct(s.roi),'Settled ROI');
    $('#ledger-list').innerHTML=table(['Matchup','Pick','Price','Stake','Result','P/L'],rows.map(r=>[r.matchup,r.pick,odd(r.price),'$'+fmt(r.stake,2),r.result||'Pending',r.profit==null?'—':'$'+fmt(r.profit,2)]),'No NHL wagers added. Use Add my wager on a priced game to record a bet you placed.');
    $('#sync-status').textContent=window.BetSync?.loadConfig()?'Using your existing shared-ledger connection. NHL wagers and settlements sync with the other boards.':'Saved in this browser. Connect the shared ledger from HQ to sync across devices.';
  }
  function settle(){
    const games=data.games.filter(g=>g.completed).map(g=>({game_id:g.game_id,completed:true,home:{score:g.home_score},away:{score:g.away_score}}));
    const out=L.settleAll(L.load(),games);if(out.changed)L.save(out.entries);
  }
  async function refresh(){
    if(loading)return;loading=true;$('#refresh').disabled=true;
    try{
      const names=['meta','games','board','standings','news','injuries','accuracy'];
      const values=await Promise.all(names.map(async name=>{const r=await fetch('data/'+name+'.json',{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error(name);return r.json();}));
      const next=Object.fromEntries(names.map((n,i)=>[n,values[i]]));
      if(!Array.isArray(next.games)||!Array.isArray(next.board)||!Array.isArray(next.standings?.teams)||!Array.isArray(next.news)||!Array.isArray(next.injuries)||!Number.isFinite(Date.parse(next.meta.generated_at)))throw Error('Invalid publication');
      const check=await fetch('data/meta.json',{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!check.ok||(await check.json()).generated_at!==next.meta.generated_at)throw Error('Publication changed; retry');
      data=next;failed=false;settle();render();
    }catch(_){failed=true;$('#health').textContent='NHL publication could not be refreshed. Retry shortly.';if(data.meta)render();else $('#games').innerHTML='<p class="empty">The NHL feed is unavailable. No sample picks are substituted.</p>';}
    finally{loading=false;$('#refresh').disabled=false;}
  }
  document.querySelector('.tabs').addEventListener('click',e=>{const b=e.target.closest('[data-tab]');if(!b)return;document.querySelectorAll('[data-tab]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));document.querySelectorAll('.panel').forEach(p=>p.hidden=p.id!==b.dataset.tab);});
  $('#date').value=day(Date.now());for(const id of ['date','filter','conference'])$('#'+id).addEventListener('change',render);
  $('#next').addEventListener('click',()=>{const g=data.games?.filter(open).sort((a,b)=>a.date.localeCompare(b.date))[0];if(g){$('#date').value=g.day;$('#filter').value='all';render();}});
  $('#games').addEventListener('click',e=>{const b=e.target.closest('[data-bet]');if(!b)return;const r=data.board[Number(b.dataset.bet)];if(!r||!actionable(r))return;pending=r;$('#bet-title').textContent=r.pick;$('#bet-detail').textContent=r.matchup+' · '+time(r.start_time)+' · '+(r.reasons?.join('; ')||r.tier);$('#stake').value='';$('#price').value=r.price;$('#book').value=r.book;$('#bet-error').textContent='';$('#bet-dialog').showModal();});
  $('#cancel-bet').addEventListener('click',()=>$('#bet-dialog').close());
  $('#bet-form').addEventListener('submit',e=>{
    e.preventDefault();const stake=Number($('#stake').value),price=Number($('#price').value),book=$('#book').value.trim();
    if(!pending||!actionable(pending)){$('#bet-error').textContent='This game or quote is no longer current. Refresh the board.';return;}
    if(!(stake>0&&stake<=100000)||Math.abs(price)<100||!Number.isFinite(price)||!book){$('#bet-error').textContent='Enter a positive stake, valid American odds (±100 or beyond), and sportsbook.';return;}
    const entry=L.entryFrom({...pending,tipoff:pending.start_time,price,book},stake),rows=L.load();
    if(rows.some(r=>L.keyOf(r)===L.keyOf(entry))){$('#bet-error').textContent='This selection is already in your ledger. Edit it from Shared ledger.';return;}
    if(!L.save([...rows,entry])){$('#bet-error').textContent='Browser storage failed. Your wager was not saved.';return;}
    $('#bet-dialog').close();renderLedger();window.BetSync?.sync().catch(()=>{});
  });
  window.nhlSharedLedger={reload:renderLedger,bank:()=>renderLedger()};
  $('#refresh').addEventListener('click',refresh);window.addEventListener('online',refresh);
  window.addEventListener('message',e=>{if(e.origin===location.origin&&e.data?.type==='kevbotbets:activate')refresh();});
  window.addEventListener('storage',renderLedger);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  setInterval(()=>{if(!document.hidden)refresh();},60000);setInterval(()=>{if(data.meta&&!document.hidden)render();},15000);refresh();
})();
