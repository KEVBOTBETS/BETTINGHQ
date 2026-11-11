"""Weekly research view of the existing NFL player model, with full rosters.

No retrospective forecast backfill, inferred availability probability or odds.
The original prop model remains responsible for its own projections.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import tempfile

VERSION = 'nfl-weekly-form-v1'
MARKETS = {
    'Pass attempts':'pass_att','Pass completions':'pass_cmp','Passing yards':'pass_yds',
    'Passing touchdowns':'pass_td','Pass interceptions':'pass_int','Rush attempts':'rush_att',
    'Rushing yards':'rush_yds','Rushing touchdowns':'rush_td','Targets':'targets',
    'Receptions':'receptions','Receiving yards':'rec_yds','Receiving touchdowns':'rec_td',
    'Touchdowns scored':'td_scored','Tackles + assists':'tackles','Solo tackles':'solo_tackles',
    'Sacks':'sacks','Field goal attempts':'fg_att','Field goals made':'fg_made',
    'Extra point attempts':'xp_att','Extra points made':'xp_made','Kicking points':'kick_points',
}


def norm(value):return re.sub(r'[^a-z0-9]','',str(value or '').casefold())
def instant(value):
    try:
        at=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return at.astimezone(timezone.utc) if at.tzinfo else None
    except (ValueError,TypeError):return None

def finite(value):
    if isinstance(value,bool):return None
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (ValueError,TypeError):return None


def schedule_events(events, season, now, schedule_root=None):
    """Use the existing full NFL schedule for January games outside the prop window."""
    merged={}
    teams={}
    for event in events:
        for c in (event.get('competitions') or [{}])[0].get('competitors',[]):
            t=c.get('team') or {}
            if t.get('id') and t.get('displayName'):teams[norm(t['displayName'])]=t
    if schedule_root:
        try:
            folder=Path(schedule_root)
            meta=json.loads((folder/'meta.json').read_text())
            at=instant(meta.get('generated_at'))
            if meta.get('season')==season and at and 0<=(now-at).total_seconds()<=48*3600:
                rows=json.loads((folder/'games.json').read_text())
                for g in rows:
                    if g.get('season_type')!=2 or not g.get('game_id'):continue
                    competitors=[]
                    for side in ('home','away'):
                        name=g.get(side+'_name');t=teams.get(norm(name))
                        if not t:break
                        competitors.append({'homeAway':side,'team':t})
                    if len(competitors)!=2:continue
                    start=instant(g.get('date'))
                    state='post' if g.get('completed') else 'pre'
                    merged[str(g['game_id'])]={'id':str(g['game_id']),'date':g.get('date'),
                        'week':{'number':g.get('week')},'season':{'year':season,'type':2},
                        'status':{'type':{'state':state,'completed':bool(g.get('completed')),'description':g.get('status')}},
                        'competitions':[{'competitors':competitors}]}
        except (OSError,ValueError,TypeError):pass
    for event in events:
        if event.get('id') and (event.get('season') or {}).get('year')==season and (event.get('season') or {}).get('type')==2:
            merged[str(event['id'])]=event
    return sorted(merged.values(),key=lambda e:str(e.get('date') or ''))


def roster_rows(payloads, events):
    registry={}
    for event in events:
        for c in (event.get('competitions') or [{}])[0].get('competitors',[]):
            t=c.get('team') or {}
            if t.get('id'):registry[norm(t.get('displayName'))]=t
    teams={};players={}
    for fallback,payload in payloads:
        team={**registry.get(norm(fallback),{}),**(payload.get('team') or {})}
        tid=str(team.get('id') or '')
        if not tid or tid not in {str(t.get('id')) for t in registry.values()}:continue
        name=team.get('displayName') or fallback
        groups=payload.get('athletes') or []
        items=[a for group in groups for a in (group.get('items') or ([group] if group.get('id') else []))]
        if not items:continue
        teams[tid]={'id':tid,'name':name,'abbreviation':team.get('abbreviation') or name}
        for a in items:
            pid=str(a.get('id') or '');player=a.get('displayName') or a.get('fullName')
            if not pid or not player:continue
            pos=a.get('position') or {};status=a.get('status') or {};inj=(a.get('injuries') or [{}])[0]
            availability=str(inj.get('status') or (inj.get('type') or {}).get('description') or status.get('name') or 'Not reported')
            raw_status=str(status.get('type') or status.get('name') or '')
            blocked=any(x in norm(availability+' '+raw_status) for x in ('injuredreserve','suspended','physicallyunable','practicesquad')) or norm(availability) in ('out','ir','pup','inactive')
            players[tid,pid]={'player_id':pid,'player':player,'team_id':tid,'team':name,
                'team_abbreviation':teams[tid]['abbreviation'],'position':pos.get('abbreviation') or 'UNK',
                'availability':availability,'unavailable':blocked}
    id_teams=defaultdict(set)
    for row in players.values():id_teams[row['player_id']].add(row['team_id'])
    for row in players.values():
        if len(id_teams[row['player_id']])>1:
            row.update(unavailable=True,availability='Roster conflict: team unconfirmed')
    return teams,list(players.values()),registry


def extra_form(summaries, now):
    """Extra counts require a complete denominator of observed appearances.

    An omitted interception/fumble category is unknown, not a zero. This avoids
    projecting one interception a week from a table listing only players who
    happened to intercept a pass.
    """
    histories=defaultdict(dict);appearances=defaultdict(set);last_played={}
    for summary in summaries:
        header=summary.get('header') or {};comp=(header.get('competitions') or [{}])[0]
        at=instant(comp.get('date') or header.get('date') or summary.get('_weekly_event_date'))
        complete=((comp.get('status') or {}).get('type') or {}).get('completed')
        if complete is None:complete=summary.get('_weekly_completed',False)
        if not complete or not at or at>now:continue
        for block in (summary.get('boxscore') or {}).get('players',[]):
            measured={};defenders=set();participants=set();optional=set()
            for group in block.get('statistics',[]):
                kind=norm(group.get('type') or group.get('name') or group.get('displayName'))
                names=group.get('keys') or group.get('names') or group.get('labels') or []
                keys=[norm(n) for n in names]
                if 'interceptions' in kind and 'interceptions' in keys:optional.add('def_int')
                if 'fumbles' in kind and 'fumblesrecovered' in keys:optional.add('fumbles_rec')
                for row in group.get('athletes',[]):
                    pid=str((row.get('athlete') or {}).get('id') or '')
                    if not pid:continue
                    last_played[pid]=max(at,last_played.get(pid,at))
                    if 'interception' not in kind and 'fumble' not in kind:participants.add(pid)
                    if 'defens' in kind and 'interception' not in kind and 'fumble' not in kind:defenders.add(pid)
                    if 'punting' in kind:appearances[pid,'punting'].add(at)
                    for key,value in zip(keys,row.get('stats',[])):
                        field=None
                        if 'punting' in kind:field={'punts':'punts','puntingyards':'punt_yds','puntyards':'punt_yds','yards':'punt_yds'}.get(key)
                        elif 'defens' in kind or 'interceptions' in kind or 'fumbles' in kind:
                            field={'interceptions':'def_int','fumblesrecovered':'fumbles_rec','defensivetouchdowns':'def_td'}.get(key)
                        value=finite(value)
                        if field and value is not None and value>=0:measured[pid,field]=value
            for pid in participants:appearances[pid,'any'].add(at)
            for pid in defenders:appearances[pid,'defense'].add(at)
            for field in optional:
                for pid in defenders if field=='def_int' else participants:
                    measured.setdefault((pid,field),0.0)
            for (pid,field),value in measured.items():histories[pid,field][at]=value
    result=defaultdict(dict)
    for (pid,field),values in histories.items():
        role='punting' if field in ('punts','punt_yds') else 'any' if field=='fumbles_rec' else 'defense'
        dates=sorted(appearances[pid,role])[-8:]
        if len(dates)<2 or any(day not in values for day in dates):continue
        vals=[values[day] for day in dates]
        weighted=sum((i+1)*v for i,v in enumerate(vals))/sum(range(1,len(vals)+1))
        result[pid][field]={'value':round(.65*weighted+.35*statistics.median(vals),2),'samples':len(vals)}
    return result,{pid:at.isoformat() for pid,at in last_played.items()}


def build_snapshot(projections, payloads, events, summaries, season, now):
    teams,players,registry=roster_rows(payloads,events)
    if not players:raise ValueError('No verified NFL roster was available')
    schedule=defaultdict(list);team_games=defaultdict(set);all_teams={}
    for event in events:
        try:week=int((event.get('week') or {}).get('number') or 0)
        except (TypeError,ValueError):continue
        if not 1<=week<=18:continue
        competitors=(event.get('competitions') or [{}])[0].get('competitors',[])
        pair={c.get('homeAway'):c.get('team') or {} for c in competitors}
        if not all(pair.get(s,{}).get('id') for s in ('home','away')):continue
        start=instant(event.get('date'))
        if not start:continue
        status=(event.get('status') or {}).get('type') or {}
        game={'event_id':str(event['id']),'start':start.isoformat(),'week':week,
              'state':status.get('state'),'time_tbd':any('TBD' in str(status.get(k,'')) for k in ('description','shortDetail','detail')),
              **{s:str(pair[s]['id']) for s in ('home','away')}}
        schedule[week].append(game)
        for s in ('home','away'):
            t=pair[s];tid=str(t['id']);team_games[tid].add(game['event_id'])
            all_teams[tid]={'id':tid,'name':t.get('displayName') or tid,'abbreviation':t.get('abbreviation') or tid}
    live=[w for w,gs in schedule.items() if any(g['state']=='in' and 0<=(now-instant(g['start'])).total_seconds()<=8*3600 for g in gs)]
    future=[(g['start'],w) for w,gs in schedule.items() for g in gs if instant(g['start'])>now]
    current=min(live) if live else min(future)[1] if future else max(schedule,default=1)
    by_name=Counter((norm(p['team']),norm(p['player'])) for p in players)
    predicted=defaultdict(dict)
    for raw in projections:
        p=raw.to_dict() if hasattr(raw,'to_dict') else raw
        field=MARKETS.get(p.get('market'));value=finite(p.get('projection'))
        identity=(norm(p.get('team')),norm(p.get('player')))
        if field and value is not None and p.get('roster_verified',True) and by_name[identity]==1:
            predicted[str(p.get('event_id')),identity][field]={'value':value,'samples':p.get('samples',0)}
    extra,last_played=extra_form(summaries,now)
    rows=[];weeks=[]
    for week in range(1,19):
        games=schedule[week];by_team=defaultdict(list)
        for g in games:
            for s in ('home','away'):by_team[g[s]].append(g)
        end=max((g['start'] for g in games),default=None)
        weeks.append({'week':week,'label':f'Week {week}','games':len(games),'last_kickoff':end,
                      'phase':'past' if week<current else 'current' if week==current else 'early'})
        if week<current:continue  # Never manufacture historical predictions.
        for player in players:
            tid=player['team_id'];matches=by_team[tid];g=matches[0] if len(matches)==1 else None
            row={**player,'id':f'{season}:{week}:{tid}:{player["player_id"]}', 'season':season,'week':week,
                 'event_id':g['event_id'] if g else None,'start':g['start'] if g else None,
                 'time_tbd':g.get('time_tbd',False) if g else False,'opponent':None,'venue':None,
                 'phase':weeks[-1]['phase'],'stats':{},'stat_samples':{},'samples':0,
                 'last_played_at':last_played.get(player['player_id']),'model_version':VERSION,
                 'captured_at':None,'first_captured_at':None}
            if not g:
                row['status']='Bye week' if not matches and len(team_games[tid])==17 else 'Schedule unavailable'
            else:
                opponent=g['away'] if g['home']==tid else g['home']
                row.update(opponent=all_teams.get(opponent,{}).get('abbreviation'),venue='Home' if g['home']==tid else 'Away')
                if instant(g['start'])<=now or g['state']!='pre':row['status']='No saved pregame forecast'
                elif player['unavailable']:row['status']='Unavailable / role not confirmed'
                else:
                    stats={**predicted.get((g['event_id'],(norm(player['team']),norm(player['player']))),{}),**extra.get(player['player_id'],{})}
                    row['stats']={k:v['value'] for k,v in stats.items()};row['stat_samples']={k:v['samples'] for k,v in stats.items()}
                    row['samples']=max(row['stat_samples'].values(),default=0)
                    row['status']='Early outlook · conditional role' if week>current and stats else 'Projection · conditional role' if stats else 'No supported individual stat history'
                    if stats:row['captured_at']=row['first_captured_at']=now.isoformat()
                    if row['stats'].get('punts',0)>0 and 'punt_yds' in row['stats']:
                        row['stats']['punt_avg']=round(row['stats']['punt_yds']/row['stats']['punts'],2)
            rows.append(row)
    return {'schema':1,'model_version':VERSION,'generated_at':now.isoformat(),'season':season,
            'current_week':current,'weeks':weeks,'teams':sorted(all_teams.values(),key=lambda t:t['name']),
            'roster_teams':sorted(teams),'missing_roster_teams':[t['name'] for tid,t in all_teams.items() if tid not in teams],
            'rostered_players':len(players),'rows':rows,'automatic_qualification':False,
            'method':'Existing ESPN recent-form and opponent-allowance research model; punting/extra defensive counts use recent completed-game form. Conditional on a continuing role, not a playing-time guarantee.',
            'sources':['https://www.espn.com/nfl/players','https://www.espn.com/nfl/scoreboard']}


def merge_history(previous, snapshot, now):
    """Update before kickoff only. Preserve the last saved pregame stat line."""
    old={r['id']:r for r in previous.get('rows',[]) if r.get('id')}
    rows={}
    fresh={r['id']:r for r in snapshot['rows']}
    week_end={w['week']:instant(w.get('last_kickoff')) for w in snapshot['weeks']}
    for key,row in old.items():
        start=instant(row.get('start'));captured=instant(row.get('captured_at'))
        moved=instant(fresh.get(key,{}).get('start'))
        if start and start<=now and captured and captured<start and not (moved and moved>now):
            rows[key]={**row,'status':'Frozen pregame projection','phase':'frozen'}
        elif not start and week_end.get(row['week']) and week_end[row['week']]<=now:
            rows[key]=row
    for row in snapshot['rows']:
        if row['id'] in rows:continue
        prior=old.get(row['id']);new=dict(row)
        if prior and new.get('captured_at') and prior.get('event_id')==new.get('event_id') and prior.get('model_version')==new.get('model_version'):
            new['first_captured_at']=prior.get('first_captured_at') or new['captured_at']
            fields=('stats','stat_samples','availability','position','start','event_id','model_version')
            if all(new.get(k)==prior.get(k) for k in fields):new['captured_at']=prior.get('captured_at') or new['captured_at']
        start=instant(new.get('start'));captured=instant(new.get('captured_at'))
        if new.get('stats') and not (start and captured and captured<start and now<start):
            new.update(stats={},stat_samples={},samples=0,captured_at=None,first_captured_at=None,status='No saved pregame forecast')
        rows[new['id']]=new
    return {'schema':1,'season':snapshot['season'],'rows':list(rows.values())}


def publish(snapshot, project_root):
    """Write complete versioned chunks and retain the prospective record."""
    root=Path(project_root);now=instant(snapshot['generated_at'])
    state_path=root/f'state/nfl-weekly-{snapshot["season"]}.json'
    try:previous=json.loads(state_path.read_text())
    except (OSError,ValueError):previous={}
    history=merge_history(previous,snapshot,now)
    target=root/'site/data/nfl-weekly';target.parent.mkdir(parents=True,exist_ok=True)
    manifest={k:v for k,v in snapshot.items() if k!='rows'}
    manifest['weeks']=[dict(w) for w in snapshot['weeks']]
    by_week=defaultdict(list)
    for row in history['rows']:by_week[row['week']].append(row)
    with tempfile.TemporaryDirectory(prefix='.nfl-weekly-',dir=target.parent) as temp:
        stage=Path(temp)/'feed';stage.mkdir()
        for week in manifest['weeks']:
            rows=sorted(by_week[week['week']],key=lambda r:(r['team'],r['player'],r['player_id']))
            week.update(file=f'week-{week["week"]:02d}.json',players=len(rows),projected_players=sum(bool(r['stats']) for r in rows))
            (stage/week['file']).write_text(json.dumps({'generated_at':manifest['generated_at'],'season':manifest['season'],'week':week['week'],'rows':rows},separators=(',',':'),allow_nan=False)+'\n')
        (stage/'manifest.json').write_text(json.dumps(manifest,separators=(',',':'),allow_nan=False)+'\n')
        backup=target.with_name('.nfl-weekly-previous')
        if backup.exists():shutil.rmtree(backup)
        if target.exists():target.rename(backup)
        try:stage.rename(target)
        except OSError:
            if backup.exists():backup.rename(target)
            raise
        if backup.exists():shutil.rmtree(backup)
    state_path.parent.mkdir(parents=True,exist_ok=True)
    tmp=state_path.with_suffix('.tmp');tmp.write_text(json.dumps(history,indent=1,allow_nan=False)+'\n');tmp.replace(state_path)
    return manifest
