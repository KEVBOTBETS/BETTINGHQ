(() => {
'use strict';
const $=s=>document.querySelector(s),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const url=v=>{try{const u=new URL(v);return u.protocol==='https:'?u.href:'';}catch{return '';}};
const params=new URLSearchParams(location.search),sport=params.get('sport')==='ncaaf'?'ncaaf':'nfl',name=sport.toUpperCase();let current='',serial=0;
const clock=v=>{const d=new Date(v);return Number.isFinite(d.getTime())?new Intl.DateTimeFormat('en-US',{timeZone:'America/Toronto',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(d)+' ET':'Unknown time';};
async function get(path){const r=await fetch('data/newsletters/'+path,{cache:'no-store',signal:AbortSignal.timeout(12000)});if(!r.ok)throw Error('Edition unavailable');return r.json();}
const image=(src,cls='')=>url(src)?`<img class="${cls}" src="${esc(url(src))}" alt="" loading="lazy" referrerpolicy="no-referrer">`:'';
function matchup(g,index){
 const o=g.odds||{},p=g.projection||{},w=g.weather||{},f=w.forecast||{},temp=f.temp_f??(f.temp_c!=null?Math.round(f.temp_c*9/5+32):null),wind=f.wind_mph,precip=f.precip_prob??f.rain_probability;
 const weather=Object.keys(f).length?[temp!=null?temp+'°F':null,wind!=null?'Wind '+wind+' mph':null,precip!=null?'Rain chance '+precip+'%':null,w.roof?'Roof: '+w.roof:null].filter(Boolean).join(' · '):'Kickoff weather unavailable. No weather advantage inferred.';
 const team=s=>`<div class="edition-team">${image(g[s+'_logo'])}<strong>${g[s+'_rank']>=1&&g[s+'_rank']<=25?'#'+esc(g[s+'_rank'])+' ':''}${esc(g[s])}</strong><small>${esc(g[s+'_name'])}</small></div>`;
 const scores=p.home!=null&&p.away!=null?`<div class="projection-score"><b>${esc(p.away)}</b><span>MODEL<br>PROJECTION</span><b>${esc(p.home)}</b></div>`:'<p class="muted">Model projection unavailable.</p>';
 const total=p.total!=null&&o.total!=null?`<div class="total-compare"><div><span>Model total</span><b>${esc(p.total)}</b></div><div><span>Book total</span><b>${esc(o.total)}</b></div><div class="total-track" aria-hidden="true"><i style="width:${Math.max(5,Math.min(95,50+(p.total-o.total)*3))}%"></i></div></div>`:'';
 return `<article class="edition-game"><header><span class="eyebrow">WATCHLIST / 0${index+1}</span><span>${esc(clock(g.date))}</span></header><div class="edition-matchup">${team('away')}<span class="versus">AT</span>${team('home')}</div>${scores}${total}<p class="desk-game-note">${esc([g.venue,g.broadcast,g.status].filter(Boolean).join(' · '))}</p><p class="quote-line">${esc(o.book||'Book unavailable')} · ${o.spread_home!=null?'Home spread '+esc(o.spread_home):'Spread unavailable'}${o.observed_at?' · captured '+esc(clock(o.observed_at)):''}</p><h3>Matchup factors</h3><ul>${(g.factors||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul><div class="weather-strip"><span aria-hidden="true">◉</span><p>${esc(weather)}<small>${esc(w.source||f.source||'Published model weather snapshot')}${w.checked_at?' · '+esc(clock(w.checked_at)):''}</small></p></div>${(g.review_flags||[]).length?`<p>${esc(g.review_flags.join(' · '))}</p>`:''}<p class="playoff-context"><b>Race context</b> ${esc(g.playoff)}</p><a class="text-link" href="https://www.espn.com/${sport==='nfl'?'nfl':'college-football'}/game/_/gameId/${encodeURIComponent(g.game_id)}" target="_blank" rel="noopener">Game coverage ↗</a></article>`;
}
async function load(id){const run=++serial;$('#edition-content').hidden=true;$('#edition-status').textContent='Loading '+name+' edition…';try{
 if(!/^[0-9]+-[0-9]+-[0-9]+$/.test(id))throw Error('Invalid edition');
 const [d,sources]=await Promise.all([get(sport+'/'+id+'.json'),get('sources.json')]);if(run!==serial)return;
 if(d.sport!==sport||d.id!==id)throw Error('Edition mismatch');
 $('#edition-label').textContent=name+' / '+d.season+' / WEEK '+d.week;
 $('#edition-title').innerHTML=name+'<br><em>The weekly dispatch.</em>';$('#edition-week').textContent='W'+d.week;
 const old=id!==current,stale=Date.now()-new Date(d.generated_at).getTime()>36*3600000;
 $('#edition-status').textContent=(old?'Archived edition · ':stale?'Published snapshot · refresh overdue · ':'Current edition · ')+clock(d.start)+' – '+clock(d.end)+' · Updated '+clock(d.generated_at)+'. Model snapshot: '+clock(d.model_generated_at)+'.';
 $('#edition-metrics').innerHTML=[['W'+d.week,'League week'],[d.games_count,'Games in the edition'],[d.headlines.length,'Dated stories'],[d.completed,'Games completed at capture']].map(([v,t])=>`<div><strong>${esc(v)}</strong><span>${esc(t)}</span></div>`).join('');
 $('#edition-news').innerHTML=d.headlines.map(n=>`<article class="edition-story">${image(n.image,'story-image')}<div><small class="eyebrow">ESPN / ${esc(clock(n.published))}</small><h3><a href="${esc(url(n.url))}" target="_blank" rel="noopener">${esc(n.headline)} ↗</a></h3><p class="muted">${(n.teams||[]).length?'Follow the '+esc(n.teams.join(', '))+' matchup coverage.':'Around the '+name+' week.'}</p></div></article>`).join('')||'<p class="muted">No dated headlines captured for this week. Today’s news is not inserted into an older edition.</p>';
 $('#edition-games').innerHTML=d.games.map(matchup).join('');$('#selection-note').textContent=d.selection_note;$('#edition-lab').href='./#'+sport;
 $('#playoff-note').textContent=d.playoff_note;$('#playoff-link').href=url(d.playoff_url);$('#edition-humor').textContent=d.humor;
 $('#edition-sources').innerHTML=sources.map(s=>`<article><span class="source-state">${esc(s.status)}</span><h3><a href="${esc(url(s.url))}" target="_blank" rel="noopener">${esc(s.name)} ↗</a></h3><p>${esc(s.use)}</p></article>`).join('');$('#edition-content').hidden=false;
 const next=new URL(location.href);next.searchParams.set('sport',sport);next.searchParams.set('edition',id);history.replaceState(null,'',next);
 }catch{if(run===serial)$('#edition-status').textContent='This edition is unavailable. Choose another week or try again after the scheduled refresh.';}}
document.documentElement.dataset.kbLeague=sport;document.documentElement.style.setProperty('--kb-art',"url('assets/sports/field.svg')");document.querySelectorAll('.league-tabs a').forEach(a=>a.setAttribute('aria-current',a.getAttribute('href')==='?sport='+sport?'page':'false'));
$('#edition-select').addEventListener('change',e=>load(e.target.value));
get(sport+'/index.json').then(index=>{current=index.current;$('#edition-select').innerHTML=index.editions.map(e=>`<option value="${esc(e.id)}">${e.season} · ${e.phase===1?'Preseason':e.phase===3?'Postseason':'Regular season'} · Week ${e.week}${e.id===current?' · Latest':''}</option>`).join('');const wanted=params.get('edition'),id=index.editions.some(e=>e.id===wanted)?wanted:current;$('#edition-select').value=id;load(id);}).catch(()=>{$('#edition-status').textContent='No weekly editions are available yet. The scheduled football refresh will publish the next edition.';});
})();
