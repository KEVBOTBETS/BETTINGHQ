/* Manual WNBA wagers share the existing sheet; model recommendations never add bets. */
(function(root,factory){
  const api=factory();
  if(typeof module==="object"&&module.exports)module.exports=api;
  if(!root?.BetSync||!root.WNBALedger)return;
  const BS=root.BetSync,L=root.WNBALedger;
  BS.register({app:"wnba-lab",sport:"WNBA",storageKey:L.STORAGE_KEY,
    readLocal:()=>L.load().map(api.toCanonical),
    writeLocal:rows=>{const next=rows.map(r=>api.fromCanonical(r,BS.impliedPnl(r)));if(JSON.stringify(L.load())!==JSON.stringify(next)){L.save(next);root.wnbaSharedLedger?.reload();}},
    applyBankroll:bank=>root.wnbaSharedLedger?.bank(bank)
  });
  BS.start();
})(typeof window!=="undefined"?window:null,function(){
  function toCanonical(e){return {id:"wnba-lab:"+e.game_id+"|"+e.market+"|"+e.side,app:"wnba-lab",sport:"WNBA",
    placed_at:e.added_at,event_date:e.date,event:e.matchup,market:e.market,selection:e.pick,side:e.side,line:e.line,
    price:e.price,book:e.book,stake:e.stake,tier:e.tier,edge:e.edge,model_prob:e.model_prob,status:e.result||"Pending",
    pnl:e.profit,closing_price:e.closing_price??null,score:e.final_score,notes:e.notes||"",native:e};}
  function fromCanonical(r,derivedPnl){
    const e=r.native?JSON.parse(JSON.stringify(r.native)):{id:r.id.slice(9),game_id:r.id.slice(9).split("|")[0],date:r.event_date,matchup:r.event,market:r.market,side:r.side,pick:r.selection,line:r.line,price:r.price,book:r.book,tier:r.tier,added_at:r.placed_at,model_prob:r.model_prob,edge:r.edge};
    e.stake=r.stake;e.result=r.status==="Pending"?null:r.status;e.profit=e.result?(r.pnl??derivedPnl??null):null;
    if(e.profit!=null)e.profit=Math.round(e.profit*100)/100;
    e.closing_price=r.closing_price??null;e.final_score=r.score||e.final_score||null;e.notes=r.notes||"";return e;
  }
  return {toCanonical,fromCanonical};
});
