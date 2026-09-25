const L=window.WNBALedger;
const state={tab:"plays",tier:"PLAYS",date:null};
let board=[],games=[],summary={},meta={},index={},performance={},simulator={teams:{}},news=[],calibration={},results=[],myBets=[];
const $=s=>document.querySelector(s);
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pct=(v,d=1)=>v==null?"—":`${(Number(v)*100).toFixed(d)}%`;
const money=v=>v==null?"—":`C$${Number(v).toFixed(2)}`;
const price=v=>v==null?"—":Number(v)>0?`+${v}`:`${v}`;
const num=(v,d=1)=>v==null?"—":Number(v).toFixed(d);
const tierClass=t=>({"BEST BET":"best","GOOD":"good","LEAN":"lean","AVOID":"pass"}[String(t||"AVOID")]||"pass");
const dateLabel=value=>{try{return new Intl.DateTimeFormat("en-CA",{timeZone:"America/Toronto",weekday:"short",month:"short",day:"numeric"}).format(new Date(value+"T12:00:00Z"));}catch{return value;}};
function easternToday(){try{return new Intl.DateTimeFormat("en-CA",{timeZone:"America/Toronto",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());}catch{return new Date().toISOString().slice(0,10);}}

function selectedGames(){return games.filter(g=>g.date===state.date)}
function selectedRows(){return board.filter(r=>r.date===state.date)}
function selectedPlays(){return selectedRows().filter(r=>r.tier!=="AVOID"&&Number(r.stake)>0)}
let sharedBank=null;
let refreshing=false,lastCheck=0,refreshError=false;
function mySummary(){if(sharedBank){const own=L.summarise(myBets,0);return {...own,bankroll:sharedBank.current};}return L?L.summarise(myBets,summary.starting_bankroll??200):{bankroll:summary.starting_bankroll??200,profit:0,pending:0,settled:0,at_risk:0}}
function isTracked(row){return myBets.some(entry=>L.keyOf(entry)===L.keyOf(row))}

function setHealth(){
  const h=$("#health"),status=window.WNBAFeed.health(meta,board,Date.now(),refreshError);
  h.className=`health ${status.level}`;h.hidden=false;h.textContent=status.message;
  $("#stamp").textContent=`${status.label} · Published ${status.age}${meta.generated_at?` · ${new Date(meta.generated_at).toLocaleString()}`:""}`;
}

function renderKpis(){
  const plays=selectedPlays();
  const d={...((summary.day_summary||{})[state.date]||{}),plays:plays.length,staked:plays.reduce((sum,row)=>sum+Number(row.stake),0)};
  const mine=mySummary();
  const items=[
    ["My bankroll",money(mine.bankroll),sharedBank?"shared across all boards":"confirmed WNBA wagers only",mine.profit>0?"pos":mine.profit<0?"neg":""],
    ["Qualified",d.plays??0,"selected slate","accent"],
    ["Suggested risk",money(d.staked??0),`${money(summary.starting_bankroll??200)} model reference · ${money(summary.daily_cap)} model cap`,(d.staked||0)>summary.daily_cap?"neg":""],
    ["Games",d.games??0,`${d.priced??0} with prices`,d.priced?"":"warn"],
    ["Walk-forward MAE",num(calibration.spread_mae),`${num(calibration.total_mae)} total · ${calibration.n||0} games`,""],
    ["My P/L",money(mine.profit),mine.settled?`${mine.settled} settled · ${mine.pending} pending`:`${mine.pending} pending`,mine.profit>0?"pos":mine.profit<0?"neg":""],
  ];
  $("#kpis").innerHTML=items.map(([k,v,n,c])=>`<div class="kpi"><div class="k">${esc(k)}</div><div class="v ${c||""}">${esc(v)}</div><div class="n">${esc(n)}</div></div>`).join("");
}

function renderDateBar(){
  const dates=index.dates||[];
  const i=dates.indexOf(state.date);$("#prevDate").disabled=i<=0;$("#nextDate").disabled=i<0||i>=dates.length-1;
  $("#curDate").textContent=state.date?dateLabel(state.date):"No slate";
  $("#week").innerHTML=dates.map(value=>{const d=(index.day_summary||{})[value]||{};const parts=dateLabel(value).split(", ");return `<button type="button" class="${value===state.date?"on":""}" data-date="${value}"><b>${esc(parts[0]||dateLabel(value))}</b>${esc(parts.slice(1).join(", ")||value)}<i>${d.games||0} games · ${d.priced||0} priced</i></button>`}).join("");
  document.querySelectorAll("[data-date]").forEach(button=>button.onclick=()=>setDate(button.dataset.date));
}

function renderTabs(){
  const tabs=[
    ["plays","Best Bets",selectedPlays().length],["board","Full Board",selectedRows().length],
    ["schedule","Schedule",selectedGames().length],["sim","Simulator",10000],
    ["ledger","My Ledger",myBets.length],["accuracy","Accuracy",Object.values(performance.by_tier||{}).reduce((n,row)=>n+Number(row.settled||0),0)],
    ["model","Model",Object.keys(simulator.teams||{}).length],["sources","Data Sources",meta.errors?.length||0],
  ];
  $("#tabs").innerHTML=tabs.map(([id,label,count])=>`<button type="button" class="${state.tab===id?"on":""}" data-tab="${id}" aria-selected="${state.tab===id}">${esc(label)}<span class="cnt">${count}</span></button>`).join("");
  document.querySelectorAll("[data-tab]").forEach(b=>b.onclick=()=>{state.tab=b.dataset.tab;renderView();});
}

function panelHead(title,description,right=""){return `<div class="panelhead"><div><h2>${esc(title)}</h2><p>${description}</p></div>${right}</div>`}
function tier(row){return `<span class="tier ${tierClass(row.tier)}">${esc(row.tier)}</span>`}

function factors(projection){
  return (projection.factors||[]).map(f=>`<div class="factor"><span>${esc(f.name)}<small>${esc(f.note)}</small></span><b>${Number(f.points)>=0?"+":""}${num(f.points,2)}</b></div>`).join("");
}
function injuries(projection){
  const groups=[[projection.away_profile?.team,projection.away_injuries],[projection.home_profile?.team,projection.home_injuries]];
  const rows=groups.flatMap(([team,block])=>(block?.players||[]).map(p=>`<div class="injury"><b>${esc(team)}</b> · ${esc(p.name)} · ${esc(p.status)} · ${esc(p.detail||p.position)} <span class="num">${p.counted===false?"(not counted as injury)":p.points?`(${p.points.toFixed(2)} pts · ${esc(p.impact_basis||"role weighted")})`:""}</span></div>`));
  return rows.length?rows.join(""):`<div class="injury">No injury adjustment was supplied in this snapshot. This does not verify that every player is healthy or that the report is complete. Confirm team news.</div>`;
}
function ledgerControl(row,compact=false){
  if(row.tier==="AVOID"||!Number(row.stake))return "";
  if(isTracked(row))return `<span class="tracked">✓ In My Ledger</span>`;
  const id=esc(row.candidate_id);
  return `<span class="addbox ${compact?"compact":""}"><label for="stake-${id}">Stake</label><input id="stake-${id}" data-stake="${id}" type="number" min="0.5" step="0.5" value="${Number(row.stake).toFixed(2)}"><button type="button" class="run add-ledger" data-add="${id}">Add to My Ledger</button></span>`;
}
function card(row){
  const p=row.projection||{};const game=games.find(g=>g.game_id===row.game_id);const notes=(row.reasons||[]).join(" · ")||row.tier_note||"Qualified at the current live price and inside the daily exposure cap.";
  const modelWidth=Math.max(2,Math.min(98,Number(row.model_prob||.5)*100));
  return `<article class="card ${tierClass(row.tier)}"><div class="hd"><div><div class="match">${esc(row.matchup)}</div><div class="meta"><span class="chip">${esc(row.start_local)}</span><span class="chip ok">${esc(row.book)} · observed ${esc(window.WNBAFeed.ageLabel(row.odds_fetched_at))}</span><span class="chip" title="Input coverage and model confidence, not the chance this bet wins">${pct(row.confidence)} data confidence</span></div></div>${tier(row)}</div><div class="body">
    <div class="glance"><div><div class="pick">${esc(row.pick)} <small>${price(row.price)}</small></div><div class="score">${esc(row.away)} ${num(p.away_score)} – ${esc(row.home)} ${num(p.home_score)}<small> · line ${p.margin>=0?row.home:row.away} ${Math.abs(Number(p.margin||0)).toFixed(1)} · total ${num(p.total)}</small></div></div>
      <div class="glance-mid"><div class="lab"><span>Model ${pct(row.model_prob)}</span><span>No-vig market ${pct(row.market_fair_prob)}</span></div><div class="bar"><i class="a" style="width:${modelWidth}%"></i><i class="h" style="width:${100-modelWidth}%"></i></div></div>
      <div class="glance-metrics"><div class="metric"><div class="k">Break-even</div><div class="v">${pct(row.breakeven)}</div></div><div class="metric"><div class="k">Probability gap</div><div class="v">${pct(row.edge_probability_points)}</div></div><div class="metric"><div class="k">Model edge</div><div class="v">${pct(row.edge)}</div></div><div class="metric"><div class="k">At-price EV</div><div class="v">${pct(row.edge_real)}</div></div><div class="metric"><div class="k">Stake</div><div class="v">${money(row.stake)}</div></div></div>
    </div>
    <div class="verdict"><span class="act ${row.tier==="BEST BET"?"act-BET":row.tier==="GOOD"?"act-LEAN":row.tier==="LEAN"?"act-WATCH":"act-PASS"}">${esc(row.tier)}</span><span><b>${row.tier==="AVOID"?"Why pass":"Why it rates"}:</b> ${esc(notes)}${game?.rationale?` ${esc(game.rationale)}`:""}</span></div>
    ${ledgerControl(row)}
    <details class="gd"><summary class="gsum">Projection arithmetic</summary>${factors(p)}</details><details class="gd"><summary class="gsum">Reported player availability</summary>${injuries(p)}</details>
  </div></article>`;
}

function playsView(){
  const rows=selectedPlays();const d=(summary.day_summary||{})[state.date]||{};
  if(!rows.length){
    const why=d.priced?"No market currently clears all edge, confidence, exposure, price-age and start-time checks. The Full Board shows each reason.":d.games?"The connected feed returned no usable prices for this slate; that does not prove lines are unavailable at sportsbooks.":"No WNBA games are listed on this date in the published schedule.";
    return panelHead("Qualified plays",`Only real, currently priced markets can appear here. Nothing enters My Ledger unless you add it.`)+`<div class="empty"><b>No qualified plays for ${esc(dateLabel(state.date))}</b>${esc(why)} No bet is being forced.</div>`;
  }
  return panelHead("Qualified plays",`Ranked from the published slate. Review the current sportsbook price before adding a wager. Suggested stakes use quarter Kelly against a ${money(summary.starting_bankroll??200)} model reference, with the existing C$5 minimum and ${money(summary.daily_cap)} daily cap. The minimum can raise a stake above its calculated quarter-Kelly amount; shared bankroll changes do not resize these suggestions.`)+`<div class="cards">${rows.map(card).join("")}</div>`;
}

function boardView(){
  const choices=["PLAYS","ALL","BEST BET","GOOD","LEAN","AVOID"];
  let rows=selectedRows();if(state.tier==="PLAYS")rows=rows.filter(r=>r.tier!=="AVOID");else if(state.tier!=="ALL")rows=rows.filter(r=>r.tier===state.tier);
  const filters=`<div class="filters">${choices.map(t=>`<button class="filter ${state.tier===t?"on":""}" data-tier="${t}">${t==="PLAYS"?"Plays only":t}</button>`).join("")}</div>`;
  const table=rows.length?`<div class="tablewrap"><table class="rt"><thead><tr><th>Tier</th><th>Game</th><th>Pick</th><th>Book</th><th class="num">Price</th><th class="num">Model</th><th class="num">Market</th><th class="num">Break-even</th><th class="num">Prob. gap</th><th class="num">Edge</th><th class="num">Confidence</th><th class="num">Stake</th><th>Ledger</th><th>Reason</th></tr></thead><tbody>${rows.map(r=>`<tr><td data-label="Tier">${tier(r)}</td><td data-primary class="mono">${esc(r.matchup)} · ${esc(r.pick)}</td><td data-label="Pick" class="mono">${esc(r.pick)}</td><td data-label="Book">${esc(r.book)}</td><td data-label="Price" class="num">${price(r.price)}</td><td data-label="Model" class="num">${pct(r.model_prob)}</td><td data-label="Market" class="num">${pct(r.market_fair_prob)}</td><td data-label="Break-even" class="num">${pct(r.breakeven)}</td><td data-label="Prob. gap" class="num">${pct(r.edge_probability_points)}</td><td data-label="Edge" class="num">${pct(r.edge)}</td><td data-label="Confidence" class="num">${pct(r.confidence)}</td><td data-label="Stake" class="num">${money(r.stake)}</td><td data-trail>${ledgerControl(r,true)}</td><td data-trail>${esc((r.reasons||[]).join(" · ")||r.tier_note||"—")}</td></tr>`).join("")}</tbody></table></div>`:`<div class="empty"><b>No priced markets in this filter</b>Unpriced games remain on the Schedule tab and never become bets.</div>`;
  setTimeout(()=>document.querySelectorAll("[data-tier]").forEach(b=>b.onclick=()=>{state.tier=b.dataset.tier;renderView();}),0);
  return panelHead("Every priced side","AVOID rows explain a quiet board. Confidence measures input coverage and model confidence, not win probability; the Model column shows the estimated probability for that bet. Always verify the current sportsbook quote.")+filters+table;
}

function scheduleView(){
  const rows=selectedGames();if(!rows.length)return panelHead("Schedule","Live ESPN schedule, scores and market availability.")+`<div class="empty"><b>No games scheduled</b>Use the arrows to move to another available WNBA date.</div>`;
  return panelHead("Schedule","The complete slate stays visible even before prices post. A game without real odds cannot produce an edge or stake.")+`<div class="schedule">${rows.map(g=>{
    const q=(g.odds||{}).quotes||{},p=g.projection||{};const line=q.home_spread?.line,total=q.over?.line??q.under?.line;
    const status=g.completed?`${g.away.abbr} ${g.away.score} – ${g.home.abbr} ${g.home.score}`:g.status_detail;
    return `<article class="game"><div class="teams">${esc(g.away.abbr)} @ ${esc(g.home.abbr)}<div class="status">${esc(g.start_local)} · ${esc(status)}${g.broadcast?` · ${esc(g.broadcast)}`:""}</div></div><div class="market">${g.odds?`${esc(g.odds.book)} ${line!=null?`${g.home.abbr} ${Number(line)>0?"+":""}${line}`:"ML posted"}`:"WAITING FOR ODDS"}<small>${total!=null?`Total ${total}`:"No total yet"}</small></div><div class="projection">${num(p.away_score)} – ${num(p.home_score)}<small>${g.markets_priced||0} markets priced</small></div></article>`;
  }).join("")}</div>`;
}

function simMatch(){return games.find(g=>g.date===state.date&&g.away.abbr===$("#simAway")?.value&&g.home.abbr===$("#simHome")?.value)}
function simDefaults(){
  const match=simMatch(),q=(match?.odds||{}).quotes||{};
  if(match){$("#simHomeLine").value=q.home_spread?.line??"";$("#simTotalLine").value=q.over?.line??q.under?.line??"";$("#simRef").textContent=`Live reference: ${match.odds?.book||"market"} · ${match.home.abbr} ${q.home_spread?.line??"no spread"} · total ${q.over?.line??q.under?.line??"not posted"}`;}else{$("#simRef").textContent="No live matchup for these two teams on the selected date; team ratings still run automatically.";}
}
function rng(seed){return()=>{seed|=0;seed=(seed+0x6D2B79F5)|0;let t=Math.imul(seed^(seed>>>15),1|seed);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296}}
function gaussian(random){let u=0,v=0;while(!u)u=random();while(!v)v=random();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v)}
function runSim(){
  const teams=simulator.teams||{},a=teams[$("#simAway").value],h=teams[$("#simHome").value];if(!a||!h)return;
  const hca=Number($("#simHca").value||0),aAdj=Number($("#simAwayAdj").value||0),hAdj=Number($("#simHomeAdj").value||0);
  const awayBase=(Number(a.raw_ppg||a.ppg)+Number(h.raw_papg||h.papg))/2+aAdj,homeBase=(Number(h.raw_ppg||h.ppg)+Number(a.raw_papg||a.papg))/2+hAdj;
  const power=(Number(h.power_rating)-Number(a.power_rating))*Number(simulator.power_weight||.35);const margin=homeBase-awayBase+hca+power+Number(simulator.margin_bias||0);
  const recent=(Number(a.classic_l10_ppg||a.l10_ppg)+Number(h.classic_l10_ppg||h.l10_ppg)+Number(a.classic_l10_papg||a.l10_papg)+Number(h.classic_l10_papg||h.l10_papg))/2;
  const total=.65*(awayBase+homeBase)+.35*recent+Number(simulator.total_bias||0);
  const line=Number($("#simHomeLine").value),totalLine=Number($("#simTotalLine").value);const hasLine=$("#simHomeLine").value!=="",hasTotal=$("#simTotalLine").value!=="";
  const random=rng([...$("#simAway").value+$("#simHome").value].reduce((s,c)=>s+c.charCodeAt(0),2026));let hw=0,hc=0,ov=0,as=0,hs=0;
  for(let i=0;i<10000;i++){const m=margin+gaussian(random)*Number(simulator.spread_sigma||11),t=total+gaussian(random)*Number(simulator.total_sigma||11);const home=(t+m)/2,away=(t-m)/2;as+=away;hs+=home;if(m>0)hw++;if(hasLine&&m+line>0)hc++;if(hasTotal&&t>totalLine)ov++;}
  $("#simResult").innerHTML=`<div class="simscore">${esc(a.team)} ${(as/10000).toFixed(1)} – ${esc(h.team)} ${(hs/10000).toFixed(1)}</div><div class="simprobs"><div class="simprob"><div class="k">${esc(h.team)} win</div><div class="v">${(hw/100).toFixed(1)}%</div><div class="meter"><i style="width:${hw/100}%"></i></div></div><div class="simprob"><div class="k">Home cover ${hasLine?line>0?`+${line}`:line:"—"}</div><div class="v">${hasLine?(hc/100).toFixed(1)+"%":"—"}</div><div class="meter"><i style="width:${hasLine?hc/100:0}%"></i></div></div><div class="simprob"><div class="k">Over ${hasTotal?totalLine:"—"}</div><div class="v">${hasTotal?(ov/100).toFixed(1)+"%":"—"}</div><div class="meter"><i style="width:${hasTotal?ov/100:0}%"></i></div></div></div><div class="note"><b>10,000 simulations.</b> Uses the board's opponent-adjusted scoring, schedule-adjusted power, home court and walk-forward calibrated uncertainty (spread σ ${num(simulator.spread_sigma)}, total σ ${num(simulator.total_sigma)}). Manual adjustments are optional what-if controls.</div>`;
}
function simulatorView(){
  const teams=Object.keys(simulator.teams||{}).sort();if(teams.length<2)return panelHead("Game simulator","Runs the current automatic model with any matchup.")+`<div class="empty"><b>Ratings are not available yet</b>The simulator activates after the first live season refresh.</div>`;
  const game=selectedGames().find(g=>g.status==="pre");const away=game?.away.abbr||teams[0],home=game?.home.abbr||teams.find(t=>t!==away)||teams[1];const opts=selected=>teams.map(t=>`<option value="${t}" ${t===selected?"selected":""}>${esc(t)}</option>`).join("");
  const html=panelHead("10,000-run game simulator","Choose any teams. Live ratings are automatic; adjustments are optional what-if controls.")+`<div class="simgrid"><section class="box"><div class="fields"><div class="field"><label for="simAway">Away team</label><select id="simAway">${opts(away)}</select></div><div class="field"><label for="simHome">Home team</label><select id="simHome">${opts(home)}</select></div><div class="field"><label for="simHca">Home court points</label><input id="simHca" type="number" step="0.5" value="${simulator.home_court??2.5}"></div><div class="field"><label for="simHomeLine">Live home spread</label><input id="simHomeLine" type="number" step="0.5"></div><div class="field"><label for="simAwayAdj">Away scenario adjustment</label><input id="simAwayAdj" type="number" step="0.5" value="0"></div><div class="field"><label for="simHomeAdj">Home scenario adjustment</label><input id="simHomeAdj" type="number" step="0.5" value="0"></div><div class="field"><label for="simTotalLine">Live total</label><input id="simTotalLine" type="number" step="0.5"></div></div><button class="run" id="runSim" type="button">Run 10,000 simulations</button><div class="now" id="simRef" style="margin-top:9px"></div></section><section class="box" id="simResult"></section></div>`;
  setTimeout(()=>{$("#simAway").onchange=()=>{simDefaults();runSim()};$("#simHome").onchange=()=>{simDefaults();runSim()};$("#runSim").onclick=runSim;simDefaults();runSim();},0);return html;
}

function ledgerView(){
  const mine=mySummary();
  const controls=`<div class="ledger-tools"><button type="button" class="iconbtn" data-export="json">Export JSON</button><button type="button" class="iconbtn" data-export="csv">Export CSV</button><label class="iconbtn importbtn">Import JSON<input id="ledgerImport" type="file" accept="application/json,.json" hidden></label>${myBets.length?`<button type="button" class="iconbtn danger" data-clear-ledger>Clear ledger</button>`:""}</div>`;
  const stats=`<div class="stats"><article class="stat"><h3>Bankroll</h3><div class="big">${money(mine.bankroll)}</div><p>${sharedBank?"Shared bankroll · WNBA record below":money(summary.starting_bankroll??200)+" start"}</p></article><article class="stat"><h3>Record</h3><div class="big">${mine.wins}-${mine.losses}-${mine.pushes}</div><p>${mine.pending} pending</p></article><article class="stat"><h3>Net P/L</h3><div class="big ${mine.profit>0?"pos":mine.profit<0?"neg":""}">${money(mine.profit)}</div><p>${mine.roi==null?"needs settled wagers":pct(mine.roi)+" ROI"}</p></article><article class="stat"><h3>At risk</h3><div class="big">${money(mine.at_risk)}</div><p>confirmed pending wagers</p></article></div>`;
  const rows=myBets.slice().sort((a,b)=>String(b.tipoff).localeCompare(String(a.tipoff)));const table=rows.length?`<div class="tablewrap" style="margin-top:14px"><table><thead><tr><th>Date</th><th>Game</th><th>Bet</th><th>Tier</th><th class="num">Price</th><th class="num">Edge</th><th class="num">Stake</th><th>Result</th><th class="num">P/L</th><th></th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.date)}</td><td class="mono">${esc(r.matchup)}</td><td class="mono">${esc(r.pick)}</td><td><span class="tier ${tierClass(r.tier)}">${esc(r.tier)}</span></td><td class="num">${price(r.price)}</td><td class="num">${pct(r.edge)}</td><td class="num">${money(r.stake)}</td><td><span class="res ${esc(r.result||"Pending")}">${esc(r.result||"Pending")}</span>${r.final_score?`<small class="block">${esc(r.final_score)}</small>`:""}</td><td class="num ${Number(r.profit)>0?"pos":Number(r.profit)<0?"neg":""}">${r.profit==null?"—":money(r.profit)}</td><td><button type="button" class="removebet" data-remove="${esc(r.id)}" aria-label="Remove ${esc(r.pick)}">Remove</button></td></tr>`).join("")}</tbody></table></div>`:`<div class="empty" style="margin-top:14px"><b>No wagers in My Ledger</b>Review a qualified card and click Add to My Ledger only after you actually place it. Model picks are never added automatically.</div>`;
  return panelHead("My Ledger","This is your manual wager record, separate from the model's shadow-book accuracy. Confirmed entries keep the price and stake you accepted, then settle from final ESPN scores.",controls)+stats+table;
}

function accuracyView(){return '<div class="note"><b>Reading this record:</b> Headline statistics include AVOID picks and legacy model versions, not just qualified wagers. Use the original-tier and version breakdowns before assessing the current model. These are hypothetical one-unit results, separate from My Ledger; small samples do not establish a reliable edge.</div><div data-model-accuracy></div>';}

function modelView(){
  const teams=Object.values(simulator.teams||{}).sort((a,b)=>Number(b.power_rating)-Number(a.power_rating));const table=teams.length?`<div class="tablewrap"><table><thead><tr><th>Rank</th><th>Team</th><th class="num">Power</th><th class="num">Games</th><th class="num">PPG</th><th class="num">Allowed</th><th class="num">Off eff.</th><th class="num">Def eff.</th><th class="num">Pace</th><th class="num">eFG%</th><th class="num">Reb share</th></tr></thead><tbody>${teams.map((t,i)=>`<tr><td class="num">${i+1}</td><td class="mono">${esc(t.team)}</td><td class="num">${Number(t.power_rating)>=0?"+":""}${num(t.power_rating,2)}</td><td class="num">${t.games}</td><td class="num">${num(t.ppg)}</td><td class="num">${num(t.papg)}</td><td class="num">${num(t.off_eff)}</td><td class="num">${num(t.def_eff)}</td><td class="num">${num(t.pace)}</td><td class="num">${pct(t.efg)}</td><td class="num">${pct(t.rebound_share)}</td></tr>`).join("")}</tbody></table></div>`:`<div class="empty"><b>No live ratings yet</b>Ratings appear automatically after completed WNBA games are available.</div>`;
  return panelHead("Model & power ratings","The scoring baseline is tested walk-forward, then checked against pace, efficiency, shot profile, rebounding, free-throw pressure, schedule density, travel and current player availability before the market anchor is applied.")+table+`<div class="note"><b>Calibration:</b> ${calibration.n||0} prior games · spread MAE ${num(calibration.spread_mae)} · total MAE ${num(calibration.total_mae)} · total uncertainty ${num(calibration.total_sigma)} points. Future results are excluded from every replay. <b>Edge safety:</b> one play maximum per game, three per slate, quarter-Kelly sizing, a 2% at-price execution buffer and a hold when a high-impact player is unresolved.</div>`;
}

function sourcesView(){
  const sources=[
    ["Schedule, scores and box-score inputs","ESPN public WNBA scoreboard · keyless · full 2026 season refreshed automatically"],
    ["Moneyline, spread and total","DraftKings prices distributed through ESPN's public game feed; only actual posted quotes are priced"],
    ["Player availability","ESPN injury reports, weighted by current team-leader role; coach's-decision and non-injury listings are not treated like injuries"],
    ["Efficiency and schedule context","Pace, offensive/defensive efficiency, eFG%, free-throw pressure, rebounding, travel, back-to-backs and compressed schedules"],
    ["Independent matchup prior","ESPN matchup predictor receives a small capped weight when available; it cannot override the local model or market"],
    ["Calibration","Walk-forward errors from completed 2026 games set bias and uncertainty; no future result is allowed into an earlier replay"],
    ["My Ledger","Only wagers you click are stored in this browser; confirmed entries settle from ESPN final scores"],
    ["Model accuracy","A separate shadow book grades every priced call, including AVOID, without adding it to My Ledger"],
  ];
  const errors=(meta.errors||[]).map(e=>`<div class="source"><h3 class="neg">Refresh warning</h3><p>${esc(e)}</p></div>`).join("");
  return panelHead("Data sources & refresh health","Everything needed for the board is fetched automatically. No spreadsheet paste, API key, sample slate or manual refresh button is required.")+`<section class="box">${sources.map(([h,p])=>`<div class="source"><h3>${esc(h)}</h3><p>${esc(p)}</p></div>`).join("")}${errors}</section><div class="note"><b>Last successful build:</b> ${esc(new Date(meta.generated_at).toLocaleString())}. The GitHub workflow refreshes several times daily, captures line movement, grades finished games and republishes the site. If a provider is temporarily unavailable, the last real cache is labeled clearly; fabricated fallback bets do not exist.</div>${news.length?`<section class="box"><h3 style="margin-top:0">Latest WNBA news</h3>${news.slice(0,8).map(n=>`<div class="source"><h3>${n.link?`<a href="${esc(n.link)}" target="_blank" rel="noopener" style="color:inherit">${esc(n.headline)}</a>`:esc(n.headline)}</h3><p>${esc(n.description||"")}</p></div>`).join("")}</section>`:""}<div class="footer">Model output only—never a guarantee or instruction to wager. Verify the price at your sportsbook and bet only what you can afford to lose.</div>`;
}

function saveMyBets(){if(L&&!L.save(myBets))window.alert("This browser blocked local ledger storage. Export your ledger to keep a copy.");window.BetSync?.touch();}
function downloadLedger(name,text,type){const blob=new Blob([text],{type});const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download=name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(link.href),1000)}
function bindLedgerActions(){
  document.querySelectorAll("[data-add]").forEach(button=>button.onclick=()=>{
    const row=board.find(item=>item.candidate_id===button.dataset.add);if(!row||isTracked(row))return;
    const blocked=window.QuoteEligibility.blockReason(row,row.max_odds_age_hours??12);
    if(blocked){window.alert(blocked);renderView();return;}
    const input=document.querySelector(`[data-stake="${CSS.escape(row.candidate_id)}"]`);const stake=Number(input?.value);
    if(!isFinite(stake)||stake<=0){window.alert("Enter the stake you actually placed.");return;}
    myBets.push(L.entryFrom(row,stake));saveMyBets();renderView();
  });
  document.querySelectorAll("[data-remove]").forEach(button=>button.onclick=()=>{
    if(!window.confirm("Remove this wager from My Ledger?"))return;
    myBets=myBets.filter(row=>row.id!==button.dataset.remove);saveMyBets();renderView();
  });
  document.querySelectorAll("[data-export]").forEach(button=>button.onclick=()=>{
    if(button.dataset.export==="csv")downloadLedger("wnba-edge-ledger.csv",L.toCSV(myBets),"text/csv");
    else downloadLedger("wnba-edge-ledger.json",JSON.stringify({schema:L.SCHEMA,exported_at:new Date().toISOString(),entries:myBets},null,2),"application/json");
  });
  const importInput=$("#ledgerImport");if(importInput)importInput.onchange=async()=>{
    try{const parsed=JSON.parse(await importInput.files[0].text());const incoming=Array.isArray(parsed)?parsed:(parsed.entries||[]);const merged=L.merge(myBets,incoming);myBets=merged.entries;saveMyBets();window.alert(`${merged.added} wager(s) imported.`);renderView();}catch(_){window.alert("That file is not a valid WNBA Edge ledger export.");}
  };
  const clear=document.querySelector("[data-clear-ledger]");if(clear)clear.onclick=()=>{if(window.confirm("Clear every wager from this browser ledger? Export first if you need a backup.")){myBets=[];saveMyBets();renderView();}};
}
function expireQuotes(){
  board=board.map(row=>{
    const reason=window.QuoteEligibility.blockReason(row,row.max_odds_age_hours??12);
    return reason?{...row,tier:"AVOID",stake:0,reasons:[...new Set([...(row.reasons||[]),reason])]}:row;
  });
}
function renderView(){expireQuotes();renderTabs();renderKpis();const views={plays:playsView,board:boardView,schedule:scheduleView,sim:simulatorView,ledger:ledgerView,accuracy:accuracyView,model:modelView,sources:sourcesView};$("#view").innerHTML=(views[state.tab]||playsView)();bindLedgerActions();}
function setDate(value){if(!(index.dates||[]).includes(value))return;state.date=value;const url=new URL(location.href);url.searchParams.set("date",value);history.replaceState({},"",url);renderDateBar();renderView();}

function refreshDeferred(){
  return document.hidden||state.tab==="sim"||state.tab==="accuracy"||document.activeElement?.matches?.("input,select,textarea,[contenteditable=true]")||[...document.querySelectorAll("[data-stake]")].some(input=>input.value!==input.defaultValue)||Boolean($("#ledgerImport")?.files?.length);
}
async function refreshPublishedData(force=false){
  if(refreshing||refreshDeferred()||(lastCheck&&Date.now()-lastCheck<(force?60000:300000)))return;
  refreshing=true;lastCheck=Date.now();
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),30000);
  try{
    const payload=await window.WNBAFeed.read(fetch,meta.generated_at,controller.signal);
    refreshError=false;
    if(!payload){setHealth();return;}
    // A user may start editing while the request is in flight. Do not replace
    // their stake, simulator scenario, history search or pending file import.
    if(refreshDeferred()){lastCheck=0;setHealth();return;}
    [board,games,summary,meta,index,performance,simulator,news,calibration,results]=payload;
    myBets=L?L.load():[];if(L){const settled=L.settleAll(myBets,[...games,...results]);myBets=settled.entries;if(settled.changed)L.save(myBets);}
    const requested=new URL(location.href).searchParams.get("date"),today=easternToday(),dates=index.dates||[];
    state.date=dates.includes(state.date)?state.date:dates.includes(requested)?requested:dates.includes(today)?today:index.built_for||dates[0]||today;
    window.dispatchEvent(new Event("wnba:feed-updated"));
    setHealth();renderDateBar();renderView();
  }catch(error){
    refreshError=true;setHealth();
    if(!meta.generated_at)$("#view").innerHTML=`<div class="empty"><b>Published data could not be loaded</b>No sample data will be substituted. This page will retry automatically.</div>`;
  }finally{clearTimeout(timeout);refreshing=false;}
}
function boot(){
  $("#prevDate").onclick=()=>{const dates=index.dates||[],i=dates.indexOf(state.date);if(i>0)setDate(dates[i-1])};
  $("#nextDate").onclick=()=>{const dates=index.dates||[],i=dates.indexOf(state.date);if(i>=0&&i<dates.length-1)setDate(dates[i+1])};
  $("#today").onclick=()=>{const dates=index.dates||[],t=easternToday();if(dates.includes(t))setDate(t);else setDate(dates.find(d=>d>=t)||dates.at(-1));};
  $("#theme").onclick=()=>{const root=document.documentElement,current=root.dataset.theme||(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark");root.dataset.theme=current==="light"?"dark":"light";try{localStorage.setItem("wnba-theme",root.dataset.theme);}catch(_){}};
  try{const theme=localStorage.getItem("wnba-theme");if(theme)document.documentElement.dataset.theme=theme;}catch(_){}
  return refreshPublishedData(true);
}
boot();
function refreshExpiredQuotes(){
  if(meta.generated_at&&board.some(row=>row.tier!=="AVOID"&&window.QuoteEligibility.blockReason(row,row.max_odds_age_hours??12)))renderView();
  if(meta.generated_at)setHealth();
}
setInterval(()=>{refreshExpiredQuotes();refreshPublishedData();},60000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden){refreshExpiredQuotes();refreshPublishedData(true);}});

window.wnbaSharedLedger={reload(){myBets=L.load();if(state.date)renderView();},bank(bank){sharedBank=bank;if(state.date)renderView();}};
