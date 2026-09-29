import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve('../../_site');
const server=createServer(async(req,res)=>{const url=new URL(req.url,'http://localhost');let file=path.resolve(root,'.'+decodeURIComponent(url.pathname));if(url.pathname.endsWith('/'))file=path.join(file,'index.html');if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':'text/html');res.end(await readFile(file));}catch(_){res.writeHead(404).end();}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const origin='http://127.0.0.1:'+server.address().port;
const meta=JSON.parse(await readFile(root+'/nhl-edge-lab/data/meta.json','utf8'));
const games=JSON.parse(await readFile(root+'/nhl-edge-lab/data/games.json','utf8'));
const game=games.find(g=>g.state==='pre'&&g.quotes?.length&&g.projection?.ratings_known);
assert.ok(game,'Live source snapshot contains an upcoming priced matchup');
const browser=await chromium.launch({headless:true});
try{
 await mkdir('test-results',{recursive:true});
 for(const width of [393,1440]){
  const context=await browser.newContext({viewport:{width,height:1000},serviceWorkers:'block'}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.clock.install({time:new Date(meta.generated_at)});
  await page.route('https://**/*',r=>r.abort());
  await page.goto(origin+'/nhl-edge-lab/');await page.locator('#health').filter({hasText:'Observed public data'}).waitFor();
  await page.locator('#date').fill(game.day);await page.locator('#date').dispatchEvent('change');
  const card=page.locator('[data-game="'+game.game_id+'"]');await card.locator('summary').click();
  assert.equal(await card.locator('.distribution span').count(),64);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:'test-results/nhl-'+width+'.png',fullPage:true});
  await card.locator('[data-bet]:enabled').first().click();await page.locator('#stake').fill('5');await page.getByRole('button',{name:'Save to my ledger'}).click();
  await page.getByRole('button',{name:'My bets',exact:true}).click();assert.match(await page.locator('#ledger-list').textContent(),/\$5.00/);
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('nhledge.ledger.v2')).entries.length),1);
  await page.getByRole('button',{name:'Team rankings',exact:true}).click();assert.equal(await page.locator('#standings-rows tr').count(),32);
  await page.locator('#conference').selectOption('Eastern Conference');assert.equal(await page.locator('#standings-rows tr').count(),16);
  for(const name of ['News & injuries','Model accuracy','Data & model'])await page.getByRole('button',{name,exact:true}).click();
  await page.goto(origin+'/bet-ledger-hq/#moneyline');let frame=page.frameLocator('#frame-moneyline');await frame.locator('#status').filter({hasText:'Forecasts checked'}).waitFor();
  await frame.locator('#date').fill(game.day);await frame.locator('#date').dispatchEvent('change');await frame.locator('#status').filter({hasText:'Forecasts checked'}).waitFor();
  await frame.locator('#sport').selectOption('nhl');assert.ok(await frame.locator('.sport-nhl').count()>0);
  await frame.getByRole('button',{name:'Use predicted winners',exact:true}).click();assert.ok(await frame.locator('.team-option[aria-pressed=true]').count()>0);
  await frame.getByRole('button',{name:'Make card',exact:true}).click();await frame.locator('#card-status').filter({hasText:/ML-/}).waitFor();
  const child=page.frames().find(f=>f.url().endsWith('moneyline.html'));assert.ok(await child.evaluate(()=>document.querySelector('#card-canvas').width===1080));
  await page.screenshot({path:'test-results/nhl-moneyline-'+width+'.png',fullPage:true});
  await page.goto(origin+'/nhl-edge-lab/');await page.locator('#health').filter({hasText:'Observed public data'}).waitFor();
  await page.route('**/nhl-edge-lab/data/meta.json',r=>r.fulfill({status:503,body:'Unavailable'}));
  await page.getByRole('button',{name:'↻ Refresh',exact:true}).click();await page.locator('#health').filter({hasText:'Refresh failed'}).waitFor();
  assert.equal(await page.locator('[data-bet]:enabled').count(),0);assert.deepEqual(errors,[]);
  await context.close();
 }
 console.log('NHL desktop/mobile, score map, all panels, local ledger, shared moneyline card and failed-feed lock passed');
}finally{await browser.close();await new Promise(r=>server.close(r));}
