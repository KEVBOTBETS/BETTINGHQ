"""Public, sport-neutral forecast audit. Never reads a wager ledger or trains a model.

Only original pregame snapshots qualify. Missing probabilities, identities and
results remain missing. Quarantined source history is retained unchanged.
"""
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LEAGUES = {'nfl':'NFL', 'ncaaf':'NCAAF', 'mlb':'MLB', 'nhl':'NHL', 'wnba':'WNBA'}

def number(value):
    if value is None or isinstance(value, bool): return None
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError): return None

def instant(value):
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return d if d.tzinfo else None
    except (ValueError, TypeError): return None

def normalize(sport, row):
    """Return a compact auditable game, or an explicit exclusion reason."""
    mlb=sport=='mlb'; nhl=sport=='nhl'
    event=row.get('gamePk') if mlb else row.get('game_id') if nhl else row.get('event_id')
    matchup=f"{row.get('away','')} @ {row.get('home','')}" if mlb or nhl else row.get('matchup','')
    if not event: return None,'missing event identity'
    if not matchup or re.search(r'\b(TBD|TBA|Unknown|None)\b',matchup,re.I): return None,'unresolved teams'
    start=instant(row.get('start')); captured=instant(row.get('updated_at') if mlb else row.get('frozen_at') if nhl else row.get('captured_at'))
    if not start or not captured or captured>=start: return None,'missing or non-pregame snapshot'
    p=number(row.get('p_home') if mlb or nhl else row.get('probability'))
    if p is None or not 0<=p<=1: return None,'invalid probability'
    result=row.get('result') if nhl else {}
    result=result if isinstance(result,dict) else {}
    h=number(result.get('home') if nhl else row.get('final_home'))
    a=number(result.get('away') if nhl else row.get('final_away'))
    final=bool(result) if nhl else row.get('status')=='graded' if mlb else row.get('result')=='Graded'
    if not final or h is None or a is None: return None,'awaiting verified result'
    if h<0 or a<0: return None,'invalid final score'
    if h==a: return None,'tied game (no binary winner)'
    market=number(row.get('p_home_market') if mlb else (row.get('market_snapshot') or {}).get('p_home'))
    if not mlb:
        observed=instant((row.get('market_snapshot') or {}).get('observed_at'))
        if not observed or observed>captured or observed>=start: market=None
    if market is not None and not 0<market<1: market=None
    projection=row.get('projection') or {}
    margin=number((number(row.get('proj_home')) or 0)-(number(row.get('proj_away')) or 0)) if mlb and number(row.get('proj_home')) is not None and number(row.get('proj_away')) is not None else number(projection.get('mu')) if nhl else number(row.get('margin'))
    total=number(row.get('proj_total') if mlb else projection.get('total') if nhl else row.get('total'))
    spread=number(row.get('market_spread'))
    return {'id':str(event),'sport':sport,'matchup':matchup,'start':start.isoformat(),'captured_at':captured.isoformat(),
        'season':row.get('season') or start.year,'version':row.get('model_version') or row.get('version') or row.get('snapshot_policy') or 'legacy',
        'p':p,'y':int(h>a),'market':market,'margin':margin,'total':total,
        'market_margin':-spread if spread is not None else None,'market_total':number(row.get('market_total')),
        'actual_margin':h-a,'actual_total':h+a,'home_score':h,'away_score':a},None

def build(root, out):
    result={'schema':1,'generated_at':datetime.now(timezone.utc).isoformat(),'leagues':{},'records':[]}
    for sport,label in LEAGUES.items():
        path=root/'projects'/('mlb-edge/data/predictions.json' if sport=='mlb' else f'{sport}-edge-lab/site/data/accuracy.json')
        data=json.loads(path.read_text()); rows=list(data.get('games',{}).values()) if sport=='mlb' else data.get('records',[])
        if sport not in ('mlb','nhl'): rows=[r for r in rows if r.get('kind')=='game']
        # Use only the latest season represented by the public report.
        years=[int(r.get('season') or str(r.get('start',''))[:4]) for r in rows if str(r.get('season') or str(r.get('start',''))[:4]).isdigit()]
        season=max(years) if years else None
        counts=Counter(); seen=set(); accepted=[]
        for row in sorted(rows,key=lambda r:str(r.get('captured_at') or r.get('frozen_at') or r.get('updated_at') or '')):
            if int(row.get('season') or str(row.get('start',''))[:4] or 0)!=season: continue
            entry,reason=normalize(sport,row)
            if reason: counts[reason]+=1; continue
            if entry['id'] in seen: counts['duplicate event']+=1; continue
            seen.add(entry['id']); accepted.append(entry)
        result['records'].extend(accepted)
        result['leagues'][sport]={'label':label,'season':season,'source_updated':data.get('generated_at'),
            'accepted':len(accepted),'excluded':dict(counts),'snapshot_policy':'Latest pregame' if sport=='mlb' else 'First pregame'}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
    return result
