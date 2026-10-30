(function(root){
  'use strict';
  const formats={five:[[1,5],[6,10],[11,15],[16,20],[21,25],[26,null]],ten:[[1,10],[11,20],[21,null]],wide:[[1,10],[11,null]]};
  const finite=x=>typeof x==='number'&&Number.isFinite(x);
  const time=x=>Date.parse(x);
  function cdf(x){if(x===Infinity)return 1;if(x===-Infinity)return 0;const z=Math.abs(x),t=1/(1+.2316419*z),v=1-Math.exp(-z*z/2)/Math.sqrt(2*Math.PI)*t*(.319381530+t*(-.356563782+t*(1.781477937+t*(-1.821255978+t*1.330274429))));return x>=0?v:1-v;}
  const day=at=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(at));
  function eligible(game,meta,now){
    const p=game.projection||{},start=time(game.tipoff),age=now-time(meta.generated_at),sourceAge=now-time(game.observed_at);
    return finite(age)&&age>=0&&age<=4*3600000&&finite(sourceAge)&&sourceAge>=0&&sourceAge<=4*3600000&&
      game.state==='pre'&&!game.completed&&!game.canceled&&!game.postponed&&!game.source_stale&&start>now&&start-now<=48*3600000&&
      p.ratings_known===true&&finite(p.mu)&&finite(p.margin_sd)&&p.margin_sd>0&&finite(p.p_home)&&p.p_home>0&&p.p_home<1&&game.home?.abbr&&game.away?.abbr;
  }
  function candidate(game,format='five'){
    if(!formats[format])throw Error('Unknown band format');
    const p=game.projection,side=p.p_home>=.5?'home':'away',win=side==='home'?p.p_home:1-p.p_home,mean=side==='home'?p.mu:-p.mu;
    // The existing baseline uses a continuous final-margin distribution. The
    // first integer band takes positive mass up to 5.5/10.5; no tie outcome is added.
    const rawWin=cdf(mean/p.margin_sd),bands=formats[format].map(([lo,hi])=>{
      const low=lo===1?0:lo-.5,high=hi===null?Infinity:hi+.5;
      const mass=cdf((high-mean)/p.margin_sd)-cdf((low-mean)/p.margin_sd);
      return {lo,hi,label:hi===null?lo+'+':lo+'–'+hi,prob:mass/rawWin*win};
    }).sort((a,b)=>b.prob-a.prob);
    return {event_id:String(game.game_id),tipoff:game.tipoff,matchup:game.away.abbr+' @ '+game.home.abbr,
      team:game[side].abbr,team_name:game[side].name||game[side].abbr,win_prob:win,margin:mean,
      home_points:p.proj_home_pts,away_points:p.proj_away_pts,bands,source_url:game.source_url};
  }
  function build(games,meta,{now=Date.now(),date=day(now),format='five'}={}){
    if(!formats[format])throw Error('Unknown band format');
    const seen=new Set(),pool=[];
    for(const g of games){if(!eligible(g,meta,now)||day(g.tipoff)!==date||seen.has(String(g.game_id)))continue;seen.add(String(g.game_id));const c=candidate(g,format);if(c.win_prob>=.6)pool.push(c);}
    pool.sort((a,b)=>b.bands[0].prob-a.bands[0].prob||a.event_id.localeCompare(b.event_id));
    const tickets=[];
    // Twelve games bound the combination search. At most one team/band per event.
    function search(start,legs,prob){
      if(legs.length>=3)tickets.push({legs:[...legs],prob,signature:legs.map(l=>l.event_id+':'+l.band.label).sort().join('|')});
      if(legs.length===4)return;
      for(let i=start;i<Math.min(pool.length,12);i++){
        const g=pool[i];for(const band of g.bands.slice(0,2)){
          if(band.prob<.1||band.prob<g.bands[0].prob*.7)continue;
          search(i+1,[...legs,{...g,band}],prob*band.prob);
        }
      }
    }
    search(0,[],1);tickets.sort((a,b)=>b.prob-a.prob||a.signature.localeCompare(b.signature));
    const chosen=tickets.slice(0,3),four=tickets.find(t=>t.legs.length===4&&!chosen.includes(t));
    if(four)chosen.push(four);else if(tickets[3])chosen.push(tickets[3]);
    return {pool,tickets:chosen,date,format,reason:pool.length<3?`Only ${pool.length} eligible teams meet the 60% win threshold. Three distinct upcoming games are required.`:chosen.length<3?'Fewer distinct combinations meet the band guards; no extra tickets were forced.':null};
  }
  const api={formats,cdf,day,eligible,candidate,build};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.NBABands=api;
})(typeof globalThis!=='undefined'?globalThis:this);
