/* Public model history and private actual tickets share a viewer, never a record. */
(() => {
 'use strict';
 const A=window.PropsApp,C=window.PropsParlays,$=s=>document.querySelector(s),e=A.esc;
 let archive=null,results=null,loading=false,busy=false,failed=false,storageFailed=false,limit=50,shown=[],audit=null;
 const when=v=>Number.isFinite(Date.parse(v))?new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',dateStyle:'medium',timeStyle:'short'}).format(new Date(v))+' ET':'Not recorded';
 const date=v=>Number.isFinite(Date.parse(v))?window.PropsQuotes.day(v):'';
 function privateRows(){return A.state.ledger.filter(r=>r.kind==='parlay').map(r=>({...r,
   result:r.result==='Pending'&&r.parlay_status==='Review'?'Review':r.result,
   captured_at:r.added_at,start_time:r.parlay_snapshot?.start_time,
   leg_count:r.parlay_snapshot?.legs?.length||r.legs?.length||0,
   legs:r.parlay_evidence?.legs||r.parlay_snapshot?.legs||(r.legs||[]).map(pick=>({pick,result:'Pending'})),
   legacy:!r.parlay_snapshot}));}
 function render(){
   const actual=$('#parlay-history-source').value==='actual';
   const auditBox=$('#parlay-audit');auditBox.hidden=actual||!audit;
   if(!auditBox.hidden)auditBox.innerHTML=`<h3>Why the headline record needs context</h3><p>${audit.wins}–${audit.losses} decided research tickets share ${audit.distinct_events} distinct games and ${audit.unique_legs} unique legs. ${audit.same_game_tickets} are same-game combinations; ${audit.estimated_tickets} include estimated prices.</p><p>${e(audit.note)}</p><p>Core now uses 2–3 fresh qualified legs at one book across distinct games, with limits on repeated exposure. Longshot remains available. These construction changes have not yet established improved win rates.</p><details><summary>Repeated legs and ticket exposures</summary><ul>${(audit.repeated_legs||[]).map(l=>`<li>${e(l.pick)} · ${e(l.result)} · shared by ${l.tickets} decided tickets</li>`).join('')}</ul></details>`;
   const all=actual?privateRows():(archive?.records||[]),status=$('#parlay-history-result').value,day=$('#parlay-history-date').value,search=$('#parlay-history-search').value.trim().toLowerCase();
   shown=all.filter(r=>(status==='all'||r.result===status)&&(!day||date(r.start_time)===day)&&(!search||JSON.stringify(r).toLowerCase().includes(search))).sort((a,b)=>Date.parse(b.captured_at)-Date.parse(a.captured_at));
   const count=s=>shown.filter(r=>r.result===s).length,w=count('Win'),l=count('Loss');
   $('#parlay-history-kpis').innerHTML=[[shown.length,'Tickets'],[w+'–'+l,'Full ticket record'],[count('Pending'),'Pending'],[count('Review'),'Book review'],[count('Void')+count('Push'),'Void / push'],[w+l?Math.round(100*w/(w+l))+'%':'—','Win rate · decided tickets']].map(([v,label])=>`<div class="kpi"><b>${e(v)}</b><span>${e(label)}</span></div>`).join('');
   $('#parlay-history-status').textContent=(actual?'Your actual wagers only. ':'Published research tickets only; not wager profit. ')+(failed?'The latest history refresh failed; any retained results are labelled historical. ':loading?'Refreshing… ':'')+`${shown.length} matching tickets. `+(actual?'Use My ledger to confirm book-specific settlements.':archive?'Updated '+when(archive.generated_at):'Public archive has not been published yet.');
   $('#parlay-history-list').innerHTML=shown.slice(0,limit).map(r=>{
     const tone=r.result==='Win'?'won':r.result==='Loss'?'lost':'muted';
     const profit=r.result==='Win'?r.stake*(r.price_american>0?r.price_american/100:100/Math.abs(r.price_american)):r.result==='Loss'?-r.stake:0;
     return `<details class="history-ticket" data-history-id="${e(r.id)}"><summary><span><b>${e(r.title||r.leg_count+'-leg '+(r.scope==='game'?'same-game':r.scope||'model')+' parlay')}</b><small>${e(when(r.start_time||r.captured_at))} · ${e(r.label||r.matchup||'Saved ticket')}</small></span><strong class="${tone}">${e(r.result==='Review'?'BOOK REVIEW':r.result.toUpperCase())}</strong></summary><div class="history-ticket-body"><p>Saved ${e(when(r.captured_at))} · ${e(r.id)}</p><p>${actual?`Actual book: ${e(r.book)} · Combined price ${A.odds(r.price_american)} · Stake ${A.money(r.stake)} · P/L ${A.money(profit)}`:`Frozen illustrative price ${A.odds(r.price_american)} · Research only; no actual stake or profit.`}</p>${actual&&r.legacy?'<p class="banner">Legacy text-only ticket: structured selections were not saved. Keep its result manually in My ledger.</p>':''}${r.result==='Review'?'<p class="banner">Push, void or conflicting leg results. Confirm the full-ticket decision and adjusted payout with your sportsbook.</p>':''}<ol class="history-leg-list">${r.legs.map(leg=>`<li><div><b>${e(leg.pick||leg.player+' '+leg.side+' '+(leg.line??'')+' '+leg.market)}</b><small>${e(leg.matchup||'')} · ${e(when(leg.start_time))}</small><small>Final statistic: ${e(leg.actual==null?'Awaiting verified result':leg.actual)}${leg.graded_at?' · checked '+e(when(leg.graded_at)):''}</small></div><strong class="${leg.result==='Win'?'won':leg.result==='Loss'?'lost':'muted'}">${e(leg.result||'Pending')}</strong></li>`).join('')}</ol>${r.note?'<p>Note: '+e(r.note)+'</p>':''}</div></details>`;
   }).join('')||'<div class="empty">No tickets match this view. Published tickets start accumulating with the new archive. To track an actual wager, use “Log actual bet” in Parlay lab.</div>';
   if(storageFailed)$('#parlay-history-status').textContent+=' Browser storage failed: settlement was not saved. Export a backup and retry.';
   $('#parlay-history-more').hidden=shown.length<=limit;$('#parlay-history-export').disabled=!shown.length;
 }
 function reconcile(){
   if(busy||!results)return;
   const update=C.settleEntries(A.state.ledger,results);
   if(update.changed){busy=true;try{A.writeStore(A.LEDGER_KEY,update.entries);A.state.ledger=update.entries;storageFailed=false;window.BetSync?.touch();A.renderLedger();}catch(_){storageFailed=true;}finally{busy=false;}}
 }
 async function refresh(){
   if(loading)return;loading=true;render();
   const get=file=>fetch('data/'+file+'?v='+Date.now(),{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Unavailable');return r.json();});
   const fetched=await Promise.allSettled([get('parlay-history.json'),get('parlay-results.json'),get('parlay-audit.json')]);
   failed=fetched.slice(0,2).some(r=>r.status==='rejected');
   if(fetched[2].status==='fulfilled')audit=fetched[2].value;
   if(fetched[0].status==='fulfilled'&&fetched[0].value.schema===1&&Array.isArray(fetched[0].value.records)){archive=fetched[0].value;audit=archive.audit||audit;}else failed=true;
   if(fetched[1].status==='fulfilled'&&fetched[1].value.schema===1&&Array.isArray(fetched[1].value.records)){results=fetched[1].value.records;reconcile();}else{results=null;failed=true;}
   loading=false;render();
 }
 for(const id of ['source','result','date','search'])$('#parlay-history-'+id).addEventListener(id==='search'?'input':'change',()=>{limit=50;render();});
 $('#parlay-history-more').addEventListener('click',()=>{limit+=50;render();});
 $('#parlay-history-export').addEventListener('click',()=>{const actual=$('#parlay-history-source').value==='actual',url=URL.createObjectURL(new Blob([JSON.stringify({schema:1,type:actual?'actual-wagers':'model-research',exported_at:new Date().toISOString(),records:shown},null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='kevbot-parlays-'+(actual?'my-wagers':'model-history')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
 window.addEventListener('props:tab',event=>{if(event.detail==='parlay-history')render();});
 window.addEventListener('props:ledger',()=>{reconcile();render();});
 window.addEventListener('props:data',refresh);
 refresh();
})();
