"""Uncalibrated NBA milestone estimates from completed regular-season game logs."""
import datetime as dt
import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .http import JsonClient, ProviderError

VERSION = 'nba-milestones-v1'
LEVELS = {'Points':[10,15,20,25,30,35,40], 'Rebounds':[4,6,8,10,12,15], 'Assists':[4,6,8,10,12], 'Threes':[1,2,3,4,5,6]}
KEYS = {'Points':'PTS','Rebounds':'REB','Assists':'AST','Threes':'3PT'}

def number(x):
    try:
        v=float(str(x).split('-')[0].split(':')[0]);return v if math.isfinite(v) and v>=0 else None
    except (TypeError,ValueError):return None

def game_log(data, now):
    from .multisport import instant
    labels=data.get('labels',[]);events=data.get('events') or {};found={}
    for season in data.get('seasonTypes') or []:
        if not str(season.get('displayName','')).lower().endswith('regular season'):continue
        for category in season.get('categories') or []:
            for row in category.get('events') or []:
                identifier=str(row.get('eventId',''));event=events.get(identifier,{})
                at=instant(event.get('gameDate'));stats=dict(zip(labels,row.get('stats') or []))
                if not at or at>=now or at<now-dt.timedelta(days=400) or event.get('gameResult') not in ['W','L'] or not event.get('score'):continue
                if (event.get('team') or {}).get('isAllStar') or (event.get('opponent') or {}).get('isAllStar') or 'all-star' in str(event.get('eventNote','')).lower():continue
                minutes=number(stats.get('MIN'))
                if minutes is None or minutes<=0:continue
                found[identifier]={'game_id':identifier,'start':at.isoformat(),'minutes':minutes,'stats':{k:number(stats.get(k)) for k in KEYS.values()}}
    return sorted(found.values(),key=lambda r:r['start'])[-30:]

def histories(root, rosters, now):
    """One prior-season request per current athlete; compact cache lasts seven days."""
    from .multisport import instant
    path=Path(root)/'state/nba-milestone-history.json'
    try:saved=json.loads(path.read_text())
    except (OSError,ValueError):saved={}
    prior_season=now.year+(now.month>=8)-1
    deadline=time.monotonic()+300
    athletes=sorted({str(a['id']) for rows in rosters.values() for a in rows if a.get('id')})[:600]
    def read(identifier):
        key=f'{identifier}:{prior_season}';old=saved.get(key,{})
        if instant(old.get('at')) and 0<=(now-instant(old['at'])).total_seconds()<7*86400:return identifier,old
        if time.monotonic()>deadline:return identifier,{'at':now.isoformat(),'rows':[],'unavailable':True}
        try:
            data=JsonClient('Public ESPN game logs','https://site.web.api.espn.com',timeout=12).get(f'/apis/common/v3/sports/basketball/nba/athletes/{identifier}/gamelog',{'season':prior_season},retries=0)
            return identifier,{'at':now.isoformat(),'rows':game_log(data,now)}
        except ProviderError:return identifier,{'at':now.isoformat(),'rows':[],'unavailable':True}
    with ThreadPoolExecutor(max_workers=6) as pool:result=dict(pool.map(read,athletes))
    compact={f'{identifier}:{prior_season}':value for identifier,value in result.items()}
    # Retry unavailable providers next publication rather than caching an outage for a week.
    compact={k:v for k,v in compact.items() if not v.get('unavailable')}
    path.parent.mkdir(exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(compact,separators=(',',':'))+'\n');temp.replace(path)
    return {identifier:value.get('rows',[]) for identifier,value in result.items()}

def forecasts(watch, past, current, injuries, now):
    from .multisport import instant
    norm=lambda x:re.sub('[^a-z0-9]','',str(x).lower())
    flagged={norm(i.get('name')) for i in injuries if str(i.get('status','')).lower() not in ['active','healthy','available','']}
    live={}
    for row in current:
        if row.get('state')!='post' or not instant(row.get('start')) or instant(row['start'])>=now:continue
        minutes=number((row.get('stats') or {}).get('MIN'))
        if not minutes:continue
        live.setdefault((str(row.get('player_id')),row.get('team')), {})[str(row.get('game_id'))]={'game_id':str(row.get('game_id')),'start':row['start'],'minutes':minutes,'stats':{k:number((row.get('stats') or {}).get(k)) for k in KEYS.values()}}
    result=[]
    for q in watch:
        if q.get('market') not in LEVELS or not q.get('roster_verified') or norm(q.get('player')) in flagged:continue
        identifier=str(q['athlete_id']);recent=list(live.get((identifier,q['team']),{}).values());recent=sorted(recent,key=lambda r:r['start'])[-8:]
        prior=[r for r in past.get(identifier,[]) if instant(r.get('start')) and instant(r['start'])<now and instant(r['start'])>=now-dt.timedelta(days=400)]
        prior_ids={r['game_id'] for r in recent};prior=[r for r in prior if r['game_id'] not in prior_ids][-30:]
        prior_minutes=sum(r['minutes'] for r in prior)/len(prior) if prior else 0
        current_minutes=sum(r['minutes'] for r in recent)/len(recent) if recent else None
        if (current_minutes is not None and (current_minutes<15 or prior_minutes and current_minutes<.6*prior_minutes)) or current_minutes is None and prior_minutes<18:continue
        values=[(r['stats'].get(KEYS[q['market']]),.35,'prior') for r in prior]+[(r['stats'].get(KEYS[q['market']]),1.,'current') for r in recent]
        values=[(v,w,source) for v,w,source in values if v is not None and math.isfinite(v)]
        if len(values)<10:continue
        weight=sum(w for _,w,_ in values);neff=weight*weight/sum(w*w for _,w,_ in values)
        for threshold in LEVELS[q['market']]:
            hits=sum(w for v,w,_ in values if v>=threshold);p=(hits+1)/(weight+2)
            if not .18<=p<=.90:continue
            # One-standard-error Wilson lower bound used for ranking, not a calibrated confidence claim.
            lower=(p+1/(2*neff)-math.sqrt(p*(1-p)/neff+1/(4*neff*neff)))/(1+1/neff)
            result.append({**q,'threshold':threshold,'line':threshold-.5,'side':'over','pick':f"{q['player']} {threshold}+ {q['market'].lower()}",
                'model_prob':round(p,6),'ranking_prob':round(lower,6),'model_version':VERSION,'samples':len(values),'effective_samples':round(neff,2),
                'prior_samples':sum(s=='prior' for _,_,s in values),'current_samples':sum(s=='current' for _,_,s in values),'history_hits':sum(v>=threshold for v,_,_ in values),
                'history_latest':max(r['start'] for r in prior+recent),'qualified':False,'status':'availability unconfirmed',
                'reason':'Model selects the threshold from completed regular-season history; current games carry more weight. Prior-season role may differ. Conditional on playing; not calibrated.'})
    return result
