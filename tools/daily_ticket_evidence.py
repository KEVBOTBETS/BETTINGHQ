"""Small, prospective-only performance summary for daily ticket planning.

Forecast hit rates are not wager ROI. Only original pregame prices can supply
simulated returns; seasons and model versions stay separate.
"""
from collections import defaultdict
from datetime import datetime, timezone
import math
from zoneinfo import ZoneInfo

def number(v):
 try:return float(v) if v is not None and not isinstance(v,bool) and math.isfinite(float(v)) else None
 except (ValueError,TypeError):return None
def instant(v):
 try:
  t=datetime.fromisoformat(str(v).replace('Z','+00:00'));return t if t.tzinfo else None
 except ValueError:return None
def decimal(p):
 p=number(p);return 1+(p/100 if p>0 else 100/-p) if p is not None and abs(p)>=100 else None
def build(performance,moneyline,spreads,now=None):
 now=now or datetime.now(timezone.utc);samples={};seasons={}
 def add(r,market,status,price=None,quote=None):
  start,capture=instant(r.get('start')),instant(r.get('captured_at'));settled=instant(r.get('result_at') or (r.get('result') or {}).get('verified_at'))
  if not start or not capture or not capture<start<=now or not settled or not start<=settled<=now or status not in ('Win','Loss','Push'):return
  sport=r.get('sport');event=str(r.get('event_id',r.get('id')));version=r.get('version') or 'unversioned';season=r.get('season') or seasons.get((sport,event,version))
  if not season:return
  key=(sport,event,version,season,market);d=decimal(price);qt=instant(quote)
  # No postgame prices, no historical quote backfills, no double-counted sides.
  priced=bool(d and qt and qt<=capture and qt<start and (capture-qt).total_seconds()<=5400)
  old=samples.get(key)
  row=dict(sport=sport,version=version,season=season,market=market,status=status,price=price if priced else None,decimal=d if priced else None,start=start,captured=capture)
  if not old or priced and old['decimal'] is None or capture<old['captured'] and not(old['decimal'] and not priced):samples[key]=row
 for r in performance.get('records',[]):
  sport=r.get('sport');event=str(r.get('id'));version=r.get('version') or 'unversioned';seasons[(sport,event,version)]=r.get('season')
  p,y=number(r.get('p')),r.get('y')
  if p is not None and p!=.5 and y in (0,1):add(r,'ML','Win' if (p>.5)==(y==1) else 'Loss')
  for market,forecast,line,actual in [('ATS',r.get('margin'),r.get('market_margin'),r.get('actual_margin')),('TOTAL',r.get('total'),r.get('market_total'),r.get('actual_total'))]:
   f,l,a=number(forecast),number(line),number(actual)
   if None in (f,l,a) or f==l:continue
   outcome=(1 if f>l else -1)*(a-l);add(r,market,'Win' if outcome>0 else 'Loss' if outcome<0 else 'Push')
 for r in moneyline.get('records',[]):add(r,'ML',(r.get('result') or {}).get('status'),r.get('price'),r.get('quote_at'))
 for r in spreads.get('records',[]):
  if r.get('cohort') not in ('prediction','recommended'):continue
  add(r,'ATS',r.get('status'),r.get('price'),r.get('line_observed_at'))
 groups=defaultdict(list)
 for r in samples.values():groups[(r['sport'],r['market'],r['version'],r['season'])].append(r)
 def metrics(rows):
  w=sum(r['status']=='Win' for r in rows);loss=sum(r['status']=='Loss' for r in rows);n=w+loss;priced=[r for r in rows if r['decimal'] is not None];profit=sum((r['decimal']-1 if r['status']=='Win' else -1 if r['status']=='Loss' else 0) for r in priced)
  low=None
  if n:
   z=1.96;p=w/n;low=(p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)
  return dict(wins=w,losses=loss,pushes=len(rows)-n,n=n,accuracy=w/n if n else None,lower=low,priced=len(priced),unit_profit=profit if priced else None,roi=profit/len(priced) if priced else None,dates=len({r['start'].astimezone(ZoneInfo('America/Toronto')).date() for r in rows}))
 rows=[]
 for (sport,market,version,season),values in sorted(groups.items()):
  preferred=[r for r in values if r['decimal'] is not None and 1+100/150<=r['decimal']<=3]
  rows.append(dict(sport=sport,market=market,version=version,season=season,all=metrics(values),preferred=metrics(preferred)))
 return dict(schema=1,generated_at=now.isoformat(),cohorts=rows,policy='First pregame forecasts; one outcome per event, market, season and model version. ROI is simulated at original recorded prices, not actual wager returns. Preferred-price samples use -150 through +200. Missing prices cannot establish profitability. No automatic model promotion.')
