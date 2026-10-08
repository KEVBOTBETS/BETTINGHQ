/* Small published diagnosis; refresh never substitutes empty data for a failed load. */
(() => {
  const target=document.getElementById('board-diagnosis');
  if(!target)return;
  let loading=null;
  function refresh(){
    if(loading)return loading;
    loading=fetch('../bet-ledger-hq/data/research/diagnostics.json?v='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(20000)})
      .then(r=>{if(!r.ok)throw Error('Unavailable');return r.json();})
      .then(r=>{
        const board=r.boards?.find(b=>b.sport===target.dataset.board);
        if(!board||!Array.isArray(board.reasons))throw Error('Invalid diagnosis');
        const age=(Date.now()-Date.parse(r.generated_at))/3600000;
        const heading=document.createElement('strong');heading.textContent='Board diagnosis: ';
        const detail=document.createElement('span');detail.textContent=`${board.scheduled_games} scheduled games · ${board.market_rows} market rows · ${board.qualified} qualified at capture. `+board.reasons.map(x=>`${x.count} ${x.reason}`).join(' · ');
        const link=document.createElement('a');link.href='../bet-ledger-hq/model-lab.html?tab=health';link.textContent=' Review feed diagnosis ↗';link.style.color='inherit';
        const time=document.createElement('small');time.style.display='block';time.textContent=`Diagnosis captured ${r.generated_at}${!Number.isFinite(age)||age<0||age>6?' · stale or uncertain diagnosis; refresh checks published files':''}. Collection runs separately.`;
        target.replaceChildren(heading,detail,link,time);target.hidden=false;
      }).catch(()=>{if(target.hidden){target.textContent='Feed diagnosis unavailable. Check the forecast and individual quote timestamps.';target.hidden=false;}})
      .finally(()=>{loading=null;});
    return loading;
  }
  document.getElementById('refresh-nfl')?.addEventListener('click',refresh);
  document.getElementById('refresh-props')?.addEventListener('click',refresh);
  window.addEventListener('online',refresh);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  setInterval(()=>{if(!document.hidden)refresh();},300000);
  refresh();
})();
