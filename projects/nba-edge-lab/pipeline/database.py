"""Recover real box scores and learn bounded uncertainty from frozen NBA forecasts."""
import gzip
import json
import math
from datetime import timedelta
from zoneinfo import ZoneInfo
from .model import instant, number


def pending_player_games(root, now):
    path=root.parent/'props-edge/state/nba-validation.json.gz'
    try:
        with gzip.open(path,'rt') as f:rows=json.load(f).get('records',[])
    except FileNotFoundError:return set(),set()
    pending=[r for r in rows if r.get('result') is None and (at:=instant(r.get('start'))) and now-timedelta(days=45)<=at<now]
    return {str(r['event_id']) for r in pending},{instant(r['start']).astimezone(ZoneInfo('America/Toronto')).date() for r in pending}


def merge_players(root, players, season, now):
    path=root/'state/player_database.json.gz'
    try:
        with gzip.open(path,'rt') as f:old=json.load(f)
    except FileNotFoundError:old={}
    rows={}
    for row in ([*old.get('players',[]),*players] if old.get('season')==season else players):
        at=instant(row.get('start'))
        if not at or at>=now or row.get('state')!='post' or not row.get('player_id') or not row.get('team') or not isinstance(row.get('stats'),dict):continue
        rows[(str(row['game_id']),str(row['player_id']),row['team'])]=row
    output=sorted(rows.values(),key=lambda r:(r['start'],str(r['game_id']),str(r['player_id'])))
    if len(output)>60000:raise ValueError('NBA season player database exceeds expected bounds')
    temp=path.with_suffix('.tmp');temp.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(temp,'wt',compresslevel=6) as f:json.dump({'season':season,'players':output},f,separators=(',',':'),allow_nan=False)
    temp.replace(path)
    return output


def residual_fit(log, now):
    errors=[];seen=set()
    for r in log.get('records',{}).values():
        start,captured=instant(r.get('start')),instant(r.get('captured_at'))
        baseline=number(r.get('raw_margin'))
        if baseline is None and r.get('version')=='nba-scoring-research-1.0':baseline=number(r.get('margin'))
        actual=number(r.get('actual_margin'))
        if r.get('kind')!='game' or r.get('league')!='NBA' or r.get('result')!='Graded' or not start or not captured or not captured<start<now or baseline is None or actual is None:continue
        identifier=str(r.get('event_id') or '')
        if not identifier or identifier in seen:continue
        seen.add(identifier);errors.append(actual-baseline)
    n=len(errors)
    if n<50:return {'games':n,'active':False,'bias':0,'margin_sd':12,'method':'Awaiting 50 frozen, completed NBA game forecasts; baseline uncertainty retained.'}
    bias=max(-3,min(3,sum(errors)/(n+100)))
    sigma=math.sqrt((sum((e-bias)**2 for e in errors)+50*12**2)/(n+50))
    return {'games':n,'active':True,'bias':round(bias,4),'margin_sd':round(max(10,min(22,sigma)),4),
            'method':'Only frozen pregame raw margins vs completed scores. Bias shrunk by 100 games and capped at 3 points; variance shrunk by 50 baseline games and bounded 10–22. Applied forward only; not probability calibration.'}


def market_lines(game, now):
    """Freeze actual current spread/total pairs for prospective comparisons."""
    output={}
    for market,sides,key in [('ATS',('home','away'),'spread_home'),('TOTAL',('over','under'),'total')]:
        for q in game.get('quotes',[]):
            at=instant(q.get('observed_at'));line=number(q.get('line'))
            if q.get('market')!=market or q.get('side')!=sides[0] or not q.get('book') or line is None or not at or not 0<=(now-at).total_seconds()<=5400:continue
            pair=next((r for r in game['quotes'] if r.get('market')==market and r.get('side')==sides[1] and r.get('book')==q['book'] and r.get('observed_at')==q['observed_at'] and number(r.get('line'))==(-line if market=='ATS' else line)),None)
            if pair and all(number(r.get('price')) is not None and abs(number(r['price']))>=100 for r in [q,pair]):
                output[key]=line
                output[key+'_source']={'book':q['book'],'observed_at':q['observed_at'],'price':q['price'],'opposite_price':pair['price']}
                break
    return output
