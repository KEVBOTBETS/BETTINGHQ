(() => {
  'use strict';
  const A=window.PropsApp,C=window.GameProps,{esc:e,pct,odds}=A,$=s=>document.querySelector(s);
  const panel=document.createElement('section');
  panel.id='tab-games';panel.className='panel';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-label','Weekly game props');
  panel.innerHTML=`<div class="panel-head"><div><p class="eyebrow">KEVBOTBETS / NFL GAME CENTER</p><h2>Every week. Every matchup.</h2><p class="lede">Up to 10 individual props per game. Qualified book prices lead by tier and edge; other posted lines follow by model probability. One selection per player and market.</p></div></div><div class="game-props-controls"><button id="game-week-prev" type="button" aria-label="Previous NFL week">←</button><label>NFL week<select id="game-week"></select></label><button id="game-week-next" type="button" aria-label="Next NFL week">→</button><label>Find your team<input id="game-team" type="search" placeholder="Team or matchup"></label></div><p id="game-props-status" role="status" aria-live="polite" class="muted">Loading the NFL schedule…</p><p class="muted">These are ranked individual selections. Combined odds and same-game probability are not calculated. EST marks a model price; HOLD and research rows are not qualified bets. Started games leave this board; frozen results remain in Accuracy.</p><div id="game-props-list" class="game-props-grid"></div>`;
  $('main').prepend(panel);
  let games=[],meta={},loading=null,ready=false,feedError='',visible=[];
  async function load(){
    if(loading)return loading;
    loading=Promise.all(['games','meta'].map(file=>fetch(`../nfl-edge-lab/data/${file}.json?v=${Date.now()}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('NFL schedule unavailable. Try reopening Weekly game props.');return r.json();})))
      .then(([g,m])=>{if(!Array.isArray(g))throw Error('NFL schedule unavailable.');games=g;meta=m||{};feedError='';ready=true;fillWeeks();})
      .catch(err=>{feedError=err.message;})
      .finally(()=>{loading=null;});
    return loading;
  }
  function fillWeeks(){
    const previous=$('#game-week').value,ws=C.weeks(games,meta);
    $('#game-week').innerHTML=ws.map(w=>`<option value="${e(w.key)}">${e(meta.season||'NFL')} · ${e(w.label)}</option>`).join('');
    const current=meta.current_week?C.weekKey(meta.current_week):'2:1';
    $('#game-week').value=ws.some(w=>w.key===previous)?previous:ws.some(w=>w.key===current)?current:'2:1';
  }
  const date=x=>Number.isFinite(Date.parse(x))?new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(x)):'Kickoff TBA';
  const rowsFor=g=>C.rank(g,A.state.legs.map(A.pricedLeg),{generatedAt:A.state.meta?.generated_at,maxAgeHours:Number(A.state.meta?.max_odds_age_hours)||12});
  function render(){
    if(!ready){$('#game-props-status').textContent=feedError||'Loading the NFL schedule…';return;}
    const search=$('#game-team').value.trim().toLowerCase(),week=$('#game-week').value;
    visible=games.filter(g=>C.weekKey(g)===week&&(!search||`${g.away} ${g.home} ${g.away_name} ${g.home_name}`.toLowerCase().includes(search))).sort((a,b)=>Date.parse(a.date)-Date.parse(b.date));
    const select=$('#game-week');$('#game-week-prev').disabled=select.selectedIndex<=0;$('#game-week-next').disabled=select.selectedIndex>=select.options.length-1;
    const entries=visible.map(g=>({game:g,rows:rowsFor(g)})),count=entries.reduce((n,x)=>n+x.rows.length,0);
    $('#game-props-status').textContent=`${visible.length} matchups · ${count} ranked props · times in Toronto · schedule built ${date(meta.generated_at)}${feedError?' · Schedule refresh unavailable; showing the last loaded schedule.':''}`;
    $('#game-props-list').innerHTML=entries.map(({game:g,rows})=>{
      const started=Date.parse(g.date)<=Date.now(),state=g.completed?'FINAL':started?'STARTED':rows.length?`${rows.length} / 10 PROPS`:'AWAITING LINES';
      return `<article class="game-props-card" data-game="${e(g.game_id)}"><header class="game-props-head"><p class="eyebrow">${e(state)} · ${e(g.broadcast||'NFL')}</p><h3>${e(g.away)} <span>@</span> ${e(g.home)}</h3><p>${e(g.away_name||g.away)} at ${e(g.home_name||g.home)}</p><p class="meta">${e(date(g.date))} · ${e(g.venue||'Venue TBA')}</p></header>${rows.length?`<ol class="game-props-rows">${rows.map((l,i)=>`<li><span class="rank">${String(i+1).padStart(2,'0')}</span><div class="game-prop-main"><b>${e(l.player)}</b><p>${e(l.market==='Anytime touchdown'?'Anytime touchdown':`${l.side} ${l.line??''} ${l.market}`)}</p><span class="tag">${e(l.game_prop_qualified?l.tier:l.held?'HOLD · RESEARCH':'RESEARCH')}</span>${l.status?` <span class="tag">${e(l.status)}</span>`:''}<p class="meta">${e(l.book||l.line_source||'Posted line')} · ${Number(l.samples)} game sample</p><p class="why">${e(l.reason||'Published player forecast')}</p></div><div class="game-prop-price"><b>${odds(l.price_american)}</b><small>${l.price_source==='book'?'BOOK':'EST PRICE'}</small><strong>${pct(l.model_prob)}</strong><small>MODEL</small></div></li>`).join('')}</ol><p class="game-props-note">${rows.length<10?'Only '+rows.length+' supported selections available. ':''}No opposite sides or alternate lines for the same player and market.</p><div class="ticket-actions"><button type="button" data-game-action="copy">Copy ranked list</button><button type="button" data-game-action="card">Make game card</button></div>`:`<div class="empty">${g.completed?'Game final. Open Accuracy for frozen forecast results.':started?'Game has started. Pregame selections are closed.':'No recent supported props on posted lines yet. This matchup will populate as the feed publishes lines and forecasts.'}</div>`}</article>`;
    }).join('')||'<div class="empty">No matchups match this week and team. Schedule entries appear when published.</div>';
  }
  const picks=rows=>rows.map(l=>({key:'props',sport:'NFL',pick:l.pick||`${l.player} ${l.side} ${l.line??''} ${l.market}`,event:l.matchup,start:l.start_time,price:l.price_american,tier:l.game_prop_qualified?l.tier:l.held?'HOLD':'RESEARCH',probability:l.model_prob,book:l.book,source:'NFL'}));
  $('#game-props-list').addEventListener('click',async ev=>{
    const button=ev.target.closest('[data-game-action]');if(!button)return;
    const g=visible.find(x=>String(x.game_id)===button.closest('[data-game]').dataset.game);if(!g)return;
    const rows=rowsFor(g);if(!rows.length){render();return;}
    if(button.dataset.gameAction==='copy'){
      const text=`KEVBOTBETS · ${g.away} @ ${g.home} · ${date(g.date)}\nRANKED INDIVIDUAL PROPS · NOT A PARLAY\n`+rows.map((l,i)=>`${i+1}. ${l.pick||l.player+' '+l.market} · ${odds(l.price_american)} ${l.price_source==='book'?'book':'EST'} · ${pct(l.model_prob)} model · ${l.game_prop_qualified?l.tier:l.held?'HOLD':'research'}`).join('\n');
      try{await navigator.clipboard.writeText(text);button.textContent='Copied ✓';}catch(_){button.textContent='Copy unavailable';}setTimeout(()=>button.textContent='Copy ranked list',1800);
    }else A.openCard({id:'game-props-'+g.game_id,day:window.PropsQuotes.day(g.date),picks:picks(rows),override:{title:'GAME PROPS',titleCase:'Game Props',subtitle:`${g.away} @ ${g.home} · TOP ${rows.length}`,stubKicker:'INDIVIDUAL PROP RANKINGS',ribbon:'KEVBOTBETS GAME CENTER',slipTitle:`${g.away} @ ${g.home} PROPS`,stamp:'RESEARCH',kicker:'INDIVIDUAL SELECTIONS · NOT A PARLAY',legal:'Individual prop research · EST prices are model estimates · Confirm current lines and prices · No combined odds or joint probability',stats:[['PROPS',String(rows.length)],['WEEK',String(g.week)],['QUALIFIED',String(rows.filter(l=>l.game_prop_qualified).length)],['SPORT','NFL']],slipLines:[['MATCHUP',`${g.away} @ ${g.home}`],['PROPS',String(rows.length)],['TYPE','INDIVIDUAL RESEARCH']]}});
  });
  $('#game-week').addEventListener('change',render);$('#game-team').addEventListener('input',render);
  for(const [id,delta] of [['game-week-prev',-1],['game-week-next',1]])$(id.startsWith('#')?id:'#'+id).addEventListener('click',()=>{const s=$('#game-week');s.selectedIndex=Math.max(0,Math.min(s.options.length-1,s.selectedIndex+delta));render();});
  window.addEventListener('props:tab',async ev=>{if(ev.detail==='games'){await load();render();}});
  window.addEventListener('props:data',()=>{if(ready)render();});
  setInterval(()=>{if(!document.hidden&&!panel.hidden)render();},60000);
})();
