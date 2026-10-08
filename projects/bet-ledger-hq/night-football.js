(() => {
  'use strict';
  const C=window.NightFootball,$=s=>document.querySelector(s),params=new URLSearchParams(location.search);
  const night=Object.hasOwn(C.nights,params.get('night'))?params.get('night'):'thursday',config=C.nights[night];
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safe=v=>{try{const u=new URL(v);return u.protocol==='https:'?u.href:'';}catch{return '';}};
  const clock=v=>{const t=C.instant(v);return t===null?'Unknown time':new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(t))+' ET';};
  const odds=v=>C.number(v)===null?'—':(Number(v)>0?'+':'')+Math.round(Number(v));
  const pct=v=>C.number(v)===null?'—':(Number(v)*100).toFixed(1)+'%';
  const empty=v=>`<div class="empty">${esc(v)}</div>`;
  const tier=r=>`<span class="night-tier ${['LEAN','GOOD','BEST BET'].includes(r.tier)?'':'pass'}">${esc(r.tier||'RESEARCH')}</span>`;
  let nfl={},props={},news={},busy=null,selected='',propLimit=40,lastChecked=0;
  $('#night-title').innerHTML=esc(night[0].toUpperCase()+night.slice(1))+' night<br><span>Football.</span>';$('#night-code').textContent=config.short;document.title=config.label+' · KEVBOTBETS';
  document.documentElement.dataset.kbLeague='nfl';document.documentElement.style.setProperty('--kb-code',`'${config.short}'`);
  document.querySelectorAll('.night-switch a').forEach(a=>a.setAttribute('aria-current',a.search==='?night='+night?'page':'false'));
  function team(g,side){const t=g[side];return t&&typeof t==='object'?t:{abbr:t||'—',name:g[side+'_name']||t||'Team unavailable'};}
  function note(row,source,now){return C.quoteState(row,source.meta,now,!!source.error);}
  function eligible(row,source,games,now){const g=games.find(g=>String(g.game_id)===C.eventId(row));return g&&!nfl.error&&C.fresh(nfl.meta?.generated_at,now)&&!g.completed&&!g.source_stale&&C.qualified(row,source.meta,now,!!source.error);}
  function marketTable(rows,source,now,player=false){
    if(!rows.length)return empty(player?'No player prop contracts have been published for this night. Check back after collection; no substitute props are generated.':'No priced market rows have been published for this night. Forecasts can remain visible without book prices.');
    return `<div class="night-table-wrap"><table class="night-table"><thead><tr><th>${player?'Player / pick':'Matchup / pick'}</th><th>Market</th><th>Book / odds</th><th>Model</th><th>Publication / eligibility</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.pick||r.player||r.matchup)}<small>${esc(r.matchup)}</small></td><td>${esc(r.market)}<small>${esc(r.side)} ${r.line==null?'':esc(r.line)}</small></td><td>${esc(r.book||'Book unavailable')} · ${odds(r.price??r.price_american)}<small>${r.price_source==='model'?'EST · model price':'Quote '+esc(clock(r.odds_observed_at||r.updated_at))}</small></td><td>${pct(r.model_prob)}<small>${tier(r)}</small></td><td>${esc(note(r,source,now))}<small>${esc(r.filtered||r.qualification||r.reason||(r.held?'Held until betting window':''))}</small></td></tr>`).join('')}</tbody></table></div>`;
  }
  function render(){
    const now=Date.now(),dates=C.schedule(nfl.games,night,now),wanted=selected||params.get('date');
    if(!selected)selected=dates.some(d=>d.day===wanted)?wanted:C.defaultDate(dates,now);
    // Keep an explicitly selected night visible if the schedule temporarily loses it.
    $('#night-date').innerHTML=(selected&&!dates.some(d=>d.day===selected)?`<option value="${esc(selected)}">${esc(selected)} · schedule unavailable</option>`:'')+dates.map(d=>`<option value="${esc(d.day)}">${esc(d.day)} · Week ${esc(d.games[0].week??'—')} · ${d.games.length} game${d.games.length===1?'':'s'}</option>`).join('')+(selected?'':'<option value="">No upcoming night published</option>');$('#night-date').value=selected;
    const scheduled=dates.find(d=>d.day===selected)?.games||[],details=new Map((nfl.details||[]).map(g=>[String(g.game_id),g]));
    const games=scheduled.map(g=>({...g,...details.get(String(g.game_id)),date:g.date,completed:g.completed||details.get(String(g.game_id))?.completed}));
    $('#night-health').innerHTML=[['NFL',nfl],['Props / parlays',props]].map(([label,s])=>`<span class="health ${s.error||!C.fresh(s.meta?.generated_at,now)?'bad':''}">${label} · ${s.error?'refresh failed; retained snapshot':C.fresh(s.meta?.generated_at,now)?'published '+esc(clock(s.meta.generated_at)):'stale or unavailable'}</span>`).join('')+`<span class="health ${news.error||news.errors?.length?'bad':''}">News · ${news.error?'refresh unavailable':news.errors?.length?news.errors.length+' team feeds unavailable; source times retained':'source times shown on each story'}</span>`;
    const blank=!nfl.games?'NFL schedule unavailable. Use Refresh view to retry.':`No ${config.label} matchup is published for this selection. Afternoon games are not included.`;
    $('#night-games').innerHTML=games.length?games.map(g=>{
      const away=team(g,'away'),home=team(g,'home'),p=g.projection||{},w=g.weather||{},f=w.forecast||{};
      const badge=t=>`<div class="night-team">${safe(t.logo)?`<img src="${esc(safe(t.logo))}" alt="" loading="lazy">`:''}<strong>${esc(t.abbr)}</strong></div>`;
      return `<article class="night-card"><span class="tag">${config.short} / WEEK ${esc(g.week??'—')}</span><div class="night-matchup">${badge(away)}<span>AT</span>${badge(home)}</div><h3>${esc(away.name)} @ ${esc(home.name)}</h3><p>${esc(clock(g.date))} · ${esc(g.broadcast||'Broadcast not supplied')}<br>${esc(g.venue||g.venue_name||'')}</p>${g.completed?`<p class="night-score">Final: ${esc(g.away_score??'—')} – ${esc(g.home_score??'—')}</p>`:C.instant(g.date)<=now?'<p class="night-warning">Kickoff passed · bets locked. Score/status reflects the published snapshot.</p>':`<p>Model projection: ${esc(away.abbr)} ${esc(p.score_away??'—')} – ${esc(home.abbr)} ${esc(p.score_home??'—')}</p>`}<small>Forecast published ${esc(clock(nfl.meta?.generated_at))}</small><p>Roof ${esc(w.roof||'unknown')} · wind ${f.wind_mph==null?'unknown':esc(f.wind_mph)+' mph'} · gusts ${f.gust_mph==null?'unknown':esc(f.gust_mph)+' mph'}<br>Injury context: ${esc((g.injuries?.reasons||[]).join(' · ')||'No matchup injury adjustment supplied')}</p><a href="https://www.espn.com/nfl/game/_/gameId/${encodeURIComponent(g.game_id)}" target="_blank" rel="noopener">Official game coverage ↗</a></article>`;
    }).join(''):empty(blank);
    const lines=C.rowsFor(nfl.board,games),propRows=C.rowsFor(props.legs,games),propBoard=C.rowsFor(props.board,games);
    $('#night-lines').innerHTML=marketTable(lines,nfl,now);
    const bets=[...lines.filter(r=>eligible(r,nfl,games,now)).map(r=>({...r,source:nfl})),...propBoard.filter(r=>eligible(r,props,games,now)).map(r=>({...r,source:props}))].sort((a,b)=>(C.number(b.action_edge)||0)-(C.number(a.action_edge)||0));
    $('#night-bets').innerHTML=bets.length?bets.slice(0,24).map(r=>`<article class="night-card">${tier(r)}<h3>${esc(r.pick)}</h3><p>${esc(r.matchup)} · ${esc(r.book)} ${odds(r.price??r.price_american)}</p><p>Model ${pct(r.model_prob)} · adjusted return ${pct(r.action_edge)}</p><small>${esc(r.qualification||r.reason||'Production model threshold met')}</small><small>Quote ${esc(clock(r.odds_observed_at||r.updated_at))}</small><a href="./#${r.event_id?'props':'nfl'}" target="_top">Review in full model ↗</a></article>`).join(''):empty(games.some(g=>C.instant(g.date)<=now)?'No eligible pregame bets remain for the started games. Any future game on this night is evaluated separately.':'No bets qualify with fresh published prices for this night. Review PASS reasons and quote status in the tables; a quiet board does not create a betting edge.');
    const propKeys=new Set(propRows.map(r=>[r.event_id,r.player,r.market,r.side,r.line,r.book].join('|')));
    for(const r of propBoard)if(!propKeys.has([r.event_id,r.player,r.market,r.side,r.line,r.book].join('|')))propRows.push(r);
    $('#night-props').innerHTML=marketTable(propRows.slice(0,propLimit),props,now,true);$('#night-more').hidden=propRows.length<=propLimit;
    const tickets=C.ticketsFor(props.parlays?.tickets,games),canView=C.fresh(props.meta?.generated_at,now)&&!props.error;
    $('#night-parlays').innerHTML=tickets.length?tickets.slice(0,24).map(t=>{
      const states=t.legs.map(l=>note(l,props,now)),sameGame=new Set(t.legs.map(C.eventId)).size<t.legs.length;
      return `<article class="night-card"><span class="tag">${esc(t.profile||'Longshot')} / ${t.legs.length} LEGS / RESEARCH</span><h3>${esc(t.label||config.label)}</h3><ol>${t.legs.map(l=>`<li>${esc(l.pick)}<small>${esc(l.book||'Book unavailable')} ${odds(l.price_american)} · ${esc(note(l,props,now))}</small></li>`).join('')}</ol><p class="night-warning">${!canView?'Stale or failed publication · ':''}${states.some(s=>s!=='Fresh published quote')?'Contains unavailable, stale, held or locked legs · ':''}${sameGame?'Same-game probability unverified.':'Joint probability unvalidated.'}</p><p>Individual-leg price estimate ${odds(t.price_american??t.american)}. Combined sportsbook payout and ticket EV unavailable.</p><a href="./#props" target="_top">Open full parlay lab ↗</a></article>`;
    }).join(''):empty('No published parlay contains only games from this night. Tickets from other nights are not relabeled or trimmed.');
    const articles=games.flatMap(g=>news.events?.[String(g.game_id)]?.articles||[]),unique=new Map();
    for(const a of articles){const at=C.instant(a.published);if(at!==null&&at<=now&&now-at<=7*86400000&&C.local(at)?.day<=selected&&safe(a.url))unique.set(a.url,a);}
    const stories=[...unique.values()].sort((a,b)=>C.instant(b.published)-C.instant(a.published));
    $('#night-news').innerHTML=stories.length?stories.slice(0,12).map(a=>`<article class="night-card"><span class="tag">MATCHUP NEWS / ESPN</span><h3><a href="${esc(safe(a.url))}" target="_blank" rel="noopener">${esc(a.headline)} ↗</a></h3><small>Published ${esc(clock(a.published))}<br>Captured ${esc(clock(a.observed_at))}${news.error?' · refresh failed; retained news':!C.fresh(a.observed_at,now,36)?' · collection overdue':''}</small></article>`).join(''):empty(news.error?'Matchup news refresh failed. Official game coverage is linked above; no replacement headlines are generated.':'No recent team-specific news has been captured for these matchups. Official game coverage is linked above.');
    if(!busy)$('#night-status').textContent=`${config.label}${selected?' · '+selected:''} · ${games.length} game${games.length===1?'':'s'} · files checked ${lastChecked?clock(new Date(lastChecked).toISOString()):'not yet'}. ${nfl.error||props.error?'A feed failed; retained snapshots cannot qualify new bets.':'Quote times remain separate from page refresh time.'}`;
  }
  async function get(path){const r=await fetch(path+'?v='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error('Unavailable');return r.json();}
  function refresh(){
    if(busy)return busy;$('#night-refresh').disabled=true;$('#night-status').textContent='Checking this night’s published feeds…';
    busy=Promise.allSettled([
      (async()=>{try{const [meta,games,details,board]=await Promise.all(['meta','games','games_detail','board'].map(f=>get('../nfl-edge-lab/data/'+f+'.json')));if(!C.instant(meta?.generated_at)||![games,details,board].every(Array.isArray)||!games.every(g=>g&&g.game_id&&C.instant(g.date)!==null)||!details.every(g=>g&&g.game_id)||!board.every(r=>r&&C.eventId(r)))throw Error('Invalid NFL publication');nfl={meta,games,details,board};}catch{nfl={...nfl,error:true};}})(),
      (async()=>{try{const [meta,legs,board,parlays]=await Promise.all(['meta','legs','board','parlays'].map(f=>get('../props-edge/data/'+f+'.json')));if(!C.instant(meta?.generated_at)||!Array.isArray(legs)||!Array.isArray(board)||!Array.isArray(parlays?.tickets)||![...legs,...board].every(r=>r&&C.eventId(r))||!parlays.tickets.every(t=>t&&Array.isArray(t.legs)&&t.legs.every(l=>l&&C.eventId(l))))throw Error('Invalid props publication');props={meta,legs,board,parlays};}catch{props={...props,error:true};}})(),
      (async()=>{try{const d=await get('data/newsletters/nights.json');if(d.schema!==1||!d.events||typeof d.events!=='object')throw Error('Invalid news');news=d;}catch{news={...news,error:true};}})()
    ]).finally(()=>{busy=null;lastChecked=Date.now();$('#night-refresh').disabled=false;render();});return busy;
  }
  $('#night-date').addEventListener('change',()=>{selected=$('#night-date').value;propLimit=40;const u=new URL(location.href);u.searchParams.set('date',selected);history.replaceState(null,'',u);render();});
  $('#night-more').addEventListener('click',()=>{propLimit+=40;render();});$('#night-refresh').addEventListener('click',refresh);
  window.addEventListener('online',refresh);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  window.addEventListener('message',e=>{if(e.origin===location.origin&&e.data?.type==='kevbotbets:activate')refresh();});
  setInterval(()=>{if(!document.hidden){render();if(Date.now()-lastChecked>=300000)refresh();}},15000);render();refresh();
})();
