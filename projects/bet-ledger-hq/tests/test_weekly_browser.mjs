import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve('../../_site');
const server=createServer(async(req,res)=>{
 const relative=new URL(req.url,'http://localhost').pathname.replace(/^\/portable\//,'/');
 const file=path.resolve(root,'.'+relative+(relative.endsWith('/')?'index.html':''));
 if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
 try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':'text/html');res.end(await readFile(file));}catch(_){res.writeHead(404).end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true});
try{
 await mkdir('test-results',{recursive:true});
 for(const width of [393,1440]){
  const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.clock.install({time:new Date('2026-09-19T12:00:00Z')});
  await page.route('https://**/*',route=>route.abort());
  let failed=false,metaRequests=0;
  await page.route('**/data/**',route=>{
   if(failed)return route.fulfill({status:503,body:'Unavailable'});
   const u=route.request().url();let data=[];
   if(u.endsWith('meta.json')){metaRequests++;data={generated_at:'2026-09-19T11:00:00Z'};}
   if(u.endsWith('games.json'))data=[{game_id:'1',date:'2026-09-20T17:00:00Z',season_type:2,home:'KC',away:'BUF',projection:{mu:3,ratings_known:true,score_home:24,score_away:21}}];
   if(u.endsWith('games_detail.json'))data=[{game_id:'1',projection:{mu:3,ratings_known:true,score_home:24,score_away:21},p_home:.6}];
   if(u.endsWith('board.json'))data=[{game_id:'1',market:'ATS',pick:'KC -2.5',price:-110,ev:.03,action_edge:.01,tier:'PASS',book:'Example',odds_observed_at:'2026-09-19T11:00:00Z'}];
   route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.goto('http://127.0.0.1:'+server.address().port+'/portable/bet-ledger-hq/#football');
  const frame=page.frameLocator('#frame-football');
  await frame.locator('#status').filter({hasText:'Forecasts checked'}).waitFor();
  assert.equal(await frame.locator('.match-card').count(),2);
  assert.equal(await frame.locator('.research').count(),2);
  await frame.locator('#date').fill('');
  await frame.locator('#date').dispatchEvent('change');
  await page.clock.fastForward(16000);
  assert.equal(await frame.locator('.match-card').count(),0);
  assert.match(await frame.locator('#cards').innerText(),/Choose a start date/);
  await frame.locator('#date').fill('2026-09-19');
  await frame.locator('#date').dispatchEvent('change');
  const requestsBefore=metaRequests;
  await Promise.all([
    page.waitForResponse(r=>r.url().endsWith('ncaaf-edge-lab/data/meta.json')),
    page.clock.fastForward(5*60*1000)
  ]);
  await frame.locator('#status').filter({hasText:'Forecasts checked'}).waitFor();
  assert.ok(metaRequests>requestsBefore,'Open weekly view must fetch newer published data automatically');
  assert.equal(await frame.locator('.research').count(),2);
  await frame.locator('#floor').fill('2');await frame.locator('#floor').dispatchEvent('change');
  assert.equal(await frame.locator('.research').count(),0);
  assert.equal(await frame.locator('.match-card').count(),2,'Winners remain visible independent of betting qualification');
  await frame.locator('#floor').fill('0.5');await frame.locator('#floor').dispatchEvent('change');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  const child=page.frames().find(f=>f.url().endsWith('football.html'));
  assert.ok(await child.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:'test-results/weekly-'+width+'.png',fullPage:true});
  failed=true;await frame.locator('#refresh').click();
  await frame.locator('#health').filter({hasText:'feed unavailable'}).waitFor();
  assert.equal(await frame.locator('.match-card').count(),0,'Failed feed must clear prior research suggestions');
  assert.deepEqual(errors,[]);
  await context.close();
 }
 console.log('Weekly browser: mobile/desktop, repository subpath, research threshold and failure handling passed');
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
