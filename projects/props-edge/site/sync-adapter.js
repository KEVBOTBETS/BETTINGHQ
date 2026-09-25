/* Only confirmed actual bets enter the shared ledger. Forecasts never do. */
(function(root,factory){
  const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;
  if(!root?.PropsApp||!root.BetSync)return;
  const A=root.PropsApp,BS=root.BetSync;
  BS.register({app:'props',sport:'NFL',storageKey:A.LEDGER_KEY,
    readLocal:()=>A.state.ledger.filter(e=>e.confirmed_actual).map(api.toCanonical),
    writeLocal:rows=>A.replaceLedger(rows.map(api.fromCanonical)),
    applyBankroll:bank=>A.applySharedBank(bank)});
  document.querySelector('#review-ledger').onclick=()=>{
    const rows=A.state.ledger.filter(e=>!e.confirmed_actual);
    if(!rows.length)return;
    if(!rows.every(e=>Number.isFinite(Number(e.stake))&&Number(e.stake)>0&&Math.abs(Number(e.price_american))>=100)){
      alert('Correct missing or invalid stakes and actual odds before sharing. Export CSV keeps your original entries.');return;
    }
    const description=rows.map(e=>`${e.title} | ${e.price_american} | $${e.stake} | ${e.result}`).join('\n');
    if(!confirm(`Review ${rows.length} existing entries:\n\n${description}\n\nConfirm these were real bets at these actual prices and stakes. This connects them to the shared ledger.`))return;
    const backup='kevbot-props-ledger-v2-before-shared';
    if(!localStorage.getItem(backup))A.writeStore(backup,A.state.ledger);
    const next=A.state.ledger.map(e=>({...e,confirmed_actual:true,ledger_schema:'props-v3'}));
    A.writeStore(A.LEDGER_KEY,next);A.state.ledger=next;BS.touch();A.renderLedger();
  };
  BS.start();
})(typeof window!=='undefined'?window:null,function(){
  function toCanonical(e){return {id:e.canonical_id||'props:'+e.id,app:'props',sport:'NFL',placed_at:e.added_at,event_date:e.event_date||'',event:e.matchup||e.title,market:e.kind==='parlay'?'PARLAY':e.market||'PROP',selection:e.title,side:e.side||'',line:e.line??null,price:e.price_american,book:e.book||'',stake:e.stake,tier:e.tier||'',edge:e.edge??null,model_prob:e.model_prob??null,status:e.result||'Pending',notes:e.note||'',native:{...e,ledger_schema:'props-v3'}};}
  function fromCanonical(r){
    const original=r.native?JSON.parse(JSON.stringify(r.native)):{};
    return {...original,canonical_id:r.id,id:original.id||r.id.replace(/^props:/,''),title:r.selection||original.title||original.pick,added_at:r.placed_at||original.added_at,kind:original.kind||(r.market==='PARLAY'?'parlay':'single'),price_american:r.price,book:r.book,stake:r.stake,result:r.status||'Pending',note:r.notes||'',model_prob:r.model_prob,confirmed_actual:true,ledger_schema:'props-v3'};
  }
  return {toCanonical,fromCanonical};
});
