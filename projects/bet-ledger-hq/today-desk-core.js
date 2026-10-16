/* Game discovery and private research drafts. Qualification is never inferred. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KevTodayDesk=api;})(typeof window!=='undefined'?window:null,function(){
 'use strict';
 const instant=v=>Date.parse(v),validPrice=v=>v!==''&&v!=null&&Number.isFinite(Number(v))&&Math.abs(Number(v))>=100;
 const day=v=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(v));
 function games(data,{sport='all',period='week',now=Date.now()}={}){return (Array.isArray(data?.games)?data.games:[]).filter(g=>['nfl','ncaaf','nhl'].includes(g.sport)&&instant(g.start)>now&&instant(g.start)<now+7*86400000&&(sport==='all'||g.sport===sport)&&(period!=='today'||day(g.start)===day(now))).sort((a,b)=>instant(a.start)-instant(b.start)||String(a.id).localeCompare(String(b.id)));}
 function fresh(g,q,now=Date.now()){const at=instant(q?.observed_at);return validPrice(q?.price)&&!!q?.book&&q.fresh!==false&&Number.isFinite(at)&&at<=now&&now-at<=(g.sport==='nhl'?90:180)*60000&&instant(g.start)>now;}
 function qualified(g,q,now=Date.now()){const pub=instant(g.publication_at);return !!g.qualified&&!!q?.qualified&&fresh(g,q,now)&&pub<=now&&now-pub<=6*3600000;}
 const identity=(g,q)=>[g.id,q.market,q.side,q.line??''].join('|');
 function add(rows,g,q,{now=Date.now(),manual=false,price=q?.price,book=q?.book}={}){
  if(!g?.id||!['nfl','ncaaf','nhl'].includes(g.sport)||!(instant(g.start)>now)||!q?.pick||!q?.market||!q?.side)throw Error('Choose an upcoming game and a complete selection.');
  if(!validPrice(price)||!String(book||'').trim())throw Error('Enter American odds (+100 or higher, -100 or lower) and a sportsbook.');
  if(!manual&&!fresh(g,q,now))throw Error('This quote needs a fresh sportsbook confirmation.');
  if(rows.length>=8)throw Error('This draft holds up to eight selections.');
  if(rows.some(r=>r.game===g.id&&r.market===q.market))throw Error('This game and market are already in your draft. Remove the existing selection first.');
  return [...rows,{id:identity(g,q),game:g.id,sport:g.sport,event:g.matchup,start:g.start,pick:q.pick,market:q.market,side:q.side,line:q.line??null,price:Number(price),book:String(book).trim().slice(0,80),observed_at:manual?new Date(now).toISOString():q.observed_at,origin:manual?'User-confirmed sportsbook offer':'Published observed offer',qualified:false}];
 }
 function audit(rows,now=Date.now()){
  const warnings=[],books=new Set(rows.map(r=>r.book.toLowerCase()));
  if(new Set(rows.map(r=>r.game)).size<rows.length)warnings.push('Same-game legs: outcomes may depend on each other; use the sportsbook’s combined price.');
  if(books.size>1)warnings.push('Multiple sportsbooks: these prices cannot be combined into one offered parlay.');
  if(rows.some(r=>!(instant(r.start)>now)))warnings.push('A game has started. Remove its selection before using this draft.');
  if(rows.some(r=>!Number.isFinite(instant(r.observed_at))||instant(r.observed_at)>now||now-instant(r.observed_at)>(r.sport==='nhl'?90:180)*60000))warnings.push('A quote has expired. Remove and reconfirm that selection.');
  const decimal=rows.reduce((d,r)=>d*(r.price>0?1+r.price/100:1+100/Math.abs(r.price)),1);
  return {warnings,illustrative:rows.length>=2&&!warnings.length?Math.round((decimal-1)*100):null};
 }
 return {games,fresh,qualified,add,audit,day,validPrice};
});
