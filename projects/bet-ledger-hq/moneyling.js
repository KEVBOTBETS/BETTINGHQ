(() => {
  'use strict';
  const C=window.Moneyling,$=s=>document.querySelector(s),KEY='kevbot-moneyling-v1';
  const LABEL={nfl:'NFL',ncaaf:'College football',mlb:'MLB'};
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const time=v=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(v));
  let saved={},bundles={},loading=false,request=0;
  try{const value=JSON.parse(localStorage.getItem(KEY)||'{}');if(value&&typeof value==='object'&&!Array.isArray(value))saved=Object.fromEntries(Object.entries(value).filter(([k,v])=>v&&v.key===k&&C.instant(v.start)!==null&&['home','away'].includes(v.side)&&LABEL[v.sport]));}
  catch(_){$('#storage-status').textContent='Saved selections could not be read. New picks will remain on this page until saving succeeds.';}
  const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(saved));$('#storage-status').textContent='Selections saved in this browser.';}catch(_){$('#storage-status').textContent='Browser storage is unavailable. Keep this page open or print your card to preserve these picks.';}};
  const allCards=()=>Object.entries(bundles).flatMap(([k,b])=>C.cards(k,b)).filter(c=>c.day===$('#date').value).sort((a,b)=>a.when-b.when||a.key.localeCompare(b.key));
  const visible=()=>allCards().filter(c=>$('#sport').value==='all'||c.sport===$('#sport').value);
  const isLocked=c=>c.locked||(saved[c.key]&&C.instant(saved[c.key].start)<=Date.now());
  async function get(url){const response=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!response.ok)throw new Error('Feed unavailable');return response.json();}
  function render(){
    const rows=visible();
    $('#cards').innerHTML=rows.length?rows.map((c,i)=>{
      const locked=isLocked(c),chosen=saved[c.key];
      return '<article class="match-card"><div class="card-top"><b>'+String(i+1).padStart(2,'0')+' / '+esc(LABEL[c.sport])+'</b><span>'+esc(time(c.start))+'</span></div><h2>'+esc(c.away+' at '+c.home)+'</h2><div class="team-options">'+['away','home'].map(side=>'<button class="team-option" data-key="'+esc(c.key)+'" data-side="'+side+'" aria-label="Pick '+esc(c[side+'Name'])+'" aria-pressed="'+(chosen?.side===side)+'" '+(loading||!c.selectable||locked?'disabled':'')+'><strong>'+esc(c[side])+'</strong><small>'+esc(c[side+'Name'])+'</small>'+(c.predicted===side?'<span class="pick-label">PREDICTED WINNER</span>':'')+'</button>').join('')+'</div><div class="card-bottom">'+(c.predicted?'<strong>'+esc(c[c.predicted])+' to win</strong>'+(c.probability!==null?' · '+Math.round(c.probability*100)+'% model estimate':''):esc(c.reason||'No prediction'))+(locked&&c.predicted?' · Locked':'')+(c.notes?'<small>'+esc(c.notes)+'</small>':'')+'</div></article>';
    }).join(''):'<div class="empty">'+(loading?'Loading the published games…':'No games available for this date and sport. Check the source status above or choose another date.')+'</div>';
    const picks=Object.values(saved).filter(r=>r.day===$('#date').value&&($('#sport').value==='all'||r.sport===$('#sport').value)).sort((a,b)=>a.start.localeCompare(b.start));
    $('#selection-count').textContent=picks.length+' pick'+(picks.length===1?'':'s')+' selected';
    $('#saved').innerHTML=picks.length?picks.map(r=>'<div class="saved-row"><span>'+esc(LABEL[r.sport]+' · '+r.away+' at '+r.home)+'<small>'+esc(time(r.start))+' · '+(C.instant(r.start)<=Date.now()?'Locked':'Open')+'</small></span><b>'+esc(r.team)+' ✓</b></div>').join(''):'<p class="empty">Choose a team on each card, or use the predicted winners.</p>';
    $('#use-picks').disabled=loading||!rows.some(c=>c.predicted&&c.selectable&&!isLocked(c));
    $('#clear').disabled=loading||!picks.some(r=>C.instant(r.start)>Date.now()&&!rows.find(c=>c.key===r.key)?.locked);
    $('#print').disabled=!picks.length;
    $('#health').innerHTML=Object.entries(LABEL).map(([k,label])=>{const b=bundles[k],stamp=(k==='mlb'?b?.slate:b?.meta)?.generated_at,fresh=C.freshness(stamp,k,Date.now()),bad=!b||b.error||fresh!=='recent';return '<span class="health '+(bad?'bad':'')+'">'+esc(label)+' · '+esc(!b?'loading':b.error?'feed unavailable':fresh==='recent'?'updated '+time(stamp):'forecast '+fresh)+'</span>';}).join('');
  }
  async function refresh(){
    const token=++request,date=$('#date').value;if(!date)return;
    loading=true;bundles={};$('#refresh').disabled=true;$('#status').textContent='Checking published forecasts…';render();
    const paths={mlb:{slate:'../mlb-edge/data/slate-'+date+'.json'},nfl:{meta:'../nfl-edge-lab/data/meta.json',games:'../nfl-edge-lab/data/games.json',details:'../nfl-edge-lab/data/games_detail.json'},ncaaf:{meta:'../ncaaf-edge-lab/data/meta.json',games:'../ncaaf-edge-lab/data/games.json'}};
    await Promise.all(Object.entries(paths).map(async([sport,files])=>{try{const entries=await Promise.all(Object.entries(files).map(async([key,url])=>[key,await get(url)]));if(token===request)bundles[sport]=Object.fromEntries(entries);}catch(_){if(token===request)bundles[sport]={error:true};}}));
    if(token!==request)return;
    loading=false;$('#refresh').disabled=false;$('#status').textContent='Forecasts checked '+time(new Date().toISOString())+'. Only fresh pregame picks can be selected.';render();
  }
  $('#cards').addEventListener('click',event=>{const b=event.target.closest('[data-key]');if(!b||loading)return;const c=visible().find(c=>c.key===b.dataset.key);if(c){saved=C.choose(saved,c,b.dataset.side);save();render();}});
  $('#use-picks').addEventListener('click',()=>{if(loading)return;for(const c of visible())if(c.predicted)saved=C.choose(saved,c,c.predicted);save();render();});
  $('#clear').addEventListener('click',()=>{const rows=visible();saved=Object.fromEntries(Object.entries(saved).filter(([key,r])=>r.day!==$('#date').value||($('#sport').value!=='all'&&r.sport!==$('#sport').value)||C.instant(r.start)<=Date.now()||rows.find(c=>c.key===key)?.locked));save();render();});
  $('#date').value=C.day(Date.now());$('#date').addEventListener('change',refresh);$('#sport').addEventListener('change',render);$('#refresh').addEventListener('click',refresh);$('#print').addEventListener('click',()=>window.print());
  window.addEventListener('message',e=>{if(e.origin===location.origin&&e.data?.type==='kevbotbets:activate')refresh();});
  window.addEventListener('online',refresh);document.addEventListener('visibilitychange',()=>{if(!document.hidden)render();});
  setInterval(render,15000);refresh();
})();
