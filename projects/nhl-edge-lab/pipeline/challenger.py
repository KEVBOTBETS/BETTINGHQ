"""Keyless NHL feature challenger; never changes the production ticket model.

Coefficients are conservative hypotheses, not fitted claims. Freeze prospective
forecasts and compare them before promotion. Missing inputs receive no adjustment.
"""
import unicodedata
from .model import instant, number, poisson

VERSION = 'nhl-context-shadow-1.0'

def clamp(value, low, high):
    return max(low, min(high, value))

def name_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value or '').lower() if c.isalpha() and not unicodedata.combining(c))

def fresh(stamp, now, hours):
    at = instant(stamp)
    return bool(at and 0 <= (now-at).total_seconds() <= hours*3600)

def goalie_index(raw, stamp, season):
    """Exact normalized-name join only; ambiguous identities are excluded."""
    grouped = {}
    for row in raw.get('data', []):
        key = name_key(row.get('goalieFullName'))
        saves, shots = number(row.get('saves')), number(row.get('shotsAgainst'))
        if not key or shots is None or saves is None or not 0 <= saves <= shots or shots <= 0:
            continue
        grouped.setdefault(key, []).append({
            'id': row.get('playerId'), 'name': row.get('goalieFullName'),
            'saves': saves, 'shots': shots, 'season': season, 'observed_at': stamp})
    return {key: rows[0] for key, rows in grouped.items() if len(rows) == 1}

def goalie_sample(goalie, by_season, season, now):
    if not goalie.get('confirmed'):
        return None
    key = name_key(goalie.get('name'))
    samples = []
    for year, weight in [(season, 1), (season-1, .5)]:
        row = by_season.get(year, {}).get(key)
        if row and fresh(row.get('observed_at'), now, 6 if year == season else 24*7):
            samples.append((row, weight))
    if not samples or len({r['id'] for r, _ in samples}) != 1:
        return None
    shots = sum(r['shots']*w for r,w in samples)
    saves = sum(r['saves']*w for r,w in samples)
    return {'save_pct': (saves+1000*.905)/(shots+1000), 'weighted_shots': shots,
            'name': samples[0][0]['name'], 'id': samples[0][0]['id']}

def team_features(team, season, now):
    year = team.get('stats_season')
    extra = team.get('context_features', {})
    if year not in (season, season-1) or not fresh(extra.get('observed_at'), now, 6 if year == season else 24*7):
        return {}
    gp = number(extra.get('gp')) or 0
    if gp <= 0: return {}
    shrink = gp/(gp+20) * (1 if year == season else .5)
    values = {'weight': shrink}
    for field in ('shots_pg', 'shots_against_pg'):
        value = number(extra.get(field))
        if value is not None and 10 <= value <= 60: values[field] = value
    for field in ('pp_pct', 'pk_pct'):
        value = number(extra.get(field))
        if value is not None and 0 <= value <= 1: values[field] = value
    won, lost = number(extra.get('ot_wins')), number(extra.get('ot_losses'))
    if won is not None and lost is not None and won >= 0 and lost >= 0 and won+lost <= gp:
        # Beta(10,10) prior; previous-season evidence is downweighted.
        w = 1 if year == season else .5
        values['ot_rate'] = (10+w*won)/(20+w*(won+lost))
        values['ot_games'] = won+lost
    ga = number(extra.get('ga_pg'))
    sa = values.get('shots_against_pg')
    if ga is not None and sa and 0 <= ga <= sa:
        # Team goal-rate proxy includes empty-net effects; bounded, small correction.
        values['team_save_proxy'] = clamp(1-ga/sa, .85, .95)
    return values

def project(game, goalies, season, now):
    base = game.get('projection', {})
    if not base.get('ratings_known') or game.get('source_stale') or game.get('stats_stale'):
        return None
    features = {s: team_features(game.get(s+'_stats', {}), season, now) for s in ('home','away')}
    changes = {}; missing = []; rates = {}
    for side, opponent in [('home','away'), ('away','home')]:
        own, opp = features[side], features[opponent]
        shots = special = goalie_delta = 0.
        if 'shots_pg' in own and 'shots_against_pg' in opp:
            shots = clamp(((own['shots_pg']+opp['shots_against_pg'])/2-30)*.025*min(own['weight'], opp['weight']), -.2, .2)
        else: missing.append(side+': shots unavailable or stale')
        if 'pp_pct' in own and 'pk_pct' in opp:
            special = clamp(((own['pp_pct']-.20)+(.80-opp['pk_pct']))*.75*min(own['weight'],opp['weight']), -.2, .2)
        else: missing.append(side+': special teams unavailable or stale')
        sample = goalie_sample(game.get(opponent+'_goalie', {}), goalies, season, now)
        if sample and 'team_save_proxy' in opp and 'shots_against_pg' in opp:
            goalie_delta = clamp(.35*opp['shots_against_pg']*(opp['team_save_proxy']-sample['save_pct']), -.3, .3)
        else: missing.append(opponent+': confirmed goalie sample unavailable')
        changes[side] = {'shots': round(shots,4), 'special_teams': round(special,4),
                         'opponent_goalie': round(goalie_delta,4), 'goalie_sample': sample}
        rates[side] = clamp(base[side+'_goals']+shots+special+goalie_delta, 1.5, 5)
    h, a = features['home'].get('ot_rate'), features['away'].get('ot_rate')
    ot = .5
    if h is not None and a is not None:
        odds_h, odds_a = h/(1-h), a/(1-a)
        ot = clamp(odds_h/(odds_h+odds_a), .35, .65)
    else: missing.append('OT/SO history unavailable; equal tie-break retained')
    hp, ap = poisson(rates['home']), poisson(rates['away'])
    tie = sum(x*y for x,y in zip(hp, ap))
    p = sum(ph*pa for i,ph in enumerate(hp) for j,pa in enumerate(ap) if i>j)+tie*ot
    return {'version': VERSION, 'mode': 'shadow-only', 'observed_at': now.isoformat(),
            'p_home': round(p,6), 'home_goals': round(rates['home'],3), 'away_goals': round(rates['away'],3),
            'ot_home_probability': round(ot,6), 'adjustments': changes, 'missing': missing,
            'note': 'Prospective experiment, not validated confidence; production picks are unchanged.'}
