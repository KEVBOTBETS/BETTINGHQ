(()=>{'use strict';
  const $=s=>document.querySelector(s),esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let data=null,busy=false,error='';
  function render(){
    const sport=$('#changes-sport').value,rows=(data?.events||[]).filter(e=>sport==='all'||e.sport===sport);
    $('#changes-status').textContent=error||(data?'Last checked '+new Date(data.checked_at).toLocaleString()+' · '+rows.length+' observations retained':'Loading change history…');
    $('#changes-list').innerHTML=rows.length?rows.slice(0,100).map(e=>'<article class="card"><span class="tag">'+esc(e.sport.toUpperCase())+'</span><h3>'+esc(e.pick)+'</h3><p>'+esc(e.event)+' · '+esc(e.day)+'</p>'+e.changes.map(c=>'<p>'+esc(c.field==='rank'?'Rank within this sport':c.field)+': '+esc(c.from)+' → <strong>'+esc(c.to)+'</strong></p>').join('')+'<p class="note">Observed '+esc(new Date(e.observed_at).toLocaleString())+'<br>Published '+esc(new Date(e.published_at).toLocaleString())+'</p></article>').join(''):'<div class="empty">No changes recorded yet for this filter. The first successful snapshot establishes a baseline; later published changes appear here.</div>';
  }
  async function refresh(){if(busy)return;busy=true;try{const response=await fetch('data/tickets/changes.json',{cache:'no-store',signal:AbortSignal.timeout(12000)});if(!response.ok)throw Error();const next=await response.json();if(!Array.isArray(next.events))throw Error();data=next;error='';}catch(_){error='Change history could not be refreshed. Existing observations may be out of date.';}finally{busy=false;render();}}
  $('#changes-sport').onchange=render;refresh();setInterval(()=>{if(!document.hidden)refresh();},300000);window.addEventListener('online',refresh);
})();
