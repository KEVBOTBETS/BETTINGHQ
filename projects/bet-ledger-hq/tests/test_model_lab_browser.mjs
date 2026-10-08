import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve('../../_site'),out=path.resolve('test-results/model-lab');
await mkdir(out,{recursive:true});
const server=createServer(async(req,res)=>{let f=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(req.url.endsWith('/'))f=path.join(f,'index.html');try{res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.json':'application/json','.woff':'font/woff','.svg':'image/svg+xml'})[path.extname(f)]||'text/html');res.end(await readFile(f));}catch{res.writeHead(404).end();}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({headless:true});
try{
  for(const width of [1440,393]){
    const context=await browser.newContext({viewport:{width,height:1050},serviceWorkers:'block'}),page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));await context.route('https://**/*',r=>r.abort());
    await page.goto(origin+'/bet-ledger-hq/model-lab.html',{waitUntil:'networkidle'});
    await page.locator('#lab-content').waitFor({state:'visible'});
    assert.match(await page.locator('#lab-status').innerText(),/Snapshot generated/);
    for(const tab of ['competition','efficiency','lineups','prices','props','validation','calibration','weather','health']){
      await page.locator(`[data-tab="${tab}"]`).click();
      assert.equal(await page.locator(`[data-tab="${tab}"]`).getAttribute('aria-selected'),'true');
      assert.ok(await page.locator('#lab-panel h2').count());
      const dimensions=await page.evaluate(()=>({w:innerWidth,scroll:document.documentElement.scrollWidth}));assert.ok(dimensions.scroll<=dimensions.w+2,`${tab} overflow at ${width}`);
      await page.screenshot({path:`${out}/${tab}-${width}.png`,fullPage:false});
      if(tab==='validation')assert.equal(await page.locator('.lab-card').count(),10);
      if(tab==='lineups'){
        const select=page.locator('.lab-scenario-select').filter({has:page.locator('option[value="1"]')}).first();
        if(await select.count())await select.selectOption('1');
      }
      if(tab==='props'){
        await page.locator('#lab-sport').selectOption('nfl');
        const books=await page.locator('#lab-book option').allTextContents();
        for(const book of books.slice(1)){
          await page.locator('#lab-book').selectOption({label:book});
          if(await page.locator('.lab-leg').count()>=3)break;
        }
        if(await page.locator('.lab-leg').count()>=3){
          await page.locator('.lab-leg').nth(0).check();await page.locator('.lab-leg').nth(1).check();await page.locator('.lab-leg').nth(2).check();
          assert.match(await page.locator('#lab-ticket-result').innerText(),/Joint win:|Duplicate or contradictory/);
          await page.locator('#lab-clear').click();assert.match(await page.locator('#lab-ticket-result').innerText(),/0 selected/);
        }
        await page.locator('#lab-sport').selectOption('ncaaf');assert.equal(await page.locator('.lab-ticket').count(),0);await page.locator('#lab-sport').selectOption('nfl');
        await page.locator('#lab-search').fill('THISPLAYERDOESNOTEXIST');assert.equal(await page.locator('.lab-leg').count(),0);
      }
      await page.locator('#lab-search').fill('');await page.locator('#lab-book').selectOption('all');await page.locator('#lab-sport').selectOption('all');
    }
    const snapshot=await page.locator('#lab-kpis').innerText();
    await page.route('**/data/research/report.json*',route=>route.fulfill({status:503,body:'offline'}));
    await page.locator('#lab-refresh').click();
    await page.waitForFunction(()=>document.querySelector('#lab-status').textContent.includes('Retaining'));
    assert.equal(await page.locator('#lab-kpis').innerText(),snapshot);
    await page.unroute('**/data/research/report.json*');
    await page.route('**/data/research/report.json*',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({schema:1,games:[],props:[]})}));
    await page.locator('#lab-refresh').click();
    await page.waitForFunction(()=>!document.querySelector('#lab-refresh').disabled);
    assert.equal(await page.locator('#lab-kpis').innerText(),snapshot);
    await page.unroute('**/data/research/report.json*');
    await page.locator('#lab-refresh').click();
    await page.waitForFunction(()=>document.querySelector('#lab-status').textContent.includes('Snapshot generated'));
    assert.deepEqual(errors,[]);
    await page.goto(origin+'/bet-ledger-hq/#model-lab',{waitUntil:'networkidle'});
    await page.frameLocator('iframe[src="model-lab.html"]').locator('#lab-content').waitFor({state:'visible'});
    await context.close();console.log(`Model Lab: nine tabs, controls, ticket masks and hub navigation passed at ${width}px.`);
  }
}finally{await browser.close();await new Promise(r=>server.close(r));}
