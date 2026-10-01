"""Publish dated weekly football editions from the public, keyless feeds.

Only the active edition is updated. Older weeks retain their captured content.
Editorial context never adds an unvalidated model coefficient.
"""
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'projects/bet-ledger-hq/data/newsletters'
UTC = dt.timezone.utc

def stamp(value):
    try:
        return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(UTC)
    except (ValueError, TypeError, AttributeError):
        return None

def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default

def active_week(games, meta, now):
    current = meta.get('current_week') or {}
    start, end = stamp(current.get('start')), stamp(current.get('end'))
    if start and end and start <= now <= end:
        return int(current['week']), int(current['season_type']), start, end
    regular = [g for g in games if g.get('season_type') == 2 and stamp(g.get('date'))]
    # A college week spans Tuesday through Monday in the schedule's local zone.
    local = now.astimezone(ZoneInfo('America/Toronto'))
    begin = (local - dt.timedelta(days=(local.weekday()-1)%7)).replace(hour=0, minute=0, second=0, microsecond=0)
    finish = begin + dt.timedelta(days=7)
    candidates = [g for g in regular if begin <= stamp(g['date']) < finish]
    if not candidates:
        return None
    week = max(set(g['week'] for g in candidates), key=lambda w:sum(g['week']==w for g in candidates))
    return int(week), 2, begin.astimezone(UTC), finish.astimezone(UTC)

def factors(game, games, meta, sport, history=None):
    kickoff = stamp(game.get('date'))
    past = [g for g in games if g.get('completed') and stamp(g.get('date')) and stamp(g['date']) < kickoff and g.get('season_type') == 2]
    notes = []
    for side in ['away', 'home']:
        team = game[side]
        previous = sorted([g for g in past if team in (g['home'], g['away'])], key=lambda g:g['date'])
        if previous:
            recent = previous[-3:]
            wins = sum((g.get('home_score',0)>g.get('away_score',0)) if g['home']==team else (g.get('away_score',0)>g.get('home_score',0)) for g in recent)
            ties = sum(g.get('home_score')==g.get('away_score') for g in recent)
            notes.append(f'{team}: {wins}-{len(recent)-wins-ties}-{ties} over the last {len(recent)} captured regular-season games. Descriptive form, not an opponent-adjusted trend.')
            days = (kickoff - stamp(previous[-1]['date'])).total_seconds()/86400
            notes.append(f'{team}: {days:.1f} days between scheduled kickoffs. Rest context, not an automatic edge.')
    historical = [g for g in (history or []) if g.get('completed') and stamp(g.get('date')) and stamp(g['date']) < kickoff and g.get('season_type') == 2]
    meetings = [g for g in past + historical if {g['home'],g['away']} == {game['home'],game['away']}]
    if meetings:
        last = max(meetings,key=lambda g:g['date'])
        notes.append(f"Last meeting in the captured results ({last['date'][:10]}): {last['away']} {last.get('away_score')}–{last['home']} {last.get('home_score')}. One result is a small sample.")
    else:
        notes.append('No earlier head-to-head result in this captured regular-season dataset. Historical advantage is unconfirmed.')
    if game.get('neutral'):
        notes.append('Neutral venue: ordinary home-field assumptions need review.')
    if sport == 'nfl':
        divisions = meta.get('divisions', {})
        same = divisions.get(game['home']) and divisions.get(game['home']) == divisions.get(game['away'])
        playoff = 'Division matchup: the result affects the division race and head-to-head tiebreak context.' if same else 'Regular-season result affects the overall record; no playoff probability is inferred.'
    else:
        same = game.get('home_conference') and game.get('home_conference') == game.get('away_conference')
        playoff = f"{game['home_conference']} matchup: conference standings and championship positioning are in play." if same else 'A nonconference result adds to the résumé; an AP rank is not a CFP selection rank.'
    return notes, playoff

def edition(sport, games, meta, news, now, forecasts=None, weather=None, history=None):
    active = active_week(games,meta,now)
    if not active: return None
    week, phase, start, end = active
    rows = [g for g in games if int(g.get('week',0))==week and g.get('season_type')==phase]
    forecasts = {str(g['game_id']):g.get('latest',{}) for g in (forecasts or [])}
    weather = weather or {}
    def priority(g):
        ranks = [g.get(s+'_rank',99) for s in ['home','away']]
        ranks = [r for r in ranks if isinstance(r,(int,float)) and 1<=r<=25]
        odds = g.get('odds') or {}
        spread = odds.get('spread_home')
        return (len(ranks)*30 + sum(26-r for r in ranks) + (10-min(abs(spread),10) if isinstance(spread,(int,float)) else 0), g['date'])
    featured=[]
    for g in sorted(rows,key=priority,reverse=True)[:6]:
        notes, playoff = factors(g,games,meta,sport,history)
        proj = g.get('projection') or forecasts.get(str(g['game_id']),{})
        context = g.get('context') or {}
        wx = context.get('weather') or weather.get(str(g['game_id']),{})
        featured.append({**{k:g.get(k) for k in ['game_id','date','away','home','away_name','home_name','away_logo','home_logo','away_rank','home_rank','venue','broadcast','status','completed','away_score','home_score']},'odds':g.get('odds') or {},'projection':{'home':proj.get('score_home'),'away':proj.get('score_away'),'total':proj.get('proj_total',proj.get('model_total'))},'factors':notes,'playoff':playoff,'weather':wx,'review_flags':context.get('review_flags',[])})
    headlines = [n for n in news if stamp(n.get('published')) and start <= stamp(n['published']) <= min(now,end) and n.get('url','').startswith('https://')][:10]
    # Keep only titles, publication date and source links, never article bodies.
    headlines = [{k:n.get(k) for k in ['headline','published','url','image','teams']} for n in headlines]
    season = meta.get('season',now.year)
    playoff_url = 'https://www.nfl.com/standings/tie-breaking-procedures' if sport=='nfl' else 'https://collegefootballplayoff.com/'
    joke = (f"Week {week}: the toughest opponent might be the remote. Six games to watch, one couch, and absolutely no bye week for the snack coordinator." if sport=='ncaaf' else f"Week {week}: the two-minute drill is impressive, but getting everyone to agree on a pizza order before kickoff remains the league's unsolved clock-management problem.")
    return {'id':f'{season}-{phase}-{week}','sport':sport,'season':season,'week':week,'phase':phase,'start':start.isoformat(),'end':end.isoformat(),'generated_at':now.isoformat(),'model_generated_at':meta.get('generated_at'),'games_count':len(rows),'completed':sum(bool(g.get('completed')) for g in rows),'games':featured,'headlines':headlines,'humor':joke,'playoff_url':playoff_url,'playoff_note':('Division and conference records matter. Review official tiebreakers; these cards do not estimate qualification odds.' if sport=='nfl' else 'Conference races and résumé quality matter. Follow the official CFP selection process; AP rankings shown here are separate from CFP rankings.'),'selection_note':'Editorial watchlist: ranked matchups first, then closely priced games. These are not the betting model’s Top Picks.'}

SOURCES = [
 {'name':'ESPN','url':'https://www.espn.com/','status':'Connected','use':'Schedules, published book quotes, headlines, team records and game results. Quotes carry capture times; missing prices never qualify a bet.'},
 {'name':'nflverse','url':'https://nflverse.nflverse.com/','status':'Connected · NFL history','use':'Existing historical NFL inputs and reproducible research. New features require chronological testing before promotion.'},
 {'name':'Open-Meteo','url':'https://open-meteo.com/','status':'Connected · weather','use':'Keyless kickoff forecasts. Usage terms apply. NFL uses its existing weather rules; college forecasts remain review context.'},
 {'name':'National Weather Service','url':'https://www.weather.gov/documentation/services-web-API','status':'Connected · NFL fallback','use':'US hourly forecasts when primary kickoff weather is missing. Source and forecast hour are preserved. No key required; User-Agent required.'},
 {'name':'Covers / VegasInsider / OddsChecker','url':'https://www.covers.com/','status':'Research links','use':'Useful for manually checking lines and matchup history. No automated historical odds feed or line-shopping coverage is claimed.'},
 {'name':'PFF / Action Network / The Athletic','url':'https://www.pff.com/','status':'Premium research','use':'Potential injury, tactical and efficiency context. Restricted content is not scraped or used as an unseen model feature.'},
 {'name':'Sportsbooks / prop menus','url':'https://www.draftkings.com/','status':'Published quotes only','use':'The current ESPN book feed supplies supported markets. Login, location and protected sportsbook screens are not bypassed.'},
 {'name':'NFL / CFP','url':'https://collegefootballplayoff.com/','status':'Official context','use':'Rules and selection-process links for playoff research. No invented playoff odds or guaranteed matchup advantages.'}
]

def publish(now=None):
    now=now or dt.datetime.now(UTC)
    OUT.mkdir(parents=True,exist_ok=True)
    for sport in ['nfl','ncaaf']:
        base=ROOT/f'projects/{sport}-edge-lab/site/data'
        news=read(base/'news.json',[])
        if sport=='ncaaf':
            cache=OUT/'ncaaf-news-cache.json'
            try:
                response=requests.get('https://site.api.espn.com/apis/site/v2/sports/football/college-football/news',params={'limit':50},timeout=20)
                response.raise_for_status()
                news=[{'headline':a.get('headline'),'published':a.get('published'),'url':(a.get('links',{}).get('web') or {}).get('href'),'image':next((i.get('url') for i in a.get('images',[]) if i.get('url')),None),'teams':[]} for a in response.json().get('articles',[])]
                cache.write_text(json.dumps(news,ensure_ascii=False)+'\n')
            except (requests.RequestException,ValueError):
                news=read(cache,[])
        prior=read(ROOT/f'projects/{sport}-edge-lab/state/history_{now.year-1}.json',[])
        history=[{**g,'date':g.get('date_utc'),'home':g.get('home',{}).get('abbr'),'away':g.get('away',{}).get('abbr')} for g in prior if isinstance(g.get('home'),dict) and isinstance(g.get('away'),dict)]
        result=edition(sport,read(base/'games.json',[]),read(base/'meta.json',{}),news,now,read(base/'forecasts.json',[]),read(base/'weather.json',{}),history)
        if not result: continue
        directory=OUT/sport; directory.mkdir(exist_ok=True)
        filename=result['id']+'.json'
        (directory/filename).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        entries=[]
        for path in directory.glob('*.json'):
            if path.name=='index.json':continue
            d=read(path,{})
            entries.append({k:d[k] for k in ['id','season','week','phase','generated_at']})
        entries.sort(key=lambda e:(e['season'],e['phase'],e['week']),reverse=True)
        (directory/'index.json').write_text(json.dumps({'current':result['id'],'editions':entries},indent=2)+'\n')
        print(f"Newsletter {sport}: week {result['week']}, {result['games_count']} games, {len(result['headlines'])} headlines")
    (OUT/'sources.json').write_text(json.dumps(SOURCES,indent=2)+'\n')

if __name__=='__main__':publish()
