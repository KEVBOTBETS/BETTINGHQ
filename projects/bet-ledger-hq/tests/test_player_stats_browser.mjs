import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve('../../_site');
const server=createServer(async(req,res)=>{const relative=new URL(req.url,'http://localhost').pathname.replace(/^\/BETTINGHQ/,'');const file=path.resolve(root,'.'+relative+(relative.endsWith('/')?'index.html':''));if(!file.startsWith(root+path.sep))return res.writeHead(403).end();try{res.setHeader('Content-Type',({'.mjs':'application/javascript','.js':'application/javascript','.css':'text/css','.json':'application/json','.woff':'font/woff','.svg':'image/svg+xml'})[path.extname(file)]||'text/html');res.end(await readFile(file));}catch{res.writeHead(404).end();}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;const browser=await chromium.launch({headless:true});
try{for(const sport of ['NBA','NHL'])for(const width of [320,1440]){
 const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.clock.setFixedTime(new Date('2026-11-12T22:00:00Z'));await context.route('https://**/*',r=>r.abort());
 let failed=false,mixed=false;const at='2026-11-12T21:30:00Z',metric=sport==='NBA'?'points':'shots';
 const rows=[['a','Alpha','A',12],['b','Beta','B',9],['z','Zero','A',0],['m','Missing','B',null]].map(([id,player,team,n])=>({id,player_id:id,player,position:'G',team,opponent:'OPP',role:'Expected starter',availability:'Participation conditional',status:'Pregame',stats:n==null?{}:{[metric]:n},stat_samples:{},samples:n==null?0:8}));
 await context.route('**/data/player-stats/**',route=>{const u=new URL(route.request().url());if(failed)return route.fulfill({status:503,body:'Unavailable'});const isManifest=u.pathname.endsWith('manifest.json'),day=u.pathname.endsWith('2026-11-13.json')?'2026-11-13':'2026-11-12';return route.fulfill({json:isManifest?{sport,generated_at:at,today:'2026-11-12',teams:['A','B'],days:['2026-11-12','2026-11-13'].map(day=>({day,file:day+'.json'})),coverage:{roster_teams:2,expected_teams:2}}:{sport,day,generated_at:mixed&&day==='2026-11-13'?'bad':at,rows}});});
 await page.goto(origin+'/BETTINGHQ/bet-ledger-hq/'+sport.toLowerCase()+'-stats.html',{waitUntil:'networkidle'});await page.locator('#stats-table tbody tr[data-player-id="a"]').waitFor();await page.evaluate(()=>document.fonts.ready);
 assert.equal(await page.locator('#stats-table tbody tr').count(),4);await page.locator('#stats-sort').selectOption(metric);await page.locator('#stats-direction').click();assert.match(await page.locator('#stats-table tbody tr').first().innerText(),/Alpha/);
 await page.locator('#stats-team').selectOption('A');assert.equal(await page.locator('#stats-table tbody tr').count(),2);await page.locator('#stats-search').fill('Zero');assert.match(await page.locator('#stats-table tbody').innerText(),/0\.0/);await page.locator('#stats-search').fill('');await page.locator('#stats-team').selectOption('all');
 mixed=true;await page.locator('#stats-date').selectOption('2026-11-13');await page.waitForFunction(()=>document.querySelector('#stats-status').textContent.includes('Still showing'));assert.equal(await page.locator('#stats-date').inputValue(),'2026-11-12');
 mixed=false;await page.locator('#stats-date').selectOption('2026-11-13');await page.waitForFunction(()=>document.querySelector('#stats-caption').textContent.includes('2026-11-13'));
 failed=true;await page.locator('#stats-refresh').click();await page.waitForFunction(()=>document.querySelector('#stats-status').textContent.includes('Keeping'));assert.equal(await page.locator('#stats-table tbody tr').count(),4);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));assert.deepEqual(errors,[]);assert.equal(await page.locator('.kb-tools').count(),0);
 if(width===1440){failed=false;await page.goto(origin+'/BETTINGHQ/bet-ledger-hq/#'+sport.toLowerCase()+'-stats');await page.frameLocator('#frame-'+sport.toLowerCase()+'-stats').locator('#stats-table tbody tr[data-player-id="a"]').waitFor();assert.equal(await page.getByRole('link',{name:sport+' player stats',exact:true}).getAttribute('aria-current'),'page');}
 await context.close();console.log(sport+' '+width+'px: filters, numeric sorting, zero/missing, routes, date version/outage guards passed');
}}finally{await browser.close();await new Promise(r=>server.close(r));}
