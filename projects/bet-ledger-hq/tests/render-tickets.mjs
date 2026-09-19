// Offline visual QA; does not fetch feeds or touch the ledger.
import fs from 'node:fs/promises';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const runtime=process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||'/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {createCanvas,Image}=require(runtime+'/@napi-rs/canvas');
const T=require('../ticket-core.js');
const context={Image,window:{KevTickets:T}};vm.createContext(context);vm.runInContext(await fs.readFile('ticket-renderer.js','utf8'),context);
const picks=Array.from({length:10},(_,i)=>({key:'mlb',source:i===5?'Props':'MLB',eventId:String(i),start:'2026-09-15T23:00:00Z',side:'over',market:'TOTAL',line:8.5,price:i%2?123:-110,tier:'GOOD',event:i===5?'Denver Broncos @ Kansas City Chiefs':'LAD @ CIN',pick:i===5?'RJ Harvey — Over 19.5 Receiving yards':'Over 8.5'}));
const ticket={id:'qa-preview',day:'2026-09-15',published_at:'2026-09-15T18:00:00Z',picks};
const results=Object.fromEntries(picks.map((r,i)=>[T.outcomeKey(r),{result:{status:['Win','Loss','Pending','Push','Void'][i%5]}}]));
await fs.mkdir('test-results',{recursive:true});
for(const style of Object.keys(context.window.KevTicketRenderer.styles)){
  const canvas=createCanvas(1080,1350);await context.window.KevTicketRenderer.draw(canvas,ticket,{style,results});await fs.writeFile('test-results/ticket-'+style+'.png',canvas.toBuffer('image/png'));
}
console.log('All four 1080×1350 ticket styles rendered.');
