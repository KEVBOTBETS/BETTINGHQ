"""Chronological checks of team/market blending and discrete winning-band probabilities."""
import math
from statistics import mean, NormalDist
from .model import instant, number
from zoneinfo import ZoneInfo

def margin(team,market,w):
    return market+max(-3,min(3,w*(team-market)))

def band(x):
    return (1 if x>0 else -1)*min(6,(abs(round(x))+4)//5)

def masses(mu,sd,errors):
    # Smoothed historical residuals, shrunk toward the normal baseline.
    def cdf(x):
        base=NormalDist(mu,sd).cdf(x)
        return (40*base+sum(NormalDist(mu+e,3).cdf(x) for e in errors))/(40+len(errors))
    result={}
    for side in (1,-1):
        for i in range(1,7):
            lo=(i-1)*5+.5; hi=i*5+.5 if i<6 else math.inf
            a,b=(lo,hi) if side==1 else (-hi,-lo)
            result[side*i]=cdf(b)-cdf(a)
    win=NormalDist(mu,sd).cdf(0); totals={side:sum(v for k,v in result.items() if k*side>0) for side in (1,-1)}
    return {k:v/totals[1 if k>0 else -1]*(1-win if k>0 else win) for k,v in result.items()}

def fit(log,now,season):
    rows=[];seen=set()
    for r in sorted(log.get('records',{}).values(),key=lambda x:x.get('captured_at','')):
        src=r.get('market_spread_source') or {};at=instant(src.get('observed_at'));cap=instant(r.get('captured_at'));start=instant(r.get('start'));end=instant(r.get('graded_at'))
        t=number(r.get('raw_margin'));s=number(r.get('market_spread'));y=number(r.get('actual_margin'));event=r.get('event_id')
        if not(event and event not in seen and r.get('league')=='NCAAB' and r.get('season')==season and r.get('kind')=='game' and r.get('result')=='Graded' and None not in (at,cap,start,end,t,s,y) and y!=0 and at<=cap<start<=end<=now and (cap-at).total_seconds()<=5400 and ''.join(str(src.get('book','')).lower().split())=='draftkings'):continue
        seen.add(event);rows.append((start,t,-s,y,end))
    rows.sort();days=sorted({r[0].astimezone(ZoneInfo('America/Toronto')).date() for r in rows});out={'games':len(rows),'weight':.2,'errors':[],'band_active':False}
    if len(days)<3:return out
    cutoff=days[max(1,2*len(days)//3)];test=[r for r in rows if r[0].astimezone(ZoneInfo('America/Toronto')).date()>=cutoff];train=[r for r in rows if r[4]<test[0][0]]
    if len(train)<15 or len(test)<8:return out
    def mae(part,w):return mean(abs(y-margin(t,m,w)) for _,t,m,y,_ in part)
    w=min((0,.1,.2,.3,.4),key=lambda v:mae(train,v)); out.update(test_games=len(test),train_games=len(train),spread_mae=round(mae(test,0),2),team_mae=round(mean(abs(y-t) for _,t,m,y,_ in test),2))
    if mae(test,w)<mae(test,.2)*.98:out['weight']=w
    w=out['weight']; ats=[(margin(t,m,w)-m)*(y-m) for _,t,m,y,_ in test if margin(t,m,w)!=m and y!=m];out.update(spread_hits=sum(a>0 for a in ats),spread_decisions=len(ats));errs=[y-margin(t,m,w) for _,t,m,y,_ in train];scores=[]
    for errors in ([],errs):
        probs=[(masses(margin(t,m,w),12,errors),band(y)) for _,t,m,y,_ in test];scores.append((mean(-math.log(max(1e-9,p[k])) for p,k in probs),sum(max(p,key=p.get)==k for p,k in probs)))
    out.update(baseline_hits=scores[0][1],challenger_hits=scores[1][1],baseline_log_loss=round(scores[0][0],4),challenger_log_loss=round(scores[1][0],4))
    if len(train)>=50 and len(test)>=25 and scores[1][0]<.98*scores[0][0] and scores[1][1]>=scores[0][1]:
        out.update(band_active=True,errors=[y-margin(t,m,w) for _,t,m,y,_ in rows[-250:]])
    return out
