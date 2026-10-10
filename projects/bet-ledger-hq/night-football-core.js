/* Night selection follows the actual NFL schedule in Toronto time. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.NightFootball=api;})(typeof self!=='undefined'?self:this,function(){
  'use strict';
  const nights={thursday:{label:'Thursday Night Football',short:'TNF',weekday:'Thu'},sunday:{label:'Sunday Night Football',short:'SNF',weekday:'Sun'},monday:{label:'Monday Night Football',short:'MNF',weekday:'Mon'}};
  const number=v=>v===null||v===undefined||v===''||typeof v==='boolean'||!Number.isFinite(Number(v))?null:Number(v);
  const instant=v=>typeof v==='string'&&/(Z|[+-]\d\d:\d\d)$/i.test(v)&&Number.isFinite(Date.parse(v))?Date.parse(v):null;
  function local(value){const t=typeof value==='number'?value:instant(value);if(t===null||!Number.isFinite(t))return null;const p=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit',weekday:'short',hour:'2-digit',hourCycle:'h23'}).formatToParts(new Date(t)).map(p=>[p.type,p.value]));return {day:`${p.year}-${p.month}-${p.day}`,weekday:p.weekday,hour:Number(p.hour)};}
  function schedule(games,night,now=Date.now()){
    const config=nights[night]||nights.thursday,groups=new Map(),seen=new Set();
    for(const g of Array.isArray(games)?games:[]){const id=String(g.game_id??''),t=instant(g.date),p=local(g.date);
      if(!id||seen.has(id)||!p||p.weekday!==config.weekday||p.hour<18||g.canceled||g.postponed||t<now-8*86400000)continue;
      seen.add(id);if(!groups.has(p.day))groups.set(p.day,[]);groups.get(p.day).push(g);
    }
    return [...groups].sort(([a],[b])=>a.localeCompare(b)).map(([day,games])=>({day,games:games.sort((a,b)=>instant(a.date)-instant(b.date))}));
  }
  function defaultDate(dates,now=Date.now()){
    const today=local(now)?.day;if(!today)return '';
    const active=dates.find(d=>d.day===today)||[...dates].reverse().find(d=>d.games.some(g=>instant(g.date)<=now&&now<instant(g.date)+12*3600000));
    return active?.day||dates.find(d=>d.day>=today)?.day||'';
  }
  function fresh(stamp,now=Date.now(),hours=6){const t=instant(stamp);return t!==null&&t<=now&&now-t<=hours*3600000;}
  function eventId(row){return String(row.game_id??row.event_id??'');}
  function rowsFor(rows,games){const ids=new Set(games.map(g=>String(g.game_id)));return (Array.isArray(rows)?rows:[]).filter(r=>ids.has(eventId(r))&&(!r.sport||String(r.sport).toLowerCase()==='nfl'));}
  function quoteState(row,meta,now=Date.now(),error=false){
    const t=instant(row.game_date||row.start_time),price=number(row.price??row.price_american);
    if(error)return 'Refresh failed; last loaded snapshot';
    if(t===null)return 'Kickoff unavailable';
    if(t<=now)return 'Kickoff passed; betting locked';
    if(row.price_source==='model')return 'EST · model price, not a sportsbook quote';
    if(price===null||Math.abs(price)<100||!row.book)return 'Book price unavailable';
    if(!fresh(meta?.generated_at,now))return 'Forecast publication is stale or unknown';
    if(!fresh(row.odds_observed_at||row.updated_at,now,4))return 'Quote is stale or its time is unknown';
    if(row.odds_verified===false)return 'Quote unverified';
    if(row.held)return 'Held until betting window';
    return 'Fresh published quote';
  }
  function qualified(row,meta,now=Date.now(),error=false){if(row.value_policy){const V=typeof module==='object'?require('./value-core.js'):self.BetValue;if(!V.evaluate(row,{sport:row.player?'props':'nfl',publication:meta?.generated_at,now}).passes)return false;}return quoteState(row,meta,now,error)==='Fresh published quote'&&['LEAN','GOOD','BEST BET'].includes(row.tier)&&!row.filtered;}
  function ticketsFor(tickets,games){const ids=new Set(games.map(g=>String(g.game_id)));return (Array.isArray(tickets)?tickets:[]).filter(t=>Array.isArray(t.legs)&&t.legs.length>=2&&t.legs.every(l=>ids.has(eventId(l))));}
  function relatedNews(articles,games,now=Date.now()){
    const tokens=games.flatMap(g=>['home','away'].flatMap(side=>{const t=g[side];return typeof t==='object'?[t.name,t.short,t.abbr]:[g[side+'_name'],t];})).filter(v=>typeof v==='string'&&v.length>=3).map(v=>v.toLowerCase());
    return (Array.isArray(articles)?articles:[]).filter(a=>{const at=instant(a.published);return at!==null&&at<=now&&now-at<=7*86400000&&tokens.some(t=>[a.headline,...(a.teams||[])].join(' ').toLowerCase().includes(t));});
  }
  return {nights,number,instant,local,schedule,defaultDate,fresh,eventId,rowsFor,quoteState,qualified,ticketsFor,relatedNews};
});
