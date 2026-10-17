"""Dated Covers reports as partial context; never infer healthy teams or starters."""
import re
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from zoneinfo import ZoneInfo
import requests
URL='https://www.covers.com/sport/football/ncaaf/injuries'
ET=ZoneInfo('America/Toronto')
def key(value):return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',value or '').encode('ascii','ignore').decode().lower())
class Node:
    def __init__(self,tag='',attrs=()):self.tag=tag;self.attrs=dict(attrs);self.children=[]
    def text(self):return ' '.join(x.text() if isinstance(x,Node) else x for x in self.children).strip()
    def find(self,tag=None,cls=None):
        result=[]
        for x in self.children:
            if isinstance(x,Node):
                if (tag is None or x.tag==tag) and (cls is None or cls in x.attrs.get('class','').split()):result.append(x)
                result.extend(x.find(tag,cls))
        return result
class Tree(HTMLParser):
    def __init__(self):super().__init__();self.root=Node();self.stack=[self.root]
    def handle_starttag(self,tag,attrs):
        n=Node(tag,attrs);self.stack[-1].children.append(n)
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):self.stack.append(n)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:del self.stack[i:];break
    def handle_data(self,text):
        if self.stack[-1].tag not in ('script','style') and text.strip():self.stack[-1].children.append(text.strip())
def parse(html,teams,now,max_hours=72):
    tree=Tree();tree.feed(html);out={};rejected=0
    title=' '.join(n.text() for n in tree.root.find('title'))
    dated=re.search(r'Full Injury Report for ([A-Za-z]{3} \d{1,2}, \d{4})',title)
    try:page_day=datetime.strptime(dated[1],'%b %d, %Y').date() if dated else None
    except ValueError:page_day=None
    if not page_day or not 0<=(now.astimezone(ET).date()-page_day).days<=1:return {},{'status':'unavailable','reason':'Page date unavailable or stale','source_url':URL}
    identities={}
    for team in teams:
        identities.setdefault(key(team.get('name')),set()).add(str(team.get('id')))
    for section in tree.root.find('section'):
        names=section.find(cls='covers-CoversMatchups-teamName')
        if len(names)!=1:continue
        ids=identities.get(key(names[0].text()),set())
        if len(ids)!=1:continue
        tid=next(iter(ids))
        for row in section.find('tr'):
            cells=[c for c in row.children if isinstance(c,Node) and c.tag=='td']
            if len(cells)!=4:continue
            person=' '.join(cells[0].text().split());position=cells[1].text();status_nodes=cells[2].find('b')
            report=re.search(r'\(\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*([A-Za-z]{3})\s+(\d{1,2})\s*\)',cells[2].text())
            if not person or not position or len(status_nodes)!=1 or not report:rejected+=1;continue
            dates=[]
            for year in (page_day.year-1,page_day.year,page_day.year+1):
                try:
                    at=datetime.strptime(f'{year} {report[1]} {report[2]}','%Y %b %d').replace(tzinfo=ET).astimezone(timezone.utc)
                    # Date-only reports use the oldest instant on that date.
                    if 0<=(now-at).total_seconds()<=max_hours*3600:dates.append(at)
                except ValueError:pass
            if len(dates)!=1:rejected+=1;continue
            links=[n.attrs.get('href','')[1:] for n in cells[3].find('a') if n.attrs.get('href','').startswith('#injuryCollapse')]
            details=[n.text() for n in section.find('tr') if n.attrs.get('id') in links]
            at=dates[0];report={'athlete_id':'covers:'+tid+':'+key(person),'name':person,'name_abbreviated':True,'position':position,
                'status':status_nodes[0].text(),'reported_at':at.isoformat(),'reported_date':at.astimezone(ET).date().isoformat(),
                'report_time_precision':'date','detail':' '.join(details),'source':'Covers','source_url':URL}
            rows=out.setdefault(tid,[])
            if not any(r['athlete_id']==report['athlete_id'] for r in rows):rows.append(report)
    return out,{'status':'partial' if out else 'unavailable','current_reports':sum(map(len,out.values())),
        'teams_with_reports':len(out),'rejected_reports':rejected,'checked_at':now.isoformat(),'source_url':URL,'max_report_age_hours':max_hours}
def fetch(teams,now):
    response=requests.get(URL,headers={'User-Agent':'Mozilla/5.0 (compatible; KEVBOTBETS/1.0; public-context-reader)','Accept':'text/html'},timeout=18)
    response.raise_for_status()
    if len(response.content)>4_000_000:raise ValueError('Injury page exceeds limit')
    return parse(response.text,teams,now)
