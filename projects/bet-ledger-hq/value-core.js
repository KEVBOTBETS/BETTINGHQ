/* Price sensitivity policy, not a statistical confidence interval or profit claim. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.BetValue=api;})(typeof self!=='undefined'?self:this,function(){
  'use strict';
  const POLICY={version:'price-stress-v1',reserve:.03,minReturn:.02};
  const number=v=>v===null||v===undefined||v===''||typeof v==='boolean'||!Number.isFinite(Number(v))?null:Number(v);
  const decimal=a=>{a=number(a);return a===null||Math.abs(a)<100?null:1+(a>0?a/100:100/-a);};
  const american=d=>!(d>1)?null:Math.ceil((d>=2?(d-1)*100:-100/(d-1))-1e-9);
  const instant=v=>typeof v==='string'&&/(Z|[+-]\d\d(?::?\d\d)?)$/i.test(v)&&Number.isFinite(Date.parse(v))?Date.parse(v):null;
  const fresh=(v,now,hours)=>{const at=instant(v);return at!==null&&at<=now&&now-at<=hours*3600000;};
  function selectionLine(row,sport){const line=number(row.line);return line!==null&&['nfl','ncaaf'].includes(String(sport||row.sport||'').toLowerCase())&&row.market==='ATS'&&row.side==='away'?-line:line;}
  function probabilities(row,sport){
    sport=String(sport||row.sport||'').toLowerCase();
    const push=number(row.push_prob)??0,p=number(row.model_prob??row.p_final);
    if(push<0||push>=1||p===null||p<=0||p>=1)return null;
    const props=sport==='props'||!!row.player;
    const conditional=props?(number(row.model_prob_no_push)??p/(1-push)):p;
    // These publishers explicitly price football/NHL conditional on non-push.
    // Unknown push-bearing publishers require an explicit conditional field.
    if(push>0&&!props&&!['nfl','ncaaf','nhl'].includes(sport)&&number(row.model_prob_no_push)===null)return null;
    const q=number(row.model_prob_no_push)??conditional;
    if(q<=0||q>=1||(props&&Math.abs(q*(1-push)-p)>.0001))return null;
    return {conditional:q,push};
  }
  function evaluate(row,options={}){
    const now=options.now??Date.now(),sport=options.sport||row.sport,
      price=options.price??row.price_american??row.price,dec=decimal(price),p=probabilities(row,sport),
      start=instant(row.game_date||row.start_time||row.tipoff||row.start),
      quote=row.odds_observed_at||row.odds_fetched_at||row.updated_at,
      book=String(options.book??row.book??'').trim(),reasons=[];
    if(!p)reasons.push('Probability basis unavailable or inconsistent');
    if(dec===null||!book||/unspecified|unknown|unavailable/i.test(book)||row.price_source==='model'||row.odds_verified===false)reasons.push('Verified sportsbook price unavailable');
    if(start===null||start<=now)reasons.push('Kickoff passed or unavailable');
    if(!fresh(quote,now,4))reasons.push('Quote stale or observation time unavailable');
    if(options.publication!==undefined&&!fresh(options.publication,now,6))reasons.push('Forecast publication stale or unavailable');
    if(options.line!==undefined&&number(options.line)!==number(row.line))reasons.push('Changed line requires a new forecast');
    if(row.held)reasons.push('Held by source model');
    if(row.quote_status&&row.quote_status!=='observed')reasons.push('Retained quote requires current sportsbook confirmation');
    if(row.reference_only===true)reasons.push('Reference price requires current sportsbook confirmation');
    if(row.filtered)reasons.push(String(row.filtered));
    const stressed=p?Math.max(0,p.conditional-POLICY.reserve):null;
    const ev=p&&dec!==null?(1-p.push)*(p.conditional*dec-1):null;
    const stressEV=p&&dec!==null?(1-p.push)*(stressed*dec-1):null;
    const worst=p&&stressed>0?american((1+POLICY.minReturn/(1-p.push))/stressed):null;
    if(stressEV!==null&&stressEV<POLICY.minReturn-1e-10)reasons.push('Fails probability stress test or 2% return buffer');
    return {...POLICY,conditional:p?.conditional??null,push:p?.push??null,stressed,ev,stressEV,worst,
      passes:reasons.length===0,reasons};
  }
  function annotate(row,sport,publication,now=Date.now()){
    const out={...row},value=evaluate(row,{sport,publication,now});
    out.value_policy=value;out.source_tier=row.source_tier??row.tier;
    if(!value.passes){
      out.tier='PASS';if('game_prop_qualified' in out)out.game_prop_qualified=false;out.value_reason=value.reasons.join('; ');
      out.qualification=[row.qualification,out.value_reason].filter(Boolean).join(' · ');
      for(const k of ['stake','recommended_stake','stake_before_daily_cap'])if(k in out)out[k]=0;
    }
    return out;
  }
  return {POLICY,number,decimal,american,instant,fresh,selectionLine,probabilities,evaluate,annotate};
});
