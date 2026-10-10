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
from .model import instant, number

URL='https://www.covers.com/sport/hockey/nhl/odds'
TORONTO=ZoneInfo('America/Toronto')
CODES={'CLB':'CBJ','NAS':'NSH','MON':'MTL','CAL':'CGY','VEG':'VGK','UTAH':'UTA','WIN':'WPG','NJ':'NJD','SJ':'SJS','TB':'TBL','LA':'LAK'}
def code(v):return CODES.get(v,v)

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
    text=' '.join(text.replace('\xa0',' ').split())
    match=re.fullmatch(r'(Today|Tomorrow),?\s+(\d{1,2}):(\d{2})',text,re.I)
    if not match:return None
    day=now.astimezone(TORONTO).date()+timedelta(days=match[1].lower()=='tomorrow')
    try:return datetime(day.year,day.month,day.day,int(match[2]),int(match[3]),tzinfo=TORONTO)
    except ValueError:return None

def parse(html,games,now):
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
            team_nodes=row.find(cls='teams-div');times=row.find(cls='game-time')
            if len(team_nodes)!=1 or len(times)!=1:continue
            names={}
            for side in ('home','away'):
                cells=team_nodes[0].find(cls=side+'-cell')
                strong=cells[0].find('strong') if len(cells)==1 else []
                if len(strong)==1:names[side]=code(strong[0].text())
            start=start_time(times[0].text(),published)
            if not start or start<=now or len(names)!=2:continue
            matches=[g for g in games if g.get('state')=='pre' and all(code(g.get(s))==names[s] for s in names) and instant(g.get('date')) and abs((instant(g['date'])-start).total_seconds())<=60]
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
                        open_price=None,source='Covers public book comparison',source_url=URL,
                        source_price_changed_at=cell.attrs.get('data-date'))
                    result[(game['game_id'],market,q['side'],q['line'],book)]=(game['game_id'],q)
    return list(result.values())

VEGAS_URL='https://www.vegasinsider.com/nhl/odds/las-vegas/'
BOOK_NAMES={'Bet365':'bet365','BetMGM':'BetMGM','DraftKings':'DraftKings','Caesars':'Caesars Odds','FanDuel':'FanDuel','HardRock':'Hard Rock Bet','Fanatics':'Fanatics Sportsbook','RiversCasino':'BetRivers'}
def name(value):return unicodedata.normalize('NFKD',value or '').encode('ascii','ignore').decode().lower()

def parse_vegas(html,games,now):
    tree=Tree();tree.feed(html);result={}
    for table in tree.root.find('table'):
        heads=table.find('thead')
        if not heads:continue
        columns=heads[0].find('th','book-pinup')
        books=[BOOK_NAMES.get(n.text()) for n in columns]
        for body in table.find('tbody'):
            market={'odds-table-moneyline--0':'ML','odds-table-spread--0':'ATS','odds-table-total--0':'TOTAL'}.get(body.attrs.get('id'))
            if not market:continue
            start=None;pair=[]
            for row in body.find('tr'):
                times=[n for n in row.find('span') if n.attrs.get('data-role')=='localtime']
                if times:
                    start=instant(times[0].attrs.get('data-value'));pair=[];continue
                cells=[n for n in row.children if isinstance(n,Node) and n.tag=='td']
                if not cells or not cells[0].has('game-team') or not start or start<=now:continue
                images=cells[0].find('img');team=name(images[0].attrs.get('alt')) if images else ''
                pair.append((team,cells[1:]))
                if len(pair)!=2:continue
                matches=[g for g in games if g.get('state')=='pre' and instant(g.get('date'))==start and all(name(g.get(side+'_name'))==pair[i][0] for i,side in enumerate(('away','home')))]
                if len(matches)!=1:pair=[];continue
                g=matches[0]
                for col,book in enumerate(books):
                    if not book or any(col>=len(cells) for _,cells in pair):continue
                    values=[]
                    for i,(_,cells) in enumerate(pair):
                        cell=cells[col]
                        if market=='ML':
                            nodes=cell.find('span','data-moneyline');price=signed(nodes[0].text()) if len(nodes)==1 else None
                            side=('away','home')[i];line=None
                        else:
                            nodes=cell.find('span','data-value');anchors=cell.find('a')
                            if len(nodes)!=1 or len(anchors)!=1:break
                            prices=cell.find(cls='data-odds')
                            price=signed(prices[0].text()) if len(prices)==1 else None
                            value=nodes[0].text()
                            if market=='ATS':
                                if not re.fullmatch(r'[+-]\d+(?:\.\d+)?',value):break
                                side=('away','home')[i];line=float(value)
                            else:
                                m=re.fullmatch(r'([ou])(\d+(?:\.\d+)?)',value,re.I)
                                if not m:break
                                side='over' if m[1].lower()=='o' else 'under';line=float(m[2])
                        if price is None:break
                        values.append({'side':side,'line':line,'price':price})
                    if len(values)!=2:continue
                    if market=='ATS' and values[0]['line']!=-values[1]['line']:continue
                    if market=='TOTAL' and (values[0]['line']!=values[1]['line'] or {v['side'] for v in values}!={'over','under'}):continue
                    for i,q in enumerate(values):
                        q.update(market=market,book=book,opposite_price=values[1-i]['price'],observed_at=now.isoformat(),open_price=None,source='VegasInsider public book comparison',source_url=VEGAS_URL)
                        result[(g['game_id'],market,q['side'],q['line'],book)]=(g['game_id'],q)
                pair=[]
    return list(result.values())

def download(url):
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; KEVBOTBETS/1.0; public-market-reader)','Accept':'text/html'})
    with urllib.request.urlopen(request,timeout=20) as response:
        raw=response.read(6_000_001)
    if len(raw)>6_000_000:raise ValueError('Public odds page exceeds limit')
    html=raw.decode('utf-8',errors='replace')
    if re.search(r'access denied|verify that you are human|captcha',html[:10000],re.I):raise ValueError('Public odds access unavailable')
    return html

def fetch(games,now):
    for url,parser in ((URL,parse),(VEGAS_URL,parse_vegas)):
        try:
            rows=parser(download(url),games,now)
            if rows:return rows
        except (OSError,ValueError):continue
    return []
