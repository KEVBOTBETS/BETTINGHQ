"""Independent public NHL feed adapters. Missing prices/goalies stay missing."""
import unicodedata
from zoneinfo import ZoneInfo
from .model import instant, number

ALIASES = {'NJD': 'NJ', 'SJS': 'SJ', 'TBL': 'TB', 'LAK': 'LA'}
def abbr(value): return ALIASES.get(value, value)
def name_key(value): return unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode().lower()

def standings(raw, identities, season):
    known = {abbr(t['abbr']): t for t in identities.values()}
    result = {}
    for row in raw.get('standings', []):
        if str(row.get('seasonId', ''))[-4:] != str(season): continue
        code = abbr(row.get('teamAbbrev', {}).get('default'))
        base = known.get(code, {}); tid = base.get('id', 'nhlteam:' + str(code))
        gp = number(row.get('gamesPlayed')) or 0
        gf, ga, points = [number(row.get(k)) for k in ('goalFor', 'goalAgainst', 'points')]
        record = lambda prefix: '-'.join(str(row.get(prefix+k, 0)) for k in ('Wins', 'Losses', 'OtLosses'))
        result[tid] = {**base, 'id': tid, 'abbr': code, 'name': row.get('teamName', {}).get('default'),
          'logo': row.get('teamLogo'), 'conference': row.get('conferenceName', '') + ' Conference',
          'gp': gp, 'gf': gf, 'ga': ga, 'gf_pg': gf/gp if gp and gf is not None else None,
          'ga_pg': ga/gp if gp and ga is not None else None, 'points': points,
          'points_pct': points/(2*gp) if gp and points is not None else None,
          'wins': row.get('wins'), 'losses': row.get('losses'), 'otl': row.get('otLosses'),
          'home_record': record('home'), 'away_record': record('road'), 'last10': record('l10'),
          'goal_diff': row.get('goalDifferential'), 'official_rank': row.get('leagueSequence')}
    return result

def summary_teams(raw, identities):
    known = {name_key(t.get('name')): t for t in identities.values()}
    result = {}
    for row in raw.get('data', []):
        base = known.get(name_key(row.get('teamFullName')))
        if not base: continue
        result[base['id']] = {**base, 'gp': row.get('gamesPlayed'), 'gf': row.get('goalsFor'),
          'ga': row.get('goalsAgainst'), 'gf_pg': row.get('goalsForPerGame'), 'ga_pg': row.get('goalsAgainstPerGame'),
          'wins': row.get('wins'), 'losses': row.get('losses'), 'otl': row.get('otLosses'),
          'points': row.get('points'), 'points_pct': row.get('pointPct')}
    return result

def quotes(game, partners, stamp):
    """Only named CA/US partners with complete American moneyline prices."""
    books = {str(p['partnerId']): p for p in partners if p.get('country') in ('CA', 'US') and p.get('name')}
    sides = {side: {str(q.get('providerId')): number(q.get('value')) for q in game.get(side+'Team', {}).get('odds', [])} for side in ('home', 'away')}
    result = []
    for pid, partner in books.items():
        h, a = sides['home'].get(pid), sides['away'].get(pid)
        if h is None or a is None or abs(h) < 100 or abs(a) < 100: continue
        for side, price, opposite in [('home', h, a), ('away', a, h)]:
            result.append({'market': 'ML', 'side': side, 'line': None, 'price': price, 'opposite_price': opposite,
              'book': partner['name'] + ' (' + partner['country'] + ')', 'observed_at': stamp,
              'open_price': None, 'source': 'NHL public schedule'})
    return result

def normalize(game, partners, stamp, identities):
    start = instant(game.get('startTimeUTC'))
    if not start or not all(game.get(s+'Team', {}).get('abbrev') for s in ('home', 'away')): return None
    state = game.get('gameState'); schedule = game.get('gameScheduleState', 'OK')
    status = {'FUT': 'Scheduled', 'PRE': 'Pregame', 'LIVE': 'In Progress', 'CRIT': 'In Progress', 'OFF': 'Final', 'FINAL': 'Final'}.get(state, 'Unknown')
    phase = 'pre' if state in ('FUT', 'PRE') else 'in' if state in ('LIVE', 'CRIT') else 'post' if state in ('OFF', 'FINAL') else 'unknown'
    if schedule not in ('OK', ''):
        status = {'PPD': 'Postponed', 'CNCL': 'Canceled', 'SUSP': 'Suspended'}.get(schedule, 'Schedule unconfirmed: '+schedule)
        phase = 'unknown'
    nhl_id = str(game['id']); period = game.get('periodDescriptor', {})
    g = {'game_id': 'nhl:'+nhl_id, 'nhl_game_id': nhl_id, 'date': start.isoformat(), 'start': start.isoformat(),
      'day': start.astimezone(ZoneInfo('America/Toronto')).date().isoformat(), 'season': int(str(game['season'])[-4:]),
      'season_type': game.get('gameType', 0), 'state': phase, 'status': status, 'completed': phase == 'post',
      'status_detail': status + (' · Period '+str(period['number']) if phase == 'in' and period.get('number') else ''),
      'venue': game.get('venue', {}).get('default'), 'neutral': game.get('neutralSite', False),
      'broadcast': ', '.join(dict.fromkeys(b['network'] for b in game.get('tvBroadcasts', []) if b.get('network'))),
      'quotes': quotes(game, partners, stamp), 'source_stale': False, 'source_name': 'NHL',
      'source_url': 'https://www.nhl.com'+game['gameCenterLink'] if game.get('gameCenterLink', '').startswith('/gamecenter/') else None}
    known = {abbr(t['abbr']): t for t in identities.values()}
    for side in ('home', 'away'):
        row = game[side+'Team']; code = abbr(row['abbrev']); base = known.get(code, {})
        g.update({side: code, side+'_id': base.get('id', 'nhlteam:'+code),
          side+'_name': base.get('name') or ' '.join(row.get(k, {}).get('default', '') for k in ('placeName', 'commonName')),
          side+'_logo': row.get('logo') or base.get('logo'), side+'_color': base.get('color'),
          side+'_score': number(row.get('score')) if phase in ('in', 'post') else None,
          side+'_record': '-'.join(str(base[k]) for k in ('wins', 'losses', 'otl')) if all(base.get(k) is not None for k in ('wins', 'losses', 'otl')) else None,
          side+'_goalie': {'name': None, 'status': 'Not supplied by NHL schedule', 'confirmed': False, 'stats': []}})
    return g

def stabilize(game, known):
    """Preserve ticket IDs when switching feeds; never carry old odds/goalies."""
    for old in known:
        same_id = game.get('nhl_game_id') and game.get('nhl_game_id') == old.get('nhl_game_id')
        before, after = instant(old.get('date') or old.get('start')), instant(game.get('date'))
        same_match = all(abbr(game.get(s)) == abbr(old.get(s)) for s in ('home', 'away')) and before and after and abs((before-after).total_seconds()) <= 6*3600
        if same_id or same_match:
            game['game_id'] = old['game_id']
            if old.get('nhl_game_id'): game['nhl_game_id'] = old['nhl_game_id']
            break
    return game
