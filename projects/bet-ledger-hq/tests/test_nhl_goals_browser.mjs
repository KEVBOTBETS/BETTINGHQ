import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve('../../_site'),server=createServer(async(req,res)=>{let file=path.resolve(root,'.'+new URL(req.url,'http://local').pathname);if(file.endsWith('/'))file+='index.html';try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.json')?'application/json':file.endsWith('.css')?'text/css':'text/html');res.end(await readFile(file));}catch(_){res.writeHead(404).end();}});await new Promise(r=>server.listen(0,'127.0.0.1',r));
const at='2026-10-10T16:15:00Z',start='2026-10-10T23:00:00Z';
const games=Array.from({length:4},(_,i)=>({game_id:'g'+i,date:start,home:'H'+i,away:'A'+i,season_type:2}));
const scorers=games.map((g,i)=>({event_id:g.game_id,start_time:start,matchup:g.away+' @ '+g.home,team:g.home,id:'p'+i,athlete_id:'p'+i,player:'Scorer '+i,market:'Anytime goal',side:'yes',line:null,average:.4,samples:84,current_goals:1,current_games:2,prior_goals:32,prior_games:82,model_prob:.4-i*.02,research_only:true,history_note:'Official counts'}));
const props={sport:'NHL',generated_at:at,games,quotes:[],watchlist:scorers,goal_scorers:scorers,errors:[]};
const browser=await chromium.launch({headless:true});
try{await mkdir('test-results',{recursive:true});for(const width of [393,1440]){
 const c=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'}),p=await c.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.clock.install({time:new Date(at)});await p.route('https://**/*',r=>r.abort());await p.route('**/data/nhl-props.json*',r=>r.fulfill({contentType:'application/json',body:JSON.stringify(props)}));
 await p.goto('http://127.0.0.1:'+server.address().port+'/props-edge/multisport.html?sport=NHL');await p.locator('#nhl-goals h2').waitFor();
 assert.equal(await p.locator('.goal-grid .goal-card').count(),4);assert.equal(await p.locator('.goal-parlays .goal-card').count(),3);assert.match(await p.locator('.goal-parlays .goal-card').first().textContent(),/15.2%/);assert.match(await p.locator('#nhl-goals').textContent(),/not a book quote/);
 await p.screenshot({path:'test-results/nhl-scorers-'+width+'.png',fullPage:true});assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 for(let i=0;i<2;i++){
  await p.locator('[data-goal-offer="'+i+'"]').click();assert.equal(await p.locator('#multi-line').isDisabled(),true);assert.equal(await p.locator('#multi-side').inputValue(),'yes');await p.locator('#multi-price').fill('200');await p.locator('#multi-book').fill('Book fixture');await p.locator('#multi-confirm').check();if(i===0){await p.locator('#multi-refresh').click();await p.waitForFunction(()=>!document.querySelector('#multi-refresh').disabled);assert.equal(await p.locator('#multi-player').inputValue(),'0');assert.equal(await p.locator('#multi-price').inputValue(),'200');assert.equal(await p.locator('#multi-side').inputValue(),'yes');}await p.locator('#multi-offer button').click();await p.locator('[data-select="'+i+'"]').click();
 }
 assert.match(await p.locator('#multi-selection').textContent(),/15.2%/);await p.locator('#multi-save').click();const t=await p.evaluate(()=>JSON.parse(localStorage.getItem('kevbot-research-props-NHL-v1')).tickets[0]);assert.equal(t.legs.length,2);assert.ok(Math.abs(t.independent_goal_probability-.152)<1e-8);assert.equal(t.legs[0].line,null);assert.equal(t.research_only,true);
 await p.locator('#multi-game').selectOption('g0');assert.equal(await p.locator('.goal-parlays .goal-card').count(),0);assert.match(await p.locator('#nhl-goals').textContent(),/correlated/);
 await p.route('**/data/nhl-props.json*',r=>r.fulfill({status:503,body:'Unavailable'}));await p.locator('#multi-refresh').click();await p.locator('#multi-status').filter({hasText:'Refresh failed'}).waitFor();assert.equal(await p.locator('#multi-save').isDisabled(),true);assert.deepEqual(errors,[]);await c.close();
}console.log('NHL scorer estimates, distinct-game parlay chances, binary manual prices, saved tickets, refresh and responsive pages passed');}finally{await browser.close();await new Promise(r=>server.close(r));}
