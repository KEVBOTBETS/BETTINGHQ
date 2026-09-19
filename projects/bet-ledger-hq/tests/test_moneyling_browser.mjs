import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=process.cwd();
const server=createServer(async(req,res)=>{
  const pathname=new URL(req.url,'http://localhost').pathname.replace(/^\/bet-ledger-hq\//,'');
  const file=path.resolve(root,pathname||'index.html');
  if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
  try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(await readFile(file));}catch(_){res.writeHead(404).end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({headless:true});
const stamp='2026-09-19T15:00:00Z',start='2026-09-19T19:00:00Z';
try{
  await mkdir('test-results',{recursive:true});
  for(const width of [320,393,1440]){
    const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});
    const page=await context.newPage(),errors=[],requests=[];
    page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
    await page.clock.install({time:new Date('2026-09-19T16:00:00Z')});
    let failMlb=false;
    await page.route('https://**/*',r=>r.abort());
    await page.route('**/data/**',route=>{
      const u=route.request().url();let data={generated_at:stamp};
      if(u.includes('/mlb-edge/')){
        if(failMlb)return route.fulfill({status:503,body:'Unavailable'});
        data={generated_at:stamp,games:[{gamePk:3,date:'2026-09-19',start,home:'NYY',away:'TOR',home_name:'New York Yankees',away_name:'Toronto Blue Jays',gameType:'R',status:'Scheduled',sim:{p_home_final:.35},lineups_confirmed:true}]};
      }
      if(u.includes('/nfl-edge-lab/data/games.json'))data=[{game_id:'1',date:start,home:'KC',away:'BUF',home_name:'Kansas City Chiefs',away_name:'Buffalo Bills',season_type:2,status:'Scheduled'}];
      if(u.includes('/nfl-edge-lab/data/games_detail.json'))data=[{game_id:'1',projection:{mu:4,ratings_known:true},p_home:.65}];
      if(u.includes('/ncaaf-edge-lab/data/games.json'))data=[{game_id:'2',date:start,home:'ALA',away:'UGA',home_name:'Alabama Crimson Tide',away_name:'Georgia Bulldogs',season_type:2,projection:{mu:-3,ratings_known:true}}];
      return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
    });
    await page.goto(origin+'/bet-ledger-hq/#moneyling');
    let frame=page.frameLocator('#frame-moneyling');
    await frame.locator('#status').filter({hasText:'Forecasts checked'}).waitFor();
    assert.equal(await frame.locator('.match-card').count(),3);
    await frame.getByRole('button',{name:'Use predicted winners',exact:true}).click();
    assert.equal(await frame.locator('.team-option[aria-pressed=true]').count(),3);
    await frame.getByRole('button',{name:'Pick Buffalo Bills',exact:true}).click();
    assert.match(await frame.locator('#saved').textContent(),/BUF ✓/);
    await frame.locator('#sport').selectOption('mlb');
    assert.equal(await frame.locator('.match-card').count(),1);
    await frame.locator('#sport').selectOption('all');
    await page.reload();
    frame=page.frameLocator('#frame-moneyling');
    await frame.locator('#status').filter({hasText:'Forecasts checked'}).waitFor();
    assert.equal(await frame.locator('.team-option[aria-pressed=true]').count(),3,'Selections survive reload');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    const child=page.frames().find(f=>f.url().endsWith('moneyling.html'));
    assert.ok(await child.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:'test-results/moneyling-'+width+'.png',fullPage:true});
    failMlb=true;await frame.getByRole('button',{name:'Refresh forecasts',exact:true}).click();
    await frame.locator('#health').filter({hasText:'MLB · feed unavailable'}).waitFor();
    assert.equal(await frame.locator('.match-card').count(),2,'Failed feed cannot leave stale actionable cards');
    assert.match(await frame.locator('#saved').textContent(),/TOR ✓/,'Failed feeds must retain saved selections');
    await page.clock.fastForward(3*3600000+1000);
    assert.equal(await frame.locator('.team-option:enabled').count(),0,'All picks lock at start');
    assert.equal(await frame.getByRole('button',{name:'Clear open picks',exact:true}).isDisabled(),true);
    assert.deepEqual(errors,[]);assert.ok(!requests.some(u=>u.includes('script.google.com')),'Winner selections never write to the wager ledger');
    await context.close();
  }
  console.log('Moneyling browser: 320px, 393px, desktop; selection, persistence, filters, failures, locks and no overflow passed');
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
