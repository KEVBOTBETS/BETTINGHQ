/* Only explicit, fresh changes become alerts. Missing reports never mean healthy. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KevAlerts=api;})(typeof self!=='undefined'?self:this,function(){
  const num=v=>v==null||v===''||!Number.isFinite(Number(v))?null:Number(v);
  const recent=(time,now,hours)=>Number.isFinite(Date.parse(time))&&now-Date.parse(time)>=-300000&&now-Date.parse(time)<=hours*3600000;
  const key=r=>[r.key,r.eventId,r.start,r.market,r.playerId||r.player||'',r.side||r.pick,r.book].join('|');
  const price=v=>(v>0?'+':'')+v;
  function lineups(bundle,now){
    if(bundle?.error||!recent(bundle?.slate?.generated_at,now,6))return {};
    return Object.fromEntries((bundle.slate.games||[]).filter(g=>Date.parse(g.start)>now&&Date.parse(g.start)<now+8*86400000).map(g=>[String(g.gamePk),{
      event:g.away+' @ '+g.home,start:g.start,confirmed:g.lineups_confirmed===true,
      away:(g.away_lineup||[]).map(p=>p.name).filter(Boolean),home:(g.home_lineup||[]).map(p=>p.name).filter(Boolean),
      awayPitcher:g.away_sp?.name||'',homePitcher:g.home_sp?.name||'',published_at:bundle.slate.generated_at
    }]));
  }
  function injuries(data,sport,now){
    if(!data||!Array.isArray(data.injuries))return null;
    const out={};for(const team of data.injuries)for(const r of team.injuries||[]){
      if(!recent(r.date,now,72))continue;
      const name=r.athlete?.displayName;if(!name||!r.status)continue;
      out[sport+':'+String(team.id)+':'+String(r.athlete?.id||name)]={sport,team:team.displayName||'',player:name,status:String(r.status),detail:String(r.details?.type||r.shortComment||'').slice(0,180),report_at:r.date};
    }return out;
  }
  function scan(previous,input,at){
    const now=Date.parse(at),old=previous||{quotes:{},lineups:{},injuries:{}},state={quotes:{...(old.quotes||{})},lineups:{...(old.lineups||{})},injuries:{...(old.injuries||{})}},events=[];
    const emit=(kind,entity,body)=>events.push({id:[kind,entity,at].join('|'),kind,observed_at:at,...body});
    const tracked=new Map((input.tracked||[]).filter(r=>Date.parse(r.start)>now).map(r=>[key(r),r]));
    for(const q of input.quotes||[]){const id=key(q),pick=tracked.get(id);if(!pick)continue;const before=old.quotes?.[id]||pick;
      if(num(q.price)==null||Math.abs(q.price)<100)continue;
      if(num(before.price)!==num(q.price)||num(before.line)!==num(q.line))emit('odds',id,{sport:q.key,event:q.event,start:q.start,pick:pick.pick,title:'Published odds changed',before:price(before.price)+(before.line!=null?' · line '+before.line:''),after:price(q.price)+(q.line!=null?' · line '+q.line:''),book:q.book,source_quote_at:q.quote||null,source:'Existing '+q.source+' board',note:'Your ticket keeps its original odds. Recheck the live book before placing a new wager.'});
      state.quotes[id]={...q};
    }
    for(const [id,g] of Object.entries(input.lineups||{})){const before=old.lineups?.[id];
      if(before){
        if(g.confirmed&&!before.confirmed)emit('lineup',id,{sport:'mlb',event:g.event,start:g.start,title:'Batting orders confirmed',before:'Projected batting orders',after:'Confirmed batting orders',source_quote_at:g.published_at,source:'MLB board'});
        else if(g.confirmed&&before.confirmed&&(JSON.stringify(g.away)!==JSON.stringify(before.away)||JSON.stringify(g.home)!==JSON.stringify(before.home)))emit('lineup',id,{sport:'mlb',event:g.event,start:g.start,title:'Confirmed batting order changed',before:before.away.join(', ')+' / '+before.home.join(', '),after:g.away.join(', ')+' / '+g.home.join(', '),source_quote_at:g.published_at,source:'MLB board'});
        for(const side of ['away','home']){const k=side+'Pitcher';if(before[k]&&g[k]&&before[k]!==g[k])emit('starter',id+side,{sport:'mlb',event:g.event,start:g.start,title:'Probable starting pitcher changed',before:before[k],after:g[k],source_quote_at:g.published_at,source:'MLB board'});}
      }state.lineups[id]=g;
    }
    for(const [sport,reports] of Object.entries(input.injuries||{})){
      if(reports===null)continue;const hasBaseline=Object.prototype.hasOwnProperty.call(old.injuries||{},sport),before=old.injuries?.[sport]||{};
      for(const [id,r] of Object.entries(reports)){const prior=before[id];if(hasBaseline&&(!prior||prior.status!==r.status||prior.detail!==r.detail))emit('injury',id,{sport,title:prior?'Player availability changed':'New availability report',event:r.team,pick:r.player,before:prior?prior.status+(prior.detail?' · '+prior.detail:''):'Not in the previous dated report',after:r.status+(r.detail?' · '+r.detail:''),source_quote_at:r.report_at,source:'ESPN injuries',note:'A report is not a confirmed lineup. Missing or removed reports do not confirm a player is healthy.'});}
      state.injuries[sport]=reports;
    }
    for(const [id,q] of Object.entries(state.quotes))if(Date.parse(q.start)<now-86400000)delete state.quotes[id];
    for(const [id,g] of Object.entries(state.lineups))if(Date.parse(g.start)<now-86400000)delete state.lineups[id];
    return {state,events};
  }
  return {key,lineups,injuries,scan};
});
