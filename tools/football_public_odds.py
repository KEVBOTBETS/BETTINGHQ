"""Read visible full-game Covers tables; exact date/time/team and same-book pairing.

No private endpoints, login, API keys, consensus/openers passed off as book odds,
failed-source timestamp renewal, or guessed prices. Fail closed on changed markup.
"""
import re
import urllib.request
import unicodedata
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from zoneinfo import ZoneInfo
import json,math
from pathlib import Path
def instant(v):
    try:
        d=datetime.fromisoformat(str(v).replace('Z','+00:00'));return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError,TypeError):return None
def number(v):
    try:return float(v) if not isinstance(v,bool) and math.isfinite(float(v)) else None
    except (ValueError,TypeError):return None
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'projects/bet-ledger-hq/data/research/football-odds.json'
URLS={s:f'https://www.covers.com/sport/football/{s}/odds' for s in ('nfl','ncaaf')}



TORONTO=ZoneInfo('America/Toronto')
def code(v,sport):
    v=re.sub(r'[^A-Z0-9]','',str(v or '').upper())
    aliases={'JAC':'JAX','WSH':'WAS','LA':'LAR'} if sport=='nfl' else {'TAMU':'TAM','TULANE':'TULN','UTSA':'UTSA'}
    return aliases.get(v,v)
def game_team(g,side,sport):
    t=g.get(side);return code(t.get('abbr') if isinstance(t,dict) else t,sport)

class Node:
    def __init__(self,tag='',attrs=()):self.tag=tag;self.attrs=dict(attrs);self.children=[]
    def has(self,cls):return cls in self.attrs.get('class','').split()
    def text(self):return ' '.join(x.text() if isinstance(x,Node) else x for x in self.children).strip()
    def find(self,tag=None,cls=None):
        result=[]
        for x in self.children:
            if not isinstance(x,Node):continue
            if (tag is None or x.tag==tag) and (cls is None or x.has(cls)):result.append(x)
            result.extend(x.find(tag,cls))
        return result

class Tree(HTMLParser):
    def __init__(self):super().__init__();self.root=Node();self.stack=[self.root]
    def handle_starttag(self,tag,attrs):
        n=Node(tag,attrs);self.stack[-1].children.append(n)
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):self.stack.append(n)
    def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs);self.handle_endtag(tag)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:del self.stack[i:];break
    def handle_data(self,text):
        if self.stack[-1].tag not in ('script','style') and text.strip():self.stack[-1].children.append(text.strip())

def signed(value):
    s=value.strip().replace('−','-')
    if s.lower() in ('even','evens'):return 100
    return float(s) if re.fullmatch(r'[+-]\d{3,6}',s) and abs(float(s))>=100 else None

def start_time(text,now):
    text=' '.join(text.replace('\xa0',' ').split());m=re.fullmatch(r'(Today|Tomorrow),?\s+(\d{1,2}):(\d{2})',text,re.I)
    if m:day=now.astimezone(TORONTO).date()+timedelta(days=m[1].lower()=='tomorrow');hour,minute=int(m[2]),int(m[3])
    else:
        m=re.fullmatch(r'([A-Za-z]{3}) (\d{1,2}),?\s+(\d{1,2}):(\d{2})',text)
        if not m:return None
        choices=[]
        for year in (now.year-1,now.year,now.year+1):
            try:choices.append(datetime.strptime(f'{year} {m[1]} {m[2]}','%Y %b %d').date())
            except ValueError:pass
        if not choices:return None
        day=min(choices,key=lambda d:abs((d-now.astimezone(TORONTO).date()).days));hour,minute=int(m[3]),int(m[4])
        if abs((day-now.astimezone(TORONTO).date()).days)>30:return None
    try:return datetime(day.year,day.month,day.day,hour,minute,tzinfo=TORONTO)
    except ValueError:return None

def parse(html,games,now,sport):
    tree=Tree();tree.feed(html);result={}
    stamp=re.search(r'Last updated\s+([A-Za-z]{3} \d{1,2}, \d{4}, \d{1,2}:\d{2} [AP]M) ET',tree.root.text())
    if not stamp:return []
    try:published=datetime.strptime(stamp[1],'%b %d, %Y, %I:%M %p').replace(tzinfo=TORONTO).astimezone(timezone.utc)
    except ValueError:return []
    if not 0<=(now-published).total_seconds()<=90*60:return []
    for table in tree.root.find('table'):
        market={'moneyline-table':'ML','spread-table':'ATS','total-table':'TOTAL'}.get(table.attrs.get('id'))
        if not market:continue
        for row in table.find('tr','oddsGameRow'):
            if 'display: none' in row.attrs.get('style',''):continue
            team_nodes=row.find(cls='teams-div');times=row.find(cls='game-time')
            if len(team_nodes)!=1 or len(times)!=1:continue
            names={}
            for side in ('home','away'):
                cells=team_nodes[0].find(cls=side+'-cell')
                strong=cells[0].find('strong') if len(cells)==1 else []
                if len(strong)==1:names[side]=code(strong[0].text(),sport)
            start=start_time(times[0].text(),published)
            if not start or start<=now or len(names)!=2:continue
            matches=[g for g in games if not g.get('completed') and not g.get('postponed') and not g.get('canceled') and g.get('state')!='in' and all(game_team(g,s,sport)==names[s] for s in names) and instant(g.get('date_utc') or g.get('date')) and abs((instant(g.get('date_utc') or g.get('date'))-start).total_seconds())<=60]
            if len(matches)!=1:continue
            game=matches[0]
            for cell in row.find('td','liveOddsCell'):
                book=cell.attrs.get('data-book','').strip()
                if not book or book.lower() in ('consensus','open','opening'):continue
                values=[]
                for side in ('away','home'):
                    sides=cell.find(cls=side+'-cell')
                    anchors=sides[0].find('a','odds-cta') if len(sides)==1 else []
                    if len(anchors)!=1:break
                    anchor=anchors[0];prices=anchor.find('span','__american')
                    price=signed(prices[0].text()) if len(prices)==1 else None
                    if price is None:break
                    direct=' '.join(c for c in anchor.children if isinstance(c,str)).strip().replace('−','-')
                    if market=='ML':line=None;out_side=side
                    elif market=='ATS':
                        if not re.fullmatch(r'[+-]\d+(?:\.\d+)?',direct):break
                        line=float(direct);out_side=side
                    else:
                        m=re.fullmatch(r'([ou])\s+(\d+(?:\.\d+)?)',direct,re.I)
                        if not m or float(m[2])<=0:break
                        line=float(m[2]);out_side='over' if m[1].lower()=='o' else 'under'
                    values.append({'side':out_side,'line':line,'price':price})
                if len(values)!=2:continue
                if market=='ATS' and values[0]['line']!=-values[1]['line']:continue
                if market=='TOTAL' and (values[0]['line']!=values[1]['line'] or {v['side'] for v in values}!={'over','under'}):continue
                for i,q in enumerate(values):
                    q.update(market=market,book=book,opposite_price=values[1-i]['price'],observed_at=published.isoformat(),captured_at=now.isoformat(),
                        open_price=None,source='Covers public book comparison',source_url=URLS[sport],
                        source_price_changed_at=cell.attrs.get('data-date'))
                    result[(game['game_id'],market,q['side'],q['line'],book)]=(game['game_id'],q)
    return list(result.values())


def markets(q):
    out=[]
    for m,line,fields in [('ML',None,['ml_home','ml_away']),('ATS','spread_home',['spread_price_home','spread_price_away']),('TOTAL','total',['over_price','under_price'])]:
        if (line is None or number(q.get(line)) is not None) and all(number(q.get(k)) is not None and abs(float(q[k]))>=100 for k in fields):out.append(m)
    return set(out)

def bundles(rows):
    pairs={}
    for gid,q in rows:pairs.setdefault((str(gid),q['book'],q['observed_at'],q['market']),[]).append(q)
    out={}
    for (gid,book,stamp,m),quotes in pairs.items():
        expected={'home','away'} if m!='TOTAL' else {'over','under'}
        if len(quotes)!=2 or {q['side'] for q in quotes}!=expected:continue
        by={q['side']:q for q in quotes};r=out.setdefault((gid,book,stamp),{'book':book,'observed_at':stamp,'source':'Covers public book comparison','source_url':quotes[0]['source_url'],'keyless':True,'verified_markets':[]})
        if m=='ML':r.update(ml_home=by['home']['price'],ml_away=by['away']['price'])
        elif m=='ATS':r.update(spread_home=by['home']['line'],spread_price_home=by['home']['price'],spread_price_away=by['away']['price'])
        else:r.update(total=by['over']['line'],over_price=by['over']['price'],under_price=by['under']['price'])
        r['verified_markets'].append(m);r['priced_markets']=r['verified_markets'][:]
    return [(gid,q) for (gid,_,_),q in out.items()]

def book_key(v):return re.sub(r'[^a-z0-9]','',str(v or '').lower())
def fresh(q,now):
    at=instant(q.get('observed_at'));return bool(at and 0<=(now-at).total_seconds()<=3*3600 and markets(q) and book_key(q.get('book')) not in ('','unknown','espn','consensus'))
def probability(v):return 100/(float(v)+100) if float(v)>0 else -float(v)/(-float(v)+100)
def agreement(primary,other,now):
    if not fresh(primary,now) or not fresh(other,now):return []
    if abs((instant(primary['observed_at'])-instant(other['observed_at'])).total_seconds())>90*60:return []
    same=book_key(primary.get('book'))==book_key(other.get('book'));rows=[]
    for m,line,fields in [('ML',None,['ml_home','ml_away']),('ATS','spread_home',['spread_price_home','spread_price_away']),('TOTAL','total',['over_price','under_price'])]:
        if m not in markets(primary)&markets(other):continue
        if line and number(primary.get(line))!=number(other.get(line)):
            rows.append({'market':m,'same_book':same,'status':'Different line','primary_line':primary.get(line),'comparison_line':other.get(line)});continue
        delta=max(abs(probability(primary[k])-probability(other[k])) for k in fields)
        rows.append({'market':m,'same_book':same,'status':'Price disagreement' if delta>=.03 else 'Prices close','max_implied_gap':delta,'independent_books':1 if same else 2,'note':'Different displays of the same sportsbook are not independent books.' if same else 'Different sportsbooks; shared upstream origin may still be unknown.'})
    return rows

def download(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; KEVBOTBETS/1.0; public-market-reader)','Accept':'text/html'}),timeout=25) as r:blob=r.read(12000001)
    if len(blob)>12000000:raise ValueError('Page exceeds size limit')
    html=blob.decode('utf-8',errors='replace')
    if re.search(r'access denied|verify that you are human|captcha',html[:10000],re.I):raise ValueError('Public source unavailable')
    return html

def enrich(games,sport,now=None,html=None,publish=True):
    now=now or datetime.now(timezone.utc);status='Read public page';error=None
    try:offers=bundles(parse(html if html is not None else download(URLS[sport]),games,now,sport))
    except (OSError,ValueError) as exc:offers=[];status='Source unavailable';error=type(exc).__name__
    by={};repairs=0;checks=[]
    for gid,q in offers:by.setdefault(gid,[]).append(q)
    for g in games:
        options=by.get(str(g.get('game_id')),[]);primary=g.get('odds') or {};start=instant(g.get('date_utc') or g.get('date'))
        if not start or start<=now or g.get('completed') or g.get('canceled') or g.get('postponed') or g.get('state')=='in':continue
        for q in options:
            for row in agreement(primary,q,now):checks.append({'game_id':str(g['game_id']),'matchup':str(g.get('away_name') or game_team(g,'away',sport))+' @ '+str(g.get('home_name') or game_team(g,'home',sport)),'primary_book':primary.get('book'),'comparison_book':q['book'],'primary_source':primary.get('source','ESPN provider feed'),'comparison_source':q['source'],'primary_observed_at':primary.get('observed_at'),'comparison_observed_at':q['observed_at'],**row})
        existing=markets(primary) if fresh(primary,now) else set()
        # Never splice books, timestamps or contracts. A replacement must retain
        # every already-priced market and add coverage, or replace a stale quote.
        eligible=[q for q in options if fresh(q,now) and (not existing or existing<markets(q))]
        if not eligible:continue
        pick=sorted(eligible,key=lambda q:(-len(markets(q)),book_key(q['book'])!=book_key(primary.get('book')),book_key(q['book'])!='draftkings',book_key(q['book'])))[0]
        g['odds']=dict(pick);g['odds_quotes']=[dict(pick)];repairs+=1
    result={'sport':sport,'checked_at':now.isoformat(),'source_url':URLS[sport],'status':status if offers else status+' · no eligible paired quotes','error':error,'paired_book_games':len(offers),'repaired_games':repairs,'checks':checks[:500],'policy':'Exact kickoff within one minute and both team codes; complete opposite prices at one book. Original page publication time is preserved. No merging books or renewing old quote timestamps. Displays sharing a sportsbook are one book, not independent votes.'}
    if publish:
        old=json.loads(REPORT.read_text()) if REPORT.exists() else {'schema':1,'leagues':{}}
        old['leagues'][sport]=result;REPORT.parent.mkdir(parents=True,exist_ok=True);tmp=REPORT.with_suffix('.tmp');tmp.write_text(json.dumps(old,separators=(',',':'))+'\n');tmp.replace(REPORT)
    return result
