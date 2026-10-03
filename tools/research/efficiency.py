"""Opponent-adjusted efficiency challenger with chronological training features."""
from collections import defaultdict
import math
import numpy as np
from .common import instant, number, key_team, margin_distribution, summary, cover

FEATURES=['pass efficiency','rush efficiency','success rate','explosive rate','home field','pace difference']

def profiles(rows, day):
    eligible=[r for r in rows if r['date']<day and r.get('plays',0)>=20]
    latest=defaultdict(list)
    for r in sorted(eligible,key=lambda x:x['date']):latest[r['team']].append(r)
    raw={}
    for team,history in latest.items():
        history=history[-12:]; weights=[.85**(len(history)-i-1) for i in range(len(history))]
        total=sum(w*r['plays'] for w,r in zip(weights,history))
        value={'games':len(history),'plays':total,'pace':sum(w*r['plays'] for w,r in zip(weights,history))/sum(weights)}
        for field in ['pass','rush']:
            n=sum(w*r[field+'_plays'] for w,r in zip(weights,history))
            value[field]=sum(w*r[field+'_epa'] for w,r in zip(weights,history))/(n+150)
        for field in ['success','explosive']:
            prior=.42 if field=='success' else .08
            value[field]=(sum(w*r[field] for w,r in zip(weights,history))+200*prior)/(total+200)
        raw[team]=value
    allowed=defaultdict(list)
    for r in sorted(eligible,key=lambda x:x['date']):
        if r['opponent'] in raw:allowed[r['opponent']].append(r)
    for t,p in raw.items():
        recent=allowed[t][-12:]
        for f in ['pass','rush']:
            p['allow_'+f]=sum(r[f+'_epa'] for r in recent)/(sum(r[f+'_plays'] for r in recent)+150)
    for t,p in raw.items():
        # Remove a conservative part of the quality of opponents faced.
        opponents=[raw[r['opponent']] for r in latest[t][-12:] if r['opponent'] in raw]
        for f in ['pass','rush']:
            p[f+'_adjusted']=p[f]-(sum(x['allow_'+f] for x in opponents)/len(opponents) if opponents else 0)
    return raw

def vector(home,away,p,neutral=False):
    if home not in p or away not in p or min(p[home]['games'],p[away]['games'])<3:return None
    h,a=p[home],p[away]
    return np.array([h['pass_adjusted']+a['allow_pass']-a['pass_adjusted']-h['allow_pass'],h['rush_adjusted']+a['allow_rush']-a['rush_adjusted']-h['allow_rush'],h['success']-a['success'],h['explosive']-a['explosive'],0 if neutral else 1,(h['pace']-a['pace'])/10])

def fit(rows, cutoff=None):
    if cutoff:rows=[r for r in rows if r['date']<cutoff]
    rows=[r for r in rows if r.get('result_verified')]
    games={r['game_id']:r for r in rows}; xs=[];ys=[];dates=[]
    for r in sorted(games.values(),key=lambda x:x['date']):
        p=profiles(rows,r['date']);x=vector(r['home'],r['away'],p,r.get('neutral',False))
        if x is None:continue
        xs.append(x);ys.append(r['home_score']-r['away_score']);dates.append(r['date'])
    if len(xs)<60:return None
    x=np.array(xs);y=np.array(ys);scale=np.maximum(np.std(x,axis=0),.03);scale[4]=1
    z=x/scale
    def solve(a,b):return np.linalg.solve(a.T@a+20*np.eye(a.shape[1]),a.T@b)
    residuals=[]
    # Errors are from forecasts trained on previous dates, never same-day games.
    for day in sorted(set(dates)):
        train=[i for i,d in enumerate(dates) if d<day]; test=[i for i,d in enumerate(dates) if d==day]
        if len(train)<60:continue
        # Scaling is itself trained before the test date.
        past_scale=np.maximum(np.std(x[train],axis=0),.03);past_scale[4]=1
        beta=solve(x[train]/past_scale,y[train])
        residuals.extend(float(y[i]-x[i]/past_scale@beta) for i in test)
    beta=solve(z,y);sd=max(10.,float(np.std(residuals)) if residuals else 14.)
    return {'beta':beta,'scale':scale,'sd':sd,'residuals':residuals[-400:],'games':len(xs),'last_date':max(dates),'features':FEATURES,'replay':'Chronological features from corrected data; exploratory.'}

def forecast(game, dataset, model, now):
    observed=instant(dataset.get('observed_at'));start=instant(game.get('date'))
    live=instant(dataset.get('live_observed_at') or dataset.get('observed_at'))
    if not observed or not observed<=now or not live or not live<=now or not start or start<=now or (now-live).total_seconds()>7*86400 or not model:return None
    def team(side):
        t=game.get(side);return key_team(t.get('abbr') if isinstance(t,dict) else t)
    p=profiles(dataset.get('teams',[]),now.date().isoformat());h,a=team('home'),team('away');x=vector(h,a,p,game.get('neutral',False))
    if x is None:return None
    contributions=x/model['scale']*model['beta'];mu=float(sum(contributions));dist=margin_distribution(mu,model['sd'],model['residuals']);out=summary(dist)
    line=number((game.get('odds') or {}).get('spread_home'))
    out.update(version='nfl-efficiency-v1',mode='shadow',training_games=model['games'],training_through=model['last_date'],source_observed_at=dataset['observed_at'],margin=mu,sd=model['sd'],cover=cover(dist,line) if line is not None else None,home_spread=line,factors=[{'name':name,'points':float(v)} for name,v in zip(FEATURES,contributions)],profiles={'home':p[h],'away':p[a]},replay=model['replay'],actionable=False)
    return out
