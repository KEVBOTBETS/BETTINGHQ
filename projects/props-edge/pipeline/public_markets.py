"""Read advertised, public Covers game pages; exact event/roster contracts only."""
import re
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
from .http import ProviderError, response_text
from .providers.covers import _book, _player_aliases, _compact, _TokenParser
ET=ZoneInfo('America/Toronto')
CODES={'WIN':'WPG','TB':'TBL','UTAH':'UTA','CLB':'CBJ','NJ':'NJD','LA':'LAK','SJ':'SJS','NAS':'NSH','CAL':'CGY','MON':'MTL','VEG':'VGK','NY':'NYK','NO':'NOP','GS':'GSW','SA':'SAS','UTAH':'UTA','PHO':'PHX','WAS':'WSH','BK':'BKN'}
PATHS={'NBA':'basketball/nba','NHL':'hockey/nhl'}
class Node:
 def __init__(self,tag='',attrs=()):self.tag=tag;self.attrs=dict(attrs);self.children=[]
 def text(self):return ' '.join(x.text() if isinstance(x,Node) else x for x in self.children).strip()
 def find(self,tag=None,cls=None):
  out=[]
  for x in self.children:
   if isinstance(x,Node):
    if (tag is None or tag==x.tag) and (cls is None or cls in x.attrs.get('class','').split()):out.append(x)
    out.extend(x.find(tag,cls))
  return out
class Tree(HTMLParser):
 def __init__(self):super().__init__();self.root=Node();self.stack=[self.root]
 def handle_starttag(self,tag,attrs):
  n=Node(tag,attrs);self.stack[-1].children.append(n)
  if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):self.stack.append(n)
 def handle_endtag(self,tag):
  for i in range(len(self.stack)-1,0,-1):
   if self.stack[i].tag==tag:del self.stack[i:];break
 def handle_data(self,s):
  if self.stack[-1].tag not in ('script','style') and s.strip():self.stack[-1].children.append(s.strip())
def code(s):return CODES.get(s,s)
def person(s):return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
def tree(html):t=Tree();t.feed(html);return t.root

def advertised(html,sport):
 root=tree(html);out={}
 for a in root.find('a'):
  href=a.attrs.get('href','');m=re.fullmatch('/sport/'+PATHS[sport]+r'/matchup/\d+/(odds|picks)(?:#props)?',href)
  if m:out[urljoin('https://www.covers.com',href.split('#')[0])]=a.text()
 return out

def match_game(label,html,games,now):
 from .multisport import instant
 root=tree(html);title=' '.join(t.text() for t in root.find('title'));m=re.search(r'(?:For |for )([A-Za-z]+ \d{1,2}, \d{4})',title)
 if not m:return None
 try:day=datetime.strptime(m[1],'%B %d, %Y').date()
 except ValueError:return None
 pairing=re.search(r'\b([A-Z]{2,5})\s+(?:at|@)\s+([A-Z]{2,5})\s+(\d{1,2}:\d{2})\s+ET\b',label)
 if not pairing:return None
 matches=[g for g in games if (at:=instant(g.get('date'))) and at>now and at.astimezone(ET).date()==day and at.astimezone(ET).strftime('%H:%M')==pairing[3] and code(g['away'])==code(pairing[1]) and code(g['home'])==code(pairing[2])]
 return matches[0] if len(matches)==1 else None

def parse_game(html,game,rosters,sport,stamp,url):
 """Full-name roster match plus named-book comparison cells; never the mixed best-odds row."""
 root=tree(html);out={};markets={'Goals Scored':'Goals','Shots On Goal':'Shots on goal','Total Saves':'Saves','Assists':'Assists','Points':'Points','Points Scored':'Points','Rebounds':'Rebounds','Three Pointers Made':'Threes','3-Pointers Made':'Threes'}
 for article in root.find('article'):
  headers=article.find('header');heading=headers[0].text().replace('Collapse Card','').strip() if headers else ''
  market=markets.get(heading)
  if not market:continue
  # Each player container has its own direct player link and comparison table.
  for container in article.find('div'):
   names=[n.text() for n in container.children if isinstance(n,Node) and n.tag=='a' and '/players/' in n.attrs.get('href','')]
   if len(names)!=1:continue
   matches=[(team,a) for team in (game['away'],game['home']) for a in rosters.get(team,[]) if person(names[0])==person(a['player'])]
   tables=container.find('table','compareOddsTable')
   if len(matches)!=1 or len(tables)!=1:continue
   team,athlete=matches[0]
   for row in tables[0].find('tr'):
    logos=row.find('th','sportsbookLogoContainer');cells=row.find('td','compareOddsSide')
    if len(logos)!=1:continue
    books={_book(n.attrs.get('alt','')) for n in logos[0].find('img')};books.discard(None)
    if len(books)!=1:continue
    book=next(iter(books))
    for cell in cells:
     m=re.fullmatch(r'([ou])\s*(\d+(?:\.\d+)?)\s+([+\-−]\d{3,6})',cell.text(),re.I)
     if not m:continue
     side='over' if m[1].lower()=='o' else 'under';line=float(m[2]);price=int(m[3].replace('−','-'));qmarket=market
     if abs(price)<100:continue
     if sport=='NHL' and market=='Goals' and line==.5 and side=='over':qmarket='Anytime goal';line=None;side='yes'
     q={'sport':sport,'event_id':str(game['game_id']),'start_time':game['date'],'matchup':game['away']+' @ '+game['home'],'team':team,'player':athlete['player'],'athlete_id':athlete['id'],'market':qmarket,'side':side,'line':line,'price_american':price,'price_decimal':1+(price/100 if price>0 else 100/-price),'book':book,'price_source':'book','observed_at':stamp,'captured_at':stamp,'source_url':url,'model_prob':None,'actionable':False,'status':'Research · participation and book rules unconfirmed'}
     out[(q['event_id'],q['athlete_id'],qmarket,side,line,book)]=q
 return list(out.values())

def collect(html,games,rosters,sport,now,limit=16):
 from .multisport import parse_offers,instant
 wanted=advertised(html,sport);selected=[]
 for url,label in wanted.items():
  m=re.search(r'([A-Z]{2,5})\s+(?:at|@)\s+([A-Z]{2,5})',label)
  if m and any(code(g['away'])==code(m[1]) and code(g['home'])==code(m[2]) and instant(g['date']) and 0<(instant(g['date'])-now).total_seconds()<72*3600 for g in games):selected.append((url,label))
 health=[]
 def get(item):
  url,label=item;entry={'url':url,'status':'unavailable','offers':0}
  try:
   request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; KEVBOTBETS public market reader)','Accept':'text/html'})
   with urllib.request.urlopen(request,timeout=15) as response:body=response_text(response,4_000_000)
   if re.search(r'access denied|verify that you are human|captcha',body[:10000],re.I):raise ProviderError('Public source restricted')
   game=match_game(label,body,games,now)
   if not game:entry['status']='event mismatch';return [],entry
   rows=parse_game(body,game,rosters,sport,now.isoformat(),url)
   cards=_TokenParser();cards.feed(body)
   # Game-page cards omit the league-index matchup token; verified page identity supplies it.
   enriched=[[c[0],game['away']+' @ '+game['home'],*c[1:]] for c in cards.cards if c]
   rows+=parse_offers(enriched,[game],rosters,sport,now.isoformat())
   for q in rows:q['source_url']=url
   entry.update(status='ok' if rows else 'no player prices',offers=len(rows),event_id=str(game['game_id']),observed_at=now.isoformat())
   return rows,entry
  except (OSError,ValueError,ProviderError) as exc:entry['error']=type(exc).__name__;return [],entry
 with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(get,selected[:limit]))
 rows=[]
 for offers,entry in results:rows.extend(offers);health.append(entry)
 return rows,health
