/* Winner selections are independent of betting tiers, prices, and stake sizes. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.Moneyling=api;})(typeof self!=='undefined'?self:this,function(){
  'use strict';
  const number=v=>v===null||v===undefined||v===''||typeof v==='boolean'||!Number.isFinite(Number(v))?null:Number(v);
  const instant=v=>typeof v==='string'&&/(Z|[+-]\d\d:\d\d)$/i.test(v)&&Number.isFinite(Date.parse(v))?Date.parse(v):null;
  const probability=v=>{const n=number(v);return n!==null&&n>=0&&n<=1?n:null;};
  const day=v=>{const t=typeof v==='number'?v:instant(v);return t===null?'':new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(t));};
  function freshness(stamp,sport,now){const t=instant(stamp);return t===null||t>now+300000?'unknown':now-t>(sport==='ncaaf'?4:6)*3600000?'stale':'recent';}
  function cards(sport,bundle,now=Date.now()){
    const stamp=(sport==='mlb'?bundle.slate:bundle.meta)?.generated_at;
    const fresh=freshness(stamp,sport,now);
    const games=sport==='mlb'?bundle.slate?.games:bundle.games;
    const details=new Map((bundle.details||[]).map(g=>[String(g.game_id),g]));
    const seen=new Set(),out=[];
    for(const g of Array.isArray(games)?games:[]){
      const id=String(g.gamePk??g.game_id??''),key=sport+':'+id;
      if(!id||seen.has(key))continue;
      if(sport==='mlb'&&g.gameType&&!['R','F','D','L','W'].includes(g.gameType))continue;
      if(sport!=='mlb'&&![2,3].includes(Number(g.season_type)))continue;
      const detail=sport==='nfl'?details.get(id):g;
      const start=g.start||g.date,when=instant(start);
      if(when===null)continue;
      const home=typeof g.home==='object'?g.home.abbr:g.home,away=typeof g.away==='object'?g.away.abbr:g.away;
      if(!home||!away||home===away)continue;
      seen.add(key);
      const unavailable=!!(g.postponed||g.canceled||g.completed)||/postpon|cancel|suspend|final|progress/i.test(g.status||'')||['Live','Final'].includes(g.abstract);
      const locked=when<=now||unavailable;
      let pHome=sport==='mlb'?probability(g.sim?.p_home_final):probability(detail?.p_home);
      if(pHome===null&&sport==='mlb')pHome=probability(g.sim?.p_home);
      const mu=number(detail?.projection?.mu);
      const known=sport==='mlb'?pHome!==null:detail?.projection?.ratings_known===true&&(pHome!==null||mu!==null);
      // College feed currently exports the projected margin but no p_home.
      // Its symmetric win distribution chooses the same side as that margin.
      // Do not fabricate a confidence percentage from a betting tier.
      const signal=pHome!==null?pHome-.5:mu;
      const predicted=known&&signal!==null&&Math.abs(signal)>1e-9?(signal>0?'home':'away'):null;
      const usable=!locked&&!bundle.error&&fresh==='recent'&&known;
      const reason=locked?(unavailable?(g.status||'Unavailable'):'Started · locked'):bundle.error?'Feed unavailable':fresh!=='recent'?'Forecast '+fresh:!known?'Forecast unavailable':!predicted?'Too close to call':'';
      out.push({key,id,sport,start,when,day:day(start),home,away,homeName:g.home_name||detail?.home?.name||home,
        awayName:g.away_name||detail?.away?.name||away,stamp,fresh,locked,selectable:usable,
        predicted:usable?predicted:null,probability:usable&&predicted&&pHome!==null?(predicted==='home'?pHome:1-pHome):null,
        reason,notes:sport==='mlb'&&!g.lineups_confirmed?'Projected lineups':sport==='ncaaf'&&g.context?.availability?.status!=='available'?'Team availability not confirmed':'',
        conditionalProbability:sport==='nfl'});
    }
    return out.sort((a,b)=>a.when-b.when||a.key.localeCompare(b.key));
  }
  function choose(saved,card,side,now=Date.now()){
    if(!['home','away'].includes(side)||!card.selectable||card.locked||card.when<=now)return saved;
    const old=saved[card.key];
    if(old&&instant(old.start)!==null&&instant(old.start)<=now)return saved;
    return {...saved,[card.key]:{key:card.key,sport:card.sport,start:card.start,day:card.day,
      home:card.home,away:card.away,side,team:card[side],predicted:card.predicted?card[card.predicted]:null,
      forecast_at:card.stamp,selected_at:new Date(now).toISOString()}};
  }
  return {cards,choose,day,instant,number,freshness};
});
