"""Public NBA collection. Preserve original observations and first pregame calls."""
import argparse,json,re,time
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from . import model,game_history,public_odds
ROOT=Path(__file__).resolve().parents[1];STATE=ROOT/'state';OUT=ROOT/'site/data'
BASE='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/';ET=ZoneInfo('America/Toronto')
def read(path,default):
    try:return json.loads(path.read_text())
    except FileNotFoundError:return default
    # Corrupt stored history must fail instead of being silently reset.
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,separators=(',',':'),allow_nan=False)+'\n');tmp.replace(path)
def fetch(url):
    # Use the same transport as the established football collector: automatic
    # content decoding, bounded responses and polite retries for transient errors.
    error=None
    for attempt in range(3):
        try:
            with requests.get(url,headers={'User-Agent':'NBA-Edge-Lab/1.0 (+https://github.com/KEVBOTBETS/BETTINGHQ)','Accept':'application/json'},timeout=18,stream=True) as response:
                if response.status_code!=200:
                    error=OSError('ESPN HTTP '+str(response.status_code))
                    if response.status_code not in (408,429,500,502,503,504):raise error
                else:
                    chunks=[];size=0
                    for chunk in response.iter_content(65536):
                        size+=len(chunk)
                        if size>8_000_000:raise ValueError('NBA source exceeds bounded response size')
                        chunks.append(chunk)
                    value=json.loads(b''.join(chunks))
                    if not isinstance(value,dict):raise ValueError('NBA source is not an object')
                    return value
        except requests.RequestException as exc:error=OSError('ESPN transport '+type(exc).__name__)
        except (ValueError,UnicodeError) as exc:error=OSError('ESPN response '+type(exc).__name__)
        if attempt<2:time.sleep(.5*(attempt+1))
    raise error or OSError('NBA source unavailable')
def standings(raw,season,observed):
    year=raw.get('season');year=year.get('year') if isinstance(year,dict) else year
    if str(year)!=str(season):return {}
    out={}
    def walk(node,conference=''):
        if node.get('isConference'):conference=node.get('name','')
        for row in node.get('standings',{}).get('entries',[]):
            t=row.get('team') or {};stats={v['name']:v for v in row.get('stats',[])}
            get=lambda k:model.number(stats.get(k,{}).get('value'))
            if not t.get('id') or not t.get('abbreviation'):continue
            wins,losses=get('wins'),get('losses');games=get('gamesPlayed')
            if games is None and wins is not None and losses is not None:games=wins+losses
            out[str(t['id'])]={'id':str(t['id']),'abbr':t['abbreviation'],'name':t.get('displayName'),'logo':(t.get('logos') or [{}])[0].get('href'),
                'conference':conference,'games':games,'wins':wins,'losses':losses,'win_pct':get('winPercent'),'points_for':get('avgPointsFor'),
                'points_against':get('avgPointsAgainst'),'differential':get('differential'),'games_back':get('gamesBehind'),
                'streak':stats.get('streak',{}).get('displayValue'),'home_record':stats.get('Home',{}).get('displayValue'),
                'away_record':stats.get('Road',{}).get('displayValue'),'last_ten':stats.get('Last Ten Games',{}).get('displayValue'),
                'season':season,'observed_at':observed}
        for child in node.get('children',[]):walk(child,conference)
    walk(raw);return out
def normalize(e,observed):
    c=(e.get('competitions') or [{}])[0];s=(e.get('status') or c.get('status') or {}).get('type',{});tip=model.instant(e.get('date'))
    sides={t.get('homeAway'):t for t in c.get('competitors',[])}
    if not tip or not all(k in sides for k in ('home','away')):return None
    season=e.get('season') or {};stype=season.get('type')
    if isinstance(stype,dict):stype=stype.get('type')
    if model.number(stype) not in (2,3):return None
    g={'game_id':str(e['id']),'date':tip.isoformat(),'tipoff':tip.isoformat(),'start':tip.isoformat(),'day':tip.astimezone(ET).date().isoformat(),
        'season':season.get('year'),'season_type':int(stype),'state':s.get('state','unknown'),'status':s.get('description','Unknown'),
        'status_detail':s.get('shortDetail') or s.get('detail'),'completed':s.get('completed',False),
        'canceled':bool(re.search('cancel',s.get('name',''),re.I)),'postponed':bool(re.search('postpon|suspend',s.get('name',''),re.I)),
        'venue':c.get('venue',{}).get('fullName'),'broadcast':', '.join(n for b in c.get('broadcasts',[]) for n in b.get('names',[])),
        'neutral':c.get('neutralSite',False),'observed_at':observed,'source_url':next((l.get('href') for l in e.get('links',[]) if str(l.get('href','')).startswith('https://www.espn.com/')),None),'quotes':[]}
    for side in ('home','away'):
        x=sides[side];t=x.get('team') or {}
        if not t.get('id') or not t.get('abbreviation'):return None
        score=model.number(x.get('score'));g[side]={'id':str(t['id']),'abbr':t['abbreviation'],'name':t.get('displayName'),'logo':t.get('logo'),'color':t.get('color'),'score':score if g['state']!='pre' else None}
        g[side+'_score']=g[side]['score'];g[side+'_name']=g[side]['name'];g[side+'_logo']=g[side]['logo'];g[side+'_color']=g[side]['color']
    return g
def parse_summary(raw,game,observed):
    header=raw.get('header') or {};comp=(header.get('competitions') or [{}])[0];tip=model.instant(comp.get('date'))
    identities={x.get('homeAway'):str(x.get('team',{}).get('id')) for x in comp.get('competitors',[])}
    if str(header.get('id'))!=game['game_id'] or tip!=model.instant(game['tipoff']) or any(identities.get(s)!=game[s]['id'] for s in ('home','away')):return [],[]
    from .quotes import parse_espn
    quotes=parse_espn(raw.get('pickcenter') or [],observed)
    players=[]
    if game['state'] in ('in','post'):
        for team in raw.get('boxscore',{}).get('players',[]):
            if str(team.get('team',{}).get('id')) not in (game['home']['id'],game['away']['id']):continue
            for group in team.get('statistics',[]):
                labels=group.get('labels') or group.get('names') or []
                for a in group.get('athletes',[]):
                    athlete=a.get('athlete') or {};values=a.get('stats') or []
                    if not athlete.get('id') or not athlete.get('displayName') or len(values)!=len(labels) or a.get('didNotPlay'):continue
                    players.append({'player_id':str(athlete['id']),'name':athlete['displayName'],'team':team['team'].get('abbreviation'),
                        'game_id':game['game_id'],'start':game['tipoff'],'state':game['state'],'observed_at':observed,'stats':dict(zip(labels,values))})
    return quotes,players
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--offline',action='store_true');args=ap.parse_args()
    now=datetime.now(timezone.utc);stamp=now.isoformat();today=now.astimezone(ET).date();season=today.year+(today.month>=8)
    cache=read(STATE/'sources.json',{});health={}
    def source(key,url,ttl=0):
        old=cache.get(key) or {};at=model.instant(old.get('observed_at'))
        if at and 0<=(now-at).total_seconds()<ttl:
            health[key]={'status':'cached','observed_at':old['observed_at'],'url':url};return old['data']
        if not args.offline:
            try:
                data=fetch(url);cache[key]={'data':data,'observed_at':stamp};health[key]={'status':'ok','observed_at':stamp,'url':url};return data
            except (OSError,ValueError) as exc:error=type(exc).__name__+': '+str(exc)[:160]
        else:error='Offline'
        health[key]={'status':'retained' if old else 'unavailable','observed_at':old.get('observed_at'),'url':url,'error':error};return old.get('data',{})
    dates={today+timedelta(days=i) for i in range(-3,9)}
    pending=read(STATE/'model_accuracy.json',{'records':{}})
    for r in pending.get('records',{}).values():
        at=model.instant(r.get('start'))
        if r.get('result')=='Pending' and at and now-timedelta(days=14)<=at<now:dates.add(at.astimezone(ET).date())
    dates=sorted(dates)
    def get_day(d):
        key='scoreboard-'+d.isoformat();raw=source(key,BASE+'scoreboard?dates='+d.strftime('%Y%m%d')+'&limit=1000');return key,raw
    with ThreadPoolExecutor(max_workers=4) as pool:boards=list(pool.map(get_day,dates))
    today_key='scoreboard-'+today.isoformat()
    if health[today_key]['status'] not in ('ok','cached') and not args.offline:raise RuntimeError('NBA schedule refresh failed; retain original publication: '+str(health[today_key]))
    current=standings(source('standings-'+str(season),'https://site.api.espn.com/apis/v2/sports/basketball/nba/standings?season='+str(season),ttl=1800),season,health['standings-'+str(season)]['observed_at'])
    prior=standings(source('standings-'+str(season-1),'https://site.api.espn.com/apis/v2/sports/basketball/nba/standings?season='+str(season-1),ttl=7*86400),season-1,health['standings-'+str(season-1)]['observed_at'])
    if len(current)<20:raise RuntimeError('Current NBA standings season/coverage unavailable')
    games={}
    for key,raw in boards:
        for event in raw.get('events',[]):
            g=normalize(event,health[key]['observed_at'])
            if not g or g['season']!=season:continue
            g['source_stale']=health[key]['status'] not in ('ok','cached');games[g['game_id']]=g
            from .quotes import parse_espn
            g['quotes']=parse_espn((event.get('competitions') or [{}])[0].get('odds') or [],g['observed_at'])
    ordered=sorted(games.values(),key=lambda g:g['tipoff']);players=[]
    wanted=[g for g in ordered if now-timedelta(days=2)<model.instant(g['tipoff'])<now+timedelta(hours=36)]
    def context(g):
        key='summary-'+g['game_id'];raw=source(key,BASE+'summary?event='+g['game_id'],ttl=0 if g['state']!='post' else 1800)
        if health[key]['status'] not in ('ok','cached'):return
        qs,ps=parse_summary(raw,g,health[key]['observed_at']);g['quotes']=qs or g['quotes'];players.extend(ps)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(context,wanted))
    attempts=[]
    upcoming=[g for g in ordered if g['state']=='pre' and not g['canceled'] and not g['postponed'] and model.instant(g['tipoff'])>now]
    if not args.offline:
        # A bounded public comparison page supplements missing markets.
        offers=public_odds.collect([g for g in upcoming if model.instant(g['tipoff'])<=now+timedelta(hours=48)],now,attempts)
        for gid,q in offers:
            if gid not in games:continue
            existing=games[gid]['quotes'];identity=lambda x:(x['market'],x['side'],x.get('line'),x['book'])
            old=next((x for x in existing if identity(x)==identity(q)),None)
            if old and model.instant(old['observed_at'])>=model.instant(q['observed_at']):continue
            existing[:]=[x for x in existing if identity(x)!=identity(q)];existing.append(q)
    teams={}
    for tid,t in current.items():teams[tid]={**t,'current':t,'prior':prior.get(tid,{})}
    def team_details(item):
        tid,t=item
        for stat_season in ([season,season-1] if (t.get('games') or 0)>0 else [season-1]):
            key='team-'+tid+'-'+str(stat_season)
            raw=source(key,BASE+'teams/'+tid+'/statistics?season='+str(stat_season)+'&seasontype=2',ttl=3600 if stat_season==season else 7*86400)
            reported=raw.get('requestedSeason') or raw.get('season') or {}
            if str(reported.get('year'))==str(stat_season):
                values={v['name']:v.get('value') for c in raw.get('results',{}).get('stats',{}).get('categories',[]) for v in c.get('stats',[]) if model.number(v.get('value')) is not None}
                if not values:continue
                t['stats']=values;t['stats_season']=stat_season;t['stats_observed_at']=health[key]['observed_at'];break
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(team_details,teams.items()))
    board=[]
    for g in ordered:
        if g in upcoming and not g['source_stale']:
            g['projection']=model.project(teams.get(g['home']['id'],{}),teams.get(g['away']['id'],{}),now,g['neutral'])
        else:g['projection']={'ratings_known':False,'reason':'No new forecast after tipoff'}
        g['p_home']=g['projection'].get('p_home')
        board.extend(model.candidates(g,now))
        # One original named-book bundle for independent market comparison history.
        ml=[q for q in g['quotes'] if q['market']=='ML']
        if ml:
            q=ml[0];paired=[r for r in ml if r['book']==q['book'] and r['observed_at']==q['observed_at']]
            g['odds']={'book':q['book'],'fetched_at':q['observed_at'],'quotes':{r['side']+'_ml':r for r in paired}}
    records=read(STATE/'model_accuracy.json',{'records':{}})
    # Frozen forecasts are displayed for started games; never recomputed from results.
    frozen={r['event_id']:r for r in records.get('records',{}).values() if r.get('kind')=='game'}
    for g in ordered:
        old=frozen.get(g['game_id'])
        if old and g['state']!='pre':g['frozen_forecast']={'p_home':old.get('probability'),'margin':old.get('margin'),'total':old.get('total'),'captured_at':old.get('captured_at')}
    accuracy=game_history.update(STATE/'model_accuracy.json',OUT/'accuracy.json',board,upcoming,ordered,'NBA')
    leader_raw=source('leaders','https://site.api.espn.com/apis/site/v3/sports/basketball/nba/leaders?season='+str(season)+'&seasontype=2&limit=10',ttl=3600)
    leader_season=leader_raw.get('requestedSeason') or {};leaders=[]
    if leader_season.get('year') in (season,season-1) and (leader_season.get('type') or {}).get('type')==2:
        for category in (leader_raw.get('leaders') or {}).get('categories',[]):
            for r in category.get('leaders',[])[:10]:
                athlete=r.get('athlete') or {}
                if athlete.get('id') and model.number(r.get('value')) is not None:
                    leaders.append({'name':athlete.get('displayName'),'player_id':str(athlete['id']),'team':(r.get('team') or {}).get('abbreviation'),'category':category.get('displayName'),'value':r['value']})
    leader_data={'season':leader_season.get('year'),'season_label':leader_season.get('displayName'),'observed_at':health['leaders']['observed_at'],'leaders':leaders}
    news_raw=source('news',BASE+'news?limit=10',ttl=1800)
    news=[{'title':a.get('headline'),'url':a.get('links',{}).get('web',{}).get('href'),'published':a.get('published')} for a in news_raw.get('articles',[]) if a.get('headline')]
    injury=source('injuries',BASE+'injuries',ttl=1800);injuries=[]
    for t in injury.get('injuries',[]):
        for a in t.get('injuries',[]):
            at=model.instant(a.get('date'))
            if not at or not 0<=(now-at).total_seconds()<=72*3600:continue
            injuries.append({'team':t.get('displayName') or t.get('team',{}).get('displayName'),'name':a.get('athlete',{}).get('displayName'),
                'position':a.get('athlete',{}).get('position',{}).get('abbreviation'),'status':a.get('status'),'reported_at':a['date'],'detail':a.get('shortComment'),'source':'ESPN'})
    near=[g for g in upcoming if model.instant(g['tipoff'])<=now+timedelta(hours=24)]
    coverage={g['game_id']:public_odds.covered_markets(g,now) for g in upcoming}
    priced=sum(bool(coverage[g['game_id']]) for g in near)
    meta={'generated_at':stamp,'season':season,'season_label':f'{season-1}-{str(season)[-2:]}','league':'NBA','model_version':model.VERSION,
        'model_mode':'research','automatic_qualification':False,'timezone':'America/Toronto','max_odds_age_hours':1.5,
        'source_status':'partial' if any(s['status'] in ('retained','unavailable') for s in health.values()) else 'live-data','sources':health,
        'public_odds_attempts':attempts,'counts':{'games':len(upcoming),'teams':len(teams),'qualified':0,'players':len(players),'forecast_games':sum(g['projection'].get('ratings_known',False) for g in upcoming)},
        'odds_health':{'status':'ok' if all(coverage[g['game_id']]=={'ML','ATS','TOTAL'} for g in near) else 'partial','window_hours':24,'window_games':len(near),'window_priced_games':priced,'upcoming_games':len(upcoming),'priced_games':sum(bool(v) for v in coverage.values()),'later_unpriced_games':sum(not coverage[g['game_id']] for g in upcoming if g not in near)},
        'limitations':['New scoring-rate baseline; probabilities are uncalibrated research estimates.','Prior-year scoring has limited roster continuity. No player injury adjustment.','All observed markets remain research selections; no automatic BEST BET labels.','Prices are snapshots. Stats and standings are season-labeled. Missing source fields remain missing.']}
    outputs={'meta':meta,'games':ordered,'board':board,'standings':{'season':season,'generated_at':stamp,'teams':list(current.values())},'teams':{'season':season,'generated_at':stamp,'teams':list(teams.values())},'players':{'season':season,'generated_at':stamp,'players':players},'leaders':leader_data,'news':news,'injuries':injuries,'results':[g for g in ordered if g['completed']]}
    for name,data in outputs.items():write(OUT/(name+'.json'),data)
    # Only public statistics/observations are stored; never browser wager state.
    cache={k:v for k,v in cache.items() if not k.startswith(('scoreboard-','summary-')) or model.instant(v.get('observed_at')) and (now-model.instant(v['observed_at'])).total_seconds()<14*86400}
    write(STATE/'sources.json',cache)
    print(json.dumps({'league':'NBA','season':season,**meta['counts'],'priced_next_24h':priced}))
if __name__=='__main__':main()
