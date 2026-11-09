import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve('../..'),at='2026-11-09T16:00:00Z';let failure=false;
const team={id:'1',abbr:'DUKE',name:'Duke Blue Devils',wins:3,losses:0,points_for:80,points_against:65,stats:{gamesPlayed:3,avgPoints:80},stats_season:2027};
const game={game_id:'college-1',tipoff:'2026-11-09T23:00:00Z',date:'2026-11-09T23:00:00Z',day:'2026-11-09',season:2027,season_type:2,state:'pre',status:'Scheduled',home:team,away:{id:'2',abbr:'UNC',name:'North Carolina'},p_home:.72,projection:{ratings_known:true,p_home:.72,mu:7,total:153,margin_sd:12,prior_weight:.8,proj_home_pts:80,proj_away_pts:73},quotes:[]};
const server=createServer(async(req,res)=>{
 const u=new URL(req.url,'http://localhost'),p=u.pathname;
 if(p.includes('/data/')){if(failure&&p.includes('/ncaab-edge-lab/'))return res.writeHead(503).end();const name=path.basename(p,'.json');let data=[];
 if(name==='meta')data={generated_at:at,league:'NCAAB',college:true,season:2027,season_label:'2026–27',sources:{},automatic_qualification:false};
 if(p.includes('/ncaab-edge-lab/')){const d={games:[game],board:[],standings:{teams:[team]},teams:{teams:[team]},players:{players:[]},leaders:{leaders:[]},news:[],injuries:[],accuracy:{records:[],games:{graded:0,pending:1}}};data=d[name]??data;}
 res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(data));}
 const parts=p.split('/').filter(Boolean),project=parts.shift(),folder=project==='bet-ledger-hq'?'': 'site';const file=path.join(root,'projects',project,folder,...parts,p.endsWith('/')?'index.html':'');try{res.setHeader('Content-Type',p.endsWith('.js')?'application/javascript':p.endsWith('.css')?'text/css':p.endsWith('.woff')?'font/woff':'text/html');res.end(await readFile(file));}catch{res.writeHead(404).end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch();
try{for(const width of [393,1440]){failure=false;const c=await browser.newContext({viewport:{width,height:1000},serviceWorkers:'block'}),p=await c.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.clock.setFixedTime(new Date(at));await p.route('https://**/*',r=>r.abort());const base=`http://127.0.0.1:${server.address().port}`;
 await p.goto(base+'/ncaab-edge-lab/',{waitUntil:'networkidle'});await p.locator('.game').waitFor();await p.waitForFunction(()=>document.querySelector('#content').textContent.includes('DUKE'),{},{timeout:10000});assert.match(await p.locator('#content').textContent(),/DUKE 72/);assert.equal(await p.locator('[data-record]').count(),0,'College research does not share NBA wager state');await p.getByRole('button',{name:'Standings',exact:true}).click();assert.match(await p.locator('#content').textContent(),/Duke/);await p.getByRole('button',{name:'Team stats',exact:true}).click();assert.match(await p.locator('#content').textContent(),/80/);await p.evaluate(()=>document.fonts.ready);await p.screenshot({path:`/tmp/college-${width}.png`,fullPage:true});assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 failure=true;await p.click('#refresh');await p.locator('#freshness').filter({hasText:'Refresh unavailable'}).waitFor();failure=false;
 await p.goto(base+'/bet-ledger-hq/#moneyline',{waitUntil:'networkidle'});const f=p.frameLocator('#frame-moneyline');await f.locator('#status').filter({hasText:'Forecasts checked'}).waitFor();await f.locator('#sport').selectOption('ncaab');assert.equal(await f.locator('.pick-label').count(),1);await f.getByRole('button',{name:'Use predicted winners',exact:true}).click();assert.match(await f.locator('#saved').innerText(),/DUKE ✓/);assert.deepEqual(errors,[]);await c.close();console.log(`College basketball ${width}px: forecasts, standings, stats, outages and moneyline choices passed`);}
}finally{await browser.close();server.close();}
