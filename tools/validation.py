"""Prospective market controls. Published recommendations may pause; research stays open.

Only immutable v2 captures with pregame prices and later verified outcomes vote.
One player/market/event vote per version; paired comparisons use the frozen price.
"""
from collections import defaultdict
from datetime import datetime, timezone
import numpy as np
try:
    from .research.common import instant, number, decimal
    from .research.calibration import VERSION, score
except ImportError:
    from research.common import instant, number, decimal
    from research.calibration import VERSION, score

MIN_CONTRACTS, MIN_EVENTS, MIN_DAYS = 200, 100, 28

def interval(rows, values):
    groups=defaultdict(list)
    for row,value in zip(rows,values):groups[row['start'][:10]].append(value)
    if len(groups)<MIN_DAYS:return None
    sums=np.array([sum(g) for g in groups.values()]);sizes=np.array([len(g) for g in groups.values()])
    rng=np.random.default_rng(781);ids=rng.integers(0,len(sums),(2000,len(sums)))
    return [float(x) for x in np.quantile(sums[ids].sum(axis=1)/sizes[ids].sum(axis=1),[.025,.975])]

def enough(rows):
    return len(rows)>=MIN_CONTRACTS and len({r['event_id'] for r in rows})>=MIN_EVENTS and len({r['start'][:10] for r in rows})>=MIN_DAYS

def paired(rows, a, b):
    def error(p,y,kind):return (p-y)**2 if kind=='brier' else score(p,y)
    return {kind:{'mean':sum(values)/len(values) if values else None,'interval':interval(rows,values) if enough(rows) else None}
            for kind in ['brier','log_loss']
            for values in [[error(r[a],r['result']['outcome']=='win',kind)-error(r[b],r['result']['outcome']=='win',kind) for r in rows]]}

def report(archive, now=None):
    now=now or datetime.now(timezone.utc);groups=defaultdict(list);excluded=0
    for r in archive:
        capture,start,result=instant(r.get('captured_at')),instant(r.get('start')),instant((r.get('result') or {}).get('observed_at'))
        quote=instant(r.get('observed_at'));generated=instant(r.get('generated_at'))
        p=number(r.get('raw_no_push'))
        valid=(r.get('version')==VERSION and capture and start and quote and generated and quote<=capture<start
               and generated<=capture and (capture-quote).total_seconds()<=4*3600 and (capture-generated).total_seconds()<=6*3600
               and r.get('sport') and r.get('market') and r.get('baseline_version') and r.get('event_id') and r.get('book') and decimal(r.get('price'))
               and r.get('quote_status','observed')=='observed' and not r.get('reference_only') and r.get('price_source')!='model'
               and result and start<=result<=now and (r.get('result') or {}).get('outcome') in ['win','loss'] and p is not None and 0<=p<=1)
        if not valid:excluded+=1;continue
        r={**r,'raw_no_push':p,'market_no_push':number(r.get('market_no_push')),'calibrated_no_push':number(r.get('calibrated_no_push'))}
        groups[(r['sport'],r['market'],r['baseline_version'])].append(r)
    markets=[]
    # Include captured markets with no completed prospective outcomes yet.
    keys=set(groups)|{(r['sport'],r['market'],r['baseline_version']) for r in archive if r.get('version')==VERSION and all(r.get(k) for k in ['sport','market','baseline_version'])}
    for sport,market,version in sorted(keys):
        unique={}
        for r in sorted(groups[sport,market,version],key=lambda r:r['captured_at']):unique.setdefault((r['event_id'],r.get('player_id') or r.get('player','')),r)
        rows=list(unique.values());pairs=[r for r in rows if number(r.get('market_no_push')) is not None and 0<=r['market_no_push']<=1]
        residual=[max(r['raw_no_push'],1-r['raw_no_push'])-((r['result']['outcome']=='win') if r['raw_no_push']>=.5 else (r['result']['outcome']=='loss')) for r in rows]
        over=interval(rows,residual) if enough(rows) else None;vs_market=paired(pairs,'raw_no_push','market_no_push')
        reasons=[]
        if over and over[0]>.05:reasons.append('Sustained overconfidence exceeds 5 percentage points')
        if all(v['interval'] and v['interval'][0]>0 for v in vs_market.values()):reasons.append('Model has higher paired Brier error and log loss than the frozen market benchmark')
        status='paused' if reasons else 'monitoring' if enough(rows) else 'building-evidence'
        shadow=[]
        for r in pairs:
            fit=r.get('calibrator') or {};trained,last=instant(fit.get('trained_at')),instant(fit.get('last_result_at'));capture=instant(r['captured_at']);p=number(r.get('calibrated_no_push'))
            if fit.get('enabled') and fit.get('contracts',0)>=MIN_CONTRACTS and fit.get('games',0)>=MIN_EVENTS and trained and last and last<trained<=capture and p is not None and 0<=p<=1:shadow.append(r)
        shadow_current=paired(shadow,'calibrated_no_push','raw_no_push');shadow_market=paired(shadow,'calibrated_no_push','market_no_push')
        candidate=bool(enough(shadow) and all(v['interval'] and v['interval'][1]<0 for group in [shadow_current,shadow_market] for v in group.values()))
        bins=[]
        for i in range(5):
            b=[r for r in rows if min(4,int(r['raw_no_push']*5))==i]
            bins.append({'low':i/5,'high':(i+1)/5,'n':len(b),'predicted':sum(r['raw_no_push'] for r in b)/len(b) if b else None,'actual':sum(r['result']['outcome']=='win' for r in b)/len(b) if b else None})
        markets.append({'sport':sport,'market':market,'baseline_version':version,'status':status,'recommendations_paused':bool(reasons),'research_available':True,'reasons':reasons,
          'contracts':len(rows),'events':len({r['event_id'] for r in rows}),'days':len({r['start'][:10] for r in rows}),'market_pairs':len(pairs),
          'predicted':sum(r['raw_no_push'] for r in rows)/len(rows) if rows else None,'actual':sum(r['result']['outcome']=='win' for r in rows)/len(rows) if rows else None,
          'overconfidence_interval':over,'vs_market':vs_market,'calibration':bins,'shadow_tests':len(shadow),'shadow_status':'review-candidate' if candidate else 'shadow-only',
          'shadow_vs_current':shadow_current,'shadow_vs_market':shadow_market,'promotion_enabled':False})
    return {'schema':1,'version':'prospective-controls-v1','generated_at':now.isoformat(),'minimum_contracts':MIN_CONTRACTS,'minimum_events':MIN_EVENTS,'minimum_dates':MIN_DAYS,'excluded':excluded,'markets':markets,
      'policy':'Forward captures only; one player/market/event vote per baseline version. Pregame same-book paired prices only. Day-clustered bootstrap intervals are exploratory controls, not proof of profit. Sufficient evidence of sustained overconfidence or inferiority to the market pauses recommendations, while manual per-game options and moonshots remain available. Calibrators stay shadow-only until reviewed.'}
