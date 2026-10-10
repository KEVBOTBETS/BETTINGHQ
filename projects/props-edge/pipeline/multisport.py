"""Keyless NHL/NCAAF prop research and exact, event-matched public offers.

Historical averages are descriptive. No NFL calibration is applied to these
sports, and no invented line or price is passed off as an offered market.
"""
import datetime as dt
import json
import re
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import urllib.request
from .http import JsonClient, ProviderError, response_text
from .providers.covers import _TokenParser, _heading, _book, _parse_offer, _compact, _player_aliases
from .providers.espn import parse_summaries
from .schema import american_to_decimal

from .nhl_goals import forecasts as goal_forecasts, VERSION as GOAL_VERSION

ROOT=Path(__file__).resolve().parents[1]
MARKETS_NHL={'SHOTS ON GOAL':'Shots on goal','GOALS':'Goals','ASSISTS':'Assists','POINTS':'Points','ANYTIME GOALSCORER':'Anytime goal','ANYTIME GOAL SCORER':'Anytime goal','SAVES':'Saves'}
NHL_CODES={'TB':'TBL','SJ':'SJS','LA':'LAK','NJ':'NJD','MON':'MTL','MTL':'MTL','WIN':'WPG','VEG':'VGK','NAS':'NSH','UTAH':'UTA'}
PATHS={'NHL':'hockey/nhl','NCAAF':'football/ncaaf'}

def instant(x):
    try:return dt.datetime.fromisoformat(x.replace('Z','+00:00')).astimezone(dt.timezone.utc)
    except (TypeError,ValueError,AttributeError):return None

class MatchupLinks(HTMLParser):
    """Read only advertised Covers matchup links, without guessing endpoints."""
    def __init__(self,sport):
        super().__init__();self.sport=sport;self.links=[];self.active=None;self.text=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='a' and re.fullmatch('/sport/'+PATHS[self.sport]+r'/matchup/\d+/odds',values.get('href','')):
            self.active=values['href'];self.text=[]
    def handle_data(self,value):
        if self.active and value.strip():self.text.append(value.strip())
    def handle_endtag(self,tag):
        if tag=='a' and self.active:
            self.links.append({'url':urljoin('https://www.covers.com',self.active),'label':' '.join(self.text)})
            self.active=None

def roster_players(data):
    rows=[]
    for group in data.get('athletes',[]):
        for a in group.get('items',[]):
            if a.get('id') and a.get('displayName'):rows.append({'id':str(a['id']),'player':a['displayName'],'image':(a.get('headshot') or {}).get('href'),'position':(a.get('position') or {}).get('abbreviation')})
    return rows

def card_market(token,sport):return MARKETS_NHL.get(token.strip().upper()) if sport=='NHL' else _heading(token)

def parse_offers(cards,games,rosters,sport,stamp):
    quotes={}
    for card in cards:
        headings=[(i,card_market(t,sport)) for i,t in enumerate(card) if card_market(t,sport)]
        if len(headings)!=1:continue
        offset,market=headings[0];tokens=card[offset+1:]
        matchups=[t for t in tokens if re.fullmatch(r'[A-Z0-9&]{2,5}\s*@\s*[A-Z0-9&]{2,5}',t)]
        matches=[g for g in games if any(_compact(t)==_compact(g['away']+'@'+g['home']) for t in matchups)]
        if len(matches)!=1:continue
        game=matches[0]
        sides=[s for s in ('away','home') if game[s] in tokens[:5]]
        if len(sides)!=1:continue
        team=game[sides[0]]
        # Match the exact displayed player token against a current team roster.
        names={_compact(t) for t in tokens[:8]}
        athletes=[a for a in rosters.get(team,[]) if names & _player_aliases(a['player'])]
        if len(athletes)!=1:continue
        athlete=athletes[0]
        for i,t in enumerate(tokens):
            book=_book(t)
            if not book:continue
            tail=[]
            for candidate in tokens[i+1:i+10]:
                if _book(candidate) or re.search(r'\b(?:logo|sportsbook)$',candidate,re.I):break
                tail.append(candidate)
            offer=_parse_offer(tail,market in ('Anytime touchdown','Anytime goal'))
            if not offer:continue
            side,line,price=offer
            key=(game['game_id'],athlete['id'],market,side,line,book)
            quotes[key]={'sport':sport,'event_id':str(game['game_id']),'start_time':game['date'],'matchup':game['away']+' @ '+game['home'],'team':team,'player':athlete['player'],'athlete_id':athlete['id'],'image':athlete.get('image'),'market':market,'side':side,'line':line,'price_american':price,'price_decimal':american_to_decimal(price),'book':book,'price_source':'book','observed_at':stamp,'source_url':'https://www.covers.com/sport/'+PATHS[sport]+'/player-props','model_prob':None,'actionable':False,'status':'Research · model not validated'}
    return list(quotes.values())

def nhl_watchlist(game,rosters,stats,season):
    rows=[]
    for side in ('away','home'):
        team=game[side];ids={a['id']:a for a in rosters.get(team,[])};data=stats.get(team,{})
        for player in data.get('skaters',[]):
            who=ids.get(str(player.get('playerId')));gp=player.get('gamesPlayed') or 0
            if not who or gp<1:continue
            for market,key in [('Shots on goal','shots'),('Goals','goals'),('Assists','assists'),('Points','points')]:
                val=player.get(key)
                if not isinstance(val,(int,float)):continue
                rows.append({'sport':'NHL','event_id':str(game['game_id']),'start_time':game['date'],'matchup':game['away']+' @ '+game['home'],'team':team,**who,'athlete_id':who['id'],'market':market,'average':round(val/gp,2),'samples':gp,'recent':[],'history_season':str(data.get('season',season)),'history_note':'Official regular-season average with this club. '+('Small current-season sample; not a stable projection. ' if gp<5 else '')+'Current roster membership does not confirm game participation.','model_prob':None})
    return sorted(rows,key=lambda x:(x['market']!='Shots on goal',-x['average']))[:50]

class Cache:
    def __init__(self):
        self.path=ROOT/'state/multisport_cache.json'
        self.data=json.loads(self.path.read_text()) if self.path.exists() else {}
    def get(self,url,hours=6):
        prior=self.data.get(url)
        now=dt.datetime.now(dt.timezone.utc)
        if prior and instant(prior['at']) and (now-instant(prior['at'])).total_seconds()<hours*3600:return prior['data']
        try:
            base,path=url.rsplit('/',1)
            d=JsonClient('Public player statistics',base,timeout=12).get('/'+path,retries=0)
        except ProviderError:
            return None
        if '/summary?' in url:
            d={'boxscore':{'players':(d.get('boxscore') or {}).get('players',[])}}
        self.data[url]={'at':now.isoformat(),'data':d};return d
    def save(self):
        self.path.parent.mkdir(exist_ok=True);self.path.write_text(json.dumps(self.data,separators=(',',':'))+'\n')

def build(sport,cache,now):
    folder=ROOT.parent/(sport.lower()+'-edge-lab')
    all_games=json.loads((folder/'site/data/games.json').read_text())
    games=[g for g in all_games if instant(g.get('date')) and now<instant(g['date'])<now+dt.timedelta(days=7) and not g.get('completed') and g.get('state')!='in' and not g.get('canceled') and not g.get('postponed')]
    teams={g[s]:g.get(s+'_name',g[s]) for g in games for s in ('home','away')}
    html='';errors=[];stamp=now.isoformat();url='https://www.covers.com/sport/'+PATHS[sport]+'/player-props'
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; KEVBOTBETS/1.0; public-market-reader)','Accept':'text/html'})
        with urllib.request.urlopen(req,timeout=20) as response:html=response_text(response,4_000_000)
        if re.search(r'access denied|verify that you are human|captcha',html[:10000],re.I):raise ProviderError('Access restricted')
    except (OSError,ProviderError):errors.append('Public prop prices unavailable; no prices inferred.')
    parser=_TokenParser();parser.feed(html)
    links=MatchupLinks(sport);links.feed(html)
    rosters={};stats={};watch=[]
    if sport=='NHL':
        start_year=now.year if now.month>=7 else now.year-1;season=start_year*10000+start_year+1
        def team_data(team):
            api_team=NHL_CODES.get(team,team)
            roster=cache.get('https://api-web.nhle.com/v1/roster/'+api_team+'/current') or {}
            athletes=[{'id':str(a['id']),'player':(a.get('firstName') or {}).get('default','')+' '+(a.get('lastName') or {}).get('default',''),'image':a.get('headshot'),'position':a.get('positionCode')} for group in ['forwards','defensemen','goalies'] for a in roster.get(group,[]) if a.get('id')]
            stat_season=season
            data=cache.get(f'https://api-web.nhle.com/v1/club-stats/{api_team}/{season}/2',3) or {}
            if not any((p.get('gamesPlayed') or 0)>0 for p in data.get('skaters',[])):
                stat_season=season-10001
                data=cache.get(f'https://api-web.nhle.com/v1/club-stats/{api_team}/{stat_season}/2',24) or {}
            prior_data=cache.get(f'https://api-web.nhle.com/v1/club-stats/{api_team}/{season-10001}/2',24*7) or {}
            data={**data,'season':stat_season,'prior':prior_data}
            return team,athletes,data
        with ThreadPoolExecutor(max_workers=6) as pool:
            for team,athletes,data in pool.map(team_data,teams):rosters[team]=athletes;stats[team]=data
        for g in games:
            watch.extend(goal_forecasts(g,rosters,stats,season))
            watch.extend(nhl_watchlist(g,rosters,stats,season))
    else:
        # Restrict roster/history calls to teams whose cards have current offered markets.
        offered={t for c in parser.cards for t in c[1:4] if t in teams}
        ids={}
        for g in games:
            for side in ['away','home']:
                logo=g.get(side+'_logo','');m=re.search(r'/ncaa/500/(\d+)',logo)
                if m and g[side] in offered:ids[g[side]]=m[1]
        def roster(team):return team,roster_players(cache.get('https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/'+ids[team]+'/roster') or {})
        with ThreadPoolExecutor(max_workers=6) as pool:
            for team,athletes in pool.map(roster,ids):rosters[team]=athletes
        past=[g for g in all_games if g.get('completed') and g.get('season_type')==2 and instant(g.get('date')) and instant(g['date'])<now]
        wanted={}
        for team in ids:
            prior=sorted([g for g in past if team in (g['away'],g['home'])],key=lambda g:g['date'],reverse=True)[:4]
            for g in prior:wanted[g['game_id']]=g
        def summary(g):return g['date'],cache.get('https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event='+str(g['game_id']),24*30)
        with ThreadPoolExecutor(max_workers=6) as pool:summaries=sorted([r for r in pool.map(summary,wanted.values()) if r[1]],key=lambda x:x[0])
        matchups={_compact(teams[g[side]]):[{'matchup':teams[g['away']]+' @ '+teams[g['home']],'start_time':g['date']}] for g in games for side in ['home','away']}
        roster_by_name={(_compact(teams[t]),_compact(a['player'])):a for t,rows in rosters.items() for a in rows}
        for p in parse_summaries([r[1] for r in summaries],'NCAAF',matchups):
            who=roster_by_name.get((_compact(p.team),_compact(p.player)))
            if not who:continue
            for g in games:
                team=next((t for t in [g['away'],g['home']] if teams[t]==p.team),None)
                if not team or g['date']!=p.start_time:continue
                watch.append({'sport':sport,'event_id':str(g['game_id']),'start_time':g['date'],'matchup':g['away']+' @ '+g['home'],'team':team,**who,'athlete_id':who['id'],'market':p.market,'average':round(sum(p.recent)/len(p.recent),2),'samples':p.samples,'recent':p.recent,'history_season':str(g.get('season',now.year)),'history_note':'Recent completed regular-season box scores, matched to the current team roster. Historical hit rates are not forecasts.','model_prob':None})
    quotes=parse_offers(parser.cards,games,rosters,sport,stamp)
    history={(w['event_id'],w['athlete_id'],w['market']):w for w in watch}
    for q in quotes:
        w=history.get((q['event_id'],q['athlete_id'],q['market']))
        if w:q.update({k:w[k] for k in ['average','samples','recent','history_season','history_note','model_prob','model_version','probability_basis'] if k in w})
    result={'sport':sport,'generated_at':stamp,'source_model_at':json.loads((folder/'site/data/meta.json').read_text()).get('generated_at'),'games':[{k:g.get(k) for k in ['game_id','date','away','home','away_name','home_name','away_logo','home_logo','season_type','venue']} for g in games],'quotes':quotes,'watchlist':watch,'errors':errors,'notes':['Public book offers are matched to one upcoming game and one current roster player.','Player participation, starting goalie and final combined parlay price must be confirmed at the book.','NHL/college history is descriptive research; no calibrated prop win probability is claimed.'],'source_url':url}
    result['diagnostics']={'advertised_game_pages':len(links.links),'index_cards':len(parser.cards),'upcoming_games':len(games),'roster_teams':sum(bool(v) for v in rosters.values()),'statistics_teams':sum(bool(v.get('skaters')) for v in stats.values()),'matched_offers':len(quotes)}
    result['public_game_pages']=links.links
    if sport=='NHL':
        result['goal_model']={'version':GOAL_VERSION,'validated':False,'method':'Gamma-Poisson goal-rate shrinkage with bounded matchup adjustment','basis':'Conditional on player participation; regulation and OT goals only; shootout excluded','prior_max_games':30,'baseline_games':12}
        result['goal_scorers']=[w for w in watch if w['market']=='Anytime goal']
    if games and not quotes:
        if links.links and not parser.cards:errors.append('Covers now advertises separate game odds pages; its index contains no player offer cards.')
        errors.append('No event-matched book offers were extracted. Player statistics and manual book-line entry remain available.')
    if sport=='NHL' and teams and not watch:
        errors.append('Official NHL player history unavailable for the scheduled teams.')

    dest=ROOT/'site/data'/f'{sport.lower()}-props.json';dest.write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
    print(sport,len(games),'games',len(quotes),'observed offers',len(watch),'history rows')
    return result

def publish():
    cache=Cache();now=dt.datetime.now(dt.timezone.utc)
    for sport in ['NHL','NCAAF']:
        try:build(sport,cache,now)
        except (OSError,ValueError,ProviderError) as exc:print(sport,'props refresh failed; prior timestamps retained:',type(exc).__name__)
    cache.save()

if __name__=='__main__':publish()
