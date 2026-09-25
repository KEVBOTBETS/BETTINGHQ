/* Event-scoped quotes and one calculation shared by screen, image and export. */
(function(root){
  'use strict';
  const norm=x=>String(x??'').toLowerCase().replace(/[^a-z0-9]+/g,'');
  const instant=x=>typeof x==='string'&&/(Z|[+-]\d\d:\d\d)$/.test(x)?Date.parse(x):NaN;
  const validPrice=x=>x!==null&&x!==''&&Number.isFinite(Number(x))&&Math.abs(Number(x))>=100;
  const decimal=x=>Number(x)>0?1+Number(x)/100:1+100/Math.abs(Number(x));
  const american=x=>x>=2?Math.round((x-1)*100):-Math.round(100/(x-1));
  const key=r=>[String(r.event_id??''),norm(r.player),norm(r.market),r.side,r.side==='yes'||r.side==='no'?'':r.line??''].join('|');
  function valid(q,leg,now=Date.now(),ageHours=12){
    if(!q||!leg||!/^\d+$/.test(String(q.event_id))||String(q.event_id)!==String(leg.event_id))return false;
    const at=instant(q.observed_at),start=instant(leg.start_time);
    return key(q)===key(leg)&&validPrice(q.price)&&Boolean(String(q.book||'').trim())&&at<=now&&at<start&&now-at<=ageHours*3600000&&start>now;
  }
  function apply(leg,imports,now=Date.now(),ageHours=12){
    const q=imports[key(leg)];
    if(!valid(q,leg,now,ageHours))return leg;
    return {...leg,price_american:Number(q.price),price_decimal:decimal(q.price),price_source:'book',book:q.book,updated_at:q.observed_at,imported:true};
  }
  function ticket(ticket,imports={},now=Date.now(),ageHours=12){
    const legs=ticket.legs.map(l=>apply(l,imports,now,ageHours));
    const dec=legs.reduce((x,l)=>x*decimal(l.price_american),1);
    const independent=legs.reduce((x,l)=>x*Number(l.model_prob),1);
    const sameGame=new Set(legs.map(l=>String(l.event_id))).size<legs.length;
    const estimated=legs.some(l=>l.price_source!=='book');
    return {legs,decimal:dec,american:american(dec),changed:legs.some(l=>l.imported),probability:sameGame?null:independent,independent,estimated,sameGame,payout:10*dec,ev:null,status:'research'};
  }
  const day=x=>Number.isFinite(Date.parse(x))?new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(x)):'';
  function csvRows(text){
    const out=[];let row=[],cell='',quoted=false;
    for(let i=0;i<String(text).length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(c===','&&!quoted){row.push(cell);cell='';}else if(c==='\n'&&!quoted){row.push(cell.replace(/\r$/,''));out.push(row);row=[];cell='';}else cell+=c;}
    if(cell||row.length){row.push(cell.replace(/\r$/,''));out.push(row);}return out;
  }
  function parseCsv(text,legs,now=Date.now(),ageHours=12){
    const rows=csvRows(text);if(!rows.length)return {};
    const header=rows.shift().map(norm),found={};
    for(const cells of rows){const get=name=>String(cells[header.indexOf(norm(name))]??'').trim();
      for(const side of ['over','under','yes','no']){
        const q={event_id:get('event_id'),player:get('player'),market:get('market'),side,line:['yes','no'].includes(side)?null:get('line')===''?null:Number(get('line')),price:get(side+'_odds'),book:get('book'),observed_at:get('observed_at')};
        const leg=legs.find(l=>key(l)===key(q));if(valid(q,leg,now,ageHours))found[key(q)]={...q,price:Number(q.price)};
      }
    }return found;
  }
  const api={key,valid,apply,ticket,day,decimal,american,validPrice,parseCsv};
  root.PropsQuotes=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
