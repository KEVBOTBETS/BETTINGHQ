/* Each board keeps its URL, relative data paths and storage. Frames are created
   on first use, then retained so switching never discards form state or scroll. */
(() => {
  "use strict";
  const configs = {
    today:{title:"Today",description:"Your daily board, data health and shared exposure.",url:"today.html"},
    football:{title:"Weekly football",description:"NFL and college football forecasts, qualified plays and research leans.",url:"football.html"},
    moneyline:{title:"Moneyline",description:"NFL, college football and MLB. Just pick the winners.",url:"moneyline.html"},
    archive:{title:"Ticket archive",description:"Published picks, original prices and verified results.",url:"archive.html"},
    ledger:{title:"Shared ledger",description:"Your bets, bankroll and results across every board.",url:"ledger.html"},
    mlb:{title:"MLB Edge",description:"Baseball matchups, best bets and your game simulator.",url:"../mlb-edge/"},
    nfl:{title:"NFL Edge Lab",description:"NFL matchups, predictions and your season record.",url:"../nfl-edge-lab/"},
    ncaaf:{title:"NCAAF Edge Lab",description:"College football schedules, edges and simulations.",url:"../ncaaf-edge-lab/"},
    props:{title:"Props Edge",description:"NFL player props, the parlay lab and your props ledger.",url:"../props-edge/"},
  };
  const links=[...document.querySelectorAll(".board-link")];
  const workspace=document.querySelector("#workspace"), frames=new Map();
  let active="",ticketPending=false;
  function activate(key){
    const record=frames.get(key);
    if(!record)return;
    const target=new URL(configs[key].url,location.href);
    record.frame.contentWindow.postMessage({type:"kevbotbets:activate"},target.origin);
    // The boards already expose this operation. Reuse it on tab selection,
    // just as their normal focus/online handlers do; never copy credentials.
    if(key!=="ledger"&&key!=="today")try{
      const sync=record.frame.contentWindow.BetSync;
      if(sync?.loadConfig())sync.sync().catch(()=>{});
    }catch(_){/* Normal board timers remain available on a different origin. */}
    if(key==="today"&&ticketPending)try{
      if(typeof record.frame.contentWindow.makeKevbotTicket==="function"){
        ticketPending=false;const button=document.querySelector('#top-ten-ticket');button.disabled=true;button.setAttribute('aria-busy','true');
        Promise.resolve(record.frame.contentWindow.makeKevbotTicket()).catch(()=>{}).finally(()=>{button.disabled=false;button.removeAttribute('aria-busy');});
      }
    }catch(_){}
  }
  function requested(){let key=location.hash.slice(1).toLowerCase();if(key==="moneyling")key="moneyline";return Object.prototype.hasOwnProperty.call(configs,key)?key:"today";}
  function create(key){
    const config=configs[key], panel=document.createElement("section"), frame=document.createElement("iframe");
    panel.className="board-panel";panel.setAttribute("aria-label",config.title);panel.hidden=true;
    frame.className="board-frame";frame.title=config.title;frame.id="frame-"+key;
    const loading=document.createElement("div");loading.className="load-state";loading.setAttribute("role","status");
    const spinner=document.createElement("span");spinner.className="spinner";spinner.setAttribute("aria-hidden","true");
    const message=document.createElement("strong"), hint=document.createElement("p"), actions=document.createElement("div");
    actions.className="actions";actions.hidden=true;
    const retry=document.createElement("button");retry.className="tool";retry.textContent="Try again";
    const direct=document.createElement("a");direct.href=config.url;direct.target="_blank";direct.rel="noopener";direct.textContent="Open directly";
    actions.append(retry,direct);loading.append(spinner,message,hint,actions);panel.append(frame,loading);
    const record={panel,frame,loading,timer:null};
    function slow(){spinner.hidden=true;message.textContent="Taking longer than expected";hint.textContent="Check your connection, then try loading this board again.";actions.hidden=false;}
    record.reload=()=>{
      clearTimeout(record.timer);loading.hidden=false;spinner.hidden=false;actions.hidden=true;
      message.textContent="Opening "+config.title;hint.textContent="Getting your board ready…";
      record.timer=setTimeout(slow,20000);frame.src=config.url;
    };
    retry.addEventListener("click",record.reload);
    frame.addEventListener("load",()=>{
      try{
        if(frame.contentWindow.location.href==="about:blank")return;
        if(/site not found|page not found|404/i.test(frame.contentDocument?.title||"")){clearTimeout(record.timer);slow();return;}
      }catch(_){/* A board moved to a custom domain can still display normally. */}
      clearTimeout(record.timer);loading.hidden=true;
      if(active===key)activate(key);
    });
    frame.addEventListener("error",()=>{clearTimeout(record.timer);slow();});
    workspace.append(panel);record.reload();return record;
  }
  function select(){
    const key=requested(),changed=key!==active;
    if(changed&&active==="today")frames.get("today")?.frame.contentWindow.postMessage({type:"kevbotbets:deactivate"},location.origin);
    active=key;
    if(!frames.has(key))frames.set(key,create(key));
    frames.forEach((r,k)=>{r.panel.hidden=k!==key;});
    links.forEach(link=>{if(link.hash==="#"+key)link.setAttribute("aria-current","page");else link.removeAttribute("aria-current");});
    if(matchMedia('(max-width:760px)').matches){
      const nav=document.querySelector('.boards'),selected=links.find(link=>link.hash==='#'+key);
      if(selected){const a=selected.getBoundingClientRect(),b=nav.getBoundingClientRect();if(a.left<b.left)nav.scrollLeft-=b.left-a.left;else if(a.right>b.right)nav.scrollLeft+=a.right-b.right;}
    }
    document.querySelector("#board-title").textContent=configs[key].title;
    document.querySelector("#board-description").textContent=configs[key].description;
    document.title=configs[key].title+" · KEVBOTBETS";
    if(changed){
      document.querySelector("#announcement").textContent=configs[key].title+" selected";
      if(frames.get(key).loading.hidden)activate(key);
    }
  }
  window.addEventListener("hashchange",select);
  document.querySelector("#reload-board").addEventListener("click",()=>frames.get(active).reload());
  document.querySelector("#top-ten-ticket").addEventListener("click",()=>{
    ticketPending=true;
    if(requested()!=="today")location.hash="today";else activate("today");
  });
  const help=document.querySelector("#help-dialog");
  document.querySelector("#help").addEventListener("click",()=>help.showModal());
  document.querySelector("#close-help").addEventListener("click",()=>help.close());
  document.querySelector(".skip").addEventListener("click",event=>{event.preventDefault();frames.get(active).frame.focus();});
  select();
})();
