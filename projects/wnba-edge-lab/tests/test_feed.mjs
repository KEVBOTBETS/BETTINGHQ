import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const F=createRequire(import.meta.url)('../site/feed.js');
const now=Date.parse('2026-09-16T12:00:00Z');
const meta={generated_at:'2026-09-16T11:00:00Z',source_status:'live',errors:[],odds_health:{status:'ok',upcoming_games:1,priced_games:1}};
const row={game_id:'one',tipoff:'2026-09-17T23:00:00Z',odds_fetched_at:meta.generated_at,max_odds_age_hours:12,tier:'AVOID',stake:0};
const before=JSON.stringify({meta,row});
assert.equal(F.ageLabel(meta.generated_at,now),'1h 0m ago');
assert.equal(F.ageLabel(null,now),'age unknown');
assert.equal(F.ageLabel('2026-09-16T14:00:00Z',now),'timestamp in the future');
assert.equal(F.health(meta,[row,row],now).fresh,1);
assert.equal(F.health(meta,[row],now).level,'ok');
assert.equal(F.health(meta,[{...row,odds_fetched_at:'2026-09-16T00:00:00Z'}],now).label,'STALE / UNVERIFIED');
assert.equal(F.health({...meta,generated_at:'2026-09-15T00:00:00Z'},[],now).level,'partial');
assert.equal(F.health({...meta,generated_at:'2026-09-16T14:00:00Z'},[row],now).level,'partial');
assert.equal(F.health({...meta,source_status:'cached-live-data'},[row],now).label,'CACHED DATA');
assert.equal(F.health({...meta,source_status:'no-live-data'},[],now).level,'error');
assert.match(F.health({...meta,errors:['Missing context']},[row],now).message,/reports may be incomplete/);
assert.equal(F.health({...meta,errors:['Missing context']},[row],now).level,'partial');
assert.match(F.health(meta,[row],now,true).message,/previous data is retained/);
assert.equal(JSON.stringify({meta,row}),before,'health inspection must not change model rows');

const base=Object.fromEntries(F.FILES.map(name=>[name,['board','games','news','results'].includes(name)?[]:{}]));
base.meta=meta;base.index={generated_at:meta.generated_at,dates:['2026-09-17']};
function fetcher(data=base,overrides={}) {
  const calls=[];
  const fn=async(url,options)=>{
    const name=url.split('/').at(-1).replace('.json','');calls.push(name);
    assert.equal(options.cache,'no-store');
    if(overrides[name])return overrides[name](calls);
    return {ok:true,json:async()=>data[name]};
  };
  return {fn,calls};
}
let f=fetcher();
assert.equal(await F.read(f.fn,meta.generated_at),null);
assert.deepEqual(f.calls,['meta'],'unchanged publication should only download metadata');
f=fetcher();assert.equal((await F.read(f.fn))[3],meta);
assert.equal(f.calls.filter(x=>x==='meta').length,2,'check version again after download');
f=fetcher(base,{results:()=>({ok:false,status:404})});
assert.deepEqual((await F.read(f.fn)).at(-1),[]);
await assert.rejects(F.read(fetcher(base,{board:()=>({ok:false,status:503})}).fn),/Unable to load board/);
await assert.rejects(F.read(fetcher({...base,board:{}}).fn),/Invalid board/);
await assert.rejects(F.read(fetcher({...base,index:{dates:[],generated_at:'different'}}).fn),/same refresh/);
await assert.rejects(F.read(fetcher({...base,meta:{...meta,generated_at:'bad'}}).fn),/timestamp/);
await assert.rejects(F.read(fetcher().fn,'2026-09-16T12:00:00Z'),/Older publication/);
f=fetcher(base,{meta:calls=>({ok:true,json:async()=>calls.filter(x=>x==='meta').length===1?meta:{...meta,generated_at:'2026-09-16T12:00:00Z'}})});
await assert.rejects(F.read(f.fn),/changed during download/);
console.log('publication health, snapshot integrity, failed refresh and non-mutation checks passed');
