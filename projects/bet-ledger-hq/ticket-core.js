/* Frozen ticket math. Results are separate from original picks and actual wagers. */
(function(root,factory){const api=factory();if(typeof module==="object"&&module.exports)module.exports=api;if(root)root.KevTickets=api;})(typeof self!=="undefined"?self:this,function(){
  const n=v=>v==null||v===""||!Number.isFinite(Number(v))?null:Number(v);
  const validPrice=p=>n(p)!=null&&Math.abs(Number(p))>=100;
  function selectionKey(r){return [r.key,r.eventId,r.start,r.market,r.playerId||r.player||"",r.side||r.pick].join("|");}
  function outcomeKey(r){return selectionKey(r)+"|line="+(n(r.line)??"");}
  function profit(status,price){if(!validPrice(price))return null;return status==="Win"?(price>0?price/100:100/-price):status==="Loss"?-1:["Push","Void"].includes(status)?0:null;}
  function outcome(value,line,side){if(n(value)==null||n(line)==null||!["over","under"].includes(side))return null;return value===line?"Push":((value>line)===(side==="over")?"Win":"Loss");}
  function gradeScore(r,game){
    if(!game?.completed||String(game.id)!==String(r.eventId)||n(game.home)==null||n(game.away)==null)return null;
    if(game.start&&Math.abs(Date.parse(game.start)-Date.parse(r.start))>36*3600000)return null;
    const market=String(r.market).toUpperCase(),side=String(r.side).toLowerCase();
    if(["TOTAL","TOTALS","OU"].includes(market))return outcome(Number(game.home)+Number(game.away),n(r.line),side);
    if(!["ML","MONEYLINE","ATS","SPREAD","RL","RUNLINE"].includes(market)||!["home","away"].includes(side))return null;
    const mine=Number(side==="home"?game.home:game.away),other=Number(side==="home"?game.away:game.home);
    const spread=["ML","MONEYLINE"].includes(market)?0:n(r.line);if(spread==null)return null;
    return mine+spread===other?"Push":mine+spread>other?"Win":"Loss";
  }
  const PROP_STATS={
    player_pass_attempts:["passing","passingAttempts"],player_pass_completions:["passing","completions"],
    player_pass_yds:["passing","passingYards"],player_pass_tds:["passing","passingTouchdowns"],
    player_rush_yds:["rushing","rushingYards"],player_rush_attempts:["rushing","rushingAttempts"],
    player_reception_yds:["receiving","receivingYards"],player_receptions:["receiving","receptions"]
  };
  function gradeProp(r,summary){
    const event=summary?.header?.competitions?.[0];
    if(!event?.status?.type?.completed||String(summary.header.id)!==String(r.eventId))return null;
    const aliases={"Passing attempts":"player_pass_attempts","Pass attempts":"player_pass_attempts","Pass completions":"player_pass_completions","Passing yards":"player_pass_yds","Passing TDs":"player_pass_tds","Rushing yards":"player_rush_yds","Rush attempts":"player_rush_attempts","Receiving yards":"player_reception_yds","Receptions":"player_receptions"};
    const wanted=PROP_STATS[aliases[r.market]||r.market];if(!wanted)return null;
    const matches=[];
    for(const team of summary.boxscore?.players||[])for(const group of team.statistics||[]){
      if(group.name!==wanted[0])continue;
      const keys=group.keys||group.names||[];let ix=keys.indexOf(wanted[1]);
      const composite=wanted[1]==='passingAttempts'||wanted[1]==='completions';
      if(ix<0&&composite)ix=keys.indexOf('completions/passingAttempts');if(ix<0)continue;
      for(const entry of group.athletes||[]){const player=entry.athlete||{};
        const same=r.playerId?String(player.id)===String(r.playerId):String(player.displayName||"").toLowerCase()===String(r.player||"").toLowerCase();
        let value=entry.stats?.[ix];if(keys[ix]==='completions/passingAttempts')value=String(value).split('/')[wanted[1]==='passingAttempts'?1:0];
        if(same&&!entry.didNotPlay&&n(value)!=null)matches.push(n(value));
      }
    }
    if(matches.length!==1)return null;return outcome(matches[0],n(r.line),r.side);
  }
  function closing(r,quote){
    if(!quote||!validPrice(quote.price)||!quote.quote||Date.parse(quote.quote)>=Date.parse(r.start)||selectionKey(r)!==selectionKey(quote)||r.book!==quote.book)return null;
    const a=n(r.line),b=n(quote.line),same=a===b;
    const ip=p=>p>0?100/(p+100):-p/(-p+100);
    const side=String(r.side),market=String(r.market).toUpperCase();
    const movement=a==null||b==null?null:["TOTAL","TOTALS","OU"].includes(market)?side==="over"?b-a:side==="under"?a-b:null:a-b;
    return {line:b,price:quote.price,observed_at:quote.quote,book:quote.book,minutes_before_start:Math.round((Date.parse(r.start)-Date.parse(quote.quote))/60000),line_advantage:movement,price_advantage:same?ip(quote.price)-ip(r.price):null};
  }
  function performance(entries,dimension){
    const groups=new Map();
    const unique=new Map();
    for(const e of entries.slice().sort((a,b)=>String(a.published_at||" ").localeCompare(String(b.published_at||" ")))){const key=selectionKey(e.pick);if(!unique.has(key))unique.set(key,e);}
    for(const e of unique.values()){const r=e.pick,key=dimension?r[dimension]||"Unknown":"All picks";if(!groups.has(key))groups.set(key,{label:key,picks:0,wins:0,losses:0,pushes:0,voids:0,pending:0,units:0,risked:0,probabilityN:0,brierSum:0,calibration:[]});
      const g=groups.get(key);g.picks++;const result=e.result?.status||"Pending";const units=profit(result,r.price);
      if(result==="Win")g.wins++;else if(result==="Loss")g.losses++;else if(result==="Push")g.pushes++;else if(result==="Void")g.voids++;else g.pending++;
      if(units!=null)g.units+=units;if(["Win","Loss","Push"].includes(result))g.risked++;
      if(["Win","Loss"].includes(result)&&n(r.probability)!=null&&r.probability>=0&&r.probability<=1){g.probabilityN++;g.brierSum+=(r.probability-(result==="Win"?1:0))**2;}
    }
    return [...groups.values()].map(g=>({...g,roi:g.risked?g.units/g.risked:null,brier:g.probabilityN?g.brierSum/g.probabilityN:null}));
  }
  return {selectionKey,outcomeKey,profit,gradeScore,gradeProp,closing,performance,validPrice};
});
