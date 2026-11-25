import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {webcrypto} from 'node:crypto';
import {JSDOM} from 'jsdom';
const dom=new JSDOM('<section id="host"></section>',{url:'https://ledger.example',runScripts:'outside-only'}),w=dom.window;
const cfg={url:'https://test.invalid/exec'},rows=Array.from({length:12},(_,i)=>({id:'t'+i,app:'manual',updated_at:new Date(1700000000000+i).toISOString(),deleted:false,status:'Pending'}));let writes=0;
Object.defineProperty(w,'crypto',{value:webcrypto});w.TextEncoder=TextEncoder;w.URL.createObjectURL=()=> 'blob:test';w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=()=>{};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
w.BetSync={canonical:r=>({...r}),loadConfig:()=>cfg,pullAll:async()=>({features:['undo-v2'],rows}),friendlyError:String,pushRows:async(c,b)=>{assert.equal(c,cfg);writes++;for(const r of b){const old=rows.find(x=>x.id===r.id);assert.equal(r.base_rev,old.updated_at);assert.equal(r.deleted,true);old.deleted=true;}return {applied:b.length};}};
try{for(const name of ['ledger-recovery.js','ledger-recovery-view.js'])w.eval(await readFile(name,'utf8'));
const host=w.document.querySelector('#host');await w.KevRecoveryView.mount(host,{loaded:true,rows,lastSync:new Date().toISOString(),sourceUrl:cfg.url},async()=>{});
await host.querySelector('[data-start-fresh]').onclick({currentTarget:host.querySelector('[data-start-fresh]')});assert.equal(writes,0);
const dlg=w.document.querySelector('dialog');assert.match(dlg.textContent,/12 current bets/);rows.push({...rows[0],id:'later'});
await dlg.querySelector('[data-confirm]').onclick();assert.equal(writes,2);assert.equal(rows.at(-1).deleted,false);assert.match(dlg.textContent,/12 of 12 reviewed bets cleared. 1 active bet verified/);
console.log('Reset preview, revision-guarded batches, concurrent new wager and verified count passed');}finally{w.close();}
