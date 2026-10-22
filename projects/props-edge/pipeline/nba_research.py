"""NBA roster-matched public prop research; no inferred sportsbook contracts."""
import datetime as dt
import json
import math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import urllib.request
from .http import ProviderError, response_text
from .providers.covers import _TokenParser

MARKETS = {'POINTS':'Points','REBOUNDS':'Rebounds','ASSISTS':'Assists','THREE POINTERS MADE':'Threes',
           'THREES MADE':'Threes','STEALS':'Steals','BLOCKS':'Blocks','POINTS + REBOUNDS + ASSISTS':'Points + rebounds + assists'}
STAT_KEYS = {'Points':'PTS','Rebounds':'REB','Assists':'AST','Steals':'STL','Blocks':'BLK','Turnovers':'TO','Threes':'3PT'}


def watchlist(games, players, rosters, now):
    from .multisport import instant
    history = defaultdict(dict)
    for p in players:
        if p.get('state') != 'post' or not instant(p.get('start')) or instant(p['start']) >= now:
            continue
        stats = p.get('stats') or {}
        try:
            if float(str(stats.get('MIN', 0)).split(':')[0]) <= 0:
                continue
        except ValueError:
            continue
        history[(str(p.get('player_id')),p.get('team'))][str(p.get('game_id'))] = p
    rows = []
    for g in games:
        for team in (g['away'],g['home']):
            for athlete in rosters.get(team, []):
                past = sorted(history.get((athlete['id'],team),{}).values(),key=lambda p:p['start'])[-8:]
                for market, key in STAT_KEYS.items():
                    values = []
                    for p in past:
                        raw = str(p['stats'].get(key, ''))
                        if key == '3PT': raw = raw.split('-')[0]
                        try: value = float(raw)
                        except ValueError: continue
                        if math.isfinite(value) and value >= 0: values.append(value)
                    rows.append(dict(sport='NBA',event_id=g['game_id'],start_time=g['date'],
                                     matchup=g['away']+' @ '+g['home'],team=team,**athlete,
                                     athlete_id=athlete['id'],market=market,average=round(sum(values)/len(values),2) if values else None,
                                     samples=len(values),recent=values,roster_verified=True,model_prob=None,
                                     history_note='Recent completed regular-season box scores; descriptive history, not a prop forecast. Roster membership does not confirm participation.'))
    return rows


def build(root, cache, now):
    from .multisport import instant, parse_offers, MatchupLinks
    root = Path(root); folder = root.parent/'nba-edge-lab/site/data'
    meta = json.loads((folder/'meta.json').read_text()); at=instant(meta.get('generated_at'))
    if not at or not 0 <= (now-at).total_seconds() <= 6*3600:
        raise ProviderError('NBA source publication is stale; previous player timestamps retained')
    source = json.loads((folder/'games.json').read_text())
    games=[]; ids={}
    for g in source:
        if not instant(g.get('date')) or not now < instant(g['date']) < now+dt.timedelta(days=7) or g.get('completed') or g.get('canceled') or g.get('postponed') or g.get('state')=='in':continue
        row={k:g.get(k) for k in ['game_id','date','away_name','home_name','season_type','venue']}
        row['game_id']=str(row['game_id'])
        for side in ['away','home']:
            t=g.get(side) or {};row[side]=t.get('abbr') if isinstance(t,dict) else t
            if isinstance(t,dict) and t.get('id'):ids[row[side]]=str(t['id'])
        if row['home'] and row['away']:games.append(row)
    def roster(item):
        team,identifier=item;data=cache.get(f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{identifier}/roster',3) or {}
        found=[]
        for group in data.get('athletes') or []:
            for a in group.get('items',[]) if 'items' in group else [group]:
                if a.get('id') and a.get('displayName'):found.append(dict(id=str(a['id']),player=a['displayName'],position=(a.get('position') or {}).get('abbreviation')))
        return team,found
    with ThreadPoolExecutor(max_workers=4) as pool:rosters=dict(pool.map(roster,ids.items()))
    raw=json.loads((folder/'players.json').read_text())
    watch=watchlist(games,raw.get('players',[]),rosters,now)
    url='https://www.covers.com/sport/basketball/nba/player-props';html='';errors=[]
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; KEVBOTBETS/1.0; public-market-reader)','Accept':'text/html'})
        with urllib.request.urlopen(req,timeout=20) as response:html=response_text(response,4_000_000)
    except (OSError,ProviderError):errors.append('NBA public prop prices unavailable; no lines or prices inferred.')
    parser=_TokenParser();parser.feed(html);quotes=parse_offers(parser.cards,games,rosters,'NBA',now.isoformat())
    if not quotes:errors.append('No exact roster-matched NBA prop offers extracted. Use current sportsbook prices in the manual entry form.')
    if ids and not all(rosters.values()):errors.append('Some current NBA rosters are unavailable; those players are excluded from offers and history matching.')
    result=dict(sport='NBA',generated_at=now.isoformat(),source_model_at=meta['generated_at'],games=games,quotes=quotes,watchlist=watch,
                errors=errors,goal_scorers=[],source_url=url,notes=['NBA player averages are history, not calibrated prop probabilities.','No line is inferred from an average. Confirm availability and the combined sportsbook quote.'])
    destination=root/'site/data/nba-props.json';temp=destination.with_suffix('.json.tmp');temp.write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n');temp.replace(destination)
    print('NBA',len(games),'games',len(quotes),'observed offers',len(watch),'player history rows')
    return result
