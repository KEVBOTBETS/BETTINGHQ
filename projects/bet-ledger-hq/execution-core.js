/* Confirmed receipts are private sheet settings; legacy entries are never assumed placed. */
(function(root,factory){const api=factory(typeof module==='object'?require('./value-core.js'):root.BetValue);if(typeof module==='object'&&module.exports)module.exports=api;else root.BetExecution=api;})(typeof self!=='undefined'?self:this,function(V){
  'use strict';
  const key=id=>'kevbot_execution_v1_'+encodeURIComponent(id);
  const statuses=['Pending','Win','Loss','Push','Void'];
  function get(settings,id){try{const x=JSON.parse(settings[key(id)]||'null');const a=x?.accepted;return x?.schema===1&&x.id===id&&x.confirmed===true&&x.reference&&a&&V.decimal(a.price)!==null&&V.number(a.stake)>0&&statuses.includes(a.status)&&typeof a.book==='string'&&V.instant(a.placed_at)!==null?x:null;}catch{return null;}}
  function selectionLine(row){return V.selectionLine(row,({'nfl-lab':'nfl','ncaaf-lab':'ncaaf'})[row.app]||'other');}
  function snapshot(row,at){
    const n=row.native||{};
    return {captured_at:at,provenance:'Ledger reference captured when receipt first confirmed; not necessarily original publication',
      event:row.event,market:row.market,selection:row.selection,side:row.side,price:n.board_price??row.price,
      line:selectionLine({...row,line:n.board_line??row.line}),line_basis:'selection',book:row.book,model_prob:n.board_model_prob??row.model_prob,
      push_prob:n.push_prob??null,model_prob_no_push:n.model_prob_no_push??null,model_version:n.model_version??null};
  }
  function confirm(row,input,previous,at=new Date().toISOString()){
    const price=V.number(input.price),stake=V.number(input.stake),line=V.number(input.line),placed=V.instant(input.placed_at),book=String(input.book||'').trim();
    if(V.decimal(price)===null||!Number.isInteger(price))throw Error('Enter whole-number American odds of at least ±100.');
    if(stake===null||stake<=0)throw Error('Enter the stake actually accepted, greater than zero.');
    if(!book||book.length>120)throw Error('Enter the sportsbook that accepted your bet.');
    if(input.line!==''&&input.line!==null&&input.line!==undefined&&line===null)throw Error('Enter a valid line or leave it blank.');
    if(row.line!==null&&row.line!==undefined&&row.line!==''&&line===null)throw Error('Enter the accepted line for this contract.');
    if(placed===null||placed>Date.parse(at)+60000)throw Error('Enter the past time the sportsbook accepted your bet.');
    if(!statuses.includes(input.status))throw Error('Choose the actual receipt result.');
    return {schema:1,id:row.id,confirmed:true,reference:previous?.reference||snapshot(row,at),
      accepted:{price,stake:Math.round(stake*100)/100,line,book,placed_at:new Date(placed).toISOString(),status:input.status},
      confirmed_at:previous?.confirmed_at||at,updated_at:at};
  }
  function pnl(receipt){const a=receipt.accepted;if(a.status==='Pending')return null;return a.status==='Win'?a.stake*(V.decimal(a.price)-1):a.status==='Loss'?-a.stake:0;}
  function summary(rows,settings){
    const receipts=rows.filter(r=>!r.deleted).map(r=>get(settings,r.id)).filter(r=>r?.confirmed),settled=receipts.filter(r=>r.accepted.status!=='Pending');
    const staked=settled.filter(r=>r.accepted.status!=='Void').reduce((n,r)=>n+r.accepted.stake,0),profit=settled.reduce((n,r)=>n+(pnl(r)||0),0);
    return {count:receipts.length,settled:settled.length,staked,pnl:profit,roi:staked?profit/staked:null,
      exposure:receipts.filter(r=>r.accepted.status==='Pending').reduce((n,r)=>n+r.accepted.stake,0)};
  }
  function comparison(receipt){
    if(!receipt)return 'No accepted receipt confirmed';
    const a=receipt.accepted,r=receipt.reference;
    if(V.number(a.line)!==V.number(r.line))return 'Different line; forecast EV unavailable';
    const before=V.decimal(r.price),after=V.decimal(a.price);
    return before===null?'Reference price unavailable':after>before?'Better accepted price':after<before?'Worse accepted price':'Same accepted price';
  }
  function csv(rows,settings){
    const cols=['id','event','selection','market','reference_price','reference_line','accepted_price','accepted_line','accepted_book','accepted_stake','accepted_at','actual_status','actual_pnl','reference_captured_at'];
    const q=v=>{const s=String(v??'');return '"'+s.replace(/"/g,'""')+'"';};
    return [cols.join(',')].concat(rows.filter(r=>!r.deleted).flatMap(r=>{const x=get(settings,r.id);if(!x)return [];const a=x.accepted;return [[r.id,x.reference.event,x.reference.selection,x.reference.market,x.reference.price,x.reference.line,a.price,a.line,a.book,a.stake,a.placed_at,a.status,pnl(x),x.reference.captured_at].map(q).join(',')];})).join('\n');
  }
  return {key,get,selectionLine,snapshot,confirm,pnl,summary,comparison,csv};
});
