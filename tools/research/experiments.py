"""Immutable prospective model comparisons. No historical forecast backfill."""
from collections import defaultdict
import math
import numpy as np
from .common import instant, number, seed

def freeze(archive, forecasts, now):
    saved={r['id']:dict(r) for r in archive if r.get('id')}
    for r in forecasts:
        start=instant(r.get('start'));p=number(r.get('p_home'));observed=instant(r.get('source_observed_at'))
        if not start or not observed or not observed<=now<start or p is None or not 0<p<1:continue
        key=str(seed([r['sport'],r['event_id'],r['model'],r['version']]))
        if key not in saved:saved[key]={**r,'id':key,'captured_at':now.isoformat(),'result':None,'result_observed_at':None}
    return list(saved.values())

def settle(archive, results, now):
    out=[]
    for original in archive:
        r=dict(original);result=results.get((r['sport'],str(r['event_id'])))
        if r.get('result') is None and result and result.get('completed') and instant(r['start'])<=now:
            h,a=number(result.get('home_score')),number(result.get('away_score'))
            at=instant(result.get('result_observed_at'))
            if h is not None and a is not None and at and instant(r['start'])<=at<=now:
                r.update(result={'home_score':h,'away_score':a,'margin':h-a,'home_win':1 if h>a else 0 if h<a else .5},result_observed_at=at.isoformat())
        out.append(r)
    return out

def completed(rows, now):
    return [r for r in rows if r.get('result') and instant(r.get('captured_at')) and instant(r['captured_at'])<instant(r['start']) and instant(r.get('result_observed_at')) and instant(r['result_observed_at'])<=now]

def metrics(rows):
    n=len(rows)
    if not n:return {'games':0,'brier':None,'log_loss':None,'margin_mae':None,'ats':None,'roi':None,'calibration':[]}
    def loss(r):
        p=min(1-1e-9,max(1e-9,r['p_home']));y=r['result']['home_win'];return -(y*math.log(p)+(1-y)*math.log(1-p))
    errors=[abs(r['margin']-r['result']['margin']) for r in rows if number(r.get('margin')) is not None]
    spread=[];profits=[];risk=0
    for r in rows:
        c=r.get('cover');line=number(r.get('home_spread'))
        if not c or line is None:continue
        # Always evaluate the frozen model's more-likely side, including pushes.
        side=1 if c['win']>=c['loss'] else -1;v=side*(r['result']['margin']+line)
        spread.append('win' if v>1e-9 else 'loss' if v< -1e-9 else 'push')
        q=r.get('home_price') if side==1 else r.get('away_price')
        if number(q) and q>1:
            profits.append(q-1 if v>1e-9 else -1 if v< -1e-9 else 0);risk+=1
    bins=[]
    for low in np.arange(0,1,.1):
        group=[r for r in rows if low<=r['p_home']<low+.1]
        if group:bins.append({'low':float(low),'high':float(low+.1),'games':len(group),'forecast':sum(r['p_home'] for r in group)/len(group),'actual':sum(r['result']['home_win'] for r in group)/len(group)})
    return {'games':n,'brier':sum((r['p_home']-r['result']['home_win'])**2 for r in rows)/n,'log_loss':sum(loss(r) for r in rows)/n,'margin_mae':sum(errors)/len(errors) if errors else None,'ats':{k:spread.count(k) for k in ['win','loss','push']} if spread else None,'roi':sum(profits)/risk if risk else None,'priced_games':risk,'calibration':bins}

def paired(rows, candidate, baseline='current', version=None):
    by=defaultdict(dict)
    for r in rows:
        if r['model']==candidate and version and r['version']!=version:continue
        by[r['sport'],r.get('cohort','regular season'),r['event_id'],r['captured_at']][r['model']]=r
    groups=defaultdict(list)
    for values in by.values():
        if candidate not in values or baseline not in values:continue
        c,b=values[candidate],values[baseline]
        if c['result']!=b['result'] or c['captured_at']!=b['captured_at']:continue
        delta=(c['p_home']-c['result']['home_win'])**2-(b['p_home']-b['result']['home_win'])**2
        groups[c['start'][:10]].append(delta)
    count=sum(len(v) for v in groups.values());days=len(groups)
    if not count:return {'games':0,'days':0,'brier_delta':None,'interval':None,'status':'Awaiting prospective results'}
    mean=sum(sum(v) for v in groups.values())/count;ci=None
    if count>=100 and days>=28:
        rng=np.random.default_rng(47);values=list(groups.values());sums=np.array([sum(v) for v in values]);sizes=np.array([len(v) for v in values]);indices=rng.integers(0,days,(2000,days));boot=sums[indices].sum(axis=1)/sizes[indices].sum(axis=1);ci=[float(x) for x in np.quantile(boot,[.025,.975])]
    return {'games':count,'days':days,'brier_delta':mean,'interval':ci,'status':'Ready for human review' if ci and ci[1]<0 else 'More evidence needed','policy':'Paired same-event predictions; date-clustered interval. No automatic promotion.'}

def ensemble_weight(archive, sport, now, candidate_version=None, baseline_version=None):
    by=defaultdict(dict)
    for r in completed(archive,now):
        if r['model']=='efficiency' and candidate_version and r['version']!=candidate_version:continue
        if r['model']=='current' and baseline_version and r['version']!=baseline_version:continue
        if r.get('cohort','regular season')!='regular season':continue
        if r['sport']==sport and instant(r['result_observed_at'])<now:by[r['event_id']][r['model']]=r
    pairs=[v for v in by.values() if 'current' in v and 'efficiency' in v and v['current']['result']==v['efficiency']['result'] and v['current']['captured_at']==v['efficiency']['captured_at']]
    if len(pairs)<40:return None
    def score(w):
        return sum((w*v['efficiency']['p_home']+(1-w)*v['current']['p_home']-v['current']['result']['home_win'])**2 for v in pairs)/len(pairs)
    weight=min([0,.25,.5,.75,1],key=score)
    return {'efficiency_weight':weight,'training_games':len(pairs),'trained_at':now.isoformat(),'policy':'Weights fitted only on settled prospective captures available before this forecast. Ensemble stays in shadow mode.'}

def report(archive, now):
    rows=completed(archive,now);groups=defaultdict(list)
    for r in rows:groups[r['sport'],r.get('cohort','regular season'),r['model'],r['version']].append(r)
    models=sorted({(r['sport'],r.get('cohort','regular season'),r['model'],r['version']) for r in archive})
    return {'records':len(archive),'events':len({(r['sport'],r['event_id']) for r in archive}),'settled_events':len({(r['sport'],r['event_id']) for r in rows}),'models':[{'sport':s,'cohort':c,'model':m,'version':v,**metrics(groups[s,c,m,v]),'comparison':paired([r for r in rows if r['sport']==s and r.get('cohort','regular season')==c],m,version=v),'market_comparison':paired([r for r in rows if r['sport']==s and r.get('cohort','regular season')==c],m,baseline='market',version=v)} for s,c,m,v in models],'policy':'First valid pregame forecast is frozen per event, model and version. Every model competes on the same captured events. Preseason and model versions stay separate. No win-rate claim before prospective results.'}
