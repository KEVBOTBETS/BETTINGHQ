"""Market-specific prospective calibration. Original captures never change.

A calibrator uses only results verified before its forecast. Models remain shadow
research; review compares paired raw/calibrated probabilities on future captures.
"""
from collections import defaultdict
import math
import hashlib
import json
import numpy as np
from .common import instant, number, seed, decimal

VERSION='market-calibration-v2'
MIN_GAMES=100
MIN_CONTRACTS=200

def group(row):
    return row['sport'],row['market'],row.get('baseline_version','unknown')

def score(p,y):
    p=max(1e-9,min(1-1e-9,p))
    return -(y*math.log(p)+(1-y)*math.log(1-p))

def transform(p,slope):
    p=max(1e-6,min(1-1e-6,p));z=slope*math.log(p/(1-p))
    return 1/(1+math.exp(-z))

def training(archive,key,now):
    # A game/market has one vote, regardless of alternate lines or sportsbooks.
    rows={}
    for r in sorted(archive,key=lambda x:x.get('captured_at','')):
        at=instant(r.get('captured_at'));start=instant(r.get('start'))
        result=r.get('result');verified=instant((result or {}).get('observed_at'))
        if r.get('version')!=VERSION or group(r)!=key or not at or not start or not at<start or not verified or not start<=verified<now or result.get('outcome') not in ['win','loss']:continue
        rows.setdefault((r['event_id'],r.get('player_id') or r.get('player','')),r)
    return list(rows.values())

def fit(archive,key,now):
    rows=training(archive,key,now);events=len({r['event_id'] for r in rows})
    if len(rows)<MIN_CONTRACTS or events<MIN_GAMES:
        return {'enabled':False,'slope':1.,'contracts':len(rows),'games':events,'reason':f'Needs {MIN_CONTRACTS} contracts and {MIN_GAMES} games in this market/version'}
    # Fixed grid, symmetric correction: complementary probabilities still sum to 1.
    def loss(s):return sum(score(transform(r['raw_no_push'],s),r['result']['outcome']=='win') for r in rows)/len(rows)
    slope=min([.5,.75,1.,1.25],key=lambda s:(loss(s),abs(s-1)))
    return {'enabled':True,'slope':slope,'contracts':len(rows),'games':events,'trained_at':now.isoformat(),'last_result_at':max(r['result']['observed_at'] for r in rows),'training_log_loss':loss(slope),'reason':'Fitted on earlier verified results only; prospective review still required'}

def freeze(archive,candidates,now):
    saved={r['id']:dict(r) for r in archive if r.get('id')};fits={}
    for q in candidates:
        start,observed=instant(q.get('start')),instant(q.get('observed_at'))
        generated=instant(q.get('generated_at'));p=number(q.get('p_win'));push=number(q.get('p_push')) or 0
        price=decimal(q.get('price'))
        if not q.get('book') or q.get('price_source')=='model' or q.get('quote_status','observed')!='observed' or q.get('reference_only'):continue
        if not start or not observed or not generated or not generated<=now<start or not observed<=now or (now-generated).total_seconds()>6*3600 or (now-observed).total_seconds()>4*3600:continue
        if q.get('probability_basis')=='conditional' and p is not None:p=p*(1-push)
        if p is None or not 0<=p<=1 or not 0<=push<1 or p+push>1+1e-7 or price is None:continue
        contract=[q['sport'],str(q['event_id']),q['market'],q.get('player_id') or q.get('player',''),q.get('line'),q.get('side'),q.get('rules','full-game'),q.get('baseline_version')]
        identity=hashlib.sha256(json.dumps([*contract,VERSION],separators=(',',':')).encode()).hexdigest()
        if identity in saved:continue
        key=group(q)
        if key not in fits:fits[key]=fit(archive,key,now)
        model=fits[key];raw=p/(1-push);cal=transform(raw,model['slope'])
        saved[identity]={**q,'id':identity,'version':VERSION,'captured_at':now.isoformat(),'raw_no_push':raw,'calibrated_no_push':cal,'calibrated_win':cal*(1-push),'calibrator':model,'price_decimal':price,'result':None,'actionable':False}
    return list(saved.values())

def settle(archive,results,now):
    out=[]
    for original in archive:
        r=dict(original);final=results.get((r['sport'],str(r['event_id'])));start=instant(r.get('start'))
        at=instant((final or {}).get('result_observed_at'))
        if r.get('result') is None and final and final.get('completed') and start and at and start<=at<=now:
            h,a=number(final.get('home_score')),number(final.get('away_score'));v=None
            if h is not None and a is not None:
                if r['market']=='ML':v=h-a
                elif r['market']=='ATS':v=h-a+r['line']
                elif r['market']=='TOTAL':v=h+a-r['line']
            if v is not None:
                if r['side'] in ['away','under']:v=-v
                r['result']={'outcome':'push' if abs(v)<1e-9 else 'win' if v>0 else 'loss','observed_at':at.isoformat()}
        out.append(r)
    return out

def attach_props(archive,props,now):
    by={(r['sport'],str(r['event_id']),r['player'],r['market'],r['side'],r['line']):r for r in props if r.get('model')=='current' and r.get('result')}
    out=[]
    for original in archive:
        r=dict(original);q=by.get((r['sport'],str(r['event_id']),r.get('player'),r['market'],r['side'],r.get('line')))
        at=instant(q['result'].get('observed_at')) if q else None
        if not r.get('result') and q and at and instant(r['start'])<=at<=now:r['result']={k:q['result'][k] for k in ['outcome','observed_at']}
        out.append(r)
    return out

def report(archive,now):
    groups=defaultdict(list)
    for r in archive:
        if r.get('version')==VERSION:groups[group(r)].append(r)
    out=[]
    for key,rows in sorted(groups.items()):
        # Same player/market alternates do not inflate a calibration evaluation.
        unique={}
        for r in sorted(rows,key=lambda x:x['captured_at']):
            result=r.get('result');at=instant((result or {}).get('observed_at'))
            if result and at and at<=now and result['outcome'] in ['win','loss'] and instant(r['captured_at'])<instant(r['start']):unique.setdefault((r['event_id'],r.get('player_id') or r.get('player','')),r)
        done=list(unique.values());n=len(done);deltas=defaultdict(list);bins=[]
        for r in done:
            y=r['result']['outcome']=='win'
            deltas[r['start'][:10]].append(score(r['calibrated_no_push'],y)-score(r['raw_no_push'],y))
        interval=None
        if n>=MIN_CONTRACTS and len({r['event_id'] for r in done})>=MIN_GAMES and len(deltas)>=28:
            values=list(deltas.values());rng=np.random.default_rng(191);ids=rng.integers(0,len(values),(2000,len(values)))
            sums=np.array([sum(v) for v in values]);sizes=np.array([len(v) for v in values]);interval=[float(x) for x in np.quantile(sums[ids].sum(axis=1)/sizes[ids].sum(axis=1),[.025,.975])]
        for low in [0,.2,.4,.6,.8]:
            b=[r for r in done if min(4,int(r['calibrated_no_push']*5))==int(round(low*5))]
            if b:bins.append({'low':low,'high':low+.2,'contracts':len(b),'forecast':sum(r['calibrated_no_push'] for r in b)/len(b),'actual':sum(r['result']['outcome']=='win' for r in b)/len(b)})
        out.append({'sport':key[0],'market':key[1],'baseline_version':key[2],'captured':len(rows),'graded':n,'games':len({r['event_id'] for r in done}),'dates':len(deltas),'raw_log_loss':sum(score(r['raw_no_push'],r['result']['outcome']=='win') for r in done)/n if n else None,'calibrated_log_loss':sum(score(r['calibrated_no_push'],r['result']['outcome']=='win') for r in done)/n if n else None,'interval':interval,'calibration':bins,'next_fit':fit(archive,key,now),'status':'Eligible for human review' if interval and interval[1]<0 else 'Awaiting stronger prospective evidence','promotion_enabled':False})
    return {'markets':out,'records':len(archive),'policy':'Separate sport/market/baseline-version fits. Pushes excluded. One player/market per event in evaluation. Only earlier verified results train each capture; original predictions are immutable. No automatic promotion.'}

def attach_verified_props(archive,results,now):
    """Exact contract matching to the existing official box-score result feed."""
    by={(str(q.get('event_id')),q.get('player'),q.get('market'),q.get('side'),q.get('line')):q for q in results if q.get('graded_at') and q.get('result') in ['Win','Loss','Push']}
    out=[]
    for original in archive:
        r=dict(original);q=by.get((str(r['event_id']),r.get('player'),r['market'],r['side'],r.get('line')));at=instant(q.get('graded_at')) if q else None
        if not r.get('result') and r.get('player') and q and at and instant(r['start'])<=at<=now:
            r['result']={'outcome':q['result'].lower(),'observed_at':at.isoformat(),'source':'Existing verified official box-score results'}
        out.append(r)
    return out
