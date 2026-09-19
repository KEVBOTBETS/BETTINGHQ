/* Read-only observations of published qualified picks. No model or wager writes. */
(function(root,factory){const api=factory(typeof module==='object'?require('./today-core.js'):root.KevToday);if(typeof module==='object')module.exports=api;else root.KevPickHistory=api;})(typeof self!=='undefined'?self:this,function(C){
  const id=r=>[r.key,r.eventId,r.start,r.market,r.playerId||r.player||'',r.side||r.pick].join('|');
  function observe(previous,bundles,at){
    const now=Date.parse(at),out=JSON.parse(JSON.stringify(previous||{schema:1,baselines:{},events:[]}));
    out.baselines=out.baselines||{};out.events=out.events||[];out.checked_at=at;
    for(const [sport,bundle] of Object.entries(bundles)){
      if(sport==='ladder')continue;
      const meta=bundle.meta||{},stamp=meta.generated_at||bundle.slate?.generated_at,h=C.health(sport,bundle,now);
      if(bundle.error||!['recent','review'].includes(h.status)||meta.errors?.length||meta.source_by_sport?.NFL?.errors?.length||meta.price_source_status==='unavailable')continue;
      const old=out.baselines[sport];if(old&&Date.parse(stamp)<=Date.parse(old.stamp))continue;
      const rows=C.topPlays(C.plays(sport,bundle,now),10000).map((r,i)=>({...r,rank:i+1}));
      const current=Object.fromEntries(rows.map(r=>[id(r),r]));
      if(old){
        for(const [key,row] of Object.entries(current)){
          const before=old.rows[key],changes=[];
          if(!before)changes.push({field:'qualified list',from:'Not in previous snapshot',to:'Listed'});
          else for(const field of ['price','line','book','tier','rank'])if((before[field]??null)!==(row[field]??null))changes.push({field,from:before[field]??null,to:row[field]??null});
          if(changes.length)out.events.unshift({id:[sport,stamp,key].join('|'),sport,observed_at:at,published_at:stamp,day:row.day,event:row.event,pick:row.pick,changes});
        }
        for(const [key,row] of Object.entries(old.rows))if(!current[key]&&Date.parse(row.start)>now)out.events.unshift({id:[sport,stamp,key,'absent'].join('|'),sport,observed_at:at,published_at:stamp,day:row.day,event:row.event,pick:row.pick,changes:[{field:'qualified list',from:'Listed',to:'Not in current snapshot; see board for reason'}]});
      }
      out.baselines[sport]={stamp,rows:current};
    }
    out.events=out.events.filter(e=>now-Date.parse(e.observed_at)<30*86400000).sort((a,b)=>b.observed_at.localeCompare(a.observed_at)).slice(0,500);
    return out;
  }
  return {id,observe};
});
