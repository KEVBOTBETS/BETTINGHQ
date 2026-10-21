"""NBA scoring-rate baseline. Research only; no automatic model promotion."""
from datetime import datetime
from statistics import NormalDist
import math
VERSION='nba-scoring-research-1.0'
def number(v):
    try:return float(v) if v is not None and not isinstance(v,bool) and math.isfinite(float(v)) else None
    except (TypeError,ValueError):return None
def instant(v):
    try:
        at=datetime.fromisoformat(str(v).replace('Z','+00:00'));return at if at.tzinfo else None
    except ValueError:return None
def decimal(v):
    p=number(v);return 1+(p/100 if p>0 else 100/-p) if p is not None and abs(p)>=100 else None
def project(home,away,now,neutral=False):
    def rate(team,field):
        current=team.get('current') or {};prior=team.get('prior') or {}
        n=number(current.get('games')) or 0;pn=number(prior.get('games')) or 0
        c,p=number(current.get(field)),number(prior.get(field))
        current_at=instant(current.get('observed_at'))
        if not current_at or not 0<=(now-current_at).total_seconds()<=24*3600:return None
        if pn<20 or p is None:return None
        observed=instant(prior.get('observed_at'))
        if not observed or not 0<=(now-observed).total_seconds()<=30*86400:return None
        if n and c is None:return None
        if n and c is not None:
            at=instant(current.get('observed_at'))
            if not at or not 0<=(now-at).total_seconds()<=24*3600:return None
            return (n*c+20*p)/(n+20)
        return p
    hf,ha,af,aa=rate(home,'points_for'),rate(home,'points_against'),rate(away,'points_for'),rate(away,'points_against')
    if None in (hf,ha,af,aa):return {'ratings_known':False,'reason':'Verified current/prior NBA scoring samples unavailable'}
    h,a=(hf+aa)/2,(af+ha)/2
    # A disclosed baseline assumption, not a fitted or validated NBA parameter.
    if not neutral:h+=1.0;a-=1.0
    mu=h-a;total=h+a;p=NormalDist(0,12).cdf(mu)
    return {'ratings_known':True,'mu':round(mu,3),'total':round(total,3),'proj_total':round(total,3),
        'proj_home_pts':round(h,2),'proj_away_pts':round(a,2),'p_home':round(p,6),'margin_sd':12,'total_sd':18,
        'prior_weight':round(20/(20+min(home.get('current',{}).get('games') or 0,away.get('current',{}).get('games') or 0)),3),
        'basis':'Previous regular-season scoring rates blended with current-season rates over 20 games. No player injury adjustment.',
        'mode':'research','calibrated':False}
def candidates(game,now):
    p=game.get('projection') or {};rows=[]
    for q in game.get('quotes',[]):
        price=decimal(q.get('price'));opp=decimal(q.get('opposite_price'));at=instant(q.get('observed_at'))
        if not price or not opp or not at or not 0<=(now-at).total_seconds()<=5400:continue
        start=instant(game.get('tipoff'))
        if not start or start<=now or game.get('state')!='pre':continue
        market,side,line=q['market'],q['side'],number(q.get('line'));win=push=None
        if p.get('ratings_known'):
            mean=p['total'] if market=='TOTAL' else p['mu'];sigma=p['total_sd'] if market=='TOTAL' else p['margin_sd'];dist=NormalDist(mean,sigma)
            threshold=line if market=='TOTAL' else -line if side=='home' and line is not None else line if side=='away' else 0
            if threshold is None:continue
            if market=='ML':win=p['p_home'] if side=='home' else 1-p['p_home'];push=0
            else:
                integer=float(threshold).is_integer();low,high=(threshold-.5,threshold+.5) if integer else (threshold,threshold)
                push=dist.cdf(high)-dist.cdf(low)
                win=1-dist.cdf(high) if side in ('home','over') else dist.cdf(low)
        conditional=win/(1-push) if win is not None and push is not None and push<1 else None
        label=game[side]['abbr']+' ML' if market=='ML' else game[side]['abbr']+f' {line:+g}' if market=='ATS' else f'{side.title()} {line:g}'
        rows.append({**q,'game_id':game['game_id'],'event_id':game['game_id'],'tipoff':game['tipoff'],'start_time':game['tipoff'],'game_date':game['tipoff'],
            'home':game['home']['abbr'],'away':game['away']['abbr'],'matchup':game['away']['abbr']+' @ '+game['home']['abbr'],
            'season':game['season'],'season_type':game['season_type'],'pick':label,'model_prob':conditional,'push_prob':push,
            'edge':(1-push)*(conditional*price-1) if conditional is not None else None,'odds_observed_at':q['observed_at'],
            'odds_verified':True,'model_version':VERSION,'tier':'RESEARCH','held':True,'stake':0,
            'reasons':['New NBA baseline is uncalibrated; research only. Confirm injuries and the current sportsbook price.']})
    return rows
