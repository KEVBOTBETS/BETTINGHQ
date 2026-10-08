import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve('../../_site');
const server=createServer(async(req,res)=>{
  const name=new URL(req.url,'http://localhost').pathname;
  const file=path.resolve(root,'.'+name+(name.endsWith('/')?'index.html':''));
  if(!file.startsWith(root+path.sep))return res.writeHead(403).end();
  try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.json')?'application/json':file.endsWith('.css')?'text/css':'text/html');res.end(await readFile(file));}catch(_){res.writeHead(404).end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base='http://127.0.0.1:'+server.address().port,browser=await chromium.launch({headless:true});
try{
  for(const width of [393,1440]){
    const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'}),page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.clock.install({time:new Date('2026-10-08T16:00Z')});
    await page.route('https://**/*',r=>r.abort());
    let fail='',stamp='2026-10-08T15:00:00Z';
    const original=JSON.parse(await readFile(path.join(root,'nfl-edge-lab/data/meta.json'),'utf8'));
    await page.route('**/nfl-edge-lab/data/*.json*',async route=>{
      const name=new URL(route.request().url()).pathname.split('/').pop().replace('.json','');
      if(name===fail)return route.fulfill({status:503,body:'Unavailable'});
      if(name==='meta')return route.fulfill({contentType:'application/json',body:JSON.stringify({...original,generated_at:stamp})});
      return route.continue();
    });
    await page.goto(base+'/nfl-edge-lab/');
    await page.waitForFunction(()=>document.querySelector('#weeksel').value==='2:5');
    await page.locator('#weeksel').selectOption('2:6');
    fail='board';stamp='2026-10-08T15:30:00Z';
    await page.locator('#refresh-nfl').click();
    await page.waitForFunction(()=>document.querySelector('#refresh-status').textContent.includes('Refresh failed'));
    assert.equal(await page.evaluate(()=>S.meta.generated_at),'2026-10-08T15:00:00Z');
    assert.equal(await page.locator('#weeksel').inputValue(),'2:6');
    fail='';await page.locator('#refresh-nfl').click();
    await page.waitForFunction(()=>S.meta.generated_at==='2026-10-08T15:30:00Z');
    assert.equal(await page.locator('#weeksel').inputValue(),'2:6');
    // Reopening the iframe refreshes; it must not reset a selected week.
    stamp='2026-10-08T15:45:00Z';
    await page.evaluate(()=>window.postMessage({type:'kevbotbets:activate'},location.origin));
    await page.waitForFunction(()=>S.meta.generated_at==='2026-10-08T15:45:00Z');
    assert.equal(await page.locator('#weeksel').inputValue(),'2:6');
    let propsFail='',propsStamp='2026-10-08T15:00:00Z';
    await page.route('**/props-edge/data/*.json*',async route=>{
      const name=new URL(route.request().url()).pathname.split('/').pop().replace('.json','');
      if(name===propsFail)return route.fulfill({status:503,body:'Unavailable'});
      if(name==='meta'){
        const meta=JSON.parse(await readFile(path.join(root,'props-edge/data/meta.json'),'utf8'));
        return route.fulfill({contentType:'application/json',body:JSON.stringify({...meta,generated_at:propsStamp})});
      }
      return route.continue();
    });
    await page.goto(base+'/props-edge/#games');
    await page.waitForFunction(()=>window.PropsApp?.state.meta&&document.querySelector('#game-week')?.value==='2:5');
    const before=await page.evaluate(()=>({legs:PropsApp.state.legs.length,tickets:PropsApp.state.parlays.tickets.length}));
    assert(before.legs>0&&before.tickets>0);
    for(const file of ['legs','parlays']){
      propsFail=file;propsStamp='2026-10-08T15:30:00Z';
      await page.locator('#refresh-props').click();
      await page.waitForFunction(()=>document.querySelector('#freshness').textContent.includes('Refresh failed'));
      const after=await page.evaluate(()=>({legs:PropsApp.state.legs.length,tickets:PropsApp.state.parlays.tickets.length,at:PropsApp.state.meta.generated_at}));
      assert.deepEqual(after,{...before,at:'2026-10-08T15:00:00Z'});
    }
    propsFail='';await page.locator('#refresh-props').click();
    await page.waitForFunction(()=>PropsApp.state.meta.generated_at==='2026-10-08T15:30:00Z');
    assert.equal(await page.locator('#game-week').inputValue(),'2:5');
    assert.deepEqual(errors,[]);await context.close();
  }
  console.log('Refresh outage/recovery and current props week passed on desktop/mobile');
}finally{await browser.close();server.close();}
