(() => {
  'use strict';
  const C=window.Moneyling,W=window.WeeklyFootball,$=s=>document.querySelector(s);
  const labels={nfl:'NFL',ncaaf:'College football'};
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const time=v=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(v));
  const pct=v=>C.number(v)===null?'Unavailable':(v*100).toFixed(1)+'%';
  let bundles={},busy=false;
  function render(){
    const floor=Math.max(0,Math.min(.1,(C.number($('#floor').value)??.5)/100));
    const cards=Object.entries(bundles).filter(([sport])=>$('#sport').value==='all'||sport===$('#sport').value)
      .flatMap(([sport,b])=>W.slate(sport,b,$('#date').value,Date.now(),floor))
      .filter(c=>$('#view').value==='all'||c.suggestions.some(r=>!r.research)).sort((a,b)=>a.when-b.when||a.key.localeCompare(b.key));
    $('#health').innerHTML=Object.entries(labels).map(([k,label])=>{const b=bundles[k],fresh=C.freshness(b?.meta?.generated_at,k,Date.now());return '<span class="health '+(!b||b.error||fresh!=='recent'?'bad':'')+'">'+esc(label)+' · '+esc(!b?'loading':b.error?'feed unavailable':fresh==='recent'?'updated '+time(b.meta.generated_at):'forecast '+fresh)+'</span>';}).join('');
    $('#cards').innerHTML=cards.length?cards.map(c=>'<article class="match-card"><div class="card-top"><b>'+esc(labels[c.sport])+'</b><span>'+esc(time(c.start))+'</span></div><h2>'+esc(c.away+' at '+c.home)+'</h2><div class="forecast">'+esc(c.predicted?c[c.predicted]+' to win':c.reason)+'</div>'+(c.probability!==null?'<p>'+pct(c.probability)+' model estimate'+(c.sport==='nfl'?' · excluding ties':'')+'</p>':'')+(c.predicted&&C.number(c.projection.score_home)!==null&&C.number(c.projection.score_away)!==null?'<p>Projected score: '+esc(c.away+' '+c.projection.score_away+' · '+c.home+' '+c.projection.score_home)+'</p>':'')+(c.notes?'<p class="context-note">'+esc(c.notes)+'</p>':'')+c.suggestions.filter(r=>$('#view').value!=='qualified'||!r.research).map(r=>'<div class="market"><b class="'+(r.research?'research':'')+'">'+esc(r.display_tier)+' · '+esc(r.pick)+' · '+(r.price>0?'+':'')+esc(r.price)+'</b><small>'+esc(r.book||'Book unspecified')+' · Adjusted model return '+pct(r.action_edge)+'</small><small>'+esc(r.reason||r.qualification||'Model threshold met')+'</small><small>'+esc(r.quote?'Quote observed '+time(r.quote):'Quote timestamp not supplied — verify the current price')+'</small></div>').join('')+(!c.suggestions.length?'<p class="context-note">No priced candidate clears this view’s checks.</p>':'')+'<a href="./#'+c.sport+'" target="_top">Review '+esc(labels[c.sport])+' model →</a></article>').join(''):'<div class="empty">'+(busy?'Loading…':'No games match these filters. Check the feed status or select another seven-day window.')+'</div>';
  }
  async function get(path){const r=await fetch(path,{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error('Feed unavailable');return r.json();}
  async function refresh(){if(busy)return;busy=true;bundles={};$('#refresh').disabled=true;$('#status').textContent='Checking forecasts…';render();
    await Promise.all(Object.keys(labels).map(async sport=>{const base='../'+(sport==='nfl'?'nfl-edge-lab':'ncaaf-edge-lab')+'/data/';try{const names=sport==='nfl'?['meta','games','board','games_detail']:['meta','games','board'];const data=await Promise.all(names.map(n=>get(base+n+'.json')));bundles[sport]=Object.fromEntries(names.map((n,i)=>[n==='games_detail'?'details':n,data[i]]));}catch(_){bundles[sport]={error:true};}}));
    busy=false;$('#refresh').disabled=false;$('#status').textContent='Forecasts checked '+time(new Date().toISOString())+'. Research minimum does not alter betting tiers.';render();
  }
  $('#date').value=C.day(Date.now());for(const id of ['date','sport','view','floor'])$('#'+id).addEventListener('change',()=>{if($('#date').value)render();});$('#refresh').addEventListener('click',refresh);
  window.addEventListener('message',e=>{if(e.origin===location.origin&&e.data?.type==='kevbotbets:activate')refresh();});setInterval(render,15000);refresh();
})();
