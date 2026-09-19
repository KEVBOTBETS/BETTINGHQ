/* Supplemental details use existing sheet settings, so no schema migration is required.
 * Each observed change has its own key: devices cannot replace each other's history.
 * This is an observation log, not a complete server audit or an undo operation. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KevLedgerDetails=api;})(typeof self!=='undefined'?self:this,function(){
  const fields=['stake','status','pnl','price','line','closing_price','deleted'];
  const encode=s=>encodeURIComponent(s);
  const closeKey=id=>'kevbot_close_v1_'+encode(id);
  function closing(settings,id){try{return JSON.parse(settings[closeKey(id)]||'null');}catch(_){return null;}}
  function changes(before,after){const out=[];for(const key of fields){const a=before?.[key]??null,b=after?.[key]??null;if(a!==b)out.push({field:key,from:a,to:b});}return out;}
  function observe(beforeRows,afterRows,observedAt,observer){
    const old=new Map(beforeRows.map(r=>[r.id,r]));return afterRows.flatMap(r=>{
      const previous=old.get(r.id);if(!previous)return [];const diff=changes(previous,r);if(!diff.length)return [];
      return [{id:r.id,event:r.event,selection:r.selection,at:r.updated_at||observedAt,observed_at:observedAt,device:r.device||'Unknown writer',observer,changes:diff}];
    });
  }
  function history(settings){return Object.entries(settings).filter(([key])=>key.startsWith('kevbot_history_v1_')&&!key.endsWith('_updated_at')).flatMap(([,v])=>{try{const row=JSON.parse(v);return row&&Array.isArray(row.changes)?[row]:[];}catch(_){return [];}}).sort((a,b)=>String(b.observed_at).localeCompare(String(a.observed_at)));}
  function historySetting(entry,unique){return {['kevbot_history_v1_'+unique]:JSON.stringify(entry)};}
  return {closeKey,closing,changes,observe,history,historySetting};
});
