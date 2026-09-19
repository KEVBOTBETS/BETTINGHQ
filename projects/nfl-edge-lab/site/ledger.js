/* My Ledger — NFL wagers the user explicitly confirms, stored in this browser. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.NFLEdgeLedger = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const STORAGE_KEY = "nfledge.ledger.v2", SCHEMA = 2;
  const decimal = american => { const a=Number(american);if(!isFinite(a)||a===0)return 1;return 1+(a>0?a/100:100/Math.abs(a)); };
  const keyOf = row => `${row.game_id}|${row.market}|${row.side}`;

  function entryFrom(row, stakeOverride) {
    const stake=stakeOverride==null?Number(row.stake||0):Number(stakeOverride);
    return {id:keyOf(row),candidate_id:`${row.game_id}:${row.market}:${row.side}`,
      game_id:row.game_id,game_date:row.game_date,week:row.week,season_type:row.season_type,
      matchup:row.matchup,market:row.market,side:row.side,pick:row.pick,
      line:row.line==null?null:Number(row.line),price:Number(row.price),book:row.book||null,
      model_prob:Number(row.model_prob),market_fair_prob:row.market_fair_prob==null?null:Number(row.market_fair_prob),
      breakeven:Number(row.breakeven),edge:Number(row.edge),edge_raw:Number(row.edge_raw),
      tier:row.tier,confidence:row.confidence,stake:Math.round(Math.max(0,stake)*100)/100,
      added_at:new Date().toISOString(),result:null,pnl:null,final_score:null};
  }

  function settle(entry,game){
    if(!game||!game.completed||game.away_score==null||game.home_score==null)return null;
    const away=Number(game.away_score),home=Number(game.home_score),margin=home-away,total=home+away;
    let result=null;
    if(entry.market==="ML")result=margin===0?"Push":((entry.side==="home")===(margin>0)?"Win":"Loss");
    else if(entry.market==="ATS"){
      if(entry.line==null)return {result:"Void",pnl:0,final_score:`${game.away} ${away} - ${game.home} ${home}`};
      const adjusted=margin+Number(entry.line);result=Math.abs(adjusted)<1e-9?"Push":((entry.side==="home")===(adjusted>0)?"Win":"Loss");
    }else if(entry.market==="TOTAL"){
      if(entry.line==null)return {result:"Void",pnl:0,final_score:`${game.away} ${away} - ${game.home} ${home}`};
      result=Math.abs(total-Number(entry.line))<1e-9?"Push":((entry.side==="over")===(total>Number(entry.line))?"Win":"Loss");
    }
    if(!result)return null;const stake=Number(entry.stake||0);
    const pnl=result==="Win"?stake*(decimal(entry.price)-1):result==="Loss"?-stake:0;
    return {result,pnl:Math.round(pnl*100)/100,final_score:`${game.away} ${away} - ${game.home} ${home}`,settled_at:new Date().toISOString()};
  }

  function settleAll(entries,games){const map=new Map((games||[]).map(g=>[String(g.game_id),g]));let changed=0;const rows=entries.map(e=>{if(e.result)return e;const s=settle(e,map.get(String(e.game_id)));if(!s)return e;changed++;return Object.assign({},e,s);});return {entries:rows,changed};}
  function summarise(entries,starting){const settled=entries.filter(e=>e.result),pnl=settled.reduce((s,e)=>s+Number(e.pnl||0),0),staked=settled.filter(e=>e.result!=="Push"&&e.result!=="Void").reduce((s,e)=>s+Number(e.stake||0),0);const wins=settled.filter(e=>e.result==="Win").length,losses=settled.filter(e=>e.result==="Loss").length,pushes=settled.filter(e=>e.result==="Push").length;let running=Number(starting||0);const curve=settled.slice().sort((a,b)=>String(a.settled_at||a.game_date).localeCompare(String(b.settled_at||b.game_date))).map(e=>{running+=Number(e.pnl||0);return {date:String(e.game_date||"").slice(0,10),bankroll:Math.round(running*100)/100};});return {starting_bankroll:Number(starting||0),current_bankroll:Math.round((Number(starting||0)+pnl)*100)/100,total_bets:entries.length,settled:settled.length,pending:entries.filter(e=>!e.result).length,wins,losses,pushes,win_rate:wins+losses?wins/(wins+losses):null,staked:Math.round(staked*100)/100,pnl:Math.round(pnl*100)/100,roi:staked?pnl/staked:null,at_risk:Math.round(entries.filter(e=>!e.result).reduce((s,e)=>s+Number(e.stake||0),0)*100)/100,curve};}
  function load(){try{const p=JSON.parse(localStorage.getItem(STORAGE_KEY)||"null"),rows=Array.isArray(p)?p:(p&&p.entries)||[];return rows.filter(r=>r&&r.game_id&&r.market&&r.side);}catch(_){return [];}}
  function save(entries){try{localStorage.setItem(STORAGE_KEY,JSON.stringify({schema:SCHEMA,saved_at:new Date().toISOString(),entries}));return true;}catch(_){return false;}}
  function merge(existing,incoming){const map=new Map(existing.map(e=>[keyOf(e),e]));let added=0;(incoming||[]).forEach(e=>{if(!e||!e.game_id||!e.market||!e.side)return;const k=keyOf(e);if(!map.has(k)){map.set(k,e);added++;}});return {entries:[...map.values()],added};}
  const CSV_COLS=["game_date","matchup","market","side","pick","line","price","book","stake","tier","edge","model_prob","result","pnl","final_score","added_at"];
  function toCSV(entries){const q=v=>{const s=v==null?"":String(v);return /[",\n]/.test(s)?`"${s.replace(/"/g,'""')}"`:s;};return [CSV_COLS.join(",")].concat(entries.map(e=>CSV_COLS.map(k=>q(e[k])).join(","))).join("\n");}
  return {STORAGE_KEY,SCHEMA,decimal,keyOf,entryFrom,settle,settleAll,summarise,load,save,merge,toCSV,CSV_COLS};
});
