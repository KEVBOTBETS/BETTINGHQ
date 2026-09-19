/* Read-only adapters for the existing boards. No odds, stakes or bets are invented. */
(function(root,factory){
  const api=factory();
  if(typeof module==="object"&&module.exports)module.exports=api;
  if(root)root.KevToday=api;
})(typeof self!=="undefined"?self:this,function(){
  "use strict";
  const HOUR=3600000;
  const LABELS={wnba:"WNBA",mlb:"MLB",nfl:"NFL",ncaaf:"NCAAF",props:"Props",ladder:"Ladder"};
  const APP={wnba:"wnba-lab",mlb:"mlb-edge",nfl:"nfl-lab",ncaaf:"ncaaf-lab",props:"props",ladder:"ladder"};
  function number(v){return v==null||v===""||!Number.isFinite(Number(v))?null:Number(v);}
  function instant(v){if(!v)return null;const n=Date.parse(v);return Number.isFinite(n)?n:null;}
  function day(v){if(typeof v==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(v))return v;const n=typeof v==="number"?v:instant(v);if(n==null)return "";return new Intl.DateTimeFormat("en-CA",{timeZone:"America/Toronto",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(n));}
  function american(v){const n=number(v);return n!=null&&Math.abs(n)>=100?n:null;}
  function tier(v){const s=String(v||"").toUpperCase();return s==="BEST"?"BEST BET":s;}
  function freshness(stamp,limitHours,now=Date.now()){
    const t=instant(stamp);
    if(t==null)return {status:"unknown",hours:null};
    const hours=(now-t)/HOUR;
    if(hours<-.0833)return {status:"unknown",hours:null};
    return {status:hours>limitHours?"stale":"recent",hours:Math.max(0,hours)};
  }
  function health(key,bundle,now=Date.now()){
    const meta=bundle.meta||bundle.slate||{};
    const stamp=meta.generated_at||meta.generated||bundle.accuracy?.generated_at;
    const limit=key==="props"?6:key==="ncaaf"?4:6;
    const age=freshness(stamp,limit,now),warnings=[];
    if(bundle.error)warnings.push("Latest fetch failed; retained data is for reference only. No current recommendations from this board.");
    if(age.status!=="recent")warnings.push(age.status==="stale"?"Published data is stale.":"Published data time is unavailable.");
    if(key==="props"){
      const source=meta.source_by_sport?.NFL||{};
      const errors=source.errors||[];
      if(errors.some(e=>/quota|credits|out_of_usage/i.test(String(e))))warnings.push("An odds provider has exhausted its quota.");
      else if(errors.length)warnings.push("One or more source requests failed.");
      if((meta.source_by_provider?.the_odds_api?.eligible_priced_quotes||0)===0&&(meta.source_by_provider?.odds_api_io?.eligible_priced_quotes||0)>0)warnings.push("Using the configured fallback odds provider.");
      if(!(meta.counts?.eligible_priced_quotes>0))warnings.push("No verified prop prices; projections are not wagers.");
    }
    if(key==="wnba"&&meta.odds_health?.status==="partial")warnings.push("Some games have no usable prices; those games cannot qualify.");
    if(key==="ncaaf"){
      if(meta.context_health?.availability?.status!=="available")warnings.push("Availability reports missing or incomplete; verify team news.");
      if(meta.quote_coverage?.games_multiple_books===0)warnings.push("No multi-book comparison in this refresh.");
    }
    if(meta.odds_health?.healthy===false||["failed","unavailable","error"].includes(meta.odds_health?.status))warnings.push("Odds coverage needs attention.");
    return {key,label:LABELS[key],stamp:stamp||null,age,status:bundle.error?"unavailable":age.status==="stale"?"stale":warnings.length?"review":"recent",warnings};
  }
  function plays(key,bundle,now=Date.now()){
    const rows=[],meta=bundle.meta||{},published=meta.generated_at||bundle.slate?.generated_at;
    function add(r,game){
      const t=tier(r.tier),start=r.start_time||r.tipoff||r.game_date||game?.start;
      if(!["BEST BET","GOOD","LEAN"].includes(t)||r.held||r.odds_verified===false)return;
      if(key==="mlb"&&!(number(r.stake)>0))return;
      if(["nfl","wnba"].includes(key)&&!(number(r.stake)>0))return;
      if(key==="props"&&!(number(r.recommended_stake)>0))return;
      if(["Final","Postponed","Cancelled","Canceled","Suspended","In Progress"].includes(game?.status))return;
      const when=instant(start),price=american(r.price_american??r.price);
      if(when==null||when<=now||price==null)return;
      const quote=r.odds_observed_at||r.odds_fetched_at||game?.odds?.fetched_at||r.updated_at;
      const age=freshness(quote,key==="props"?Math.min(6,number(meta.max_odds_age_hours)||6):key==="ncaaf"?3:6,now);
      const publishedAge=freshness(published,key==="ncaaf"?4:6,now);
      if((quote&&age.status==="unknown")||age.status==="stale"||publishedAge.status!=="recent"||bundle.error)return;
      const review=[];
      if(age.status==="unknown")review.push("Quote time not supplied; confirm the current price.");
      if(key==="mlb"&&!game?.lineups_confirmed)review.push("Projected batting orders; lineups not confirmed.");
      if(key==="ncaaf"&&r.context?.availability?.status!=="available")review.push("Availability reports not confirmed.");
      if(key==="props"&&!(number(r.current_season_samples)>0))review.push("No current-season player sample yet.");
      if(key==="props"&&r.roster_verified===false)return;
      const event=r.matchup||(game?String(game.away)+" @ "+String(game.home):"");
      const selection=String(r.selection||"").toLowerCase();
      const side=r.side||(game?(selection===String(game.home).toLowerCase()?"home":selection===String(game.away).toLowerCase()?"away":["over","under"].includes(selection)?selection:""):"");
      const rawLine=number(r.line),line=rawLine!=null&&["nfl","ncaaf","mlb"].includes(key)&&["ATS","RL"].includes(r.market)&&side==="away"?-rawLine:rawLine;
      rows.push({key,app:APP[key],sport:key==="props"?"NFL":LABELS[key],event,
        eventId:String(r.result_event_id||r.game_id||r.event_id||game?.gamePk||""),
        player:r.player||"",playerId:String(r.player_id||""),side,home:r.home||game?.home||"",away:r.away||game?.away||"",version:String(r.model_version||meta.model_version||meta.version||"unversioned"),start,when,day:day(start),pick:r.pick||r.label||r.selection||"",
        market:r.market||"",line,sourceLine:rawLine,price,book:r.book||"Unspecified book",
        tier:t,score:number(r.action_edge??r.edge_real??r.edge),quote:quote||null,
        review,probability:number(r.model_prob??r.p_final),source:LABELS[key]});
    }
    if(key==="mlb")(bundle.slate?.games||[]).forEach(g=>(g.bets||[]).forEach(r=>add(r,g)));
    else (Array.isArray(bundle.board)?bundle.board:[]).forEach(r=>add(r));
    const seen=new Set();
    return rows.filter(r=>{const id=[r.key,r.eventId,r.start,r.market,r.pick,r.line].join("|");if(seen.has(id))return false;seen.add(id);return true;});
  }
  function sortPlays(rows,mode="time"){
    const order={"BEST BET":0,GOOD:1,LEAN:2};
    return rows.slice().sort((a,b)=>mode==="tier"?(order[a.tier]-order[b.tier]||a.when-b.when||a.key.localeCompare(b.key)):a.when-b.when||order[a.tier]-order[b.tier]||a.key.localeCompare(b.key));
  }
  function topPlays(rows,limit=10){
    const order={"BEST BET":0,GOOD:1,LEAN:2};
    const bySource=new Map();
    for(const r of rows){if(!bySource.has(r.key))bySource.set(r.key,[]);bySource.get(r.key).push(r);}
    const queues=[...bySource.values()].map(group=>group.sort((a,b)=>(order[a.tier]??9)-(order[b.tier]??9)||
      (number(b.score)??-Infinity)-(number(a.score)??-Infinity)||a.when-b.when));
    const ranked=[];
    for(const t of ["BEST BET","GOOD","LEAN"]){
      let available=queues.map(q=>q.filter(r=>r.tier===t));
      while(available.some(q=>q.length)){
        const round=available.filter(q=>q.length).map(q=>q.shift()).sort((a,b)=>a.when-b.when||a.key.localeCompare(b.key));
        ranked.push(...round);
      }
    }
    return ranked.slice(0,Math.max(0,limit));
  }
  function rate(correct,n){return number(n)>0&&number(correct)!=null?correct/n:null;}
  function accuracy(key,bundle){
    const a=bundle.accuracy||{};
    if(key==="mlb"){
      const o=a.overall||{},m=a.vs_market||{};
      return {key,label:"MLB game predictions",scope:"Verified pregame forecasts · "+(a.scope?.season||bundle.meta?.settings?.season||"season not supplied"),
        n:o.n||0,wins:o.correct??null,winRate:o.accuracy??null,marketN:m.n||0,modelBrier:m.model_brier??null,marketBrier:m.market_brier??null,
        modelCorrect:m.model_correct??null,marketCorrect:m.market_correct??null,
        notes:["Model and market comparisons use the same matched games.","Game-winner accuracy is not betting ROI.",...(a.scope?.excluded_graded?[a.scope.excluded_graded+" legacy graded records excluded: no valid pregame snapshot."]:[])]};
    }
    if(key==="props")return {key,label:"NFL player projections",scope:[a.scope?.season,a.scope?.season_type_label].filter(Boolean).join(" "),
      markets:Object.entries(a.props||{}).map(([market,v])=>({market,n:v.graded||0,mae:v.mae??null,bias:v.bias??null})),notes:["Player-stat error is not a wager win rate.","Only frozen pregame projections are graded."]};
    if(key==="ladder")return {key,label:"Ladder screened options",scope:"Published screened-option history",
      n:a.overall?.settled||0,wins:a.overall?.wins??null,losses:a.overall?.losses??null,pushes:a.overall?.pushes??0,voids:a.overall?.voids??0,winRate:a.overall?.win_rate??null,roi:a.overall?.roi??null,
      notes:["Market-derived screening, not an independent prediction model.","One-unit hypothetical result; not your actual ladder return."]};
    const g=a.games||{};
    return {key,label:LABELS[key]+" game predictions",scope:[a.scope?.season,a.scope?.season_type_label].filter(Boolean).join(" "),
      n:g.winner?.n||0,wins:g.winner?.correct??null,winRate:g.winner?.accuracy??null,
      ats:g.ats||{},totals:g.totals||{},margin:g.margin_comparison||{},total:g.total_comparison||{},
      notes:["Only the current-season accuracy feed is used; legacy mixed-season exports are excluded.","Small samples do not establish a betting edge."]};
  }
  const NFL_TEAMS={"arizona cardinals":"ari","atlanta falcons":"atl","baltimore ravens":"bal","buffalo bills":"buf","carolina panthers":"car","chicago bears":"chi","cincinnati bengals":"cin","cleveland browns":"cle","dallas cowboys":"dal","denver broncos":"den","detroit lions":"det","green bay packers":"gb","houston texans":"hou","indianapolis colts":"ind","jacksonville jaguars":"jax","kansas city chiefs":"kc","las vegas raiders":"lv","los angeles chargers":"lac","los angeles rams":"lar","miami dolphins":"mia","minnesota vikings":"min","new england patriots":"ne","new orleans saints":"no","new york giants":"nyg","new york jets":"nyj","philadelphia eagles":"phi","pittsburgh steelers":"pit","san francisco 49ers":"sf","seattle seahawks":"sea","tampa bay buccaneers":"tb","tennessee titans":"ten","washington commanders":"wsh","was":"wsh","jac":"jax"};
  function league(row){return String(row.sport||({props:"NFL","nfl-lab":"NFL","ncaaf-lab":"NCAAF","mlb-edge":"MLB","wnba-lab":"WNBA"}[row.app])||"").toUpperCase();}
  function team(s,sport){const n=String(s||"").toLowerCase().replace(/[.]/g,"").replace(/\s+/g," ").trim();return sport==="NFL"?(NFL_TEAMS[n]||n):n;}
  function eventKey(row){
    const sport=league(row),event=String(row.event||row.matchup||"");
    const parts=event.split(/\s*(?:@|\bat\b|\bvs\.?\b)\s*/i).filter(Boolean);
    const d=day(row.event_date||row.game_date||row.start_time||row.start);
    if(parts.length!==2||!d||!sport)return null;
    return [sport,d,...parts.map(x=>team(x,sport)).sort()].join("|");
  }
  function exposure(rows){
    const groups=new Map(),bySport={},open=rows.filter(r=>!r.deleted&&r.status==="Pending"&&(number(r.stake)||0)>0);
    let unmatched=0,total=0;
    for(const r of open){
      const stake=number(r.stake)||0,sport=league(r)||"Other";total+=stake;bySport[sport]=(bySport[sport]||0)+stake;
      const key=eventKey(r);
      if(!key){unmatched++;continue;}
      if(!groups.has(key))groups.set(key,{key,event:r.event||r.matchup,sport,stake:0,rows:[],apps:new Set()});
      const g=groups.get(key);g.stake+=stake;g.rows.push(r);g.apps.add(r.app);
    }
    return {total,count:open.length,unmatched,bySport,groups:[...groups.values()].map(g=>({...g,apps:[...g.apps]})).sort((a,b)=>b.stake-a.stake)};
  }
  function drawdown(rows,starting){
    let equity=number(starting)||0,peak=equity,max=0;
    for(const r of rows.filter(r=>!r.deleted&&["Win","Loss","Push","Void"].includes(r.status)).slice().sort((a,b)=>String(a.updated_at||a.event_date||"").localeCompare(String(b.updated_at||b.event_date||"")))){
      const pnl=number(r.pnl);if(pnl==null)continue;equity+=pnl;peak=Math.max(peak,equity);max=Math.max(max,peak-equity);
    }
    return {max,current:peak-equity,note:"Reconstructed from settlement/update order; edits can change the historical curve."};
  }
  return {number,instant,day,american,tier,freshness,health,plays,sortPlays,topPlays,accuracy,eventKey,exposure,drawdown,LABELS};
});
