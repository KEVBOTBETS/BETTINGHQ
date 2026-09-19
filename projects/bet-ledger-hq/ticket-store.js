/* Private backup uses the existing sheet connection. No images, tokens or ledger rows. */
(function(root,factory){const api=factory(root);if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KevTicketStore=api;})(typeof window!=='undefined'?window:null,function(root){
  const LOCAL='kevbot.local-tickets.v1',META='kevbot.ticket-backups.v1',PREFIX='kevbot_ticket_v1_',LIMIT=100;
  const fields=['key','app','sport','event','eventId','player','playerId','side','home','away','version','start','when','day','pick','market','line','sourceLine','price','book','tier','score','quote','review','probability','source'];
  function clean(ticket){
    if(!ticket||!/^local-[a-zA-Z0-9-]{8,64}$/.test(ticket.id)||!/^\d{4}-\d{2}-\d{2}$/.test(ticket.day)||!Number.isFinite(Date.parse(ticket.published_at))||!Array.isArray(ticket.picks)||ticket.picks.length>10)throw Error('Invalid ticket snapshot.');
    const out={schema:1,id:ticket.id,day:ticket.day,published_at:ticket.published_at,picks:ticket.picks.map(r=>{if(!r||typeof r.pick!=='string'||!Number.isFinite(Number(r.price))||Math.abs(Number(r.price))<100)throw Error('Invalid ticket pick.');const row={};for(const k of fields)if(r[k]!==undefined)row[k]=r[k];return row;})};
    if(JSON.stringify(out).length>30000)throw Error('Ticket is too large to back up.');return out;
  }
  function valid(rows){return (Array.isArray(rows)?rows:[]).flatMap(r=>{try{return [clean(r)];}catch(_){return [];}});}
  function merge(a,b){const map=new Map();for(const t of [...a,...b])if(!map.has(t.id))map.set(t.id,t);return [...map.values()].sort((x,y)=>y.published_at.localeCompare(x.published_at)).slice(0,LIMIT);}
  function fromSettings(settings){return Object.entries(settings||{}).filter(([k])=>k.startsWith(PREFIX)&&!k.endsWith('_updated_at')).flatMap(([key,value])=>{try{const t=clean(JSON.parse(value));return key===PREFIX+t.id?[t]:[];}catch(_){return [];}});}
  function patch(local,settings){
    const remote=fromSettings(settings),combined=merge(local,remote),out={};
    for(const t of combined){const key=PREFIX+t.id,body=JSON.stringify(clean(t));if(settings[key]){let old;try{old=JSON.stringify(clean(JSON.parse(settings[key])));}catch(_){throw Error('A shared ticket is unreadable. Original data was preserved.');}if(old!==body)throw Error('A ticket ID contains different picks. Original data was preserved.');}else out[key]=body;}
    const keep=new Set(combined.map(t=>t.id));for(const t of remote)if(!keep.has(t.id))out[PREFIX+t.id]='';return {combined,settings:out};
  }
  function get(key,fallback){try{return JSON.parse(root.localStorage.getItem(key)||'null')??fallback;}catch(_){return fallback;}}
  function put(key,value){root.localStorage.setItem(key,JSON.stringify(value));}
  function list(){return valid(get(LOCAL,[]));}
  function save(ticket){const t=clean(ticket);put(LOCAL,merge([t],list()));return t;}
  let running=null;
  function sync(){if(running)return running;running=syncNow().finally(()=>{running=null;});return running;}
  async function syncNow(){
    const BS=root?.BetSync,cfg=BS?.loadConfig();if(!cfg)return {state:'unconfigured',tickets:list(),message:'Saved on this browser. Connect Ledger to back up tickets across devices.'};
    if(root.navigator?.onLine===false)return {state:'offline',tickets:list(),message:'Offline. Ticket backup will retry when this device reconnects.'};
    const bytes=await root.crypto.subtle.digest('SHA-256',new TextEncoder().encode(cfg.url+'\n'+cfg.token));
    const scope=Array.from(new Uint8Array(bytes)).map(x=>x.toString(16).padStart(2,'0')).join('');
    const metadata=get(META,{owners:{}});metadata.owners=metadata.owners||{};
    const local=list().filter(t=>!metadata.owners[t.id]||metadata.owners[t.id]===scope);
    for(const t of local)metadata.owners[t.id]=scope;put(META,metadata);
    const res=await BS.pullAll(cfg,''),plan=patch(local,res.settings||{});let settings=res.settings||{};
    if(Object.keys(plan.settings).length){const saved=await BS.pushRows(cfg,[],plan.settings);settings=saved.settings||{};const confirmed=new Set(fromSettings(settings).map(t=>t.id));for(const t of plan.combined)if(!confirmed.has(t.id))throw Error('The sheet did not confirm every backup. Your browser copy is retained.');}
    const remote=fromSettings(settings),all=merge(remote,list());for(const t of remote)metadata.owners[t.id]=scope;
    metadata.at=new Date().toISOString();put(LOCAL,all);put(META,metadata);
    return {state:'synced',tickets:all,sharedIds:remote.map(t=>t.id),at:metadata.at,message:'Tickets backed up to your connected sheet · latest 100 across devices.'};
  }
  return {clean,valid,merge,fromSettings,patch,list,save,sync,LIMIT,PREFIX};
});
