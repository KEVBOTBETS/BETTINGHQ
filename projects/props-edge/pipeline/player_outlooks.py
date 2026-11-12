"""Pregame NBA/NHL stat outlooks; conditional means, never sportsbook offers."""
import datetime as dt
import json
import math
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

VERSION='player-outlook-1.0'
ZONE=ZoneInfo('America/Toronto')

def instant(value):
    try:
        at=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return at if at.tzinfo else None
    except (TypeError,ValueError):return None

def number(value):
    if isinstance(value,bool):return None
    try:
        v=float(value)
        return v if math.isfinite(v) and v>=0 else None
    except (TypeError,ValueError):return None

def minutes(value):
    try:
        parts=str(value).split(':')
        return number(parts[0]) if len(parts)==1 else float(parts[0])+float(parts[1])/60 if len(parts)==2 else None
    except (ValueError,TypeError):return None

def norm(value):return ''.join(c for c in unicodedata.normalize('NFKD',str(value)).casefold() if c.isalnum() and not unicodedata.combining(c))
def weighted(values):
    return sum((i+1)*v for i,v in enumerate(values))/sum(range(1,len(values)+1)) if values else None

def starter_ids(payload):
    answer=set()
    for unit in payload.get('depthchart',[]):
        for pos in (unit.get('positions') or {}).values():
            players=pos.get('athletes') or []
            if players and players[0].get('id'):answer.add(str(players[0]['id']))
    return answer

NBA_FIELDS={'points':'PTS','rebounds':'REB','assists':'AST','steals':'STL','blocks':'BLK','turnovers':'TO','off_rebounds':'OREB','def_rebounds':'DREB','fouls':'PF'}
def nba_rows(games,players,rosters,injuries,depth,now):
    history=defaultdict(dict)
    for p in players:
        at=instant(p.get('start'));mins=minutes((p.get('stats') or {}).get('MIN'))
        if p.get('state')!='post' or not at or not now-dt.timedelta(days=42)<=at<now or not mins:continue
        history[str(p.get('player_id')),p.get('team')][str(p.get('game_id'))]=p
    flagged={norm(r.get('name')):r.get('status','Unknown') for r in injuries or []}
    result=[]
    for g in games:
        if not instant(g.get('date')) or instant(g['date'])<=now:continue
        for side in ('away','home'):
            team=g[side];opponent=g['home' if side=='away' else 'away'];starters={}
            members={w['id']:w for w in rosters.get(team,[])}
            blocked={pid for pid,w in members.items() if norm(flagged.get(norm(w['player']),w.get('availability',''))) in ('out','doubtful','inactive','suspended','injuredreserve','suspension')}
            for unit in depth.get(team,{}).get('depthchart',[]):
                for pos in (unit.get('positions') or {}).values():
                    ordered=[str(a['id']) for a in pos.get('athletes',[]) if a.get('id')]
                    chosen=next((pid for pid in ordered if pid in members and pid not in blocked),None)
                    if chosen:starters[chosen]='Expected starter' if chosen==ordered[0] else 'Replacement candidate'
            for who in rosters.get(team,[]):
                status=flagged.get(norm(who['player']),who.get('availability') or 'Not reported')
                if norm(status) in ('out','doubtful','inactive','suspended','injuredreserve','suspension'):continue
                past=sorted(history[who['id'],team].values(),key=lambda p:p['start'])[-8:]
                mins=[minutes(p['stats']['MIN']) for p in past]
                recent=mins[-3:];is_starter=who['id'] in starters
                if not past:
                    if is_starter:result.append(make_row('NBA',g,who,team,opponent,starters[who['id']],status,{},{},now,'Expected role, but no usable recent current-team history. No workload is invented.'))
                    continue
                if (now-instant(past[-1]['start'])).days>14 and not is_starter:continue
                rotation=len(recent)>=2 and sum(m>=16 for m in recent)>=2
                if not is_starter and not rotation:continue
                expected_minutes=.65*weighted(recent)+.35*median(recent)
                stats={};samples={}
                if len(past)>=3:
                    stats['minutes']=round(min(42,expected_minutes),2);samples['minutes']=len(recent)
                    for field,key in NBA_FIELDS.items():
                        observations=[(number(p['stats'].get(key)),minutes(p['stats'].get('MIN'))) for p in past]
                        rates=[v/m for v,m in observations if v is not None and m and m>=8]
                        if len(rates)>=3:
                            stats[field]=round(weighted(rates)*stats['minutes'],2);samples[field]=len(rates)
                    for field,key in [('fg','FG'),('threes','3PT'),('ft','FT')]:
                        for index,suffix in [(0,'made'),(1,'att')]:
                            rates=[]
                            for p in past:
                                pair=str(p['stats'].get(key,'')).split('-');m=minutes(p['stats'].get('MIN'))
                                v=number(pair[index]) if len(pair)==2 else None
                                if v is not None and m and m>=8:rates.append(v/m)
                            if len(rates)>=3:stats[field+'_'+suffix]=round(weighted(rates)*stats['minutes'],2);samples[field+'_'+suffix]=len(rates)
                    for prefix in ('fg','threes','ft'):
                        if prefix+'_made' in stats and prefix+'_att' in stats:stats[prefix+'_made']=min(stats[prefix+'_made'],stats[prefix+'_att'])
                    # Reconcile scoring and rebounding components when complete.
                    if all(k in stats for k in ('fg_made','threes_made','ft_made')):
                        stats['threes_made']=min(stats['threes_made'],stats['fg_made'])
                        stats['points']=round(2*stats['fg_made']+stats['threes_made']+stats['ft_made'],2)
                    if all(k in stats for k in ('off_rebounds','def_rebounds')):stats['rebounds']=round(stats['off_rebounds']+stats['def_rebounds'],2)
                    if all(k in stats for k in ('points','rebounds','assists')):stats['pra']=round(sum(stats[k] for k in ('points','rebounds','assists')),2)
                role=starters[who['id']] if is_starter else 'Regular rotation'
                result.append(make_row('NBA',g,who,team,opponent,role,status,stats,samples,now,
                    'Current-team per-minute rates × recent expected minutes. Last eight completed games within six weeks; at least three usable games. No automatic injury workload transfer.'))
    return result


def make_row(sport,game,who,team,opponent,role,availability,stats,samples,now,basis):
    return dict(id=f"{sport}:{game['game_id']}:{who['id']}",event_id=str(game['game_id']),player_id=who['id'],player=who['player'],
        position=who.get('position') or 'UNK',team=team,opponent=opponent,start=game['date'],day=instant(game['date']).astimezone(ZONE).date().isoformat(),
        role=role,availability=availability,stats=stats,stat_samples=samples,samples=max(samples.values(),default=0),
        captured_at=now.isoformat(),model_version=VERSION,basis=basis,status='Pregame · conditional on playing' if stats else 'Insufficient usable history')


def nhl_rows(games,rosters,stats,inputs,scorers,season,now):
    goals={(str(w['event_id']),str(w['athlete_id'])):w for w in scorers if w.get('market')=='Anytime goal'}
    result=[]
    from .multisport import NHL_CODES
    for g in games:
        if not instant(g.get('date')) or instant(g['date'])<=now:continue
        for side in ('away','home'):
            team=g[side];opponent=g['home' if side=='away' else 'away'];data=stats.get(team,{})
            current=data.get('season')==season
            by_id={str(p.get('playerId')):p for p in data.get('skaters',[])+data.get('goalies',[])} if current else {}
            lineup=(inputs.get('lineups') or {}).get(NHL_CODES.get(team,team),{})
            roles=defaultdict(list)
            for record in lineup.get('players',[]):roles[norm(record.get('name'))].append(record)
            goalie=((inputs.get('goalies') or {}).get(str(g['game_id'])) or {}).get(side,{})
            max_gp=max((number(p.get('gamesPlayed')) or 0 for p in data.get('skaters',[])),default=0)
            for who in rosters.get(team,[]):
                matches=roles.get(norm(who['player']),[])
                if len(matches)>1:matches=[r for r in matches if str(r.get('line','')).startswith('d' if who.get('position')=='D' else 'f')]
                r=matches[0] if len(matches)==1 else {}
                p=by_id.get(who['id'],{})
                if not p and inputs.get('year')==season//10000 and r.get('season'):
                    p={**r['season'],'blockedShots':r['season'].get('blocks')}
                gp=number(p.get('gamesPlayed')) or 0
                if r.get('available') is False:continue
                is_goalie=who.get('position')=='G'
                if is_goalie:
                    if norm(goalie.get('name'))!=norm(who['player']) or not (goalie.get('confirmed') or norm(goalie.get('status')) in ('likely','expected','probable')):continue
                    role='Confirmed starting goalie' if goalie.get('confirmed') else 'Expected goalie · unconfirmed'
                else:
                    line=str(r.get('line') or '')
                    projected=r.get('available') is True and line.lower() in ('f1','f2','f3','f4','d1','d2','d3')
                    regular=not roles and gp>=5 and max_gp and gp/max_gp>=.65
                    if not projected and not regular:continue
                    role='Projected skater · '+line.upper() if projected else 'Regular skater · lineup unconfirmed'
                values={};samples={}
                if gp>=3:
                    if is_goalie:
                        for field,key in [('saves','saves'),('shots_against','shotsAgainst'),('goals_against','goalsAgainst')]:
                            v=number(p.get(key))
                            if v is not None:values[field]=round(v/gp,2);samples[field]=int(gp)
                        if 'saves' not in values and 'shots_against' in values and 'goals_against' in values:
                            values['saves']=round(max(0,values['shots_against']-values['goals_against']),2)
                        if number(p.get('savePercentage')) is not None and 0<=float(p['savePercentage'])<=1:values['save_pct']=round(float(p['savePercentage'])*100,2)
                    else:
                        for field,key in [('shots','shots'),('goals','goals'),('assists','assists'),('points','points'),('blocks','blockedShots')]:
                            season_value=number(p.get(key));recent=r.get('last5') or {};recent_gp=number(recent.get('gamesPlayed')) or 0
                            recent_key='blocks' if field=='blocks' else key
                            if season_value is None:season_value=number((r.get('season') or {}).get(recent_key))
                            if season_value is None:continue
                            mean=season_value/gp;recent_value=number(recent.get(recent_key))
                            if recent_gp>=3 and recent_value is not None:mean=.6*mean+.4*recent_value/recent_gp
                            values[field]=round(mean,3);samples[field]=int(gp)
                        scoring=goals.get((str(g['game_id']),who['id']))
                        if scoring and number(scoring.get('expected_goals')) is not None:values['goals']=round(scoring['expected_goals'],3)
                        if 'goals' in values and 'assists' in values:values['points']=round(values['goals']+values['assists'],3)
                        season_usage=r.get('season') or {};usage_gp=number(season_usage.get('gamesPlayed')) or 0
                        if usage_gp and number(season_usage.get('toiMinutes')) is not None:
                            values['ice_minutes']=round((float(season_usage['toiMinutes'])+(number(season_usage.get('toiSeconds')) or 0)/60)/usage_gp,2)
                result.append(make_row('NHL',g,who,team,opponent,role,'Questionable' if r.get('questionable') else 'Participation conditional',values,samples,now,
                    'Current-season official per-game counts, with last-five form where reported. Goals use the existing shrunk goal-rate model; other counts are form-based conditional estimates. Goalie averages depend on playing time.'))
    return result


def publish(root,sport,rows,games,now,coverage=None):
    """Freeze before kickoff; monthly files retain prospective history without one giant blob."""
    root=Path(root);history={}
    months={ (now+dt.timedelta(days=n)).strftime('%Y-%m') for n in (-8,0,8)}
    for month in months:
        path=root/f'state/player-stats-{sport}-{month}.json'
        try:history.update({r['id']:r for r in json.loads(path.read_text())})
        except (OSError,ValueError,TypeError):pass
    incoming={row['id'] for row in rows}
    history={key:r for key,r in history.items() if instant(r.get('start')) and (instant(r['start'])<=now or key in incoming)}
    for row in rows:
        at=instant(row.get('start'));old=history.get(row['id'])
        if old and instant(old.get('start')) and instant(old['start'])<=now:continue
        if at and at>now:history[row['id']]=row
    months_rows=defaultdict(list)
    for row in history.values():months_rows[instant(row['start']).strftime('%Y-%m')].append(row)
    for month in months:months_rows.setdefault(month,[])
    for month,records in months_rows.items():
        path=root/f'state/player-stats-{sport}-{month}.json';path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(records,separators=(',',':'),allow_nan=False)+'\n');tmp.replace(path)
    days=defaultdict(list);today=now.astimezone(ZONE).date()
    for row in history.values():
        at=instant(row['start']);day=at.astimezone(ZONE).date()
        if today-dt.timedelta(days=7)<=day<=today+dt.timedelta(days=7):
            days[day.isoformat()].append({**row,'status':'Frozen pregame outlook' if at<=now else row['status']})
    for g in games:days.setdefault(instant(g['date']).astimezone(ZONE).date().isoformat(),[])
    days.setdefault(today.isoformat(),[])
    folder=root/f'site/data/player-stats/{sport.lower()}';folder.mkdir(parents=True,exist_ok=True)
    chunks=[]
    for day,records in sorted(days.items()):
        name=day+'.json';payload=dict(schema=1,sport=sport,day=day,generated_at=now.isoformat(),rows=records)
        tmp=folder/(name+'.tmp');tmp.write_text(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n');tmp.replace(folder/name)
        chunks.append(dict(day=day,file=name,players=len(records),projected=sum(bool(r['stats']) for r in records)))
    manifest=dict(schema=1,sport=sport,model_version=VERSION,generated_at=now.isoformat(),today=today.isoformat(),days=chunks,
        teams=sorted({r['team'] for r in history.values()}),coverage=coverage or {},automatic_qualification=False,
        sources=['https://www.espn.com/nba/depth','https://www.espn.com/nba/injuries'] if sport=='NBA' else ['https://www.nhl.com/stats/players','https://www.dailyfaceoff.com/starting-goalies'],
        note='Conditional statistical outlooks, not sportsbook lines, calibrated hit probabilities or qualified bets. Frozen history starts with the first saved pregame forecast.')
    tmp=folder/'manifest.tmp';tmp.write_text(json.dumps(manifest,separators=(',',':'),allow_nan=False)+'\n');tmp.replace(folder/'manifest.json')
    return manifest


def publish_nba(root,result,players,rosters,injuries,cache,ids,now):
    def depth(item):
        team,identifier=item
        return team,cache.get(f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{identifier}/depthcharts',1) or {}
    with ThreadPoolExecutor(max_workers=4) as pool:charts=dict(pool.map(depth,ids.items()))
    now=dt.datetime.now(dt.timezone.utc)
    rows=nba_rows(result['games'],players,rosters,injuries,charts,now)
    if injuries is None:
        for row in rows:row.update(stats={},stat_samples={},samples=0,availability='Availability unverified',status='Forecast withheld: current injury coverage unavailable')
    return publish(root,'NBA',rows,result['games'],now,dict(availability_verified=injuries is not None,roster_teams=sum(bool(v) for v in rosters.values()),depth_teams=sum(bool(starter_ids(p)) for p in charts.values()),expected_teams=len(ids)))
