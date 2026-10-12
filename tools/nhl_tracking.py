"""Prospective NHL scorer evidence. Ordinary site builds never capture forecasts."""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
try:
    from .research.common import instant, number, read, write
except ImportError:
    from research.common import instant, number, read, write
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=Path('projects/bet-ledger-hq/data/research/nhl-scorers.json')

def identity(r,version):return '|'.join([str(r['event_id']),str(r['athlete_id']),version])

def capture(archive,props,games,at):
    rows=archive.setdefault('records',[]);seen={r['id'] for r in rows};publication=instant(props.get('generated_at'))
    if not publication or not 0<=(at-publication).total_seconds()<=6*3600:return archive
    by_id={str(g['game_id']):g for g in games}
    for q in props.get('goal_scorers',[]):
        start=instant(q.get('start_time'));g=by_id.get(str(q.get('event_id')),{})
        if not start or not at<start<=at+timedelta(days=2) or g.get('completed') or g.get('state')!='pre' or not g.get('nhl_game_id'):continue
        forecasts=[(q.get('model_version'),q.get('model_prob'))]
        shadow=q.get('shadow') or {}
        if shadow.get('version'):forecasts.append((shadow['version'],shadow.get('model_prob')))
        for version,p in forecasts:
            if not version or number(p) is None or not 0<p<1:continue
            key=identity(q,version)
            if key in seen:continue
            rows.append({'id':key,'version':version,'event_id':str(q['event_id']),'nhl_game_id':str(g['nhl_game_id']),'athlete_id':str(q['athlete_id']),
                'player':q['player'],'team':q['team'],'matchup':q['matchup'],'start':q['start_time'],'captured_at':at.isoformat(),
                'publication_at':props['generated_at'],'probability':p,'result':None,'probability_basis':'Conditional on playing; regulation/OT goal; shootout excluded'})
            seen.add(key)
    return archive

def grade(archive,games,results,observed_at,official_at,now):
    observed,official=instant(observed_at),instant(official_at)
    if not observed or not official or observed>now or official>now:return archive
    finals={str(g.get('nhl_game_id')):g for g in games if g.get('completed') and g.get('state')=='post'}
    index=defaultdict(list)
    for q in results:index[(str(q.get('gameId')),str(q.get('playerId')))].append(q)
    for r in archive.get('records',[]):
        if r.get('result') is not None:continue
        start=instant(r['start']);frozen=instant(r['captured_at'])
        if not start or not frozen or frozen>=start or start>=min(observed,official) or r['nhl_game_id'] not in finals:continue
        matches=index.get((r['nhl_game_id'],r['athlete_id']),[])
        signatures={(q.get('I_F_goals'),q.get('icetime'),q.get('team')) for q in matches}
        if len(signatures)!=1:continue
        q=matches[0];seconds=number(q.get('icetime'));goals=number(q.get('I_F_goals'))
        if seconds is None or seconds<=0 or goals is None or goals<0 or int(goals)!=goals:continue
        r.update(result=int(goals>0),goals=int(goals),result_observed_at=observed_at,official_result_observed_at=official_at,
                 result_source='Completed official NHL game + MoneyPuck player game download; participation verified')
    return archive

def metrics(rows):
    n=len(rows)
    if not n:return {'n':0,'brier':None,'logloss':None,'hit_rate':None,'predicted':None}
    return {'n':n,'hit_rate':sum(r['result'] for r in rows)/n,'predicted':sum(r['probability'] for r in rows)/n,
            'brier':sum((r['probability']-r['result'])**2 for r in rows)/n,
            'logloss':-sum(math.log(max(1e-12,r['probability'] if r['result'] else 1-r['probability'])) for r in rows)/n}

def report(archive,at):
    grouped=defaultdict(list)
    for r in archive.get('records',[]):grouped[r['version']].append(r)
    models=[]
    for version,rows in grouped.items():
        decided=[r for r in rows if r.get('result') in (0,1)];m=metrics(decided);m.update(version=version,pending=len(rows)-len(decided),games=len({r['event_id'] for r in decided}),dates=len({r['start'][:10] for r in decided}),validated=False)
        m['bins']=[{'from':lo,'to':hi,**metrics([r for r in decided if lo<=r['probability']<hi])} for lo,hi in [(0,.15),(.15,.25),(.25,.35),(.35,.5),(.5,1)]]
        models.append(m)
    pairs=defaultdict(dict)
    for r in archive.get('records',[]):
        if r.get('result') in (0,1):pairs[(r['event_id'],r['athlete_id'],r['captured_at'])][r['version']]=r
    paired=[p for p in pairs.values() if 'nhl-anytime-gamma-1.0' in p and 'nhl-role-xg-1.0' in p]
    groups=defaultdict(list)
    for p in paired:
        a,b=p['nhl-anytime-gamma-1.0'],p['nhl-role-xg-1.0'];groups[a['event_id']].append((b['probability']-b['result'])**2-(a['probability']-a['result'])**2)
    diff=sum(sum(x) for x in groups.values())/len(paired) if paired else None
    interval=None
    if len(groups)>=30:
        import numpy as np
        rng=np.random.default_rng(12026);vals=list(groups.values());draws=[]
        for _ in range(1000):
            sample=[vals[i] for i in rng.integers(0,len(vals),len(vals))];draws.append(sum(sum(x) for x in sample)/sum(len(x) for x in sample))
        interval=[float(x) for x in np.quantile(draws,[.025,.975])]
    return {'schema':1,'generated_at':at.isoformat(),'models':models,'paired':{'players':len(paired),'games':len(groups),'brier_difference_shadow_minus_baseline':diff,'game_cluster_95_interval':interval},
        'status':'Collecting prospective scorer evidence; promotion disabled','rules':['First pregame capture per player/game/model version.','Missing participation stays ungraded; it is never counted as zero goals.','No retrospective forecasts. Paired comparisons require the same capture time.','Intervals resample games, since players from one game are dependent.'],'minimum_review':{'players':200,'games':100,'dates':28},'validated':False}

def build(root=ROOT,capturing=False,now=None):
    now=now or datetime.now(timezone.utc);props=read(root/'projects/props-edge/site/data/nhl-props.json',{});folder=root/'projects/nhl-edge-lab/site/data'
    games=read(folder/'games.json',[]);inputs=read(folder/'public-research.json',{});meta=read(folder/'meta.json',{});archive=read(root/ARCHIVE,{'schema':1,'records':[]})
    if capturing:
        capture(archive,props,games,now);grade(archive,games,inputs.get('player_results',[]),inputs.get('results_observed_at'),meta.get('generated_at'),now)
        archive['generated_at']=now.isoformat();write(root/ARCHIVE,archive)
    out=report(archive,now);write(folder/'scorer-tracking.json',out)
    valid=props.get('sport')=='NHL'
    props['scorer_tracking']=out
    if valid:write(root/'projects/props-edge/site/data/nhl-props.json',props)
    return out

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--capture',action='store_true');args=parser.parse_args();r=build(capturing=args.capture);print('NHL scorer tracking',[(x['version'],x['n'],x['pending']) for x in r['models']])
