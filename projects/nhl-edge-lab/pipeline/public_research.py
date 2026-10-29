"""Public HTML and advertised CSV downloads. Experimental inputs, not APIs.

MoneyPuck inputs are credited, used for personal/non-commercial research and
summarized rather than republished wholesale. Failed reads retain original
observation timestamps. No protected/private endpoints or authentication.
"""
import csv
import io
import json
import math
import re
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from .model import instant, number, score_grid
from .public_odds import Tree, code

ROOT=Path(__file__).resolve().parents[1]
VERSION='nhl-public-context-1.0'
MP='https://moneypuck.com/data.htm'
DF='https://www.dailyfaceoff.com/starting-goalies'
FIELDS={'playerId','season','name','team','position','situation','games_played','icetime','iceTime','I_F_xGoals','I_F_goals','I_F_shotsOnGoal','xGoals','goals','xGoalsFor','xGoalsAgainst','flurryAdjustedxGoalsFor','flurryAdjustedxGoalsAgainst','goalsFor','goalsAgainst','shotsOnGoalFor','shotsOnGoalAgainst','gameId','gameDate','opposingTeam','home_or_away','playerTeam'}

def norm(value):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFKD',value or '').lower() if c.isalpha() and not unicodedata.combining(c))

def fresh(at,now,hours):
    time=instant(at)
    return bool(time and 0<=(now-time).total_seconds()<=hours*3600)

def download(url,limit=12_000_000):
    host=urlparse(url).hostname
    if host not in ('www.dailyfaceoff.com','dailyfaceoff.com','moneypuck.com','www.moneypuck.com','peter-tanner.com'):raise ValueError('Unapproved public research host')
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; KEVBOTBETS personal research; attribution in site)','Accept':'text/html,text/csv,application/zip'})
    with urllib.request.urlopen(req,timeout=18) as r:raw=r.read(limit+1)
    if len(raw)>limit:raise ValueError('Download exceeds bounded size')
    if b'Access denied' in raw[:8000] or b'captcha' in raw[:8000].lower():raise ValueError('Source unavailable')
    return raw

def embedded(html):
    tree=Tree();tree.feed(html)
    # Tree intentionally omits script contents; read only the public page's data script.
    m=re.search(r'<script\b[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',html,re.S)
    result=json.loads(m[1]).get('props',{}).get('pageProps',{}) if m else {}
    result['_advertised_goalie_pages']=sorted({urljoin(DF,a.attrs['href']) for a in tree.root.find('a') if re.fullmatch(r'/starting-goalies/\d{4}-\d{2}-\d{2}',a.attrs.get('href',''))})
    return result

def links(html):
    tree=Tree();tree.feed(html)
    return [urljoin(MP,n.attrs['href']) for n in tree.root.find('a') if n.attrs.get('href')]

def csv_rows(raw):
    text=raw.decode('utf-8-sig');rows=[]
    for r in csv.DictReader(io.StringIO(text)):
        if r.get('situation') not in ('all','5on5','5on4'):continue
        rows.append({k:v for k,v in r.items() if k in FIELDS})
    return rows

def zip_results(raw):
    rows=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist()
        if len(infos)>2000 or sum(i.file_size for i in infos)>80_000_000:raise ValueError('Archive exceeds bounded size')
        for i in infos:
            if i.filename.endswith('.csv'):
                for r in csv_rows(z.read(i)):
                    if r.get('situation')=='all' and r.get('gameId'):
                        rows.append({**{k:r.get(k) for k in ('playerId','name','gameId','gameDate','icetime','I_F_goals','I_F_shotsOnGoal')},'team':r.get('team') or r.get('playerTeam')})
    return rows

class Cache:
    def __init__(self,now,path=None):
        self.now=now;self.path=path or ROOT/'state/public_research_cache.json';self.health={}
        try:self.data=json.loads(self.path.read_text())
        except (OSError,ValueError):self.data={}
    def get(self,url,parser,hours):
        old=self.data.get(url,{})
        if fresh(old.get('at'),self.now,hours):
            self.health[url]={'status':'cached','observed_at':old['at']};return old.get('data')
        try:
            data=parser(download(url));record={'at':self.now.isoformat(),'data':data};self.data[url]=record
            self.health[url]={'status':'ok','observed_at':record['at']};return data
        except (OSError,ValueError,KeyError,zipfile.BadZipFile) as exc:
            self.health[url]={'status':'retained' if old else 'unavailable','observed_at':old.get('at'),'error':type(exc).__name__}
            return old.get('data')
    def save(self):
        self.path.parent.mkdir(exist_ok=True);self.path.write_text(json.dumps(self.data,separators=(',',':'),allow_nan=False)+'\n')

def goalie_reports(raw,games,now,observed):
    result={}
    if not fresh(observed,now,6):return result
    for row in (raw or {}).get('data',[]):
        start=instant(row.get('dateGmt'))
        matched=[g for g in games if instant(g.get('date'))==start and all(norm(g.get(s+'_name'))==norm(row.get(s+'TeamName')) for s in ('home','away'))]
        if len(matched)!=1:continue
        g=matched[0];sides={}
        for side in ('home','away'):
            status=row.get(side+'NewsStrengthName') or 'Unknown';at=row.get(side+'NewsCreatedAt')
            confirmed=status=='Confirmed' and fresh(at,now,72) and isinstance(row.get(side+'NewsSourceUrl'),str) and row[side+'NewsSourceUrl'].startswith('https://')
            sides[side]={'name':row.get(side+'GoalieName'),'status':status,'confirmed':confirmed,
                'observed_at':observed,'reported_at':at,'source_url':row.get(side+'NewsSourceUrl') or DF,
                'source_name':'Daily Faceoff public starting-goalie page','note':row.get(side+'NewsDetails') or 'No confirmation supplied'}
        result[str(g['game_id'])]=sides
    return result

def lineup(raw,now,observed):
    c=(raw or {}).get('combinations',{})
    if not fresh(observed,now,48) or not fresh(c.get('updatedAt'),now,72):return None
    players={}
    for r in c.get('players',[]):
        key=norm(r.get('name'))
        if not key:continue
        p=players.setdefault(key,{'name':r['name'],'line':None,'power_play':None,'available':None,'questionable':False,'season':r.get('season') or {},'last5':r.get('last5') or {}})
        cat,group=r.get('categoryIdentifier'),r.get('groupIdentifier')
        if cat=='ev' and re.fullmatch(r'f[1-4]|d[1-3]',group or ''):
            p['line']=group
            if p['available'] is not False:p['available']=True
        if cat=='pp':p['power_play']=group
        if cat=='oi' and group in ('ir','scr','scratched','injured'):p['available']=False
        if r.get('gameTimeDecision') or r.get('injuryStatus'):p['questionable']=True
    return {'team':code(c.get('teamAbbreviation')),'name':c.get('teamName'),'players':list(players.values()),'updated_at':c['updatedAt'],'observed_at':observed,'source_url':'https://www.dailyfaceoff.com/teams/'+str(c.get('teamSlug'))+'/line-combinations','status':'Projected lineup; participation unconfirmed'}

def refresh(games,now=None):
    now=now or datetime.now(timezone.utc);cache=Cache(now);year=now.year if now.month>=7 else now.year-1
    raw=cache.get(DF,lambda x:embedded(x.decode()),.25) or {}
    reports=goalie_reports(raw,games,now,cache.health.get(DF,{}).get('observed_at'))
    from zoneinfo import ZoneInfo
    wanted_days={instant(g['date']).astimezone(ZoneInfo('America/Toronto')).date().isoformat() for g in games if instant(g.get('date')) and 0<(instant(g['date'])-now).total_seconds()<48*3600 and g.get('state')=='pre'}
    extra_data=[]
    for url in raw.get('_advertised_goalie_pages',[]):
        if url.rsplit('/',1)[-1] not in wanted_days:continue
        data=cache.get(url,lambda x:embedded(x.decode()),.25) or {};extra_data.append(data)
        reports.update(goalie_reports(data,games,now,cache.health.get(url,{}).get('observed_at')))
    raw={**raw,'data':list(raw.get('data',[]))+[r for payload in extra_data for r in payload.get('data',[])]}
    wanted={norm(g.get(s+'_name')) for g in games if instant(g.get('date')) and now<instant(g['date'])<now+timedelta(days=2) and g.get('state')=='pre' for s in ('home','away')}
    slugs={norm(r.get(s+'TeamName')):r.get(s+'TeamSlug') for r in raw.get('data',[]) for s in ('home','away') if r.get(s+'TeamSlug')}
    # Current goalie page advertises today's teams. Directory pages advertise all others.
    directory=cache.get('https://www.dailyfaceoff.com/teams',lambda x:embedded(x.decode()),24) or {}
    teams=directory.get('teams') or directory.get('sortedTeams') or []
    if isinstance(teams,list):slugs.update({norm(t.get('name')):t.get('slug') for t in teams if isinstance(t,dict) and t.get('slug')})
    lineups={}
    def get_line(pair):
        name,slug=pair;url='https://www.dailyfaceoff.com/teams/'+slug+'/line-combinations'
        data=cache.get(url,lambda x:embedded(x.decode()),2)
        return lineup(data,now,cache.health.get(url,{}).get('observed_at'))
    with ThreadPoolExecutor(max_workers=4) as pool:
        for item in pool.map(get_line,[(n,s) for n,s in slugs.items() if n in wanted]):
            if item:lineups[item['team']]=item
    # Team lineup pages themselves publish an all-team directory in their HTML.
    for record in list(cache.data.values()):
        payload=record.get('data')
        if isinstance(payload,dict):
            for t in payload.get('sortedTeams',[]):
                if isinstance(t,dict) and t.get('slug'):slugs.setdefault(norm(t.get('name')),t['slug'])
    remaining=[(n,s) for n,s in slugs.items() if n in wanted and not any(norm(v.get('name'))==n for v in lineups.values())]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for item in pool.map(get_line,remaining):
            if item:lineups[item['team']]=item
    advertised=cache.get(MP,lambda x:links(x.decode()),24) or []
    downloads=[]
    for y in (year,year-1):
        for kind in ('skaters','goalies','teams'):
            matches=[u for u in advertised if f'/seasonSummary/{y}/regular/{kind}.csv' in u]
            if len(matches)==1:downloads.append((y,kind,matches[0]))
    stats={}
    def get_csv(item):
        y,kind,url=item;rows=cache.get(url,csv_rows,6 if y==year else 7*24) or []
        at=cache.health.get(url,{}).get('observed_at')
        return str(y),kind,{'rows':rows if fresh(at,now,24 if y==year else 30*24) else [],'observed_at':at,'source_url':url}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for y,kind,value in pool.map(get_csv,downloads):stats.setdefault(y,{})[kind]=value
    results=[];result_at=None
    archives=[u for u in advertised if f'/seasonPlayersSummary/skaters/{year}.zip' in u]
    if len(archives)==1:
        rows=cache.get(archives[0],zip_results,6) or [];result_at=cache.health.get(archives[0],{}).get('observed_at')
        if fresh(result_at,now,24):results=rows
    out={'version':VERSION,'generated_at':now.isoformat(),'year':year,'goalies':reports,'lineups':lineups,'statistics':stats,'player_results':results,'results_observed_at':result_at,'sources':cache.health,
        'credit':'Shot quality, ice-time and goalie data: MoneyPuck.com. Lineup and starter reports: DailyFaceoff.com.',
        'usage':'Personal/non-commercial research. MoneyPuck commercial use requires permission. Only advertised downloads used; no API requests.',
        'validated':False,'mode':'Research; no automatic model promotion'}
    cache.save();return out

def values(rows,team,situation='all'):
    selected=[r for r in rows if code(r.get('team'))==code(team) and r.get('situation')==situation]
    return selected

def team_rates(data,team):
    years=data.get('statistics',{});year=data.get('year');parts=[]
    for y,w in ((year,1),(year-1,.4)):
        rows=values(years.get(str(y),{}).get('teams',{}).get('rows',[]),team)
        if len(rows)!=1:continue
        r=rows[0];gp=number(r.get('games_played'))
        if not gp or gp<=0 or any(number(r.get(k)) is None for k in ('flurryAdjustedxGoalsFor','flurryAdjustedxGoalsAgainst','shotsOnGoalFor','shotsOnGoalAgainst','goalsFor','goalsAgainst')):continue
        parts.append((r,w,gp))
    gp=sum(w*n for _,w,n in parts)
    if not gp:return None
    def rate(key):return sum((number(r.get(key)) or 0)*w for r,w,_ in parts)/gp
    return {'xgf':(rate('flurryAdjustedxGoalsFor')*gp+3.05*20)/(gp+20),'xga':(rate('flurryAdjustedxGoalsAgainst')*gp+3.05*20)/(gp+20),
        'gf':rate('goalsFor'),'ga':rate('goalsAgainst'),'shots_for':rate('shotsOnGoalFor'),'shots_against':rate('shotsOnGoalAgainst'),'weighted_games':gp}

def goalie_effect(data,team,goalie):
    if not goalie.get('confirmed'):return None
    parts=[]
    for y,w in ((data.get('year'),1),(data.get('year',0)-1,.4)):
        rows=[r for r in data.get('statistics',{}).get(str(y),{}).get('goalies',{}).get('rows',[]) if r.get('situation')=='all' and (y!=data.get('year') or code(r.get('team'))==code(team)) and norm(r.get('name'))==norm(goalie.get('name'))]
        if len(rows)==1:parts.append((rows[0],w))
    if len({r.get('playerId') for r,_ in parts})!=1:return None
    minutes=sum((number(r.get('icetime')) or 0)/60*w for r,w in parts)
    if minutes<=0:return None
    saved=sum(((number(r.get('xGoals')) or 0)-(number(r.get('goals')) or 0))*w for r,w in parts)
    return {'name':goalie['name'],'gsax_per60':max(-.4,min(.4,saved*60/(minutes+600))),'weighted_minutes':minutes}

def context(game,data):
    home,away=team_rates(data,game['home']),team_rates(data,game['away'])
    starters=data.get('goalies',{}).get(str(game['game_id']),{})
    out={'version':VERSION,'mode':'Research; unvalidated','observed_at':data.get('generated_at'),'goalies':starters,
        'lineups':{s:data.get('lineups',{}).get(code(game[s])) for s in ('home','away')},'team_rates':{'home':home,'away':away},'credit':data.get('credit')}
    if not home or not away:return out
    h=(home['xgf']+away['xga'])/2+.12;a=(away['xgf']+home['xga'])/2-.12
    effects={s:goalie_effect(data,game[s],starters.get(s,{}) or game.get(s+'_goalie',{})) for s in ('home','away')}
    if effects['away']:h-=effects['away']['gsax_per60']
    if effects['home']:a-=effects['home']['gsax_per60']
    if game.get('home_rest')==0:h-=.10;a+=.06
    if game.get('away_rest')==0:a-=.10;h+=.06
    h,a=max(1.7,min(4.6,h)),max(1.7,min(4.6,a))
    def forecast(hh,aa):
        grid=score_grid(hh,aa)
        return {'ratings_known':True,'home_goals':round(hh,4),'away_goals':round(aa,4),'mu':round(hh-aa,4),'p_home':round(sum(p for (h,a),p in grid.items() if h>a),6),'total':round(sum((h+a)*p for (h,a),p in grid.items()),4)}
    out.update(projection=forecast(h,a),goalie_effects=effects,
        goalie_scenarios=[{'label':'Opposing goalie weaker by 0.2 goal','home_goals':h+.2,'away_goals':a,'p_home':forecast(h+.2,a)['p_home']},
                         {'label':'Opposing goalie stronger by 0.2 goal','home_goals':max(1.7,h-.2),'away_goals':a,'p_home':forecast(max(1.7,h-.2),a)['p_home']}],
        scenario_note='Unweighted sensitivity, not probabilities of a starter playing. No double-counted baseline goalie adjustment.')
    return out


if __name__=='__main__':
    games=json.loads((ROOT/'site/data/games.json').read_text())
    data=refresh(games)
    (ROOT/'site/data/public-research.json').write_text(json.dumps(data,separators=(',',':'),allow_nan=False)+'\n')
    print('NHL public research:',len(data['goalies']),'goalie matchups,',len(data['lineups']),'lineups,',len(data['player_results']),'completed player rows')
