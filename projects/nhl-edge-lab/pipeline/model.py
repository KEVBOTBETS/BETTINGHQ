"""Transparent NHL baseline. Goal-rate Poisson model; no claimed calibration."""
import math
from copy import deepcopy
from datetime import datetime, timezone

VERSION = 'nhl-poisson-1.0'
MAX_QUOTE_HOURS = 1.5

def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and not isinstance(value, bool) else None
    except (ValueError, TypeError):
        return None

def instant(value):
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d if d.tzinfo else None
    except (ValueError, TypeError):
        return None

def decimal(price):
    p = number(price)
    return 1 + (p / 100 if p > 0 else 100 / -p) if p is not None and abs(p) >= 100 else None

def poisson(mu, size=25):
    values = [math.exp(-mu)]
    for i in range(1, size):
        values.append(values[-1] * mu / i)
    total = sum(values)
    return [p / total for p in values]

def score_grid(home, away):
    """Final-score distribution: ties receive an OT/SO deciding goal, equally split."""
    grid = {}
    for h, ph in enumerate(poisson(home)):
        for a, pa in enumerate(poisson(away)):
            if h == a:
                for hh, aa in [(h+1, a), (h, a+1)]:
                    grid[hh, aa] = grid.get((hh, aa), 0) + ph * pa / 2
            else:
                grid[h, a] = grid.get((h, a), 0) + ph * pa
    return grid

def project(home, away, home_rest=None, away_rest=None, neutral=False):
    def rate(team, name):
        current, prior = team.get('current', {}), team.get('prior', {})
        n, prev = current.get('gp', 0), prior.get('gp', 0)
        if not n and not prev:
            return None
        prior_rate = prior.get(name) if prev >= 20 else 3.05
        if prior_rate is None:
            return None
        # Previous season regresses 45% to league baseline; first 20 games blend it out.
        baseline = 3.05 + .55 * (prior_rate - 3.05)
        return ((current.get(name) or baseline) * n + baseline * 20) / (n + 20)
    hf, ha, af, aa = (rate(home, 'gf_pg'), rate(home, 'ga_pg'), rate(away, 'gf_pg'), rate(away, 'ga_pg'))
    if None in (hf, ha, af, aa):
        return {'ratings_known': False, 'reason': 'Team goal-rate samples unavailable'}
    h, a = (hf + aa)/2, (af + ha)/2
    if not neutral:
        h += .12
        a -= .12
    if home_rest == 0:
        h -= .10
        a += .06
    if away_rest == 0:
        a -= .10
        h += .06
    h, a = [max(1.7, min(4.6, x)) for x in (h, a)]
    grid = score_grid(h, a)
    p_home = sum(p for (hh, aa), p in grid.items() if hh > aa)
    return {'ratings_known': True, 'home_goals': round(h, 3), 'away_goals': round(a, 3),
            'mu': round(h-a, 3), 'p_home': round(p_home, 6),
            'total': round(sum((hh+aa)*p for (hh, aa), p in grid.items()), 3),
            'overtime_prob': round(sum(x*y for x,y in zip(poisson(h),poisson(a))), 6),
            'scores': [{'home':hh,'away':aa,'probability':round(p,6)} for (hh,aa),p in sorted(grid.items(),key=lambda x:-x[1])[:8]],
            'matrix': [[round(grid.get((hh,aa),0),6) for hh in range(8)] for aa in range(8)],
            'prior_weight': round(20/(20+min(home.get('current',{}).get('gp',0),away.get('current',{}).get('gp',0))),3)}

def market_probability(projection, market, side, line=None):
    if not projection.get('ratings_known'):
        return None, None
    win = push = 0
    for (h,a), p in score_grid(projection['home_goals'], projection['away_goals']).items():
        if market == 'ML':
            margin = (h-a) if side == 'home' else (a-h)
        elif market == 'ATS':
            margin = ((h-a) if side == 'home' else (a-h)) + line
        else:
            margin = (h+a-line) * (1 if side == 'over' else -1)
        if margin > 0: win += p
        elif margin == 0: push += p
    return win, push

def candidates(game, now):
    result=[]
    proj=game['projection']
    for quote in game.get('quotes', []):
        p,push=market_probability(proj,quote['market'],quote['side'],quote['line'])
        dec=decimal(quote['price']); opposite=decimal(quote.get('opposite_price'))
        observed=instant(quote.get('observed_at')); start=instant(game['date'])
        reasons=[]
        if p is None: reasons.append('Team statistics unavailable')
        if not dec or not opposite: reasons.append('Complete two-sided prices unavailable')
        if not observed or not (-300 <= (now-observed).total_seconds() <= MAX_QUOTE_HOURS*3600): reasons.append('Quote stale or timestamp unavailable')
        if not start or not (0 < (start-now).total_seconds() <= 24*3600) or game['state']!='pre': reasons.append('Outside the pregame 24-hour window')
        if game['season_type'] not in (2,3): reasons.append('Preseason / exhibition')
        if not all(game.get(side+'_goalie',{}).get('confirmed') for side in ('home','away')): reasons.append('Starting goalies not both confirmed')
        if game.get('stats_stale'): reasons.append('Team statistics are stale or unavailable')
        fair=(1/dec)/(1/dec+1/opposite) if dec and opposite else None
        raw_p=p/(1-push) if p is not None else None
        # New model: shrink priced probability 75% toward the same-book no-vig market.
        priced_p=.25*raw_p+.75*fair if raw_p is not None and fair is not None else raw_p
        ev=(1-push)*(priced_p*dec-1) if priced_p is not None and dec else None
        if ev is None or ev < .03: reasons.append('Below 3% expected-return threshold')
        # Large disagreement is a data/model review, never a forced best bet.
        if p is not None and fair is not None and abs(raw_p-fair) > .15: reasons.append('Large model/market disagreement; review required')
        if ev is not None and ev > .15: reasons.append('Expected return above 15%; data/model review required')
        tier='PASS' if reasons else 'BEST BET' if ev>=.08 else 'GOOD' if ev>=.05 else 'LEAN'
        name=game.get(quote['side'],quote['side'].title())
        label=f"{name} ML" if quote['market']=='ML' else f"{name} {quote['line']:+g}" if quote['market']=='ATS' else f"{quote['side'].title()} {quote['line']:g}"
        result.append({**quote,'game_id':game['game_id'],'start_time':game['date'],'date':game['day'],
          'home':game['home'],'away':game['away'],'matchup':f"{game['away']} @ {game['home']}",
          'pick':label,'model_prob':round(priced_p,6) if priced_p is not None else None,'raw_model_prob':raw_p,'push_prob':push,
          'market_fair_prob':fair,'edge':round(ev,6) if ev is not None else None,'tier':tier,
          'stake':1 if not reasons else 0,'held':bool(reasons),'reasons':reasons,
          'odds_verified':bool(dec and opposite),'odds_observed_at':quote['observed_at'],
          'model_version':VERSION,'season_type':game['season_type']})
    # At most one qualified recommendation per game avoids opposing/correlated ticket legs.
    qualified=sorted([r for r in result if not r['held']],key=lambda r:-r['edge'])
    for row in qualified[1:]:
        row.update(held=True,stake=0,tier='PASS',reasons=['Higher-ranked market selected for this game'])
    return result

def market_snapshot(game, stamp):
    """Freeze a fresh same-book two-sided benchmark with the original forecast."""
    now, start = instant(stamp), instant(game.get('date'))
    if not now or not start or now >= start or game.get('source_stale'): return None
    for quote in game.get('quotes', []):
        if quote.get('market') != 'ML' or quote.get('side') != 'home' or not quote.get('book'): continue
        observed = instant(quote.get('observed_at'))
        home, away = decimal(quote.get('price')), decimal(quote.get('opposite_price'))
        if not observed or not 0 <= (now-observed).total_seconds() <= MAX_QUOTE_HOURS*3600 or not home or not away: continue
        h, a = 1/home, 1/away
        return {'p_home': h/(h+a), 'home_price':quote['price'], 'away_price':quote['opposite_price'],
                'book':quote['book'], 'observed_at':quote['observed_at'], 'method':'same-book proportional no-vig'}
    return None

def update_accuracy(records, games, board, stamp):
    """Freeze first pregame forecast; never manufacture forecasts from final games."""
    now=instant(stamp)
    for game in games:
        key=str(game['game_id']);start=instant(game['date'])
        if key not in records and game['season_type'] in (2,3) and game['state']=='pre' and start and start>now and game['projection'].get('ratings_known'):
            records[key]={'game_id':key,'season':game['season'],'season_type':game['season_type'],'start':game['date'],
               'frozen_at':stamp,'home':game['home'],'away':game['away'],'p_home':game['p_home'],
               'projection':deepcopy(game['projection']),'model_version':VERSION,'market_snapshot':market_snapshot(game,stamp),'challenger':deepcopy(game.get('challenger')),'result':None}
        record=records.get(key)
        if record and game.get('nhl_game_id'):record['nhl_game_id']=game['nhl_game_id']
        if record and game['completed'] and game['home_score'] is not None and game['away_score'] is not None and game['home_score']!=game['away_score']:
            if abs((instant(record['start'])-start).total_seconds())>36*3600:continue
            old=record.get('result') or {}
            if old.get('home')!=game['home_score'] or old.get('away')!=game['away_score']:
                record['result']={'home':game['home_score'],'away':game['away_score'],'home_won':game['home_score']>game['away_score'],'verified_at':stamp}
    return records

def accuracy_report(records, season, stamp):
    rows=[r for r in records.values() if r['season']==season]
    settled=[r for r in rows if r.get('result')]
    n=len(settled);correct=sum((r['p_home']>.5)==r['result']['home_won'] for r in settled)
    brier=sum((r['p_home']-int(r['result']['home_won']))**2 for r in settled)/n if n else None
    return {'generated_at':stamp,'scope':{'season':f'{season-1}-{str(season)[-2:]}','season_type_label':'Regular season + playoffs · forward-only'},
       'games':{'winner':{'n':n,'correct':correct,'accuracy':correct/n if n else None,'brier':brier}},
       'pending':len(rows)-n,'model_version':VERSION,'records':rows[-500:],
       'note':'Uncalibrated baseline. Game-winner accuracy includes forecasts you did not bet; it is not wager ROI.'}
