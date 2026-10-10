"""Keyless NHL publication. Independent schedule feeds; optional data stays labelled."""
import json, re, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from . import public_odds
from . import official as nhl
from . import challenger
from .model import VERSION, number, instant, project, candidates, update_accuracy, accuracy_report
ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'state'; OUT=ROOT/'site/data'
BASE='https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/'
TORONTO=ZoneInfo('America/Toronto')
def read(path, default):
    try:return json.loads(path.read_text())
    except (FileNotFoundError,json.JSONDecodeError):return default
def write(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');temp.replace(path)
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'KEVBOT-NHL/1.0 (public statistics)','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
def flatten_standings(raw):
    result={}
    def visit(node,conference=''):
        if 'Conference' in node.get('name',''):conference=node['name']
        for row in node.get('standings',{}).get('entries',[]):
            team=row.get('team',{});stats={s['name']:s for s in row.get('stats',[])}
            get=lambda k:number(stats.get(k,{}).get('value'))
            gp=get('gamesPlayed') or 0
            result[str(team['id'])]={'id':str(team['id']),'abbr':team.get('abbreviation'),'name':team.get('displayName'),
              'logo':(team.get('logos') or [{}])[0].get('href'),'color':team.get('color'),'conference':conference,
              'gp':gp,'wins':get('wins'),'losses':get('losses'),'otl':get('overtimeLosses'),'points':get('points'),
              'gf':get('pointsFor'),'ga':get('pointsAgainst'),'gf_pg':get('pointsFor')/gp if gp else None,
              'ga_pg':get('pointsAgainst')/gp if gp else None,'points_pct':get('points')/(2*gp) if gp and get('points') is not None else None,
              'home_record':stats.get('Home',{}).get('displayValue'),'away_record':stats.get('Road',{}).get('displayValue'),
              'last10':stats.get('Last Ten Games',{}).get('displayValue'),'streak':stats.get('streak',{}).get('displayValue'),
              'goal_diff':get('pointDifferential')}
        for child in node.get('children',[]):visit(child,conference)
    visit(raw);return result

def extra_stats(raw):
    s={s['name']:number(s.get('value')) for c in raw.get('results',{}).get('stats',{}).get('categories',[]) for s in c.get('stats',[])}
    gp=s.get('games') or 0
    rate=lambda k:s[k]/gp if gp and s.get(k) is not None else None
    return {'shots_pg':rate('shotsTotal'),'shots_against_pg':rate('shotsAgainst'),'save_pct':s.get('savePct'),
      'shooting_pct':s.get('shootingPct'),'faceoff_pct':s.get('faceoffPercent'),'pp_goals':s.get('powerPlayGoals'),
      'sh_goals':s.get('shortHandedGoals'),'penalty_minutes_pg':rate('penaltyMinutes')}

def quotes(competition, stamp):
    rows=[]
    for source in competition.get('odds',[]):
        book=source.get('provider',{}).get('name')
        if not book:continue
        for field,market,sides in [('moneyline','ML',('home','away')),('pointSpread','ATS',('home','away')),('total','TOTAL',('over','under'))]:
            points=[]
            for side in sides:
                data=source.get(field,{}).get(side,{})
                q=data.get('current') or data.get('close') or {}
                price=number(q.get('odds'));line=number(re.sub(r'^[ou]','',str(q.get('line','')))) if market!='ML' else None
                if price is None and market=='ML':price=number(source.get(side+'TeamOdds',{}).get('moneyLine'))
                if price is None or abs(price)<100 or (market!='ML' and line is None):break
                points.append({'market':market,'side':side,'line':line,'price':price,'book':book,'observed_at':stamp,
                               'open_price':number(data.get('open',{}).get('odds'))})
            if len(points)!=2:continue
            if market=='ATS' and abs(points[0]['line']+points[1]['line'])>1e-8:continue
            if market=='TOTAL' and points[0]['line']!=points[1]['line']:continue
            for i,row in enumerate(points):row['opposite_price']=points[1-i]['price']
            rows.extend(points)
    return rows

def goalie(competitor):
    raw=next((p for p in competitor.get('probables',[]) if 'goalie' in p.get('name','').lower()),{})
    a=raw.get('athlete',{});status=raw.get('status',{}).get('type','unknown')
    return {'name':a.get('displayName'),'headshot':a.get('headshot'),'id':a.get('id'),'status':status,
            'confirmed':status=='confirmed','stats':raw.get('statistics',[])}

def normalize(event,stamp):
    c=(event.get('competitions') or [{}])[0];s=event.get('status',c.get('status',{})).get('type',{})
    teams={t.get('homeAway'):t for t in c.get('competitors',[])}
    if not all(side in teams for side in ('home','away')):return None
    start=instant(event.get('date'))
    if not start:return None
    g={'game_id':str(event['id']),'date':start.isoformat(),'start':start.isoformat(),'day':start.astimezone(TORONTO).date().isoformat(),
      'season':event.get('season',{}).get('year'),'season_type':int(event.get('season',{}).get('type') or event.get('seasonType',{}).get('type') or 0),
      'completed':s.get('completed',False),'state':s.get('state','unknown'),'status':s.get('description','Unknown'),
      'status_detail':s.get('detail'),'venue':c.get('venue',{}).get('fullName'),'neutral':c.get('neutralSite',False),
      'broadcast':', '.join(n for b in c.get('broadcasts',[]) for n in b.get('names',[])),'quotes':quotes(c,stamp),
      'source_name':'ESPN','source_url':next((l['href'] for l in event.get('links',[]) if l.get('href','').startswith('https://www.espn.com/')),None)}
    for side in ('home','away'):
        row=teams[side];t=row['team'];score=row.get('score');score=score.get('value') if isinstance(score,dict) else score
        g.update({side:t.get('abbreviation'),side+'_id':str(t['id']),side+'_name':t.get('displayName'),
          side+'_logo':t.get('logo') or (t.get('logos') or [{}])[0].get('href'),side+'_color':t.get('color'),
          side+'_score':number(score) if s.get('state')!='pre' else None,side+'_goalie':goalie(row),
          side+'_record':next((r.get('summary') for r in row.get('records',[]) if r.get('type')=='total'),None)})
    return g

def main():
    now=datetime.now(timezone.utc);stamp=now.isoformat();today=now.astimezone(TORONTO).date()
    STATE.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
    cache=read(STATE/'sources.json',{});health={}
    def source(key,url,ttl=0,required=False):
        old=cache.get(key);at=instant(old.get('observed_at')) if old else None
        if at and 0 <= (now-at).total_seconds() < ttl:
            health[key]={'status':'cached','observed_at':old['observed_at'],'url':url};return old['data']
        try:
            value=fetch(url);cache[key]={'observed_at':stamp,'data':value}
            health[key]={'status':'ok','observed_at':stamp,'url':url};return value
        except Exception as exc:
            health[key]={'status':'unavailable','observed_at':old.get('observed_at') if old else None,'url':url,'error':type(exc).__name__}
            if required:raise RuntimeError(f'Required NHL source failed: {key}') from exc
            return old['data'] if old else {}
    # ESPN enriches the board; an independent NHL schedule keeps refreshes working
    # when ESPN denies requests from a CI runner. Never retry a denied endpoint.
    first=source('scoreboard',BASE+'scoreboard?dates='+today.strftime('%Y%m%d'))
    espn_ok=health['scoreboard']['status']!='unavailable' and isinstance(first.get('events'),list)
    season=int(first.get('leagues',[{}])[0].get('season',{}).get('year') or (today.year+1 if today.month>=8 else today.year))
    dates=[today+timedelta(days=i) for i in range(-14,9) if i]
    def day_fetch(day):
        key='scoreboard-'+day.isoformat()
        raw=source(key,BASE+'scoreboard?dates='+day.strftime('%Y%m%d'))
        return key,raw
    boards=[]
    if espn_ok:
        with ThreadPoolExecutor(max_workers=4) as pool:boards=[('scoreboard',first),*pool.map(day_fetch,dates)]
    official_boards=[]
    for offset in (0,-14,-7,7):
        day=today+timedelta(days=offset);key='nhl-schedule-'+day.isoformat()
        raw=source(key,'https://api-web.nhle.com/v1/schedule/'+day.isoformat())
        if health[key]['status']!='unavailable' and isinstance(raw.get('gameWeek'),list):official_boards.append((key,raw))
    if not espn_ok and not any(k=='nhl-schedule-'+today.isoformat() for k,_ in official_boards):
        raise RuntimeError('Both independent current NHL schedule feeds failed; retain prior publication')
    standings_url='https://site.api.espn.com/apis/v2/sports/hockey/nhl/standings?season='
    current=flatten_standings(source('standings-'+str(season),standings_url+str(season),ttl=1800))
    prior=flatten_standings(source('standings-'+str(season-1),standings_url+str(season-1),ttl=7*86400))
    for rows,year in ((current,season),(prior,season-1)):
        for t in rows.values():t['observed_at']=health['standings-'+str(year)]['observed_at']
    official=source('nhl-official','https://api-web.nhle.com/v1/standings/now',ttl=1800)
    official_teams=nhl.standings(official,{**prior,**current},season)
    if official_teams and health['nhl-official']['status']!='unavailable':
        for t in official_teams.values():t['observed_at']=health['nhl-official']['observed_at']
        current.update(official_teams)
    summaries={}; goalie_data={}
    for stats_year in (season-1,season):
        season_id=f'{stats_year-1}{stats_year}'
        url='https://api.nhle.com/stats/rest/en/team/summary?isAggregate=false&isGame=false&start=0&limit=100&cayenneExp=seasonId='+season_id+'%20and%20gameTypeId=2'
        key='nhl-team-summary-'+str(stats_year)
        raw=source(key,url,ttl=6*3600 if stats_year==season else 7*86400);summaries[stats_year]=raw
        goalie_key='nhl-goalies-'+str(stats_year)
        goalie_url='https://api.nhle.com/stats/rest/en/goalie/summary?isAggregate=false&isGame=false&start=0&limit=1000&cayenneExp=seasonId='+season_id+'%20and%20gameTypeId=2'
        goalie_raw=source(goalie_key,goalie_url,ttl=6*3600 if stats_year==season else 7*86400)
        goalie_data[stats_year]=challenger.goalie_index(goalie_raw,health[goalie_key]['observed_at'],stats_year) if health[goalie_key]['status']!='unavailable' else {}
        if stats_year==season-1 and health[key]['status']!='unavailable':
            mapped=nhl.summary_teams(raw,{**prior,**current})
            for t in mapped.values():t['observed_at']=health[key]['observed_at']
            prior.update(mapped)
    if not current and not prior:raise RuntimeError('NHL team statistics unavailable')
    def team_stats(tid):
        base=current.get(tid,prior.get(tid,{}));stats_season=season if current.get(tid,{}).get('gp',0)>0 else season-1
        extra={};observed=None
        if espn_ok and not tid.startswith('nhlteam:'):
            key=f'team-{tid}-{stats_season}'
            extra=extra_stats(source(key,BASE+f'teams/{tid}/statistics?season={stats_season}&seasontype=2',ttl=6*3600 if stats_season==season else 7*86400))
            observed=health[key]['observed_at']
        rows={nhl.name_key(r.get('teamFullName')):r for r in summaries[stats_season].get('data',[])}
        summary=rows.get(nhl.name_key(base.get('name')),{});summary_key='nhl-team-summary-'+str(stats_season)
        if summary:
            extra.update(pp_pct=summary.get('powerPlayPct'),pk_pct=summary.get('penaltyKillPct'),regulation_wins=summary.get('winsInRegulation'),
                         ot_wins=(summary['wins']-summary['winsInRegulation']) if summary.get('wins') is not None and summary.get('winsInRegulation') is not None else None,
                         ot_losses=summary.get('otLosses'))
            if not espn_ok:
                extra.update(shots_pg=summary.get('shotsForPerGame'),shots_against_pg=summary.get('shotsAgainstPerGame'),faceoff_pct=(summary['faceoffWinPct']*100 if summary.get('faceoffWinPct') is not None else None))
                observed=health[summary_key]['observed_at']
        context={'observed_at':health[summary_key]['observed_at'] if health[summary_key]['status']!='unavailable' else None,
          'gp':summary.get('gamesPlayed'),'ga_pg':summary.get('goalsAgainstPerGame'),
          'shots_pg':summary.get('shotsForPerGame'),'shots_against_pg':summary.get('shotsAgainstPerGame'),
          'pp_pct':summary.get('powerPlayPct'),'pk_pct':summary.get('penaltyKillPct'),
          'ot_wins':extra.get('ot_wins'),'ot_losses':extra.get('ot_losses')}
        return tid,{**base,'current':current.get(tid,{}),'prior':prior.get(tid,{}),'stats_season':stats_season,'extra':extra,'stats_observed_at':observed,'context_features':context}
    with ThreadPoolExecutor(max_workers=4) as pool:teams=dict(pool.map(team_stats,sorted(set(current)|set(prior))))
    records=read(STATE/'model_accuracy.json',{})
    known=read(OUT/'games.json',[])+list(records.values());games={}
    for key,raw in boards:
        for event in raw.get('events',[]):
            g=normalize(event,health[key]['observed_at'])
            if g:
                g=nhl.stabilize(g,known);g['source_stale']=health[key]['status']=='unavailable';games[g['game_id']]=g
    for key,raw in official_boards:
        for week in raw['gameWeek']:
            for event in week.get('games',[]):
                g=nhl.normalize(event,raw.get('oddsPartners',[]),health[key]['observed_at'],teams)
                if not g or not today-timedelta(days=14)<=instant(g['date']).astimezone(TORONTO).date()<=today+timedelta(days=8):continue
                g=nhl.stabilize(g,list(games.values())+known);existing=games.get(g['game_id'])
                if existing and not existing['source_stale']:
                    existing['nhl_game_id']=g['nhl_game_id']
                    if not existing['quotes']:existing['quotes']=g['quotes']
                else:games[g['game_id']]=g
    upcoming_for_prices=[g for g in games.values() if g['state']=='pre' and instant(g['date'])>now]
    if any(not g['quotes'] for g in upcoming_for_prices):
        try:
            offers=public_odds.fetch(upcoming_for_prices,now)
            for game_id,quote in offers:
                existing=games[game_id]['quotes']
                if not any((q['market'],q['side'],q.get('line'),q['book'])==(quote['market'],quote['side'],quote.get('line'),quote['book']) for q in existing):existing.append(quote)
            health['public-book-odds']={'status':'ok' if offers else 'no matched prices','observed_at':stamp,'url':offers[0][1]['source_url'] if offers else public_odds.URL,'quotes':len(offers)}
        except (OSError,ValueError) as exc:
            health['public-book-odds']={'status':'unavailable','observed_at':None,'url':public_odds.URL,'error':type(exc).__name__}
    board=[];ordered=sorted(games.values(),key=lambda g:g['date'])
    for g in ordered:
        for side in ('home','away'):
            tid=g[side+'_id'];t=teams.get(tid,{})
            previous=[p for p in ordered if p['date']<g['date'] and tid in (p['home_id'],p['away_id']) and p['state'] in ('pre','in','post') and not re.search('postpon|cancel|suspend',p['status'],re.I)]
            rest=max(0,(instant(g['date']).astimezone(TORONTO).date()-instant(previous[-1]['date']).astimezone(TORONTO).date()).days-1) if previous else None
            g[side+'_rest']=rest;g[side+'_stats']=t
        g['projection']=project(g['home_stats'],g['away_stats'],g['home_rest'],g['away_rest'],g['neutral'])
        timestamps=[(g[side+'_stats'].get(period,{}).get('observed_at'),limit) for side in ('home','away') for period,limit in [('current',24*3600),('prior',30*86400)]]
        g['stats_stale']=any(not instant(t) or not -300<=(now-instant(t)).total_seconds()<=limit for t,limit in timestamps)
        if g['stats_stale'] or g['source_stale']:g['projection']={'ratings_known':False,'reason':'Source data stale or unavailable'}
        g['challenger']=challenger.project(g,goalie_data,season,now) if g['state']=='pre' and instant(g['date'])>now else None
        if g['state']!='pre' or instant(g['date'])<=now:
            g['projection']=records.get(g['game_id'],{}).get('projection',{'ratings_known':False,'reason':'No frozen pregame forecast for this game'})
            g['challenger']=records.get(g['game_id'],{}).get('challenger')
        g['p_home']=g['projection'].get('p_home');board.extend(candidates(g,now))
    for record in list(records.values()):
        if record.get('result') or record['game_id'] in games:continue
        start=instant(record['start'])
        if start and 0 <= (now-start).total_seconds() < 90*86400:
            key='nhl-result-'+start.date().isoformat()
            raw=source(key,'https://api-web.nhle.com/v1/schedule/'+start.date().isoformat(),ttl=300)
            matched=False
            if health[key]['status']!='unavailable':
                for week in raw.get('gameWeek',[]):
                    for event in week.get('games',[]):
                        g=nhl.normalize(event,[],health[key]['observed_at'],teams)
                        if not g:continue
                        g=nhl.stabilize(g,[record])
                        if g['game_id']==record['game_id']:
                            g['projection']=record.get('projection',{});ordered.append(g);matched=True;break
                    if matched:break
            if not matched and espn_ok and not record['game_id'].startswith('nhl:'):
                raw=source('result-'+record['game_id'],BASE+'summary?event='+record['game_id']);header=raw.get('header',{});comp=(header.get('competitions') or [{}])[0]
                if comp:
                    g=normalize({**header,'date':comp.get('date'),'season':{'year':record['season'],'type':record['season_type']}},stamp)
                    if g:g['projection']=record.get('projection',{});ordered.append(g)
    records=update_accuracy(records,ordered,board,stamp)
    news=source('news',BASE+'news?limit=8',ttl=1800);injury_raw=source('injuries',BASE+'injuries',ttl=1800)
    injuries=[]
    for group in injury_raw.get('injuries',[]):
        for r in group.get('injuries',[]):
            injuries.append({'team':group.get('displayName') or group.get('team',{}).get('displayName'),
              'team_id':str(group.get('id') or group.get('team',{}).get('id') or ''),'player':r.get('athlete',{}).get('displayName'),
              'status':r.get('status'),'date':r.get('date'),'detail':r.get('shortComment') or r.get('details',{}).get('type')})
    upcoming=[g for g in ordered if instant(g['date'])>now and g['state']=='pre']
    meta={'generated_at':stamp,'model_version':VERSION,'season':season,'timezone':'America/Toronto','max_odds_age_hours':1.5,
      'challenger':{'version':challenger.VERSION,'mode':'shadow-only','promotion_enabled':False,'features':['shots','special teams','confirmed goalie performance','shrunk OT/SO outcomes']},
      'source_status':'partial' if any(v['status']=='unavailable' for v in health.values()) else 'live-data','schedule_source':'ESPN + NHL' if espn_ok else 'NHL fallback','sources':health,'odds_health':{'status':'ok' if all(g['quotes'] for g in upcoming) else 'partial',
       'upcoming_games':len(upcoming),'priced_games':sum(bool(g['quotes']) for g in upcoming)},
      'counts':{'games':len(upcoming),'qualified':sum(not r['held'] for r in board),'teams':len(teams)},
      'settings':{'tiers':{'lean':.03,'good':.05,'best':.08}},'limitations':[
       'Uncalibrated goal-rate model; probabilities are estimates, not measured confidence.',
       'Equal OT/SO tie-break chance; no player-level goalie or injury adjustment.',
       'Priced picks blend 25% model / 75% same-book no-vig market probability.',
       'Prior-season team strength is regressed and blended over the first 20 games.',
       'Odds are observed public snapshots, not a live sportsbook guarantee.']}
    outputs={'meta':meta,'games':ordered,'board':board,'standings':{'season':season,'teams':list(teams.values())},
      'news':[{'title':r.get('headline'),'url':r.get('links',{}).get('web',{}).get('href'),'published':r.get('published'),
         'image':(r.get('images') or [{}])[0].get('url')} for r in news.get('articles',[])[:8]],
      'injuries':injuries,'accuracy':accuracy_report(records,season,stamp),'index':{'generated_at':stamp,'dates':sorted(set(g['day'] for g in ordered))}}
    write(STATE/'model_accuracy.json',records)
    # Bound date caches while keeping long-lived season statistics.
    cache={k:v for k,v in cache.items() if not k.startswith('scoreboard-') or k>='scoreboard-'+(today-timedelta(days=16)).isoformat()}
    def slim(value):
        if isinstance(value,list):return [slim(x) for x in value]
        if not isinstance(value,dict):return value
        ignored={'uid','$ref','tracking','footer','header','calendar','calendarStartDate','calendarEndDate','description','shortDescription','perGameDisplayValue','leaders','headlines','tickets','geoBroadcasts','situation','headshot','birthPlace','birthDate','college','experience','citizenship','jersey','weight','height','displayHeight','displayWeight'}
        return {k:slim(v) for k,v in value.items() if k not in ignored}
    # Keep raw scoreboard status descriptions and goalie headshots intact. Persist only
    # season statistics: schedules/news/injuries are freshly requested each build.
    cache={k:slim(v) for k,v in cache.items() if k.startswith(('team-','standings-','nhl-')) and not k.startswith(('nhl-schedule-','nhl-result-'))}
    write(STATE/'sources.json',cache)
    for name,data in outputs.items():write(OUT/(name+'.json'),data)
    print(json.dumps({'sport':'NHL',**meta['counts'],'optional_source_failures':[k for k,v in health.items() if v['status']=='unavailable']}))
if __name__=='__main__':main()
