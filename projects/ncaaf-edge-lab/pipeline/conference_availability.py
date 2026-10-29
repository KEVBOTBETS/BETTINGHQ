"""Dated conference-report mirrors with original report links and exact game matching.

The public mirror is an additional partial source, never an assertion that an
unlisted athlete is healthy. Unofficial notes and page-refresh dates are excluded.
"""
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import requests
from .public_availability import Tree,Node,key
URL='https://kickoffstatus.com/'
PT=ZoneInfo('America/Los_Angeles')
OFFICIAL={'bigten.org','secsports.com','theacc.com','admin.theacc.com','big12sports.com','sunbeltsports.org','theamerican.org','getsomemaction.com','mountainwest.com','conferenceusa.com','pac-12.com'}
def source_link(tree):
 return next((n.attrs['href'] for n in tree.root.find('a') if urlparse(n.attrs.get('href','')).hostname and urlparse(n.attrs['href']).hostname.removeprefix('www.') in OFFICIAL),'')
def matches(team,label):
 return key(team.get('short_name'))==key(label) or key(team.get('abbr'))==key(label) or str(team.get('name','')).lower()==label.lower() or str(team.get('name','')).lower().startswith(label.lower()+' ')
def advertised(html,games,now):
 from .game_context import instant
 tree=Tree();tree.feed(html);out=[]
 for a in tree.root.find('a'):
  href=a.attrs.get('href','');m=re.fullmatch(r'/games/(\d{4}-\d{2}-\d{2})-[a-z0-9-]+/',href)
  if not m or 'game' not in a.attrs.get('class','').split():continue
  labels=a.find(cls='nm');meta=a.find(cls='meta');stage=a.find(cls='stage')
  if len(labels)!=2 or not meta or not stage or 'pending' in stage[0].text().lower():continue
  clock=re.search(r'·\s*(\d{1,2}:\d{2}\s*[AP]M) PT',meta[0].text())
  if not clock:continue
  try:at=datetime.strptime(m[1]+' '+clock[1],'%Y-%m-%d %I:%M %p').replace(tzinfo=PT)
  except ValueError:continue
  away=labels[0].text().strip();home=labels[1].text().lstrip('@ ').strip()
  found=[g for g in games if instant(g.get('date_utc')) and instant(g['date_utc'])>now and abs((instant(g['date_utc'])-at).total_seconds())<=60 and matches(g['away'],away) and matches(g['home'],home)]
  if len(found)==1:out.append((URL.rstrip('/')+href,found[0],away,home))
 return out

def parse(html,game,away,home,url,now):
 from .game_context import instant
 tree=Tree();tree.feed(html);text=tree.root.text();link=source_link(tree)
 posted=re.search(r'Latest:\s*(Initial|Update|Game Day|Gameday|Final)\s+posted\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3}\s+\d{1,2},\s*\d{1,2}:\d{2}\s*[AP]M)\s+PT',text,re.I)
 if not posted or not link:return []
 start=instant(game.get('date_utc'));report_date=None
 for year in [start.year-1,start.year,start.year+1]:
  try:
   at=datetime.strptime(str(year)+' '+posted[2],'%Y %b %d, %I:%M %p').replace(tzinfo=PT)
   if 0<=(now-at).total_seconds()<=72*3600 and at<start:report_date=at
  except ValueError:pass
 if not report_date:return []
 groups=tree.root.find(cls='teams2')
 if len(groups)!=1:return []
 rows=[]
 for card in [n for n in groups[0].children if isinstance(n,Node)]:
  headings=card.find('h3') or card.find('h2');tables=card.find('table')
  if len(headings)!=1 or len(tables)!=1:continue
  links=headings[0].find('a');label=links[0].text() if len(links)==1 else ' '.join(c for c in headings[0].children if isinstance(c,str)).strip();side='away' if key(label)==key(away) else 'home' if key(label)==key(home) else None
  if side is None:continue
  tid=str(game[side]['id'])
  for row in tables[0].find('tr'):
   cells=[n for n in row.children if isinstance(n,Node) and n.tag=='td']
   if len(cells)!=3:continue
   name=re.sub(r'\s*#\d+\s*$','',cells[0].text()).strip();status=cells[2].text().strip()
   if not name or status.lower() not in ['available','probable','questionable','doubtful','out','game time decision','game-time decision']:continue
   rows.append((tid,{'athlete_id':'conference:'+tid+':'+key(name),'name':name,'position':cells[1].text(),'status':status,
    'reported_at':report_date.isoformat(),'report_stage':posted[1],'game_id':str(game['game_id']),'game_date':game['date_utc'],
    'source':'Kickoff Status conference-report mirror','source_url':url,'official_source_url':link,'detail':'Dated conference report mirrored by Kickoff Status. Verify the linked original; this is partial availability context.'}))
 return rows

def fetch(games,now):
 def read(url):
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (compatible; KEVBOTBETS public availability reader)'},timeout=15);r.raise_for_status()
  if len(r.content)>3_000_000:raise ValueError('Public report exceeds limit')
  return r.text
 html=read(URL);wanted=advertised(html,games,now)[:48]
 def get(item):
  url,g,away,home=item
  try:return parse(read(url),g,away,home,url,now)
  except (requests.RequestException,ValueError):return []
 out={}
 with ThreadPoolExecutor(max_workers=4) as pool:
  for rows in pool.map(get,wanted):
   for tid,row in rows:out.setdefault(tid,[]).append(row)
 return out,{'status':'partial' if out else 'unavailable','checked_at':now.isoformat(),'current_reports':sum(map(len,out.values())),'teams_with_reports':len(out),'game_pages_checked':len(wanted),'source_url':URL,'note':'Only dated report tables with original conference source links; unofficial notes excluded.'}
