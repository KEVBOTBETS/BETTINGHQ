"""Explicit keyless NFLverse import. No network calls during an offline site build."""
import argparse
import csv
import gzip
import io
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from .common import number, key_team, write, read

ROOT=Path(__file__).resolve().parents[2]

def aggregate(rows, completed_games=None):
    teams={}; players={}; final={};ended=set()
    for r in rows:
        if r.get('season_type') not in ('REG','POST'):continue
        game=r.get('game_id'); date=r.get('game_date'); own=key_team(r.get('posteam')); opponent=key_team(r.get('defteam'))
        if game and (number(r.get('game_seconds_remaining'))==0 or str(r.get('desc','')).strip().upper()=='END GAME'):ended.add(game)
        if not game or not date or not own or not opponent:continue
        if completed_games is not None and game not in completed_games:continue
        h=number(r.get('total_home_score'));a=number(r.get('total_away_score'))
        if h is not None and a is not None:final[game]=(h,a)
        if r.get('play_type') not in ('pass','run') or r.get('qb_kneel')=='1' or r.get('qb_spike')=='1':continue
        epa=number(r.get('epa')); yards=number(r.get('yards_gained')); wp=number(r.get('wp'))
        if epa is None or yards is None:continue
        key=(game,own)
        t=teams.setdefault(key,dict(game_id=game,date=date,team=own,opponent=opponent,home=key_team(r.get('home_team')),away=key_team(r.get('away_team')),plays=0,epa=0.,success=0,explosive=0,pass_plays=0,pass_epa=0.,rush_plays=0,rush_epa=0.,neutral_plays=0,neutral_pass=0))
        t['plays']+=1;t['epa']+=epa;t['success']+=epa>0;t['explosive']+=yards>=20
        group='pass' if r.get('qb_dropback')=='1' or r.get('play_type')=='pass' else 'rush'
        t[group+'_plays']+=1;t[group+'_epa']+=epa
        if wp is not None and .2<=wp<=.8:t['neutral_plays']+=1;t['neutral_pass']+=group=='pass'
        for role in ['rusher','receiver','passer']:
            identity=r.get(role+'_player_id');name=r.get(role+'_player_name')
            if not identity or not name:continue
            p=players.setdefault((game,own,identity),dict(game_id=game,date=date,team=own,player_id=identity,name=name,carries=0,targets=0,receptions=0,pass_attempts=0,rush_yards=0.,receiving_yards=0.,passing_yards=0.))
            if role=='rusher':p['carries']+=1;p['rush_yards']+=number(r.get('rushing_yards')) or 0
            elif role=='receiver':p['targets']+=1;p['receptions']+=r.get('complete_pass')=='1';p['receiving_yards']+=number(r.get('receiving_yards')) or 0
            elif r.get('pass_attempt')=='1':p['pass_attempts']+=1;p['passing_yards']+=number(r.get('passing_yards')) or 0
    result=[]
    for t in teams.values():
        if t['game_id'] not in final:continue
        if completed_games is not None and t['game_id'] not in ended:continue
        if completed_games is not None:
            verified=completed_games[t['game_id']];t['home_score'],t['away_score']=verified['home_score'],verified['away_score'];t['neutral']=verified['neutral'];t['result_verified']=True
        else:t['home_score'],t['away_score']=final[t['game_id']];t['result_verified']=False
        result.append(t)
    accepted={r['game_id'] for r in result}
    return {'teams':result,'players':[p for p in players.values() if p['game_id'] in accepted]}

def collect(root=ROOT,seasons=None):
    if seasons is None:
        today=datetime.now(timezone.utc);active=today.year if today.month>=8 else today.year-1;seasons=(active-1,active)
    dest=root/'research/inputs'; dest.mkdir(parents=True,exist_ok=True)
    merged={'teams':[],'players':[]};sources=[];errors=[];successes=0;previous=read(dest/'nfl-pbp.json',{})
    schedule=root/'projects/nfl-edge-lab/state/nflverse_games.csv'
    if not schedule.exists():raise ValueError('Verified schedule results are required before importing training data')
    completed={}
    official={str(g['game_id']):g for path in root.glob('projects/nfl-edge-lab/state/games_*.json') for g in read(path,[]) if g.get('completed')}
    with schedule.open() as stream:schedule_rows=list(csv.DictReader(stream))
    for r in schedule_rows:
        h,a=number(r.get('home_score')),number(r.get('away_score'))
        live=official.get(str(r.get('espn')))
        if live:
            h,a=number(live.get('home_score')),number(live.get('away_score'))
        if h is not None and a is not None:completed[r['game_id']]={'home_score':h,'away_score':a,'neutral':live.get('neutral',False) if live else r.get('location')=='Neutral'}
    for season in seasons:
        url=f'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{int(season)}.csv.gz'
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'BETTINGHQ-research/1.0'})
            with urllib.request.urlopen(request,timeout=45) as response:
                blob=response.read(40_000_001)
            if len(blob)>40_000_000:raise ValueError('Dataset exceeds size limit')
            with gzip.GzipFile(fileobj=io.BytesIO(blob)) as stream:
                data=aggregate(csv.DictReader(io.TextIOWrapper(stream,encoding='utf-8-sig')),completed)
            if not data['teams']:raise ValueError('No usable completed play records')
            for kind in merged:merged[kind].extend(data[kind])
            sources.append({'url':url,'season':season,'rows':len(data['teams']),'observed_at':datetime.now(timezone.utc).isoformat()})
            successes+=1
        except (OSError,ValueError,EOFError) as exc:
            errors.append({'season':season,'error':type(exc).__name__})
            for kind in merged:merged[kind].extend(r for r in previous.get(kind,[]) if r.get('game_id','').startswith(str(season)+'_'))
            sources.extend(s for s in previous.get('sources',[]) if s.get('season')==season)
    # Failed imports retain the last good input and its original timestamp.
    if not successes:
        print('::warning::NFL play import failed; last good input and timestamp retained.');print(errors)
        return previous
    if merged['teams']:
        merged.update(schema=1,observed_at=datetime.now(timezone.utc).isoformat(),sources=sources,errors=errors,policy='Corrected public historical data. Historical replay is exploratory, not an original-vintage backtest. Live forecasts use only records available at capture. Player samples require a recorded opportunity; zero-opportunity absences are unknown.')
        merged['live_observed_at']=next((s.get('observed_at') or previous.get('observed_at') for s in sources if s['season']==max(seasons)),None)
        write(dest/'nfl-pbp.json',merged)
    print({'team_games':len(merged['teams']),'player_games':len(merged['players']),'errors':errors})
    return merged

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--seasons',nargs='+',type=int);args=parser.parse_args();collect(seasons=args.seasons)

def collect_workload(root=ROOT,season=None,now=None):
    """Public snap/depth releases, independently transactional per source."""
    now=now or datetime.now(timezone.utc);season=season or (now.year if now.month>=8 else now.year-1)
    path=root/'research/inputs/nfl-workload.json';old=read(path,{});out=dict(old);errors=[]
    for kind in ['snap_counts','depth_charts']:
        url=f'https://github.com/nflverse/nflverse-data/releases/download/{kind}/{kind}_{season}.csv'
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'BETTINGHQ-research/2.0'})
            limit=80_000_000 if kind=='depth_charts' else 15_000_000
            with urllib.request.urlopen(request,timeout=30) as response:blob=response.read(limit+1)
            if len(blob)>limit:raise ValueError('Dataset exceeds size limit')
            rows=list(csv.DictReader(io.StringIO(blob.decode('utf-8-sig'))))
            required={'game_id','team','player','offense_snaps','offense_pct'} if kind=='snap_counts' else {'dt','team','player_name','pos_abb','pos_rank'}
            if not rows or not required.issubset(rows[0]):raise ValueError('Invalid workload schema')
            if kind=='depth_charts':
                # Retain the latest expected QB role per team, not a season of daily rosters.
                latest={}
                for r in rows:
                    if r.get('pos_abb')!='QB' or number(r.get('pos_rank'))!=1:continue
                    t=r['team'];dt=r['dt']
                    if t not in latest or dt>latest[t][0]['dt']:latest[t]=[r]
                    elif dt==latest[t][0]['dt']:latest[t].append(r)
                rows=[r for values in latest.values() for r in values]
            out[kind]={'rows':rows,'observed_at':now.isoformat(),'url':url,'season':season}
        except (OSError,ValueError,UnicodeError) as exc:errors.append({'source':kind,'error':type(exc).__name__})
    out.update(schema=1,errors=errors,policy='Offensive snaps are recorded participation, not route counts. Depth rank is expected role, not confirmed gameday availability. Failed sources keep their original timestamps.')
    write(path,out);return out

def enrich_workload(dataset,workload,now):
    from .common import instant
    from .opportunity import identity
    result={**dataset,'players':[dict(p) for p in dataset.get('players',[])]}
    feed=workload.get('snap_counts') or {};at=instant(feed.get('observed_at'));matched=0
    if at and at<=now and (now-at).total_seconds()<=7*86400:
        index=defaultdict(list)
        for r in feed.get('rows',[]):index[r.get('game_id'),key_team(r.get('team')),identity(r.get('player'))].append(r)
        for p in result['players']:
            hits=index[p['game_id'],key_team(p['team']),identity(p['name'])]
            if len(hits)!=1:continue
            snaps,share=number(hits[0].get('offense_snaps')),number(hits[0].get('offense_pct'))
            if snaps is None or snaps<0 or share is None or not 0<=share<=1:continue
            p.update(offensive_snaps=snaps,snap_share=share,snap_observed_at=feed['observed_at']);matched+=1
    depth=workload.get('depth_charts') or {};received=instant(depth.get('observed_at'));starters={}
    if received and received<=now and (now-received).total_seconds()<=36*3600:
        rows=defaultdict(list)
        for r in depth.get('rows',[]):
            at=instant(r.get('dt'))
            if r.get('pos_abb')=='QB' and number(r.get('pos_rank'))==1 and at and at<=now and (now-at).total_seconds()<=36*3600:rows[key_team(r['team'])].append(r)
        for t,values in rows.items():
            newest=max(r['dt'] for r in values);latest=[r for r in values if r['dt']==newest]
            if len({r['player_name'] for r in latest})==1:starters[t]={'player':latest[0]['player_name'],'player_id':latest[0].get('gsis_id'),'observed_at':newest,'fresh':True}
    result['workload_coverage']={'matched_player_games':matched,'snap_observed_at':feed.get('observed_at'),'expected_qb_teams':len(starters),'errors':workload.get('errors',[])}
    result['expected_starters']=starters
    return result

if __name__=='__main__':collect_workload()
