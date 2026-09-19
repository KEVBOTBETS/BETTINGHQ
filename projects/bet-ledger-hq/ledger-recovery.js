/* Dated, private browser backups. No connection credentials or model settings. */
(function(root,factory){const api=factory(typeof module==='object'?require('./betsync.js'):root.BetSync);if(typeof module==='object')module.exports=api;else root.KevRecovery=api;})(typeof self!=='undefined'?self:this,function(BS){
  const FORMAT='kevbot-ledger-backup',FENCE='restore-missing-only-v1';
  const secret=/token|secret|password|authorization|api.?key|credential|^__proto__$|^constructor$|^prototype$/i;
  function clean(value,depth=0){
    if(depth>30)throw Error('Backup nesting is too deep.');
    if(Array.isArray(value))return value.map(v=>clean(v,depth+1));
    if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).filter(([k])=>!secret.test(k)).map(([k,v])=>[k,clean(v,depth+1)]));
    return value;
  }
  function rows(input){
    if(!Array.isArray(input)||input.length>20000)throw Error('Backup must contain at most 20,000 ledger rows.');
    const seen=new Set();
    return input.map(r=>{
      if(!r||typeof r!=='object'||typeof r.id!=='string'||!r.id||typeof r.app!=='string'||!r.app||seen.has(r.id))throw Error('Backup contains missing or duplicate wager identifiers.');
      seen.add(r.id);
      if(!['Pending','Win','Loss','Push','Void'].includes(r.status))throw Error('Backup contains an invalid result.');
      for(const key of ['stake','price','line','pnl','closing_price','model_prob','edge'])if(r[key]!=null&&r[key]!==''&&!Number.isFinite(Number(r[key])))throw Error('Backup contains invalid numeric data.');
      if(Number(r.stake)<0)throw Error('Backup contains a negative stake.');
      return clean(BS.canonical(r));
    });
  }
  function create(input,scope,at){return {format:FORMAT,schema:1,scope,created_at:at,rows:rows(input)};}
  function validate(backup,scope){
    if(backup?.format!==FORMAT||backup.schema!==1||backup.scope!==scope||!Number.isFinite(Date.parse(backup.created_at)))throw Error('Use a KEVBOT ledger backup from this same sheet connection.');
    return create(backup.rows,scope,backup.created_at);
  }
  function plan(backup,current){
    const existing=new Map(current.map(r=>[r.id,r])),missing=[],present=[],deleted=[];
    for(const row of backup.rows){const here=existing.get(row.id);if(row.deleted||here?.deleted)deleted.push(row);else if(here)present.push(row);else missing.push({...row,updated_at:'',base_rev:FENCE});}
    return {missing,present,deleted};
  }
  function remember(storage,key,backup){
    let saved=JSON.parse(storage.getItem(key)||'[]');if(!Array.isArray(saved))saved=[];
    if(saved[0]&&BS.stable(saved[0].rows)===BS.stable(backup.rows))return saved;
    saved=[backup,...saved].slice(0,10);
    for(;;){try{storage.setItem(key,JSON.stringify(saved));return saved;}catch(e){if(saved.length<=1)throw e;saved.pop();}}
  }
  return {FORMAT,FENCE,clean,create,validate,plan,remember};
});
