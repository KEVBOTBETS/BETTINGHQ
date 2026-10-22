import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
const root=path.resolve('..'),at='2026-10-22T19:00:00Z';
const fixture=JSON.parse(execFileSync('python',['-c',`import json,datetime as dt
from pipeline.parlays import build_parlays
from pipeline.schema import american_to_decimal
s=json.load(open('config/settings.json'));at='2026-10-22T19:00:00Z'
legs=[dict(id=str(i),sport='NFL',event_id='401873010',player='Player '+str(i),team='Team',matchup='New England Patriots @ Chicago Bears',market='Receiving yards',group='receiving',side='over',line=35.5,model_prob=.6,price_american=p,price_decimal=american_to_decimal(p),price_source='book',book='DraftKings',samples=8,confidence=.7,tier='PASS',held=True,updated_at=at,start_time='2026-10-23T00:15Z') for i,p in enumerate([100,100,150,150,200,200])]
legs += [{**l,'id':'other-'+l['id'],'event_id':'999','matchup':'Other @ Game','start_time':'2026-10-25T17:00Z'} for l in legs.copy()]
print(json.dumps(dict(legs=legs,parlays=build_parlays(legs,s,dt.datetime.fromisoformat(at.replace('Z','+00:00'))))))`],{cwd:path.join(root,'props-edge'),encoding:'utf8'}));
const server=createServer(async(req,res)=>{const u=new URL(req.url,'http://local');let p=u.pathname;if(p.endsWith('/'))p+='index.html';
 const data={'meta.json':{generated_at:at,counts:{},accuracy:{},source_by_sport:{}},'legs.json':fixture.legs,'parlays.json':fixture.parlays};
 if(p.includes('/data/')){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(data[p.split('/').pop()]||[]));}
 const prefix=p.startsWith('/props-edge/')?'props-edge/site':'bet-ledger-hq';const file=path.join(root,prefix,p.replace(/^\/(?:props-edge|bet-ledger-hq)\//,''));
 try{res.setHeader('Content-Type',p.endsWith('.js')?'application/javascript':p.endsWith('.css')?'text/css':'text/html');res.end(await readFile(file));}catch{res.writeHead(404).end();}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch();
try{for(const width of [393,1440]){const c=await browser.newContext({viewport:{width,height:950},serviceWorkers:'block'}),p=await c.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.clock.install({time:new Date(at)});await p.route('https://**/*',r=>r.abort());await p.goto(`http://127.0.0.1:${server.address().port}/props-edge/#parlays`,{waitUntil:'networkidle'});await p.locator('#targets button').first().waitFor();
 assert.equal(await p.locator('[data-target="300"]').count(),0);
 await p.selectOption('#parlay-game','New England Patriots @ Chicago Bears');
 for(const target of [300,400,500]){await p.click(`[data-target="${target}"]`);assert.ok(await p.locator('#parlays .ticket').filter({hasText:'Tonight extra'}).count()>0);assert.match(await p.locator('#parlays').innerText(),/Combined price needs confirmation/);}
 await p.selectOption('#parlay-game','Other @ Game');assert.equal(await p.locator('[data-target="300"]').count(),0);assert.equal(await p.locator('[data-target="400"]').count(),0);assert.doesNotMatch(await p.locator('#parlays').innerText(),/Tonight extra/);
 await p.selectOption('#parlay-game','New England Patriots @ Chicago Bears');await p.clock.setSystemTime(new Date('2026-10-23T00:15:00Z'));await p.click('[data-target="500"]');assert.equal(await p.locator('[data-target="300"]').count(),0);assert.doesNotMatch(await p.locator('#parlays').innerText(),/Tonight extra/);
 assert.deepEqual(errors,[]);await c.close();console.log('Tonight-only +300/+400/+500 targets, unchanged other games and kickoff expiry passed at '+width+'px');}}finally{await browser.close();await new Promise(r=>server.close(r));}
