(function(root,factory){const api=factory(typeof module==='object'?require('./moneyline-core.js'):root.Moneyline);if(typeof module==='object')module.exports=api;else root.WeeklyFootball=api;})(typeof self!=='undefined'?self:this,function(C){
  'use strict';
  function addDays(day,n){const d=new Date(day+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10);}
  function candidate(row,now,floor){
    const p=C.number(row.price),ev=C.number(row.ev),edge=C.number(row.action_edge);
    if(p===null||Math.abs(p)<100||ev===null||ev<=0||edge===null||edge<floor||row.held||row.odds_verified===false)return null;
    // Volume/correlation limits may expose a research alternative; data and
    // integrity failures must never be reopened by a display threshold.
    const why=String(row.filtered||'');
    const volume=/^(outside the top \d+ plays|correlated with a stronger play)/i.test(why);
    if(why&&!volume)return null;
    // A newly generated forecast does not prove its cached price is current.
    const quote=row.odds_observed_at,t=C.instant(quote);
    if(t===null||t>now+300000||now-t>4*3600000)return null;
    const tier=['BEST BET','GOOD','LEAN'].includes(row.tier)&&!why?row.tier:'RESEARCH LEAN';
    return {...row,display_tier:tier,research:tier==='RESEARCH LEAN',reason:why||row.warning||(tier==='RESEARCH LEAN'?'Below the model’s betting threshold':''),quote:quote||null};
  }
  function slate(sport,bundle,startDay,now=Date.now(),floor=.005){
    if(!/^\d{4}-\d{2}-\d{2}$/.test(startDay)||!Number.isFinite(Date.parse(startDay+'T12:00:00Z')))return [];
    const end=addDays(startDay,7),boards=new Map();
    for(const row of Array.isArray(bundle.board)?bundle.board:[]){
      const key=String(row.game_id);if(!boards.has(key))boards.set(key,[]);boards.get(key).push(row);
    }
    const details=new Map((bundle.details||bundle.games||[]).map(g=>[String(g.game_id),g]));
    return C.cards(sport,bundle,now).filter(c=>c.day>=startDay&&c.day<end).map(c=>{
      const d=details.get(c.id),projection=d?.projection||{};
      const suggestions=[];
      if(c.selectable&&!c.locked&&c.predicted){
        for(const market of ['ML','ATS','TOTAL']){
          const options=(boards.get(c.id)||[]).filter(r=>r.market===market).map(r=>candidate(r,now,floor)).filter(Boolean)
            .sort((a,b)=>Number(a.research)-Number(b.research)||b.action_edge-a.action_edge);
          if(options.length)suggestions.push(options[0]);
        }
      }
      return {...c,projection,suggestions};
    });
  }
  return {addDays,candidate,slate};
});
