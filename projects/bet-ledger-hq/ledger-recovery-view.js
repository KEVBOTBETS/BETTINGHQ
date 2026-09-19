(()=>{'use strict';
  const R=window.KevRecovery,BS=window.BetSync,esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function scopeFor(cfg){if(!cfg?.url)throw Error('Connect this device first.');const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(cfg.url));return [...new Uint8Array(hash)].map(v=>v.toString(16).padStart(2,'0')).join('');}
  function download(backup){const url=URL.createObjectURL(new Blob([JSON.stringify(backup,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='kevbot-ledger-'+backup.created_at.replace(/[:.]/g,'-')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  async function review(backup,scope,onRefresh){
    const cfg=BS.loadConfig();if(await scopeFor(cfg)!==scope)throw Error('Sheet connection changed. Reopen recovery.');
    const fresh=await BS.pullAll(cfg,''),safe=R.validate(backup,scope),plan=R.plan(safe,(fresh.rows||[]).map(BS.canonical));
    const supported=(fresh.features||[]).includes('undo-v2'),batch=plan.missing.slice(0,100);
    const dialog=document.createElement('dialog');dialog.className='recovery-dialog';dialog.setAttribute('aria-labelledby','recovery-title');
    dialog.innerHTML='<h2 id="recovery-title">Review ledger recovery</h2><p>Backup: '+esc(new Date(safe.created_at).toLocaleString())+'</p><p>'+plan.missing.length+' missing · '+plan.present.length+' already present · '+plan.deleted.length+' deleted records left untouched.</p><p>Only missing wager IDs can be restored. Existing results, stakes, deletions and bankroll settings will not be overwritten. Up to 100 missing records per review.</p><div class="scroll"><table><thead><tr><th>Pick</th><th>Stake</th><th>Result</th></tr></thead><tbody>'+batch.map(r=>'<tr><td>'+esc(r.selection)+'<br>'+esc(r.event)+'</td><td>'+esc(r.stake)+'</td><td>'+esc(r.status)+'</td></tr>').join('')+'</tbody></table></div><p class="note" data-recovery-status role="status">'+(supported?'Confirm only after reviewing these saved wagers.':'Downloads and previews work now. Restoring requires the existing safe-undo server upgrade.')+'</p>'+(!supported?'<p><a href="server-upgrade.html" target="_blank" rel="noopener">Enable safe recovery on your sheet</a></p>':'')+'<div class="recovery-actions"><button class="btn" data-cancel>Cancel</button><button class="btn primary" data-restore '+(!supported||!batch.length?'disabled':'')+'>Restore '+batch.length+' missing wagers</button></div>';
    document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove());dialog.querySelector('[data-cancel]').onclick=()=>dialog.close();
    let writing=false;dialog.addEventListener('cancel',e=>{if(writing)e.preventDefault();});
    dialog.querySelector('[data-restore]').onclick=async()=>{
      const status=dialog.querySelector('[data-recovery-status]'),button=dialog.querySelector('[data-restore]');button.disabled=true;writing=true;dialog.querySelector('[data-cancel]').disabled=true;
      try{
        if(await scopeFor(BS.loadConfig())!==scope)throw Error('Sheet connection changed. Nothing restored.');
        const latest=await BS.pullAll(cfg,'');if(!(latest.features||[]).includes('undo-v2'))throw Error('Safe recovery is not supported by this server.');
        const allowed=new Set(batch.map(r=>r.id)),next=R.plan(safe,(latest.rows||[]).map(BS.canonical)).missing.filter(r=>allowed.has(r.id));
        // The non-date base revision is deliberately impossible to match.
        // The server rejects a concurrent existing/deleted record under lock.
        const result=next.length?await BS.pushRows(cfg,next):{applied:0,conflicts:[]};
        status.textContent=(result.applied||0)+' missing wager(s) restored. '+(result.conflicts?.length||0)+' concurrent changes left untouched.';
        await onRefresh();
      }catch(e){status.textContent=BS.friendlyError(e)+' Reopen recovery to check the latest sheet before retrying.';}
      finally{writing=false;dialog.querySelector('[data-cancel]').disabled=false;dialog.querySelector('[data-cancel]').textContent='Close';}
    };
    dialog.showModal();
  }
  window.KevRecoveryView={async mount(host,state,onRefresh){
    if(!host||!state.loaded||state.sourceUrl!==BS.loadConfig()?.url)return;
    host.innerHTML='<h2>Ledger backups & recovery</h2><div class="card"><p class="note">Up to 10 distinct snapshots are saved on this browser after successful sheet reads. Download a dated copy to keep it outside this device. Backups contain personal wager history, not connection credentials. Imports always require a preview and confirmation.</p><div class="recovery-actions"><button class="btn" data-download-current>Download current ledger</button><label class="btn">Review backup file<input type="file" accept="application/json,.json" data-backup-file hidden></label></div><p class="note" data-backup-status role="status"></p><div data-local-backups></div></div>';
    const status=host.querySelector('[data-backup-status]');
    try{
      const cfg=BS.loadConfig(),scope=await scopeFor(cfg);
      if(state.sourceUrl!==cfg.url||BS.loadConfig()?.url!==cfg.url)return;
      const key='kevbot.ledger-backups.v1.'+scope,backup=R.create(state.rows,scope,state.lastSync||new Date().toISOString());
      if(!host.isConnected)return;
      host.querySelector('[data-download-current]').onclick=()=>download(backup);
      host.querySelector('[data-backup-file]').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>10000000)throw Error('Backup file exceeds 10 MB.');await review(JSON.parse(await file.text()),scope,onRefresh);}catch(err){status.textContent=err.message;}finally{e.target.value='';}};
      let saved=[];try{saved=R.remember(localStorage,key,backup);status.textContent='Last verified read: '+new Date(backup.created_at).toLocaleString()+'. '+saved.length+' local backup(s).';}catch(_){status.textContent='Browser backup storage is unavailable or full. Download the current ledger to keep a copy.';}
      const list=host.querySelector('[data-local-backups]');list.innerHTML=saved.map((b,i)=>'<div class="recovery-actions"><span class="note">'+esc(new Date(b.created_at).toLocaleString())+' · '+b.rows.length+' records</span><button class="btn sm" data-download="'+i+'">Download</button><button class="btn sm" data-review="'+i+'">Review recovery</button></div>').join('');
      list.querySelectorAll('[data-download]').forEach(b=>b.onclick=()=>download(saved[Number(b.dataset.download)]));
      list.querySelectorAll('[data-review]').forEach(b=>b.onclick=()=>review(saved[Number(b.dataset.review)],scope,onRefresh).catch(e=>status.textContent=e.message));
    }catch(e){status.textContent=e.message;}
  }};
})();
