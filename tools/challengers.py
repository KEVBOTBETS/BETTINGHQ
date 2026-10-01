"""Read-only chronological challenger tests; never promotes a model.

Train only on same-league/version results recorded before the test forecast.
Missing result times stay missing. Repeated inspection is exploratory, not proof.
"""
from collections import defaultdict
from datetime import datetime
import math

MIN_TRAIN = 40
MIN_TEST = 100
SLOPES = (.5, .75, 1., 1.25)

def instant(value):
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d if d.tzinfo else None
    except (ValueError, TypeError): return None

def probability(value):
    return isinstance(value, (float,int)) and not isinstance(value,bool) and math.isfinite(value) and 0 <= value <= 1

def loss(p, y):
    p = min(1-1e-6, max(1e-6, p))
    return -(y*math.log(p)+(1-y)*math.log(1-p))

def calibrate(p, slope):
    p = min(1-1e-6, max(1e-6, p))
    return 1/(1+math.exp(-slope*math.log(p/(1-p))))

def slope_for(train):
    return min(SLOPES, key=lambda s: (sum(loss(calibrate(r['p'],s),r['y']) for r in train),abs(s-1)))

def metrics(rows, key):
    n=len(rows)
    buckets=[]
    for i in range(5):
        group=[r for r in rows if min(4,int(r[key]*5))==i]
        buckets.append({'range':[i/5,(i+1)/5],'n':len(group),
            'predicted':sum(r[key] for r in group)/len(group) if group else None,
            'actual':sum(r['y'] for r in group)/len(group) if group else None})
    return {'n':n, 'brier':sum((r[key]-r['y'])**2 for r in rows)/n if n else None,
            'logloss':sum(loss(r[key],r['y']) for r in rows)/n if n else None,
            'calibration':buckets,'calibration_gap':sum(b['n']*abs(b['predicted']-b['actual']) for b in buckets if b['n'])/n if n else None}

def delta(rows, other, metric):
    """Approximate day-clustered 95% interval of paired mean loss differences."""
    groups=defaultdict(list)
    for r in rows:
        score = (lambda p:(p-r['y'])**2) if metric=='brier' else (lambda p:loss(p,r['y']))
        groups[r['start'][:10]].append(score(r['challenger'])-score(r[other]))
    n=len(rows); mean=sum(sum(g) for g in groups.values())/n if n else None
    k=len(groups); interval=None
    if k>=2:
        variance=k/(k-1)*sum((sum(g)-len(g)*mean)**2 for g in groups.values())/(n*n)
        error=1.96*math.sqrt(variance); interval=[mean-error,mean+error]
    return {'mean':mean,'interval':interval,'days':k,'method':'Approximate day-clustered normal 95% interval; exploratory'}

def compare(rows):
    paired=[r for r in rows if probability(r.get('market'))]
    current={m:delta(rows,'p',m) for m in ('brier','logloss')}
    market={m:delta(paired,'market',m) for m in ('brier','logloss')}
    enough=len(rows)>=MIN_TEST and len(paired)>=MIN_TEST and current['brier']['days']>=28 and market['brier']['days']>=28
    favorable=enough and all(v['interval'] and v['interval'][1]<0 for group in (current,market) for v in group.values())
    return {'n':len(rows),'market_pairs':len(paired),'current':metrics(rows,'p'),'challenger':metrics(rows,'challenger'),
            'market':metrics(paired,'market'),'challenger_on_market_pairs':metrics(paired,'challenger'),
            'vs_current':current,'vs_market':market,
            'status':'review-candidate' if favorable else 'insufficient-evidence' if not enough else 'not-demonstrated',
            'promotion_enabled':False}

def evaluate(records):
    reports={}
    for sport in ('nfl','ncaaf','mlb','nhl','wnba'):
        source=[r for r in records if r['sport']==sport]
        valid=[r for r in source if instant(r.get('result_at')) and instant(r['result_at'])>=instant(r['start'])]
        reports[sport]={'excluded_result_time':len(source)-len(valid),'models':[]}
        for version in sorted({r['version'] for r in valid}):
            cohort=sorted([r for r in valid if r['version']==version],key=lambda r:r['captured_at'])
            tested=[]; frozen=defaultdict(list); warmup=0
            for row in cohort:
                cutoff=instant(row['captured_at'])
                train=[r for r in cohort if r['id']!=row['id'] and instant(r['result_at'])<cutoff and instant(r['start'])<cutoff]
                if len(train)>=MIN_TRAIN:
                    slope=slope_for(train)
                    tested.append({**row,'challenger':calibrate(row['p'],slope),'training_games':len(train),'slope':slope,
                                   'last_training_result_at':max(instant(r['result_at']) for r in train).isoformat()})
                else: warmup+=1
                shadow=row.get('challenger') or {}
                at=instant(shadow.get('observed_at'))
                if probability(shadow.get('p_home')) and at and at<=cutoff and at<instant(row['start']) and shadow.get('version'):
                    frozen[shadow['version']].append({**row,'challenger':shadow['p_home']})
            reports[sport]['models'].append({'name':'Chronological slope calibration','version':'symmetric-slope-v1','baseline':version,
                'training_minimum':MIN_TRAIN,'warmup_games':warmup,**compare(tested),
                'predictions':[{'id':r['id'],'start':r['start'],'captured_at':r['captured_at'],'training_games':r['training_games'],'last_training_result_at':r['last_training_result_at'],'slope':r['slope'],'p':r['challenger']} for r in tested]})
            for shadow_version, rows in frozen.items():
                reports[sport]['models'].append({'name':'Frozen NHL context challenger','version':shadow_version,'baseline':version,
                    'training_minimum':0,'warmup_games':0,**compare(rows)})
        if sport=='nhl' and not any(m['name']=='Frozen NHL context challenger' for m in reports[sport]['models']):
            reports[sport]['models'].append({'name':'Frozen NHL context challenger','version':'nhl-context-shadow-1.0','baseline':'nhl-poisson-1.0',
                'training_minimum':0,'warmup_games':0,**compare([])})
    return {'schema':1,'minimum_test_games':MIN_TEST,'minimum_test_days':28,
            'policy':'Shadow only. No automatic promotion. Historical slope replay is exploratory; prospective context forecasts are never backfilled.',
            'leagues':reports}
