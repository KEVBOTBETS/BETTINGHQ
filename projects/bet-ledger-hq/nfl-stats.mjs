import {fields,views,selectRows,formatStat,exportCSV} from './nfl-stats-core.mjs';
const $=s=>document.querySelector(s),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const BASE='../props-edge/data/nfl-weekly/',KEY='kevbot-nfl-weekly-view-v1';
let manifest=null,rows=[],loadedWeek=null,limit=100,busy=false,direction='asc',asOf=null,followCurrent=true,lastChecked=0;
const when=v=>{const d=new Date(v);return Number.isNaN(+d)?'Unknown time':d.toLocaleString(undefined,{timeZone:'America/Toronto',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'});};
function status(text,state='ok'){$('#stats-status').textContent=text;$('#stats-status').dataset.state=state;}
function preferences(){return {team:$('#stats-team').value,position:$('#stats-position').value,search:$('#stats-search').value,projected:$('#stats-only').checked,sort:$('#stats-sort').value,direction};}
function save(){try{localStorage.setItem(KEY,JSON.stringify({...preferences(),week:loadedWeek,view:$('#stats-view').value}));}catch{}}
function freshness(){if(!asOf)return;const age=(Date.now()-Date.parse(asOf))/3600000;return Number.isFinite(age)&&age>=-.25&&age<=6;}
function stamp(){if(!manifest)return;const missing=manifest.missing_roster_teams||[],fresh=freshness();status(`Snapshot ${when(asOf)} · ${manifest.roster_teams.length}/${manifest.teams.length} team rosters verified${fresh?'':' · stale or uncertain snapshot; refresh before relying on it'}${missing.length?' · Missing rosters: '+missing.join(', '):''}`,fresh&&!missing.length?'ok':'warning');}
function options(select,values,initial){const previous=select.value;select.replaceChildren(...values.map(([value,label])=>{const o=document.createElement('option');o.value=String(value);o.textContent=label;return o;}));select.value=[...select.options].some(o=>o.value===String(initial??previous))?String(initial??previous):select.options[0]?.value;}
function table(){
 if(!manifest)return;
 const filtered=selectRows(rows,preferences()),visible=filtered.slice(0,limit),keys=views[$('#stats-view').value]||views.overview,week=manifest.weeks.find(w=>w.week===loadedWeek);
 const groups=new Map();for(const r of rows){if(!r.event_id)continue;const key=String(r.event_id);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r);}
 $('#td-games').innerHTML=[...groups.values()].filter(rs=>preferences().team==='all'||rs.some(r=>r.team_id===preferences().team)).sort((a,b)=>String(a[0].start).localeCompare(String(b[0].start))).map(rs=>{const g=rs[0],teams=new Set(rs.map(r=>r.team_id)),scorers=rs.filter(r=>!r.unavailable&&r.role_eligible!==false&&Number.isFinite(r.stats?.td_scored)&&r.stats.td_scored>0&&Date.parse(r.captured_at)<Date.parse(r.start)).sort((a,b)=>b.stats.td_scored-a.stats.td_scored),total=scorers.reduce((s,r)=>s+r.stats.td_scored,0);return '<details><summary>'+esc(g.team_abbreviation+' vs '+g.opponent)+' · '+esc(when(g.start))+'</summary>'+(scorers.length?'<table><thead><tr><th>Player</th><th>Anytime TD</th><th>First TD share*</th><th>TD sample</th></tr></thead><tbody>'+scorers.map(r=>'<tr><td>'+esc(r.player+' · '+r.team_abbreviation)+'</td><td>'+((1-Math.exp(-r.stats.td_scored))*100).toFixed(1)+'%</td><td>'+(teams.size===2&&new Set(scorers.map(s=>s.team_id)).size===2?(100*r.stats.td_scored/total).toFixed(1)+'%':'—')+'</td><td>'+esc(r.stat_samples?.td_scored??'—')+'</td></tr>').join('')+'</tbody></table>':'No supported pregame TD rates.')+'</details>';}).join('')||'No matchups with roster records for this selection.';
 $('#week-summary').textContent=`${manifest.season} · W${loadedWeek}`;$('#player-summary').textContent=filtered.length.toLocaleString();$('#projection-summary').textContent=filtered.filter(r=>Object.keys(r.stats||{}).length).length.toLocaleString();
 $('#stats-direction').textContent=direction==='asc'?'↑ Ascending':'↓ Descending';
 $('#stats-context').textContent=(week?.phase==='early'?'Early outlook using today’s roster and form. ':week?.phase==='past'?'Saved pregame projections only. ':'')+'Expected starters, regular contributors and injury replacement candidates only. Passing TD and TD scored are separate. — means unavailable or not applicable. Scroll the table for more stats.';
 $('#stats-caption').textContent=`${manifest.season} · Week ${loadedWeek} · ${$('#stats-view').selectedOptions[0].textContent} · estimates conditional on a continuing role`;
 const head=[['player','Player / position'],['team','Team'],['opponent','Opponent'],...keys.map(k=>[k,fields[k][0]]),['samples','Games (max)']];
 $('#stats-table thead').innerHTML='<tr>'+head.map(([key,label])=>`<th scope="col" aria-sort="${$('#stats-sort').value===key?(direction==='asc'?'ascending':'descending'):'none'}"><button type="button" data-sort="${key}" title="${esc(fields[key]?.[1]||label)}">${esc(label)}${$('#stats-sort').value===key?(direction==='asc'?' ↑':' ↓'):''}</button></th>`).join('')+'</tr>';
 $('#stats-table tbody').innerHTML=visible.map(r=>`<tr data-player-id="${esc(r.player_id)}"><td><span class="stats-pos">${esc(r.position)}</span><span class="player-name">${esc(r.player)}</span><span class="player-note">${esc(r.role||r.status)}${r.role?' · '+esc(r.status):''}${r.availability&&!['Active','Not reported'].includes(r.availability)?' · '+esc(r.availability):''}</span></td><td title="${esc(r.team)}">${esc(r.team_abbreviation||r.team)}</td><td>${r.opponent?`${r.venue==='Away'?'@ ':''}${esc(r.opponent)}`:`<span class="stats-bye">${esc(r.role||r.status)}${r.role?' · '+esc(r.status):''}</span>`}${r.time_tbd?'<small> · time TBD</small>':''}</td>${keys.map(k=>`<td class="${r.stats?.[k]==null?'stats-missing':''}" title="${esc(fields[k][1])}${r.stat_samples?.[k]!=null?' · '+r.stat_samples[k]+' sample games':''}">${formatStat(r.stats?.[k])}</td>`).join('')}<td title="Up to this many recent games per available statistic">${r.samples||'—'}</td></tr>`).join('')||`<tr><td class="stats-empty" colspan="${head.length}">${rows.length?'No players match these filters.':week?.phase==='past'?'No pregame forecast was saved for this week. History begins with this feature’s first capture; past predictions are not backfilled.':'Player data is unavailable for this week. Check roster and schedule coverage, then refresh.'}</td></tr>`;
 $('#stats-count').textContent=`Showing ${Math.min(limit,filtered.length).toLocaleString()} of ${filtered.length.toLocaleString()} matching players.`;$('#stats-more').hidden=filtered.length<=limit;$('#stats-export').disabled=!filtered.length;
 save();
}
async function json(url){const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(25000)});if(!r.ok)throw Error('Feed unavailable');return r.json();}
async function loadWeek(week,newManifest=manifest){
 const w=newManifest?.weeks.find(w=>w.week===Number(week));if(!w||!/^week-\d{2}\.json$/.test(w.file))throw Error('Invalid week');
 const data=await json(BASE+w.file+'?v='+encodeURIComponent(newManifest.generated_at));
 if(data.generated_at!==newManifest.generated_at||data.season!==newManifest.season||data.week!==w.week||!Array.isArray(data.rows))throw Error('Mixed publication versions');
 if(!data.rows.every(r=>r&&typeof r.id==='string'&&typeof r.player==='string'&&typeof r.team_id==='string'&&typeof r.position==='string'&&r.stats&&typeof r.stats==='object'&&!Array.isArray(r.stats)&&Object.values(r.stats).every(v=>typeof v==='number'&&Number.isFinite(v))&&Number.isFinite(r.samples)))throw Error('Invalid player rows');
 return data;
}
async function refresh(initial=false){
 if(busy)return;busy=true;lastChecked=Date.now();$('#stats-refresh').disabled=true;$('#stats-week').disabled=true;status('Checking the published weekly data…');
 try{
  const next=await json(BASE+'manifest.json?v='+Date.now());
  if(!Array.isArray(next.weeks)||!Array.isArray(next.teams)||!Array.isArray(next.roster_teams)||!next.generated_at)throw Error('Invalid manifest');
  if(!initial&&manifest&&next.generated_at===manifest.generated_at){stamp();return;}
  let prefs={};if(initial)try{prefs=JSON.parse(localStorage.getItem(KEY)||'{}');}catch{}
  const requested=initial?Number(new URLSearchParams(location.search).get('week')):loadedWeek;
  const explicit=next.weeks.some(w=>w.week===requested);
  const desired=initial?(explicit?requested:next.current_week):(followCurrent?next.current_week:explicit?requested:next.current_week);
  followCurrent=desired===next.current_week;
  const data=await loadWeek(desired,next);
  manifest=next;rows=data.rows;loadedWeek=data.week;asOf=next.generated_at;
  options($('#stats-week'),next.weeks.map(w=>[w.week,`Week ${w.week}${w.week===next.current_week?' · current':w.phase==='early'?' · early outlook':w.phase==='past'?' · history':''}`]),loadedWeek);
  options($('#stats-team'),[['all','Entire NFL · all teams'],...next.teams.map(t=>[t.id,t.name])],prefs.team);
  options($('#stats-position'),[['all','All positions'],...[...new Set(rows.map(r=>r.position))].sort().map(p=>[p,p])],prefs.position);
  if(initial){if(views[prefs.view])$('#stats-view').value=prefs.view;if(prefs.search)$('#stats-search').value=prefs.search;$('#stats-only').checked=!!prefs.projected;direction=prefs.direction==='desc'?'desc':'asc';if([...$('#stats-sort').options].some(o=>o.value===prefs.sort))$('#stats-sort').value=prefs.sort;}
  limit=100;table();stamp();
 }catch{status(manifest?`Could not refresh. Keeping Week ${loadedWeek} from ${when(asOf)}; check its age.`:'The weekly player feed is unavailable. Try Refresh data after the next publication.','error');}
 finally{busy=false;$('#stats-refresh').disabled=false;$('#stats-week').disabled=!manifest;}
}
async function changeWeek(){
 if(busy)return;const requested=Number($('#stats-week').value),previous=loadedWeek;busy=true;$('#stats-week').disabled=true;
 try{const data=await loadWeek(requested);rows=data.rows;loadedWeek=requested;followCurrent=requested===manifest.current_week;limit=100;options($('#stats-position'),[['all','All positions'],...[...new Set(rows.map(r=>r.position))].sort().map(p=>[p,p])]);table();stamp();}
 catch{$('#stats-week').value=String(previous);status(`Week ${requested} could not be loaded. Still showing Week ${previous} from ${when(asOf)}.`,'error');}
 finally{busy=false;$('#stats-week').disabled=false;}
}
for(const [key,label] of Object.entries(fields))$('#stats-sort').add(new Option(label[1],key));
$('#stats-week').addEventListener('change',changeWeek);
for(const id of ['stats-team','stats-position','stats-view','stats-sort','stats-only'])$('#'+id).addEventListener('change',()=>{limit=100;table();});
$('#stats-search').addEventListener('input',()=>{limit=100;table();});
$('#stats-direction').addEventListener('click',()=>{direction=direction==='asc'?'desc':'asc';table();});
$('#stats-table thead').addEventListener('click',ev=>{const button=ev.target.closest('[data-sort]');if(!button)return;const key=button.dataset.sort;direction=$('#stats-sort').value===key?(direction==='asc'?'desc':'asc'):(key in fields?'desc':'asc');$('#stats-sort').value=key;limit=100;table();});
$('#stats-more').addEventListener('click',()=>{limit+=100;table();});$('#stats-refresh').addEventListener('click',()=>refresh());
$('#stats-export').addEventListener('click',()=>{const blob=new Blob([exportCSV(selectRows(rows,preferences()))],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`NFL-${manifest.season}-Week-${loadedWeek}-player-projections.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
function activate(){if(Date.now()-lastChecked>30000)refresh();else stamp();}
window.addEventListener('online',activate);document.addEventListener('visibilitychange',()=>{if(!document.hidden)activate();});
window.addEventListener('message',e=>{if(e.origin===location.origin&&e.data?.type==='kevbotbets:activate')activate();});
setInterval(()=>{if(!document.hidden)refresh();},300000);
refresh(true);
