import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve('../../_site'),out=path.resolve('test-results/nfl-stats');await mkdir(out,{recursive:true});
const server=createServer(async(req,res)=>{
 const pathname=new URL(req.url,'http://localhost').pathname.replace(/^\/BETTINGHQ(?=\/)/,'');
 let f=path.resolve(root,'.'+pathname);if(pathname.endsWith('/'))f=path.join(f,'index.html');
 try{res.setHeader('Content-Type',({'.mjs':'application/javascript','.js':'application/javascript','.css':'text/css','.json':'application/json','.woff':'font/woff','.svg':'image/svg+xml'})[path.extname(f)]||'text/html');res.end(await readFile(f));}
 catch{res.writeHead(404).end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({headless:true});
try{for(const width of [320,393,1440]){
 const context=await browser.newContext({viewport:{width,height:1000},serviceWorkers:'block'}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));await context.route('https://**/*',r=>r.abort());
 let badWeek=false,failed=false,stale=false,week12Requests=0;
 const rows=[['a','Alpha Player','1','QB',{pass_yds:100,pass_att:32.5}],['b','Beta Player','2','QB',{pass_yds:99}],['c','Zero Receiver','1','WR',{receptions:0,rec_yds:0}],['d','Lineman Player','1','OT',{}],['e','Defender Player','2','LB',{tackles:8.3,sacks:.3}],['f','Kicker Player','2','K',{fg_made:1.9}],['g','Punter Player','1','P',{punts:4.3,punt_yds:190}]].map(([id,player,team_id,position,stats])=>({id,player_id:id,player,team_id,team:team_id==='1'?'Alfa':'Beta',team_abbreviation:team_id==='1'?'ALF':'BET',position,stats,stat_samples:{},samples:Object.keys(stats).length?8:0,status:Object.keys(stats).length?'Projection · conditional role':'No supported individual stat history',availability:'Active',opponent:'OPP',venue:'Home',week:11,season:2026}));
 const stamp=()=>new Date(Date.now()-(stale?8*3600000:0)).toISOString();let generation=stamp();
 const manifest=()=>({generated_at:generation,season:2026,current_week:11,roster_teams:['1','2'],teams:[{id:'1',name:'Alfa'},{id:'2',name:'Beta'}],missing_roster_teams:[],weeks:Array.from({length:18},(_,i)=>({week:i+1,file:`week-${String(i+1).padStart(2,'0')}.json`,phase:i+1<11?'past':i+1===11?'current':'early'}))});
 await context.route('**/props-edge/data/nfl-weekly/**',async route=>{
  const url=new URL(route.request().url());if(url.pathname.endsWith('manifest.json')){if(failed)return route.fulfill({status:503,body:'Unavailable'});generation=stamp();return route.fulfill({json:manifest()});}
  const week=Number(url.pathname.match(/week-(\d+)/)?.[1]);if(week===12)week12Requests++;
  return route.fulfill({json:{generated_at:badWeek&&week===12?'wrong-version':generation,season:2026,week,rows:week<11?[]:rows.map(r=>({...r,week,stats:r.id==='a'&&week===12?{pass_yds:210}:r.stats}))}});
 });
 await page.addInitScript(()=>localStorage.setItem('kevbot-nfl-weekly-view-v1',JSON.stringify({week:6})));
 await page.goto(origin+'/BETTINGHQ/bet-ledger-hq/nfl-stats.html',{waitUntil:'networkidle'});
 await page.locator('#stats-table tbody tr[data-player-id="a"]').waitFor();assert.equal(await page.locator('#stats-week').inputValue(),'11');assert.equal(week12Requests,0);assert.equal(await page.locator('.kb-tools').count(),0);
 await page.locator('#stats-sort').selectOption('pass_yds');await page.locator('#stats-direction').click();assert.match(await page.locator('#stats-table tbody tr').first().innerText(),/Alpha Player/);
 await page.locator('#stats-position').selectOption('OT');assert.match(await page.locator('#stats-table tbody').innerText(),/Lineman Player/);assert.ok(await page.locator('.stats-missing').count());
 await page.locator('#stats-position').selectOption('all');await page.locator('#stats-team').selectOption('2');assert.equal(await page.locator('#stats-table tbody tr').count(),3);
 await page.locator('#stats-team').selectOption('all');await page.locator('#stats-search').fill('Zero Receiver');assert.match(await page.locator('#stats-table tbody').innerText(),/0\.0/);await page.locator('#stats-search').fill('');
 await page.locator('#stats-view').selectOption('special');assert.match(await page.locator('#stats-table thead').innerText(),/Punts/);
 badWeek=true;await page.locator('#stats-week').selectOption('12');await page.waitForFunction(()=>document.querySelector('#stats-status').textContent.includes('Still showing Week 11'));assert.equal(await page.locator('#stats-week').inputValue(),'11');assert.match(await page.locator('#week-summary').innerText(),/W11/);
 badWeek=false;await page.locator('#stats-week').selectOption('12');await page.waitForFunction(()=>document.querySelector('#week-summary').textContent.includes('W12'));assert.ok(week12Requests>=2);
 failed=true;await page.locator('#stats-refresh').click();await page.waitForFunction(()=>document.querySelector('#stats-status').textContent.includes('Keeping Week 12'));assert.match(await page.locator('#stats-table tbody').innerText(),/Alpha Player/);
 failed=false;stale=true;await page.locator('#stats-refresh').click();await page.waitForFunction(()=>document.querySelector('#stats-status').textContent.includes('stale or uncertain'));
 await page.locator('#stats-week').selectOption('1');await page.waitForFunction(()=>document.querySelector('#stats-table tbody').textContent.includes('No pregame forecast'));
 await page.locator('#stats-week').selectOption('11');await page.waitForFunction(()=>document.querySelector('#week-summary').textContent.includes('W11'));
 const dimensions=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));assert.ok(dimensions.scroll<=dimensions.width+2,`overflow at ${width}`);assert.deepEqual(errors,[]);
 await page.screenshot({path:`${out}/weekly-${width}.png`,fullPage:false});
 if(width===1440){await page.goto(origin+'/BETTINGHQ/bet-ledger-hq/#nfl-stats',{waitUntil:'networkidle'});await page.frameLocator('#workspace iframe').locator('#stats-table tbody tr[data-player-id=\"a\"]').waitFor();assert.equal(await page.getByRole('link',{name:'NFL player stats',exact:true}).getAttribute('aria-current'),'page');}
 await context.close();console.log(`NFL weekly stats ${width}px: current week, filters, zero/missing, sorts, lazy weeks, outages and stale snapshots passed`);
}}finally{await browser.close();await new Promise(r=>server.close(r));}
