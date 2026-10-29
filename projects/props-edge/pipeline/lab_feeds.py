"""Small versioned lab manifests and daily payloads; legacy feeds stay compatible."""
import json
from pathlib import Path
from zoneinfo import ZoneInfo
ROWS=('quotes','watchlist','milestone_forecasts','goal_scorers')
def publish(root,result):
 from .multisport import instant
 folder=Path(root)/'site/data/labs'/result['sport'].lower();folder.mkdir(parents=True,exist_ok=True)
 games=result.get('games',[]);days={}
 for g in games:
  at=instant(g.get('date'))
  if at:days.setdefault(at.astimezone(ZoneInfo('America/Toronto')).date().isoformat(),set()).add(str(g['game_id']))
 chunks=[]
 for index,(day,ids) in enumerate(sorted(days.items())):
  payload=dict(schema=1,sport=result['sport'],generated_at=result['generated_at'],source_model_at=result.get('source_model_at'),day=day)
  for key in ROWS:payload[key]=[q for q in result.get(key,[]) if str(q.get('event_id')) in ids]
  payload['games']=[g for g in games if str(g['game_id']) in ids]
  raw=json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n';name=f'day-{index}.json';temp=folder/(name+'.tmp');temp.write_text(raw);temp.replace(folder/name)
  chunks.append({'day':day,'file':name,'bytes':len(raw.encode()),'games':len(ids),'quotes':len(payload['quotes']),'forecasts':len(payload['milestone_forecasts'])})
 metadata={k:v for k,v in result.items() if k not in ROWS};metadata.update(schema=1,chunks=chunks,payload_mode='daily chunks',counts={key:len(result.get(key,[])) for key in ROWS})
 tmp=folder/'manifest.tmp';tmp.write_text(json.dumps(metadata,separators=(',',':'),allow_nan=False)+'\n');tmp.replace(folder/'manifest.json')
 return metadata
