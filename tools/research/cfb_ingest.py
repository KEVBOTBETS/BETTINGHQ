"""Keyless public ESPN-processed college play data; only independently final games."""
import argparse,io,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
from .common import number,instant,key_team,read,write
ROOT=Path(__file__).resolve().parents[2]
BASE='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_pbp/'
META='https://api.github.com/repos/sportsdataverse/sportsdataverse-data/releases/tags/espn_cfb_pbp'
COLUMNS=['game_id','id','season','seasonType','status_type_completed','homeTeamAbbrev','awayTeamAbbrev','homeFinalScore','awayFinalScore','pos_team_id','homeTeamId','awayTeamId','rush','pass','sack','pass_attempt','kneel_down','penalty_no_play','EPA_scrimmage','EPA','statYardage','wp_before','wallclock']
def abbr(g,side):
 t=g.get(side);return key_team(t.get('abbr') if isinstance(t,dict) else t)
def aggregate(rows,official,now):
 teams={};seen=set()
 for r in rows:
  gid=str(r.get('game_id'));g=official.get(gid);pid=r.get('id');wall=instant(r.get('wallclock'))
  if not g or not g.get('completed') or g.get('canceled') or g.get('postponed') or pid is None or (gid,str(pid)) in seen:continue
  seen.add((gid,str(pid)))
  start=instant(g.get('date_utc') or g.get('date'))
  if not start or start>=now or wall and wall>now or r.get('seasonType') not in (2,3) or not r.get('status_type_completed'):continue
  h,a=number(g.get('home_score')),number(g.get('away_score'))
  if h is None or a is None or (h,a)!=(number(r.get('homeFinalScore')),number(r.get('awayFinalScore'))):continue
  home,away=key_team(r.get('homeTeamAbbrev')),key_team(r.get('awayTeamAbbrev'))
  if (home,away)!=(abbr(g,'home'),abbr(g,'away')):continue
  if r.get('kneel_down') or r.get('penalty_no_play') or not (r.get('rush') or r.get('pass') or r.get('pass_attempt') or r.get('sack')):continue
  epa=number(r.get('EPA_scrimmage'));epa=epa if epa is not None else number(r.get('EPA'));yards=number(r.get('statYardage'))
  if epa is None or yards is None:continue
  own=home if r.get('pos_team_id')==r.get('homeTeamId') else away if r.get('pos_team_id')==r.get('awayTeamId') else None
  if not own:continue
  opp=away if own==home else home;key=(gid,own)
  t=teams.setdefault(key,{'game_id':gid,'season':int(r['season']),'date':start.date().isoformat(),'team':own,'opponent':opp,'home':home,'away':away,'home_score':h,'away_score':a,'neutral':bool(g.get('neutral')),'result_verified':True,'plays':0,'epa':0.,'success':0,'explosive':0,'pass_plays':0,'pass_epa':0.,'rush_plays':0,'rush_epa':0.,'neutral_plays':0,'neutral_pass':0})
  group='pass' if r.get('pass') or r.get('pass_attempt') or r.get('sack') else 'rush';t['plays']+=1;t['epa']+=epa;t['success']+=epa>0;t['explosive']+=yards>=20;t[group+'_plays']+=1;t[group+'_epa']+=epa;wp=number(r.get('wp_before'))
  if wp is not None and .2<=wp<=.8:t['neutral_plays']+=1;t['neutral_pass']+=group=='pass'
 accepted={gid for gid,_ in teams if len([1 for (game,_),t in teams.items() if game==gid and t['plays']>=20])==2}
 return [t for (gid,_),t in teams.items() if gid in accepted and t['plays']>=20]
def fetch_json(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BETTINGHQ-research/1.0','Accept':'application/json'}),timeout=25) as r:return json.load(r)
def collect(root=ROOT,seasons=None,now=None,local_files=None):
 import pyarrow.parquet as pq
 now=now or datetime.now(timezone.utc);season=now.year if now.month>=8 else now.year-1;seasons=seasons or [season-1,season];dest=root/'research/inputs/ncaaf-pbp.json';old=read(dest,{});official={}
 for path in sorted((root/'projects/ncaaf-edge-lab/state').glob('*.json')):
  if not path.name.startswith(('games_','history_')):continue
  rows=read(path,[])
  if isinstance(rows,list):
   for g in rows:
    if g.get('completed'):official[str(g['game_id'])]=g
 assets={} if local_files else {a['name']:a for a in fetch_json(META).get('assets',[])}
 rows=[];sources=[];errors=[];success=0
 for year in seasons:
  previous=next((s for s in old.get('sources',[]) if s.get('season')==year),None);name=f'play_by_play_{year}.parquet';asset=assets.get(name)
  if not local_files and asset and previous and previous.get('updated_at')==asset.get('updated_at') and any(str(r.get('date','')).startswith(str(year)) for r in old.get('teams',[])):
   rows.extend(r for r in old.get('teams',[]) if r.get('season',int(r['date'][:4]))==year);sources.append(previous);success+=1;continue
  try:
   if local_files:blob=Path(local_files[year]).read_bytes()
   else:
    if not asset or not instant(asset.get('updated_at')) or instant(asset['updated_at'])>now or asset.get('size',0)>90000000:raise ValueError('Current public asset is unavailable')
    with urllib.request.urlopen(urllib.request.Request(BASE+name,headers={'User-Agent':'BETTINGHQ-research/1.0'}),timeout=45) as r:blob=r.read(90000001)
   if len(blob)>90000000 or not blob.startswith(b'PAR1'):raise ValueError('Invalid play file')
   file=pq.ParquetFile(io.BytesIO(blob));missing=set(COLUMNS)-set(file.schema_arrow.names)
   if missing:raise ValueError('Play schema changed: '+','.join(sorted(missing)))
   def records():
    for batch in file.iter_batches(batch_size=4096,columns=COLUMNS):yield from batch.to_pylist()
   data=aggregate(records(),official,now)
   if not data:raise ValueError('No independently verified completed team-games')
   rows.extend(data);sources.append({'url':BASE+name,'season':year,'observed_at':now.isoformat(),'updated_at':asset.get('updated_at') if asset else now.isoformat(),'team_games':len(data)});success+=1
  except (OSError,ValueError,KeyError) as exc:
   errors.append({'season':year,'error':type(exc).__name__});rows.extend(r for r in old.get('teams',[]) if r.get('season',int(r['date'][:4]))==year)
   if previous:sources.append(previous)
 if not success:return old
 unique={(r['game_id'],r['team']):r for r in rows};live=next((s['observed_at'] for s in sources if s['season']==season),None)
 result={'schema':1,'observed_at':now.isoformat(),'live_observed_at':live,'teams':list(unique.values()),'sources':sources,'errors':errors,'policy':'Corrected public ESPN-processed cfbfastR files; both teams, game identity and final scores matched to the independently saved ESPN schedule. Kneels, no-plays and incomplete games excluded. Corrected-history replay is exploratory; only new frozen forecasts establish forward accuracy.'};write(dest,result);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--current-only',action='store_true');a=p.parse_args();now=datetime.now(timezone.utc)
 try:
  d=collect(seasons=[now.year if now.month>=8 else now.year-1] if a.current_only else None);print({'ncaaf_team_games':len(d.get('teams',[])),'errors':d.get('errors',[])})
 except (OSError,ValueError) as e:print('::warning::College play import unavailable; previous timestamps retained: '+type(e).__name__)
