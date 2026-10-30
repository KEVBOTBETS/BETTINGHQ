(function(){
  'use strict';const C=window.NBABands,$=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const state={games:[],meta:{},result:null,failed:true};const percent=p=>(100*p).toFixed(1)+'%';
  function render(){
    const date=$('#night').value||C.day(Date.now()),format=$('#format').value;
    const r=C.build(state.failed?[]:state.games,state.meta,{date,format});state.result=r;
    $('#summary').innerHTML=`<span><b>${r.pool.length}</b>60%+ predicted winners</span><span><b>${r.tickets.length}</b>nightly options · max 4 legs</span><span><b>Research</b>Exact book prices unverified</span>`;
    $('#tickets').innerHTML=r.tickets.length?r.tickets.map((t,i)=>`<article class="band-ticket"><span class="band-badge">${i===0?'Highest estimated chance':'Alternative '+i} · ${t.legs.length} games</span><h3>${i===0?'Top bands combination':t.legs.length===4?'Four-game option':'Three-game option'}</h3><ol>${t.legs.map(g=>`<li><strong>${esc(g.team)} to win by ${esc(g.band.label)}</strong><small>${esc(g.matchup)} · team win ${percent(g.win_prob)}<br>Band hit ${percent(g.band.prob)} · predicted win by about ${g.margin.toFixed(1)}</small></li>`).join('')}</ol><p class="band-chance">${percent(t.prob)}</p><small>Estimated whole-ticket hit chance · independence assumed</small><p>Sportsbook odds unavailable. Confirm every exact band and price.</p><button data-copy="${i}" type="button">Copy selections</button></article>`).join(''):`<p class="notice">${state.failed?'Forecast feed unavailable. Tickets are paused.':esc(r.reason)}</p>`;
    $('#games').innerHTML=r.pool.length?r.pool.map(g=>`<article class="band-game"><h3>${esc(g.team_name)}</h3><small>${esc(g.matchup)} · ${new Date(g.tipoff).toLocaleTimeString('en-CA',{timeZone:'America/Toronto',hour:'numeric',minute:'2-digit'})} ET</small><div class="band-meter" aria-hidden="true"><span style="width:${g.win_prob*100}%"></span></div><strong>${percent(g.win_prob)} to win · about ${g.margin.toFixed(1)} points</strong><p>Top band: ${esc(g.bands[0].label)} · ${percent(g.bands[0].prob)} band hit chance</p><small>${g.bands.map(b=>esc(b.label)+': '+percent(b.prob)).join(' · ')}</small></article>`).join(''):'<p>No fresh, qualifying winners for this night. Other nights remain selectable; games below 60% are not promoted.</p>';
  }
  async function load(){
    const old=$('#night').value;state.failed=true;$('#refresh').disabled=true;render();$('#status').textContent='Refreshing published NBA forecasts…';
    try{
      const [games,meta]=await Promise.all(['games','meta'].map(async n=>{const res=await fetch(`data/${n}.json`,{cache:'no-store'});if(!res.ok)throw Error('HTTP '+res.status);return res.json();}));
      if(!Array.isArray(games)||!meta.generated_at)throw Error('Invalid feed');state.games=games;state.meta=meta;state.failed=false;
      const today=C.day(Date.now()),days=[...new Set([today,...games.filter(g=>Date.parse(g.tipoff)>Date.now()&&Date.parse(g.tipoff)-Date.now()<=48*3600000).map(g=>C.day(g.tipoff))])].sort();
      $('#night').innerHTML=days.map(d=>`<option value="${d}">${d}${d===today?' · Tonight':''}</option>`).join('');$('#night').value=days.includes(old)?old:today;
      const age=Date.now()-Date.parse(meta.generated_at);$('#status').textContent=Number.isFinite(age)&&age>=0&&age<=4*3600000?`Published ${new Date(meta.generated_at).toLocaleString('en-CA',{timeZone:'America/Toronto'})} ET · Research baseline · live prices unverified`:'Forecasts are stale or have an invalid timestamp. New tickets are paused.';
    }catch(e){state.games=[];state.meta={};$('#status').textContent='NBA feed unavailable. Refresh to try again; no old tickets are treated as current.';}
    finally{$('#refresh').disabled=false;render();}
  }
  $('#night').addEventListener('change',render);$('#format').addEventListener('change',render);$('#refresh').addEventListener('click',load);
  $('#tickets').addEventListener('click',async event=>{
    const button=event.target.closest('[data-copy]');if(!button)return;const ticket=state.result?.tickets[Number(button.dataset.copy)];if(!ticket)return;
    if(state.failed||ticket.legs.some(l=>Date.parse(l.tipoff)<=Date.now())||Date.now()-Date.parse(state.meta.generated_at)>4*3600000){render();$('#action-status').textContent='Ticket expired. Refresh the lab.';return;}
    const text=['NBA winning-margin research · '+state.result.date,...ticket.legs.map(l=>`${l.team} by ${l.band.label} (${l.matchup}); team win ${percent(l.win_prob)}, band hit ${percent(l.band.prob)}`),`Whole ticket estimate ${percent(ticket.prob)}; independence assumed. Exact sportsbook odds and band availability unverified.`].join('\n');
    try{await navigator.clipboard.writeText(text);$('#action-status').textContent='Selections copied. Confirm the exact book bands and prices.';$('#copy-fallback').hidden=true;}catch(e){$('#copy-fallback').hidden=false;$('#copy-fallback').value=text;$('#copy-fallback').select();$('#action-status').textContent='Select and copy the ticket text below.';}
  });
  setInterval(render,30000);load();
})();
