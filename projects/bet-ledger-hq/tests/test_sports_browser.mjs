import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve('../../_site'),out=path.resolve('test-results/sports');
await mkdir(out,{recursive:true});
const server=createServer(async(req,res)=>{let f=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(f===root||req.url.endsWith('/'))f=path.join(f,'index.html');try{res.setHeader('Content-Type',({'.woff':'font/woff','.js':'application/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp'})[path.extname(f)]||'text/html');res.end(await readFile(f));}catch{res.writeHead(404).end();}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({headless:true});const results=[];
try{
for(const width of [1440,393]){
const ctx=await browser.newContext({viewport:{width,height:1050},colorScheme:'dark',serviceWorkers:'block'});
await ctx.route('https://**/*',r=>r.abort());
for(const [name,url] of [['hub','bet-ledger-hq/#today'],['moneyline','bet-ledger-hq/moneyline.html'],['weekly','bet-ledger-hq/football.html'],['ledger','bet-ledger-hq/ledger.html'],['archive','bet-ledger-hq/archive.html'],['nhl','nhl-edge-lab/'],['nfl','nfl-edge-lab/'],['ncaaf','ncaaf-edge-lab/'],['mlb','mlb-edge/'],['wnba','wnba-edge-lab/'],['props','props-edge/'],['ladder','ladderbet/']]){
 const page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin+'/'+url,{waitUntil:'networkidle'});await page.evaluate(()=>document.fonts.ready);
 if(name==='nhl'){const b=page.locator('#next');if(await b.count())await b.click();}
 const info=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,font:getComputedStyle(document.querySelector('h1')||document.body).fontFamily,theme:document.documentElement.dataset.kbSport,fonts:document.fonts.check('800 40px "KB Display"')}));
 await page.screenshot({path:out+'/'+name+'-'+width+'.png',fullPage:false});results.push({name,width,...info,errors});console.log(JSON.stringify(results.at(-1)));await page.close();
}
await ctx.close();
}
await writeFile(out+'/report.json',JSON.stringify(results,null,2));
const failures=results.filter(r=>!r.theme||!r.fonts||r.scroll>r.width+2||r.errors.length);
assert.deepEqual(failures,[],'Every app must load its theme and fonts without script errors or horizontal page overflow');
console.log('All 12 apps passed the sports presentation checks at desktop and mobile sizes.');
}finally{await browser.close();await new Promise(r=>server.close(r));}
