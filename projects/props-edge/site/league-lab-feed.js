/* Version-consistent daily prop payloads. Missing manifests alone use the legacy feed. */
(function(root){'use strict';
 function create(sport,get){const name=sport.toLowerCase();let metadata=null,cache=new Map(),legacy=false;
  return {get metadata(){return metadata;},get chunked(){return !legacy&&metadata!==null;},async refresh(){const previous=metadata;metadata=null;try{const next=await get('data/labs/'+name+'/manifest.json',true);if(next===null){metadata=await get('data/'+name+'-props.json');legacy=true;cache.clear();return metadata;}
   if(next?.schema!==1||next.sport!==sport||!Array.isArray(next.games)||!Array.isArray(next.chunks)||next.chunks.some(q=>!/^\d{4}-\d{2}-\d{2}$/.test(q.day)||!/^day-\d+\.json$/.test(q.file)))throw Error('Invalid lab manifest');
   if(previous?.generated_at!==next.generated_at||legacy)cache.clear();metadata=next;legacy=false;return metadata;}catch(error){cache.clear();legacy=false;throw error;}
  },async read(days=[]){if(!metadata)throw Error('No lab manifest');if(legacy)return metadata;
   const wanted=metadata.chunks.filter(q=>days.includes(q.day)),version=metadata.generated_at;
   const fetched=await Promise.all(wanted.filter(q=>!cache.has(q.day)).map(async q=>{const data=await get('data/labs/'+name+'/'+q.file);if(data?.schema!==1||data.sport!==sport||data.generated_at!==version||data.source_model_at!==metadata.source_model_at||data.day!==q.day||!Array.isArray(data.quotes)||!Array.isArray(data.watchlist))throw Error('Lab payload changed during refresh');return [q.day,data];}));
   if(version!==metadata.generated_at)throw Error('Lab manifest changed during load');for(const [day,data] of fetched)cache.set(day,data);
   const merged={...metadata,loaded_days:[...cache.keys()],quotes:[],watchlist:[],milestone_forecasts:[],goal_scorers:[]};for(const data of cache.values())for(const key of ['quotes','watchlist','milestone_forecasts','goal_scorers'])merged[key].push(...(data[key]||[]));return merged;
  }};
 }
 const api={create};root.LeagueLabFeed=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
