import assert from 'node:assert/strict';
import http from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright';
const root=path.resolve('../..'),at='2026-10-30T16:00:00Z';let fail=false;
const games=Array.from({length:6},(_,i)=>({game_id:String(i),tipoff:'2026-10-30T23:00:00Z',observed_at:at,state:'pre',home:{abbr:'HOME'+i,name:'Home '+i},away:{abbr:'AWAY'+i},projection:{ratings_known:true,mu:1,margin_sd:12,p_home:.5332}}));
const server=http.createServer(async(req,res)=>{
 const p=new URL(req.url,'http://localhost').pathname;
 if(p.endsWith('/data/games.json')||p.endsWith('/data/meta.json')){if(fail)return res.writeHead(503).end();res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(p.endsWith('games.json')?games:{generated_at:at}));}
 try{const mapped=p.startsWith('/NBA/')?'projects/nba-edge-lab/site/'+p.slice(5):p.startsWith('/NCAAB/')?'projects/ncaab-edge-lab/site/'+p.slice(7):p.startsWith('/nba-edge-lab/')?'projects/nba-edge-lab/site/'+p.slice(14):null;if(!mapped)throw Error('Unknown fixture path');res.setHeader('Content-Type',p.endsWith('.js')?'application/javascript':p.endsWith('.css')?'text/css':'text/html');res.end(await readFile(path.join(root,mapped)));}catch{res.writeHead(404).end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch();
try{for(const league of ['NBA','NCAAB'])for(const width of [393,1440]){
 fail=false;const context=await browser.newContext({viewport:{width,height:1000}}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.clock.install({time:new Date(at)});
 await page.goto(`http://127.0.0.1:${server.address().port}/${league}/bands.html`,{waitUntil:'networkidle'});
 await page.locator('.band-ticket').first().waitFor();assert.equal(await page.locator('.band-ticket').count(),4);assert.match(await page.locator('.band-ticket').first().innerText(),/Highest estimated chance/i);assert.match(await page.locator('.band-ticket').first().innerText(),/53.3%/);assert.match(await page.locator('.band-ticket').first().innerText(),/Band hit/);assert.ok(await page.locator('.band-ticket').last().locator('li').count()<=4);assert.match(await page.locator('#coverage-note').innerText(),/6 of 6/);
 await page.selectOption('#format','wide');assert.match(await page.locator('#games').innerText(),/11\+/);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await mkdir('test-results/basketball-bands',{recursive:true});await page.screenshot({path:`test-results/basketball-bands/${league}-${width}.png`,fullPage:true});
 fail=true;await page.click('#refresh');await page.waitForFunction(()=>!document.querySelector('#refresh').disabled);assert.equal(await page.locator('.band-ticket').count(),0);assert.match(await page.locator('#tickets').innerText(),/paused/);
 // Returning to the hub tab recovers a temporary failure without a manual refresh.
 fail=false;await page.clock.runFor(31000);await page.evaluate(()=>window.postMessage({type:'kevbotbets:activate'},location.origin));await page.locator('.band-ticket').first().waitFor();
 await page.clock.setSystemTime(new Date('2026-10-30T23:01Z'));await page.selectOption('#format','five');assert.equal(await page.locator('.band-ticket').count(),0);assert.deepEqual(errors,[]);await context.close();console.log(`${league} bands ${width}px: below-60% tickets, formats, coverage, no overflow, activation recovery and kickoff lock passed`);
}}finally{await browser.close();server.close();}
