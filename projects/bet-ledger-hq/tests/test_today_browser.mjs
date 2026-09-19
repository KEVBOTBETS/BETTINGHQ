import {chromium} from "playwright";
import {createServer} from "node:http";
import {readFile,mkdir} from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
const root=process.cwd();
await mkdir("test-results",{recursive:true});
const server=createServer(async(req,res)=>{
  const pathname=decodeURIComponent(new URL(req.url,"http://localhost").pathname),rel=pathname.replace(/^\/bet-ledger-hq\//,"");
  const file=path.resolve(root,rel===""?"index.html":rel);
  if(!file.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
  try{const data=await readFile(file);res.setHeader("Content-Type",file.endsWith(".css")?"text/css":file.endsWith(".js")?"text/javascript":file.endsWith('.webmanifest')?'application/manifest+json':file.endsWith(".json")?"application/json":file.endsWith(".jpg")?"image/jpeg":file.endsWith(".png")?"image/png":file.endsWith('.webp')?'image/webp':"text/html");res.end(data);}
  catch(_){res.writeHead(404);res.end("Not found");}
});
await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
const origin="http://127.0.0.1:"+server.address().port;
const browser=await chromium.launch({headless:true});
try{
  for(const width of [320,393,1440]){
    const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});
    const page=await context.newPage(),errors=[];
    page.on("pageerror",e=>errors.push(e.message));
    const stamp=new Date().toISOString(),start=new Date(Date.now()+3600000).toISOString();
    const chosen=new Intl.DateTimeFormat("en-CA",{timeZone:"America/Toronto",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(start));
    await page.route("**/data/**",async route=>{
      if(route.request().url().endsWith('/alerts.json'))return route.fulfill({contentType:'application/json',body:JSON.stringify({checked_at:stamp,coverage:{nfl:{status:'available',reports:1}},events:[{id:'test-odds',sport:'nfl',kind:'odds',title:'Published odds changed',pick:'DEN ML',event:'DEN @ KC',before:'-110',after:'-125',observed_at:stamp,source_quote_at:stamp,source:'NFL board'}]})});
      if(route.request().url().includes("/data/tickets/"))return route.continue();
      const u=route.request().url();let data={generated_at:stamp};
      if(u.includes("board.json")){await new Promise(resolve=>setTimeout(resolve,350));data=[{game_id:"1",game_date:start,tipoff:start,odds_fetched_at:stamp,side:"away",market:"ML",tier:"GOOD",stake:2,price:-110,matchup:"DEN @ KC",pick:"DEN ML",book:"DraftKings"}];}
      if(u.includes("latest.json"))data={generated_at:stamp,games:[]};
      if(u.includes("accuracy.json"))data={generated_at:stamp,scope:{season:2026,season_type_label:"regular season"},games:{winner:{n:15,correct:11,accuracy:11/15}}};
      return route.fulfill({contentType:"application/json",body:JSON.stringify(data)});
    });
    await page.route("https://site.api.espn.com/**",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({events:[],articles:[{headline:"League news test"}]})}));
    await page.goto(origin+"/bet-ledger-hq/#ledger");
    await page.getByRole('button',{name:'Install KEVBOT BETS',exact:true}).click();
    await page.getByRole('heading',{name:'Keep KEVBOT BETS handy'}).waitFor();
    await page.getByRole('button',{name:'Got it',exact:true}).click();
    const frame=page.frameLocator("#frame-today");
    const today=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    if(width===393&&chosen===today){
      await page.getByRole('button',{name:/Make daily ticket/i}).click();
      await frame.locator('#ticket-dialog').waitFor({state:'visible'});
      assert.ok(!/^0 qualified/.test(await frame.locator('#ticket-note').textContent()),'Cold sidebar launch must wait for delayed published feeds');
      await frame.getByRole('button',{name:'Close image preview'}).click();
    }else await page.getByRole('link',{name:'Today',exact:true}).click();
    await frame.getByRole('heading',{name:'Published odds changed',exact:true}).waitFor();
    await frame.locator('#alerts-read').click();assert.equal(await frame.locator('#alerts-count').textContent(),'0 unread');
    await frame.locator("#refresh-status").filter({hasText:"Published files checked"}).waitFor();
    await frame.locator("#date").fill(chosen);
    await frame.locator("#date").dispatchEvent("change");
    await frame.getByRole("heading",{name:"DEN ML",exact:true}).first().waitFor();
    assert.equal(await frame.locator('#make-top-ten').count(),0);
    assert.equal(await page.locator('.ticket-tool').count(),1);
    if(width<=760){
      const layout=await page.evaluate(()=>({nav:document.querySelector('.sidebar').getBoundingClientRect().height,workspace:document.querySelector('.workspace').getBoundingClientRect().height,direction:getComputedStyle(document.querySelector('.boards')).flexDirection}));
      assert.equal(layout.direction,'row');assert.ok(layout.nav<110);assert.ok(layout.workspace>650);
    }
    await page.getByRole("button",{name:/Make daily ticket/i}).click();
    await frame.getByRole("heading",{name:"KEVBOT BETS Daily Top Picks"}).waitFor();
    assert.ok((await frame.locator("#ticket-preview").getAttribute("src")).startsWith("blob:"));
    if(width===393)await page.screenshot({path:"test-results/ticket-preview-393.png",fullPage:true});
    const classicSrc=await frame.locator('#ticket-preview').getAttribute('src');
    await frame.locator('#ticket-style').selectOption('baseball');
    await frame.locator('#ticket-preview').evaluate((img,old)=>new Promise(resolve=>{const timer=setInterval(()=>{if(img.src!==old){clearInterval(timer);resolve();}},25);}),classicSrc);
    await frame.locator('#ticket-preview').evaluate(img=>img.decode());
    for(const style of ['gridiron','ballpark','scoreboard','northern','slip']){
      const before=await frame.locator('#ticket-preview').getAttribute('src');
      await frame.locator('#ticket-style').selectOption(style);
      await frame.locator('#ticket-preview').evaluate((img,old)=>new Promise(resolve=>{const timer=setInterval(()=>{if(img.src!==old){clearInterval(timer);resolve();}},25);}),before);
      assert.ok(await frame.locator('#ticket-preview').evaluate(async img=>{await img.decode();return img.naturalWidth===1080&&img.naturalHeight>=1350;}),style+' ticket renders');
    }
    await frame.getByRole("button",{name:"Close image preview"}).click();
    await frame.getByRole("button",{name:"Accuracy",exact:true}).click();
    await frame.getByRole("heading",{name:"Predictions, not your bet record"}).waitFor({state:"visible"});
    await frame.getByRole("button",{name:"Exposure",exact:true}).click();
    await frame.getByText("Connect and sync in Ledger").waitFor();
    assert.equal(await page.locator(".board-link").count(),8);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    const child=page.frames().find(f=>f.url().endsWith("today.html"));
    assert.ok(await child.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.getByRole("link",{name:"Ledger",exact:true}).click();
    await page.locator("#frame-ledger").waitFor({state:"visible"});
    await page.getByRole("link",{name:"Today",exact:true}).click();
    await page.locator("#frame-today").waitFor({state:"visible"});
    assert.equal(await frame.getByRole("button",{name:"Exposure",exact:true}).getAttribute("aria-pressed"),"true");
    await frame.getByRole("button",{name:"Today's board",exact:true}).click();
    await mkdir("test-results",{recursive:true});
    await page.screenshot({path:"test-results/today-"+width+".png"});
    await page.getByRole('link',{name:'Tickets & results',exact:true}).click();
    const archive=page.frameLocator('#frame-archive');
    await archive.locator('#archive-select option').first().waitFor({state:'attached'});
    await archive.locator('#archive-select').selectOption({index:0});
    await archive.locator('#archive-preview').waitFor({state:'visible'});
    await archive.locator('#backup-status').filter({hasText:'Connect Ledger'}).waitFor();
    assert.deepEqual(errors,[]);
    await context.close();
  }
  // Capability detection and reviewed undo use a fake endpoint, never the user's ledger.
  const context=await browser.newContext({viewport:{width:393,height:900},serviceWorkers:'block'}),page=await context.newPage();
  await page.addInitScript(()=>{localStorage.setItem('betsync.config.v1',JSON.stringify({url:'https://script.google.com/macros/s/test/exec',token:'fixture',device:'Test phone'}));});
  let upgraded=false,undone=false,ledgerMissing=false,restored=false;
  const row={id:'fixture:one',app:'mlb-edge',sport:'MLB',selection:'Example ML',event:'A @ B',event_date:'2026-09-15',market:'ML',price:-110,stake:10,status:'Win',pnl:9.09,updated_at:'2026-09-15T18:00:00Z'};
  await page.route('https://script.google.com/**',async route=>{const req=route.request().postDataJSON(),features=upgraded?['audit-v2','undo-v2']:[];let res={ok:true,rows:[{...row,status:undone?'Pending':'Win',pnl:undone?null:9.09}],settings:{starting_bankroll:250},features};
    if(ledgerMissing)res.rows=[];
    if(req.action==='push'&&req.rows?.length){assert.equal(req.rows[0].base_rev,'restore-missing-only-v1');assert.equal(req.settings,null);restored=true;ledgerMissing=false;res.rows=[{...row,status:'Pending',pnl:null}];res.applied=1;}
    if(req.action==='audit')res={ok:true,entries:[{id:'audit-one',entity:'bet',entity_id:row.id,action:'edit',at:row.updated_at,device:'Test laptop',state:'applied',can_undo:!undone,before:{...row,status:'Pending',pnl:null},after:row}],next_before:null};
    if(req.action==='undo'){assert.equal(req.audit_id,'audit-one');assert.equal(req.expected_rev,row.updated_at);undone=true;res.rows=[{...row,status:'Pending',pnl:null}];}
    await route.fulfill({contentType:'application/json',body:JSON.stringify(res)});
  });
  await page.goto(origin+'/bet-ledger-hq/ledger.html');
  await page.getByRole('link',{name:'Enable full history and safe undo'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Review undo',exact:true}).count(),0);
  upgraded=true;await page.locator('#sync').click();await page.getByRole('button',{name:'Review undo',exact:true}).click();
  await page.getByRole('button',{name:'Cancel',exact:true}).click();assert.equal(undone,false);
  await page.getByRole('button',{name:'Review undo',exact:true}).click();await page.getByRole('button',{name:'Confirm undo',exact:true}).click();
  await page.getByRole('dialog').waitFor({state:'detached'});assert.equal(undone,true);assert.equal(await page.getByRole('button',{name:'Review undo',exact:true}).count(),0);
  const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Download current ledger',exact:true}).click();const backupBytes=await readFile(await (await downloaded).path());
  const backup=JSON.parse(backupBytes);assert.equal(backup.rows.length,1);assert.equal(backup.rows[0].id,row.id);assert.equal(backup.token,undefined);
  ledgerMissing=true;await page.locator('#sync').click();await page.getByText('No bets yet.',{exact:true}).waitFor();
  const file={name:'saved-ledger.json',mimeType:'application/json',buffer:backupBytes};
  await page.locator('[data-backup-file]').setInputFiles(file);await page.getByRole('heading',{name:'Review ledger recovery'}).waitFor();assert.equal(restored,false);
  await page.getByRole('button',{name:'Cancel',exact:true}).click();assert.equal(restored,false);
  await page.locator('[data-backup-file]').setInputFiles(file);await page.getByRole('button',{name:'Restore 1 missing wagers',exact:true}).click();await page.locator('[data-recovery-status]').filter({hasText:'1 missing wager(s) restored'}).waitFor();assert.equal(restored,true);
  await page.getByRole('button',{name:'Close',exact:true}).click();
  await page.screenshot({path:'test-results/ledger-audit-393.png',fullPage:true});await context.close();
  const offlineContext=await browser.newContext(),offlinePage=await offlineContext.newPage();
  await offlineContext.route('https://**/*',route=>route.abort());
  await offlinePage.goto(origin+'/bet-ledger-hq/',{waitUntil:'domcontentloaded'});
  await offlinePage.evaluate(()=>navigator.serviceWorker.ready);
  await offlinePage.waitForFunction(()=>!!navigator.serviceWorker.controller);
  await offlinePage.evaluate(()=>localStorage.setItem('kevbot.local-tickets.v1',JSON.stringify([{schema:1,id:'local-offline123',day:'2026-09-15',published_at:'2026-09-15T18:00:00Z',picks:[{key:'mlb',eventId:'1',event:'A @ B',pick:'Example ML',price:-110,market:'ML',side:'A',start:'2026-09-15T23:00:00Z',source:'MLB',tier:'GOOD'}]}])));
  await offlineContext.setOffline(true);await offlinePage.goto(origin+'/bet-ledger-hq/archive.html');
  await offlinePage.locator('#archive-preview').waitFor({state:'visible'});await offlinePage.locator('#archive-status').filter({hasText:'Local originals remain available'}).waitFor();
  assert.ok((await offlinePage.locator('#archive-detail').textContent()).includes('Pending'));
  const cached=await offlinePage.evaluate(async()=>{const urls=[];for(const name of await caches.keys()){for(const req of await (await caches.open(name)).keys())urls.push(req.url);}return urls;});
  assert.ok(cached.length>20);assert.equal(cached.some(url=>url.includes('/data/')||url.includes('script.google.com')),false);
  await offlineContext.close();
  console.log("Desktop and mobile ticket, alert, install, backup and undo smoke checks passed.");
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
