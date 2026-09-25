/* The Today view only reads existing public feeds and the configured sheet. */
(() => {
  "use strict";
  const C=window.KevToday, BS=window.BetSync, $=s=>document.querySelector(s);
  const sources={
    wnba:{meta:"../wnba-edge-lab/data/meta.json",board:"../wnba-edge-lab/data/board.json",accuracy:"../wnba-edge-lab/data/accuracy.json"},
    props:{meta:"../props-edge/data/meta.json",board:"../props-edge/data/board.json",accuracy:"../props-edge/data/accuracy-summary.json"},
    ladder:{accuracy:"../ladderbet/data/accuracy.json"},
    mlb:{meta:"../mlb-edge/data/index.json",slate:"../mlb-edge/data/latest.json",accuracy:"../mlb-edge/data/predictions.json"},
    nfl:{meta:"../nfl-edge-lab/data/meta.json",board:"../nfl-edge-lab/data/board.json",accuracy:"../nfl-edge-lab/data/accuracy.json"},
    ncaaf:{meta:"../ncaaf-edge-lab/data/meta.json",board:"../ncaaf-edge-lab/data/board.json",accuracy:"../ncaaf-edge-lab/data/accuracy.json"}
  };
  const S={feeds:{},busy:false,sheetBusy:false,sheet:null,sheetError:"",sheetAt:null,loadedAt:null,active:true};
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const money=v=>C.number(v)==null?"—":new Intl.NumberFormat("en-CA",{style:"currency",currency:"CAD",maximumFractionDigits:2}).format(v);
  const num=(v,d=1)=>C.number(v)==null?"—":Number(v).toFixed(d);
  const pct=v=>C.number(v)==null?"—":num(v*100)+"%";
  const odds=v=>v==null?"—":(v>0?"+":"")+v;
  const time=v=>C.instant(v)==null?"Unknown":new Intl.DateTimeFormat("en-CA",{timeZone:"America/Toronto",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"}).format(new Date(v));
  function elapsed(v){const n=C.instant(v);if(n==null)return "not available";const m=Math.max(0,Math.floor((Date.now()-n)/60000));return m<1?"just now":m<60?m+"m ago":num(m/60)+"h ago";}
  const tickerLeagues={NBA:"basketball/nba",WNBA:"basketball/wnba",MLB:"baseball/mlb",NCAAF:"football/college-football",NCAAB:"basketball/mens-college-basketball",NHL:"hockey/nhl",NFL:"football/nfl"};
  let ticketBlob=null,ticketUrl="",currentTicket=null;
  function scoreText(event){
    const c=event.competitions?.[0],teams=c?.competitors||[],away=teams.find(x=>x.homeAway==="away"),home=teams.find(x=>x.homeAway==="home");
    if(!away||!home)return "";
    const name=x=>x.team?.abbreviation||x.team?.shortDisplayName||"TBD",state=c.status?.type?.state||event.status?.type?.state;
    if(state==="pre")return name(away)+" @ "+name(home)+" · "+time(event.date)+" ET";
    return name(away)+" "+(away.score??0)+" · "+name(home)+" "+(home.score??0)+" · "+(c.status?.type?.shortDetail||event.status?.type?.shortDetail||"");
  }
  async function refreshTicker(){
    const button=$("#ticker-refresh");button.disabled=true;
    const batches=await Promise.all(Object.entries(tickerLeagues).map(async([label,path])=>{
      const base="https://site.api.espn.com/apis/site/v2/sports/"+path;
      const [score,news]=await Promise.allSettled([get(base+"/scoreboard"),get(base+"/news?limit=2")]);
      const items=[];
      if(score.status==="fulfilled")for(const e of (score.value.events||[]).slice(0,3)){const value=scoreText(e);if(value)items.push({label,value,news:false});}
      if(news.status==="fulfilled"){const h=(news.value.articles||news.value.headlines||[])[0];if(h?.headline)items.push({label,value:h.headline,news:true});}
      return items;
    }));
    const items=batches.flat();
    $("#ticker-track").innerHTML=(items.length?items:[{label:"LIVE WIRE",value:"Scores and news feed temporarily unavailable.",news:true}]).map(x=>'<span class="ticker-item"><b class="ticker-league">'+esc(x.label)+'</b><span class="'+(x.news?"ticker-news":"")+'">'+esc(x.value)+'</span></span>').join("");
    button.disabled=false;
  }
  const ticketRows=()=>C.topPlays(Object.entries(S.feeds).flatMap(([k,b])=>C.plays(k,b)).filter(r=>r.day===$("#date").value),10);
  function loadImage(src){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=reject;img.src=src;});}
  function rounded(ctx,x,y,w,h,r){ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();}
  function fit(ctx,text,max){let s=String(text||"");while(s.length&&ctx.measureText(s).width>max)s=s.slice(0,-1);return s===String(text||"")?s:s.replace(/[ .,;:-]+$/g,"")+"…";}
  async function buildTicket(fresh=false){
    if(fresh||!currentTicket){currentTicket={id:"local-"+crypto.randomUUID(),day:$("#date").value,published_at:new Date().toISOString(),picks:ticketRows()};
      try{window.KevTicketStore.save(currentTicket);}catch(_){currentTicket.saveFailed=true;}
    }
    const rows=currentTicket.picks,canvas=document.createElement("canvas"),ctx=canvas.getContext("2d"),W=1080,H=1350;canvas.width=W;canvas.height=H;
    const ticket=currentTicket;
    await window.KevTicketRenderer.draw(canvas,ticket,{style:$("#ticket-style").value});
    ticketBlob=await new Promise(resolve=>canvas.toBlob(resolve,"image/png"));if(ticketUrl)URL.revokeObjectURL(ticketUrl);ticketUrl=URL.createObjectURL(ticketBlob);$("#ticket-preview").src=ticketUrl;$("#ticket-note").textContent=rows.length+" qualified pick"+(rows.length===1?"":"s")+" · "+(currentTicket.saveFailed?"Browser storage failed; download this image now.":"Saved locally. Checking ticket backup…");$("#ticket-share").hidden=!(navigator.canShare&&navigator.canShare({files:[new File([ticketBlob],"kevbot-bets-top-picks.png",{type:"image/png"})]}));if(!$("#ticket-dialog").open)$("#ticket-dialog").showModal();
    const snapshotId=currentTicket.id;
    if(!currentTicket.saveFailed)window.KevTicketStore.sync().then(result=>{if(currentTicket.id===snapshotId)$("#ticket-note").textContent=rows.length+" qualified picks · "+result.message;}).catch(()=>{if(currentTicket.id===snapshotId)$("#ticket-note").textContent="Image saved on this browser. Sheet backup failed; it will retry on reconnect or from Tickets & results.";});
  }
  function downloadTicket(){if(!ticketBlob)return;const a=document.createElement("a");a.href=ticketUrl;a.download="kevbot-bets-top-picks-"+currentTicket.day+".png";a.click();}
  async function shareTicket(){if(!ticketBlob)return;const file=new File([ticketBlob],"kevbot-bets-top-picks-"+currentTicket.day+".png",{type:"image/png"});try{await navigator.share({title:"KEVBOT BETS Daily Top Picks",files:[file]});}catch(_){}
  }
  const link=(key,label)=>'<a class="cta" href="./#'+key+'" target="_top">'+esc(label||("Open "+C.LABELS[key]))+' →</a>';
  const empty=text=>'<div class="empty">'+esc(text)+'</div>';
  function chosen(){return Object.entries(S.feeds).flatMap(([k,b])=>C.plays(k,b)).filter(r=>r.day===$("#date").value&&($("#sport").value==="all"||r.key===$("#sport").value));}
  function renderBank(){
    if(!S.sheet){
      $("#bank").innerHTML=empty(S.sheetError||"Connect in Ledger to read your shared bankroll here. No default bankroll is assumed.");
      return;
    }
    const rows=S.sheet.rows.filter(r=>!r.deleted),b=BS.bankroll(rows,S.sheet.settings.starting_bankroll);
    $("#bank").innerHTML='<div class="kpis">'+[["Bankroll",b.current],["Available",b.available],["Open exposure",b.exposure],["Profit / loss",b.pnl]].map(([label,v])=>'<div class="kpi"><small>'+label+'</small><strong>'+money(v)+'</strong></div>').join("")+'</div><p class="note">Sheet '+(S.sheetBusy?"syncing…":"last read "+elapsed(S.sheetAt))+'. '+b.pending+' open bet(s). Sheet sync is separate from odds freshness.</p>'+(S.sheetError?'<p class="warning">Sheet read failed. The figures above are the last successful read; reconnect in Ledger.</p>':"");
  }
  function renderPlays(){
    const rows=C.sortPlays(chosen(),$("#sort").value),risk=S.sheet?C.exposure(S.sheet.rows):null;
    $("#play-count").textContent=rows.length+" available";
    $("#plays").innerHTML=rows.length?rows.map(r=>{
      const group=risk?.groups.find(g=>g.key===C.eventKey({sport:r.sport,event:r.event,start:r.start}));
      return '<article class="card"><span class="tag">'+esc(r.source)+'</span><span class="tag '+(r.review.length?"review":"recent")+'">'+esc(r.tier)+'</span><h3>'+esc(r.pick)+'</h3><p>'+esc(r.event)+'<br><small>'+esc(time(r.start))+' ET</small></p><dl><dt>Offered price</dt><dd>'+odds(r.price)+'</dd><dt>Book</dt><dd>'+esc(r.book)+'</dd><dt>Quote observed</dt><dd>'+esc(r.quote?elapsed(r.quote):"Not supplied")+'</dd></dl>'+r.review.map(t=>'<p class="warning">'+esc(t)+'</p>').join("")+(group?'<p class="warning">Already exposed to this game: '+money(group.stake)+' across '+group.rows.length+' bet(s).</p>':"")+link(r.key,"Review odds and stake")+'</article>';
    }).join(""):empty(S.busy?"Loading board-qualified plays…":"No current qualified plays for this date and filter. This may mean no edge, no prices, or stale/unavailable data—see Data health below.");
  }
  function renderHealth(){
    $("#health").innerHTML=Object.keys(sources).map(key=>{
      const b=S.feeds[key]||{error:true},h=C.health(key,b),meta=b.meta||b.slate||{};
      const auth=key==="props"?(meta.counts?.eligible_priced_quotes>0?"Keyless player statistics and observed prop prices are connected. Confirm the current sportsbook quote.":meta.statistics_status==='available'?"Player statistics are available. This refresh returned no verified eligible prop prices; see the Props board for feed status.":"Check the Props board for player-statistics and price-feed status. No personal API key is required."):key==="ladder"?"Market-based screening; see the Ladder board for its source.":"Existing public data feeds; no personal API key required.";
      return '<article class="card"><span class="tag '+h.status+'">'+esc(h.status)+'</span><h3>'+esc(h.label)+'</h3><p>Published '+esc(h.stamp?time(h.stamp)+" ET":"time unavailable")+'<br><small>Data age: '+esc(elapsed(h.stamp))+'</small></p><p class="note">'+esc(auth)+'</p>'+(key==="ladder"?'<p class="note">This timestamp covers screening history, not the current Ladder quote.</p>':"")+(b.error&&b.lastGoodAt?'<p class="note">Last successful read: '+esc(time(b.lastGoodAt))+' ET</p>':"")+h.warnings.map(w=>'<p class="warning">'+esc(w)+'</p>').join("")+link(key)+'</article>';
    }).join("");
  }
  function metric(label,value){return '<p><span>'+esc(label)+'</span><b>'+esc(value)+'</b></p>';}
  function renderAccuracy(){
    $("#accuracy").innerHTML=Object.keys(sources).map(key=>{
      const b=S.feeds[key]||{},a=C.accuracy(key,b);
      if(!b.accuracy)return '<article class="card"><h3>'+esc(C.LABELS[key])+'</h3><p>Prediction data unavailable.</p></article>';
      let body='';
      if(a.markets){
        const selected=a.markets.filter(x=>x.n>0).sort((x,y)=>y.n-x.n);
        body='<div class="table-scroll"><table><thead><tr><th>Market</th><th>Graded</th><th>Avg. error</th><th>Bias</th></tr></thead><tbody>'+selected.map(x=>'<tr><td>'+esc(x.market)+'</td><td>'+x.n+'</td><td>'+num(x.mae)+'</td><td>'+num(x.bias)+'</td></tr>').join("")+'</tbody></table></div><p class="note">Each market has its own units; errors are not comparable across markets. Several forecasts can belong to one player/game.</p>';
        if(!selected.length)body=empty("No graded player forecasts yet.");
      }else{
        body='<div class="metrics">'+metric("Winner / screened-option record",a.wins==null?"—":a.wins+"–"+(key==="ladder"?(a.losses??"—"):Math.max(0,a.n-a.wins))+(key==="ladder"?"–"+a.pushes:""))+metric(key==="ladder"?"Settled sample":"Decided sample",a.n)+metric("Win rate",pct(a.winRate));
        if(key==="mlb")body+=metric("Matched games",a.marketN)+metric("Model / market winners",a.modelCorrect+" / "+a.marketCorrect)+metric("Probability error: model / market",num(a.modelBrier,3)+" / "+num(a.marketBrier,3));
        if(a.ats)body+=metric("Spread direction",pct(a.ats.accuracy)+" · n="+(a.ats.n||0))+metric("Total direction",pct(a.totals.accuracy)+" · n="+(a.totals.n||0))+metric("Margin error: model / market",num(a.margin.model_mae)+" / "+num(a.margin.market_mae)+" · n="+(a.margin.n||0))+metric("Total error: model / market",num(a.total.model_mae)+" / "+num(a.total.market_mae)+" · n="+(a.total.n||0));
        if(key==="ladder")body+=metric("Voids",a.voids)+metric("Hypothetical one-unit ROI",pct(a.roi));
        body+='</div><p class="note">Lower prediction error is better. A high winner rate alone does not prove value at the offered odds.</p>';
      }
      return '<article class="card"><h3>'+esc(a.label)+'</h3><p><small>'+esc(a.scope)+'</small></p>'+body+a.notes.map(x=>'<p class="note">'+esc(x)+'</p>').join("")+link(key,"Full board accuracy")+'</article>';
    }).join("");
  }
  function renderRisk(){
    if(!S.sheet){$("#risk").innerHTML=empty("Connect and sync in Ledger to see shared exposure. No bets are created here.");return;}
    const e=C.exposure(S.sheet.rows),d=C.drawdown(S.sheet.rows,S.sheet.settings.starting_bankroll);
    $("#risk").innerHTML=(S.sheetError?'<p class="warning">Using the last successful sheet read; exposure may have changed.</p>':"")+'<div class="cards"><article class="card"><h3>'+money(e.total)+' currently at risk</h3>'+Object.entries(e.bySport).map(([sport,value])=>metric(sport,money(value))).join("")+'</article><article class="card"><h3>Historical drawdown</h3>'+metric("Largest drop from a prior peak",money(d.max))+metric("Current drop from a prior peak",money(d.current))+'<p class="note">'+esc(d.note)+'</p></article></div><h3>Open bets grouped by game</h3><div class="cards">'+(e.groups.length?e.groups.map(g=>'<article class="card"><h3>'+esc(g.event)+'</h3>'+metric("Combined stake",money(g.stake))+metric("Open bets",g.rows.length)+'<p>'+esc(g.apps.join(" · "))+'</p>'+(g.rows.length>1?'<p class="warning">Multiple positions on this game. Check overlap before adding another.</p>':"")+link("ledger","Review in Ledger")+'</article>').join(""):empty("No matched open game positions."))+'</div><p class="note">'+e.unmatched+' open bet(s) could not be matched to a game. They remain included in total exposure. Parlays, doubleheaders and inconsistent team names may need manual review; grouping is not a complete correlation check.</p>';
  }
  function render(){renderBank();renderPlays();renderHealth();renderAccuracy();renderRisk();}
  async function readSheet(){
    if(S.sheetBusy)return;
    let cfg;
    try{cfg=BS.loadConfig();}catch(_){}
    if(!cfg){S.sheet=null;S.sheetAt=null;S.sheetError="";renderBank();renderRisk();return;}
    S.sheetBusy=true;renderBank();
    try{const res=await BS.pullAll(cfg,"");S.sheet={rows:(res.rows||[]).map(BS.canonical),settings:res.settings||{}};S.sheetAt=new Date().toISOString();S.sheetError="";}
    catch(_){S.sheetError="Could not read the shared sheet. Open Ledger to check your connection.";}
    finally{S.sheetBusy=false;renderBank();renderRisk();renderPlays();}
  }
  async function get(url){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
    try{const res=await fetch(url,{cache:"no-store",signal:controller.signal});if(!res.ok)throw Error("unavailable");return await res.json();}
    finally{clearTimeout(timer);}
  }
  let refreshTask=null;
  function refresh(){if(!refreshTask)refreshTask=refreshFeeds().finally(()=>{refreshTask=null;});return refreshTask;}
  async function refreshFeeds(){
    if(S.busy)return;
    S.busy=true;$("#refresh").disabled=true;$("#refresh-status").textContent="Loading published board data…";
    const sheet=readSheet();
    await Promise.all(Object.entries(sources).map(async([key,paths])=>{
      const b={};await Promise.all(Object.entries(paths).map(async([field,url])=>{
        try{b[field]=await get(url);}catch(_){if(field!=="accuracy"||key==="ladder")b.error=true;}
      }));
      const cacheKey="kevbot.feed.v1."+key;
      if(b.error){let prior=S.feeds[key];try{prior=prior||JSON.parse(localStorage.getItem(cacheKey)||"null");}catch(_){}
        S.feeds[key]={...(prior||b),error:true,failedAt:new Date().toISOString()};
      }else{b.lastGoodAt=new Date().toISOString();S.feeds[key]=b;try{localStorage.setItem(cacheKey,JSON.stringify({meta:b.meta,lastGoodAt:b.lastGoodAt,slate:b.slate?{generated_at:b.slate.generated_at}:undefined,accuracy:b.accuracy?{generated_at:b.accuracy.generated_at}:undefined}));}catch(_){}}

    }));
    S.busy=false;S.loadedAt=new Date().toISOString();$("#refresh").disabled=false;
    const failed=Object.values(S.feeds).filter(b=>b.error).length;
    $("#refresh-status").textContent="Published files checked "+time(S.loadedAt)+" ET"+(failed?" · "+failed+" board feed(s) need attention.":".")+" Odds collection runs separately.";
    render();await sheet;
  }
  $("#date").value=C.day(Date.now());
  ["date","sport","sort"].forEach(id=>$("#"+id).addEventListener("change",renderPlays));
  document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>{
    document.querySelectorAll("[data-view]").forEach(b=>b.setAttribute("aria-pressed",String(b===button)));
    ["plays","accuracy","risk"].forEach(key=>$("#view-"+key).hidden=key!==button.dataset.view);
  }));
  $("#refresh").addEventListener("click",refresh);
  $("#ticker-refresh").addEventListener("click",refreshTicker);
  $("#ticket-style").addEventListener("change",()=>buildTicket().catch(e=>$("#ticket-note").textContent=e.message));
  $("#ticket-close").addEventListener("click",()=>$("#ticket-dialog").close());
  $("#ticket-download").addEventListener("click",downloadTicket);
  $("#ticket-share").addEventListener("click",shareTicket);
  window.makeKevbotTicket=async()=>{try{if(S.busy||!S.loadedAt||Date.now()-Date.parse(S.loadedAt)>300000)await refresh();await buildTicket(true);}catch(e){$("#refresh-status").textContent=e.message;}};
  window.addEventListener("message",e=>{
    if(e.source!==window.parent||e.origin!==window.location.origin)return;
    if(e.data?.type==="kevbotbets:deactivate")S.active=false;
    if(e.data?.type==="kevbotbets:activate"){S.active=true;render();readSheet();if(!S.loadedAt||Date.now()-Date.parse(S.loadedAt)>300000)refresh();}
  });
  document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible"&&S.active){render();readSheet();}});
  window.addEventListener("online",()=>{if(S.active)refresh();window.KevTicketStore.sync().catch(()=>{});});
  setInterval(()=>{if(document.visibilityState==="visible"&&S.active)render();},60000);
  setInterval(()=>{if(document.visibilityState==="visible"&&S.active)refresh();},300000);
  setInterval(()=>{if(document.visibilityState==="visible"&&S.active)refreshTicker();},180000);
  if(new URLSearchParams(location.search).get("view")==="accuracy")document.querySelector('[data-view="accuracy"]').click();
  refresh();refreshTicker();
})();
