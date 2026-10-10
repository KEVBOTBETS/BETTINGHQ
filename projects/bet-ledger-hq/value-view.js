/* Compact details inside existing cards/tables; no new navigation or desk. */
(() => {
  const V=window.BetValue;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const odds=v=>v===null?'unavailable':(v>0?'+':'')+v;
  window.betValueDetails=(row,sport)=>{
    const v=V.evaluate(row,{sport});
    return `<small class="bet-value-details">Minimum acceptable odds: <b>${esc(odds(v.worst))}</b> at this exact line${row.line==null?'':' '+esc(row.line)}. Stress return: ${v.stressEV===null?'unavailable':(100*v.stressEV).toFixed(1)+'%'}. ${v.passes?'Price stress test passed; source qualification still applies.':'PASS · '+esc(v.reasons.join('; '))}<br>3 percentage-point probability stress test + 2% return buffer; policy settings, not a confidence interval.</small>`;
  };
})();
