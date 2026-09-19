import {webkit} from 'playwright';
import {createServer} from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=process.cwd();
const server=createServer(async(req,res)=>{
  const file=path.resolve(root,new URL(req.url,'http://localhost').pathname.replace(/^\/+/, '')||'index.html');
  if(!file.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
  try{const bytes=await readFile(file);res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':file.endsWith('.jpg')?'image/jpeg':'text/html');res.end(bytes);}catch(_){res.writeHead(404);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await webkit.launch();
try{
  await mkdir('test-results',{recursive:true});
  for(const [width,height] of [[320,568],[393,852],[852,393]]){
    const page=await browser.newPage({viewport:{width,height},isMobile:true,hasTouch:true,serviceWorkers:'block'});
    await page.route('https://**/*',r=>r.abort());
    await page.goto('http://127.0.0.1:'+server.address().port+'/');
    await page.frameLocator('#frame-today').getByRole('heading',{name:'Today, together.'}).waitFor();
    const bounds=await page.evaluate(()=>{const nav=document.querySelector('.sidebar').getBoundingClientRect(),work=document.querySelector('.workspace').getBoundingClientRect();return {navHeight:nav.height,workHeight:work.height,workBottom:work.bottom,navTop:nav.top,horizontal:document.documentElement.scrollWidth<=innerWidth};});
    assert.ok(bounds.horizontal);
    if(width<=760){assert.ok(bounds.navHeight<110);assert.ok(bounds.workHeight>height-180);assert.ok(bounds.workBottom<=bounds.navTop+1);}
    assert.equal(await page.locator('.ticket-tool:visible').count(),1);
    assert.equal(await page.frameLocator('#frame-today').locator('#make-top-ten').count(),0);
    await page.screenshot({path:`test-results/webkit-mobile-${width}.png`});await page.close();
  }
  console.log('WebKit small-phone, iPhone portrait and landscape navigation checks passed');
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
