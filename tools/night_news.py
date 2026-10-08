"""Keyless, team-specific news for scheduled NFL evening games.

Each team collection is independent; failures keep the original receipt time.
News is context, never a model coefficient or a claim of confirmed availability.
"""
import concurrent.futures
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ROOT=Path(__file__).resolve().parents[1]
EASTERN=ZoneInfo('America/Toronto')

def instant(value):
    try:
        at=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return at.astimezone(timezone.utc) if at.tzinfo else None
    except (ValueError,TypeError):return None

def eligible(g,now):
    at=instant(g.get('date'))
    if not at or g.get('canceled') or g.get('postponed'):return False
    local=at.astimezone(EASTERN)
    return local.weekday() in [0,3,6] and local.hour>=18 and now-timedelta(hours=12)<=at<=now+timedelta(days=14)

def articles_for(team_id,now):
    if not str(team_id).isdigit():raise ValueError('Invalid team ID')
    url=f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?team={team_id}&limit=8'
    response=requests.get(url,timeout=12,headers={'User-Agent':'BETTINGHQ-night-football/1.0'})
    response.raise_for_status();data=response.json()
    if not isinstance(data.get('articles'),list):raise ValueError('Invalid news response')
    articles=[]
    for row in data['articles']:
        at=instant(row.get('published'));link=(row.get('links',{}).get('web') or {}).get('href')
        if not at or not now-timedelta(days=7)<=at<=now or not isinstance(link,str) or not link.startswith('https://') or not row.get('headline'):continue
        articles.append({'headline':row['headline'],'published':at.isoformat(),'url':link,'observed_at':now.isoformat(),'team_id':str(team_id),'source':'ESPN team news'})
    return {'articles':articles,'observed_at':now.isoformat(),'source_url':url}

def collect(root=ROOT,now=None):
    now=now or datetime.now(timezone.utc);path=root/'projects/bet-ledger-hq/data/newsletters/nights.json'
    old=json.loads(path.read_text()) if path.exists() else {};events=dict(old.get('events',{}));teams=dict(old.get('teams',{}));errors=[]
    source=root/'projects/nfl-edge-lab/site/data/games_detail.json'
    games=json.loads(source.read_text()) if source.exists() else []
    selected=[g for g in games if eligible(g,now)]
    ids=sorted({str(g[s]['id']) for g in selected for s in ['home','away'] if isinstance(g.get(s),dict) and str(g[s].get('id','')).isdigit()})
    def fetch(team_id):
        try:return team_id,articles_for(team_id,now),None
        except (requests.RequestException,ValueError,TypeError):return team_id,None,'Team news unavailable; prior snapshot retained'
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for team_id,data,error in pool.map(fetch,ids):
            if error:errors.append({'team_id':team_id,'error':error})
            else:teams[team_id]=data
    for g in selected:
        rows=[];seen=set()
        for side in ['home','away']:
            value=g.get(side);team_id=str(value.get('id','')) if isinstance(value,dict) else ''
            for article in teams.get(team_id,{}).get('articles',[]):
                if article['url'] not in seen:seen.add(article['url']);rows.append(article)
        if rows or all(str((g.get(s) or {}).get('id','')) in teams for s in ['home','away']):
            events[str(g['game_id'])]={'date':g['date'],'articles':rows,'team_ids':[str((g.get(s) or {}).get('id','')) for s in ['home','away']]}
    # Bound the cache by event date; never re-stamp a retained article.
    events={key:value for key,value in events.items() if instant(value.get('date')) and instant(value['date'])>=now-timedelta(days=14)}
    result={'schema':1,'checked_at':now.isoformat(),'events':events,'teams':teams,'errors':errors,'policy':'Published team-news context. Original article and collection timestamps retained; no inferred injury confirmation.'}
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(result,separators=(',',':'))+'\n');temp.replace(path)
    return result

if __name__=='__main__':
    result=collect();print({'night_games':len(result['events']),'news_errors':len(result['errors'])})
