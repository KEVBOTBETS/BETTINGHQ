(() => {
'use strict';
const $=s=>document.querySelector(s),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=(v,d=3)=>v==null?'—':Number(v).toFixed(d),pct=v=>v==null?'—':n(v*100,1)+'%',interval=v=>v?v.map(pct).join(' – '):'—';
const time=v=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(v));
let data,selected=[];
function chart(buckets){
 const x=p=>50+p*360,y=p=>295-p*260;
 return '<svg viewBox="0 0 450 345" role="img" aria-label="Calibration plot: predicted home win probability on horizontal axis and observed home wins on vertical axis">'+[0,.25,.5,.75,1].map(p=>`<path class="chart-grid" d="M50 ${y(p)}H410 M${x(p)} 35V295"/><text x="42" y="${y(p)+4}" text-anchor="end">${p*100}%</text><text x="${x(p)}" y="316" text-anchor="middle">${p*100}%</text>`).join('')+'<path class="chart-ideal" d="M50 295L410 35"/>'+buckets.filter(b=>b.n).map(b=>`<g><title>${b.bucket}: ${b.n} games; forecast ${pct(b.predicted)}; actual ${pct(b.actual)}; interval ${interval(b.interval)}</title><path class="chart-whisker" d="M${x(b.predicted)} ${y(b.interval[0])}V${y(b.interval[1])} M${x(b.predicted)-5} ${y(b.interval[0])}h10 M${x(b.predicted)-5} ${y(b.interval[1])}h10"/><circle class="chart-dot" cx="${x(b.predicted)}" cy="${y(b.actual)}" r="${Math.min(10,4+Math.sqrt(b.n)/2)}"/></g>`).join('')+'<text x="230" y="340" text-anchor="middle">PREDICTED HOME WIN PROBABILITY</text></svg>';
}
function render(){
 const sport=$('#perf-sport').value,days=$('#perf-window').value,version=$('#perf-version').value,league=data.leagues[sport];
 const cutoff=days==='all'?0:Date.now()-Number(days)*86400000;
 selected=data.records.filter(r=>r.sport===sport&&Date.parse(r.start)>=cutoff&&(version==='all'||r.version===version)).sort((a,b)=>Date.parse(b.start)-Date.parse(a.start));
 const s=KevPerformance.summarize(selected);
 document.documentElement.dataset.kbLeague=sport;
 $('#perf-status').textContent=`${league.label} · ${league.season} · ${league.snapshot_policy} snapshot · ${s.n} verified games in view · Source ${league.source_updated?time(league.source_updated)+" ET":"time unavailable"} · Audit built ${time(data.generated_at)} ET`;
 $('#perf-kpis').innerHTML=[['Winner calls',pct(s.accuracy),`${s.correct} / ${s.picks} · 95% interval ${interval(s.interval)}`],['Brier score',n(s.brier),'Lower is better · probability error'],['Log loss',n(s.logloss),'Lower is better · clipped at 0.000001'],['Market pairs',String(s.paired.n),'Same games with a frozen market probability']].map(([label,value,note])=>`<div class="broadcast-stat"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`).join('');
 $('#perf-chart').innerHTML=chart(s.calibration);
 $('#perf-buckets').innerHTML=s.calibration.map(b=>`<tr><th>${b.bucket}</th><td>${b.n}</td><td>${pct(b.predicted)}</td><td>${pct(b.actual)}</td><td>${interval(b.interval)}</td></tr>`).join('');
 const comparison=(label,v)=>`<div class="comparison"><div><b>${label}</b><small>${v.n} paired games · lower is better</small></div><div class="comparison-values"><span>Model <strong>${n(v.model)}</strong></span><span>Market <strong>${n(v.market)}</strong></span></div></div>`;
 $('#perf-market').innerHTML=(s.paired.n?`<div class="market-verdict"><span>PAIRED BRIER SKILL</span><strong>${pct(s.paired.skill)}</strong><p>${s.paired.skill>0?'Lower probability error than market in this sample.':s.paired.skill<0?'Market has lower probability error in this sample.':'Equal probability error in this sample.'}</p></div>`:'<div class="market-verdict"><span>PROBABILITY BENCHMARK</span><strong>Building.</strong><p>No eligible market pairs in this view. Missing historical prices are never reconstructed.</p></div>')+comparison('Winner probability / Brier',{n:s.paired.n,model:s.paired.model.brier,market:s.paired.market.brier})+comparison('Margin error / points',s.margin)+comparison('Total error / points',s.total);
 $('#perf-board').href='./#'+sport;
 $('#perf-records').innerHTML=selected.slice(0,25).map(r=>`<tr><td><b>${esc(r.matchup)}</b><small>${time(r.start)}</small></td><td>${time(r.captured_at)}</td><td>${pct(r.p)}</td><td>${pct(r.market)}</td><td>${r.away_score}–${r.home_score}</td><td><span class="result-chip ${(r.p>.5)===(r.y===1)?'hit':'miss'}">${r.p===.5?'No call':(r.p>.5)===(r.y===1)?'Correct':'Miss'}</span></td></tr>`).join('')||'<tr><td colspan="6">No verified games in this selection yet.</td></tr>';
 $('#perf-excluded').innerHTML=Object.entries(league.excluded).map(([reason,count])=>`<div><strong>${count}</strong><span>${esc(reason)}</span></div>`).join('')||'<p>No exclusions in the current season source.</p>';
 $('#perf-export').disabled=!selected.length;$('#perf-content').hidden=false;
}
function versions(){const sport=$('#perf-sport').value;$('#perf-version').innerHTML='<option value="all">All versions</option>'+[...new Set(data.records.filter(r=>r.sport===sport).map(r=>r.version))].sort().reverse().map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');render();}
$('#perf-sport').addEventListener('change',versions);for(const id of ['perf-window','perf-version'])$('#'+id).addEventListener('change',()=>data&&render());
$('#perf-export').addEventListener('click',()=>{const keys=['sport','id','season','version','matchup','start','captured_at','p','market','y','away_score','home_score'];const cell=v=>'"'+String(v??'').replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';const csv=[keys,...selected.map(r=>keys.map(k=>r[k]))].map(row=>row.map(cell).join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv'})),a=document.createElement('a');a.href=url;a.download='kevbot-'+$('#perf-sport').value+'-forecast-audit.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
fetch('data/performance.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(d=>{if(d.schema!==1||!Array.isArray(d.records))throw Error();data=d;versions();}).catch(()=>{$('#perf-status').textContent='Forecast audit unavailable. Reload to try again; no performance figures are inferred.';});
})();
