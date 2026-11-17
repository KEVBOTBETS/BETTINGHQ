import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';import {JSDOM} from 'jsdom';
const now=Date.parse('2026-11-17T18:00Z'),at=new Date(now).toISOString();
for(const sport of ['nfl','ncaaf','nba','ncaab','nhl','mlb','wnba']){
 const dom=new JSDOM(`<html data-kb-sport="${sport}" data-kb-page="${sport}"><body><main><header>League</header></main><script src="https://test.invalid/bet-ledger-hq/site-tools.js"></script></body></html>`,{url:'https://test.invalid/league/',runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window,D=w.Date;
 w.Date=class extends D{constructor(...args){super(...(args.length?args:[now]));}static now(){return now;}};w.AbortSignal=globalThis.AbortSignal;
 const system={schema:1,generated_at:at,feeds:[],games:Array.from({length:14},(_,i)=>({id:sport+'|'+i,event_id:String(i),sport,season:2027,start:'2026-11-17T23:00Z',publication_at:at,forecast_available:true,p_home:.65,home:'HOME',away:'AWAY',matchup:'Away @ Home',selections:[]}))};
 w.fetch=async url=>({ok:true,json:async()=>String(url).includes('system.json')?system:String(url).includes('daily-performance')?{schema:1,cohorts:[]}: {quotes:[],events:[]}});
 try{for(const file of ['value-core.js','daily-tickets-core.js','site-tools-core.js','site-tools.js'])w.eval(await readFile(file,'utf8'));await new Promise(r=>setTimeout(r,40));const panel=w.document.querySelector('#top-model-picks');assert.ok(panel,sport);assert.match(panel.textContent,/TOP 10 MODEL PICKS/);assert.equal(panel.querySelectorAll('article').length,10);assert.match(panel.textContent,/#10/);assert.match(panel.textContent,/FORECAST ONLY/);assert.match(panel.textContent,/Recommended stake \$0/);assert.doesNotMatch(panel.textContent,/\$5 preview/);}finally{w.close();}
}
console.log('Top 10 DOM: all seven boards, numbered shortlist, forecast continuity and no unpriced stake passed');
