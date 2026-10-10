import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import {createRequire} from 'node:module';
import path from 'node:path';
const require=createRequire(import.meta.url),V=require('../value-core.js'),root=path.resolve('../../_site');
const server=createServer(async(req,res)=>{let f=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(req.url.endsWith('/'))f=path.join(f,'index.html');try{res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.json':'application/json'})[path.extname(f)]||'text/html');res.end(await readFile(f));}catch{res.writeHead(404).end();}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port,browser=await chromium.launch({headless:true});
const stamp='2026-10-10T03:30:00Z',now=Date.parse('2026-10-10T04:00:00Z'),row={id:'nfl-lab:one',app:'nfl-lab',sport:'NFL',event:'AAA @ BBB',selection:'BBB -3.5',market:'ATS',side:'home',line:-3.5,price:-110,book:'Reference Book',stake:5,status:'Pending',placed_at:stamp,event_date:'2026-10-12',model_prob:.58};
try{for(const width of [1440,393]){
 const context=await browser.newContext({viewport:{width,height:1000},serviceWorkers:'block'}),page=await context.newPage(),errors=[];let settings={starting_bankroll:'100'},writes=[];
 page.on('pageerror',e=>errors.push(e.message));await page.clock.install({time:now});
 await context.addInitScript(()=>localStorage.setItem('betsync.config.v1',JSON.stringify({url:'https://script.google.com/macros/s/fixture/exec',token:'fixture',device:'Fixture'})));
 await context.route('https://**/*',async route=>{if(route.request().url().startsWith('https://script.google.com/')){const body=JSON.parse(route.request().postData());if(body.action==='push'){writes.push(body);settings={...settings,...body.settings};}return route.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,rows:[row],settings,full:true,server_time:new Date(now).toISOString()})});}return route.abort();});
 await page.goto(origin+'/bet-ledger-hq/ledger.html',{waitUntil:'networkidle'});await page.getByText('Confirmed actual bets',{exact:true}).waitFor();
 assert.match(await page.locator('#main').innerText(),/Confirmed receipts\s+0/i);
 const open=()=>page.getByText('Confirm or reconcile accepted bets',{exact:true}).click();await open();
 await page.getByLabel('Accepted odds',{exact:true}).fill('-120');await page.getByLabel('Actual stake',{exact:true}).fill('10');await page.getByLabel('Accepted sportsbook',{exact:true}).fill('Actual Book');
 await page.locator('[data-act="save-execution"]').click();await page.getByText('Worse accepted price',{exact:true}).waitFor({state:'attached'});assert.equal(writes.length,1);assert.deepEqual(writes[0].rows,[]);assert.match(await page.locator('#main').innerText(),/Actual open exposure\s+\$10/i);
 await open();await page.getByLabel('Actual result',{exact:true}).selectOption('Win');await page.locator('[data-act="save-execution"]').click();await page.waitForFunction(()=>document.querySelector('#main').textContent.includes('8.33'));
 const receipt=JSON.parse(settings['kevbot_execution_v1_'+encodeURIComponent(row.id)]);assert.equal(receipt.reference.price,-110);assert.equal(receipt.accepted.price,-120);assert.equal(receipt.accepted.status,'Win');
 await page.reload({waitUntil:'networkidle'});assert.match(await page.locator('#main').innerText(),/83\.3%/);await open();await page.getByLabel('Accepted odds',{exact:true}).fill('50');await page.locator('[data-act="save-execution"]').click();await page.locator('.execution-error').waitFor();assert.equal(writes.length,2);assert.equal(await page.getByLabel('Accepted odds',{exact:true}).inputValue(),'50');assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
 const g={game_id:'one',date:'2026-10-13T00:15:00Z',home:'BBB',away:'AAA',week:6},quote={...row,game_id:'one',game_date:g.date,odds_observed_at:stamp,tier:'GOOD'},board=[V.annotate(quote,'nfl',stamp,now),V.annotate({...quote,pick:'Bad price',price:-140},'nfl',stamp,now)];
 await page.route('**/nfl-edge-lab/data/*.json*',route=>{const file=new URL(route.request().url()).pathname.split('/').pop();return route.fulfill({contentType:'application/json',body:JSON.stringify(file==='meta.json'?{generated_at:stamp}:file==='board.json'?board:[g])});});
 await page.route('**/props-edge/data/*.json*',route=>{const file=new URL(route.request().url()).pathname.split('/').pop();return route.fulfill({contentType:'application/json',body:JSON.stringify(file==='meta.json'?{generated_at:stamp}:file==='parlays.json'?{tickets:[]}:[])});});
 await page.goto(origin+'/bet-ledger-hq/night-football.html?night=monday',{waitUntil:'networkidle'});assert.match(await page.locator('#night-lines').innerText(),/Minimum acceptable odds: -117/);assert.equal(await page.locator('#night-bets .night-card').count(),1);assert(!await page.locator('#night-bets').innerText().then(t=>t.includes('Bad price')));assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
 await mkdir('test-results/value-execution',{recursive:true});await page.screenshot({path:`test-results/value-execution/night-${width}.png`,fullPage:false});assert.deepEqual(errors,[]);await context.close();console.log(`Confirmed receipts, price retention, actual ROI and night stress gates passed at ${width}px`);
}}finally{await browser.close();await new Promise(r=>server.close(r));}
