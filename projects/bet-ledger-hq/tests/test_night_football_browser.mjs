import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve('../../_site'),out=path.resolve('test-results/night-football');await mkdir(out,{recursive:true});
const server=createServer(async(req,res)=>{const pathname=new URL(req.url,'http://localhost').pathname;let f=path.resolve(root,'.'+pathname);if(pathname.endsWith('/'))f=path.join(f,'index.html');try{res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.woff':'font/woff'})[path.extname(f)]||'text/html');res.end(await readFile(f));}catch{res.writeHead(404).end();}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port,browser=await chromium.launch({headless:true});
const meta={generated_at:'2026-10-08T18:30Z'},game=(id,date,week=5)=>({game_id:id,date,week,season_type:2,home:{abbr:'DAL',name:'Dallas Cowboys'},away:{abbr:'TB',name:'Tampa Bay Buccaneers'},projection:{score_home:24,score_away:21},broadcast:'Network',status:'Scheduled'});
const games=[game('thu','2026-10-09T00:15Z'),game('day','2026-10-08T17:00Z'),game('sun','2026-10-12T00:20Z'),game('afternoon','2026-10-11T20:25Z'),game('mon1','2026-10-12T23:00Z'),game('mon2','2026-10-13T00:15Z'),game('next','2026-10-16T00:15Z',6)];
const board=games.map(g=>({game_id:g.game_id,game_date:g.date,market:'ATS',side:'home',line:-3,price:-110,book:'Book',pick:g.game_id+' HOME -3',model_prob:.57,tier:'GOOD',action_edge:.03,odds_observed_at:'2026-10-08T18:30Z'}));
const legs=games.map(g=>({event_id:g.game_id,start_time:g.date,player:g.game_id+' Player',pick:g.game_id+' Player Over 50.5 Receiving yards',market:'Receiving yards',side:'over',line:50.5,price_american:-110,price_source:'book',book:'Book',model_prob:.6,tier:'LEAN',updated_at:'2026-10-08T18:30Z'}));
const tickets=[{id:'thu-ticket',label:'Thursday only',profile:'longshot',legs:[legs[0],{...legs[0],player:'Second Player',pick:'Second Player Over 20.5'}],price_american:1000},{id:'mixed-ticket',label:'MIXED NIGHT MUST NOT APPEAR',legs:[legs[0],legs[2]]},{id:'monday-ticket',label:'Monday doubleheader',legs:[legs[4],legs[5]]}];
const news={schema:1,events:Object.fromEntries(games.map(g=>[g.game_id,{articles:[{headline:g.game_id+' matchup headline',published:'2026-10-08T17:00Z',observed_at:'2026-10-08T18:30Z',url:'https://www.espn.com/'+g.game_id}]}]))};
try{
 for(const width of [1440,393]){
  const context=await browser.newContext({viewport:{width,height:1000},serviceWorkers:'block'}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.clock.install({time:new Date('2026-10-08T19:00Z')});await page.route('https://**/*',r=>r.abort());let failNFL=false,failProps=false,malformedNFL=false;
  await page.route('**/data/*.json*',route=>{
   const u=new URL(route.request().url()),name=u.pathname.split('/').pop().replace('.json','');let data;
   if(u.pathname.includes('nfl-edge-lab')){if(failNFL)return route.fulfill({status:503,body:'offline'});data={meta,games:malformedNFL?[null]:games,games_detail:games,board}[name];}
   if(u.pathname.includes('props-edge')){if(failProps)return route.fulfill({status:503,body:'offline'});data={meta,legs,board:legs,parlays:{tickets}}[name];}
   return data?route.fulfill({contentType:'application/json',body:JSON.stringify(data)}):route.continue();
  });
  await page.route('**/data/newsletters/nights.json*',r=>r.fulfill({contentType:'application/json',body:JSON.stringify(news)}));
  for(const [night,expected] of [['thursday',1],['sunday',1],['monday',2]]){
   await page.goto(base+'/bet-ledger-hq/night-football.html?night='+night);await page.waitForFunction(()=>document.querySelector('#night-status').textContent.includes('files checked'));
   assert.equal(await page.locator('#night-games .night-card').count(),expected);
   assert.equal(await page.locator('#night-news .night-card').count(),expected);
   assert.equal(await page.locator('#night-lines tbody tr').count(),expected);
   assert.equal(await page.locator('#night-props tbody tr').count(),expected);
   assert.equal(await page.locator('#night-bets .night-card').count(),expected*2);
   assert.doesNotMatch(await page.locator('#night-parlays').innerText(),/MIXED NIGHT/);
   assert.equal(await page.locator('#night-parlays .night-card').count(),night==='sunday'?0:1);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
   await page.screenshot({path:`${out}/${night}-${width}.png`,fullPage:true});
  }
  await page.goto(base+'/bet-ledger-hq/night-football.html?night=thursday');await page.waitForFunction(()=>document.querySelector('#night-bets .night-card'));
  failNFL=true;failProps=true;await page.locator('#night-refresh').click();await page.waitForFunction(()=>document.querySelector('#night-status').textContent.includes('A feed failed'));
  assert.equal(await page.locator('#night-games .night-card').count(),1);assert.equal(await page.locator('#night-bets .night-card').count(),0);assert.match(await page.locator('#night-lines').innerText(),/Refresh failed/);
  failNFL=false;failProps=false;await page.locator('#night-refresh').click();await page.waitForFunction(()=>document.querySelectorAll('#night-bets .night-card').length===2);
  failNFL=true;await page.locator('#night-refresh').click();await page.waitForFunction(()=>!document.querySelector('#night-refresh').disabled);assert.equal(await page.locator('#night-bets .night-card').count(),0);assert.equal(await page.locator('#night-props tbody tr').count(),1);
  failNFL=false;malformedNFL=true;await page.locator('#night-refresh').click();await page.waitForFunction(()=>!document.querySelector('#night-refresh').disabled);assert.equal(await page.locator('#night-games .night-card').count(),1);assert.equal(await page.locator('#night-bets .night-card').count(),0);
  malformedNFL=false;await page.locator('#night-refresh').click();await page.waitForFunction(()=>document.querySelectorAll('#night-bets .night-card').length===2);
  await page.locator('#night-date').selectOption('2026-10-15');await page.locator('#night-refresh').click();await page.waitForFunction(()=>!document.querySelector('#night-refresh').disabled);assert.equal(await page.locator('#night-date').inputValue(),'2026-10-15');
  await page.locator('#night-date').selectOption('2026-10-08');await page.clock.setFixedTime(new Date('2026-10-09T01:00Z'));await page.locator('#night-refresh').click();await page.waitForFunction(()=>!document.querySelector('#night-refresh').disabled);assert.equal(await page.locator('#night-date').inputValue(),'2026-10-08');assert.equal(await page.locator('#night-bets .night-card').count(),0);assert.match(await page.locator('#night-games').innerText(),/Kickoff passed/);
  await page.clock.setFixedTime(new Date('2026-10-08T19:00Z'));await page.goto(base+'/bet-ledger-hq/#thursday-night');
  for(const night of ['thursday','sunday','monday']){await page.locator(`a.board-link[href="#${night}-night"]`).click();const f=page.frameLocator('#frame-'+night+'-night');await f.locator('#night-games .night-card').first().waitFor();assert.match(await page.locator('#board-title').innerText(),new RegExp(night,'i'));}
  assert.deepEqual(errors,[]);await context.close();console.log(`Night pages: all sections, event scoping, doubleheader, outage retention, recovery, kickoff lock, date persistence and sidebar navigation passed at ${width}px`);
 }
}finally{await browser.close();await new Promise(r=>server.close(r));}
