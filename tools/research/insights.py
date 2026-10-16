"""Plain-language diagnostics. Observational research, never automatic model changes."""
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import hashlib,json
import numpy as np
from .common import read,write,instant,number,decimal
ROOT=__import__('pathlib').Path(__file__).resolve().parents[2]
CONTEXT=__import__('pathlib').Path('projects/bet-ledger-hq/data/research/availability-log.json')
ET=ZoneInfo('America/Toronto')
def first(rows,version=None):
 saved={}
 for r in sorted(rows,key=lambda r:r.get('captured_at','')):
  if version and r.get('version')!=version:continue
  if not instant(r.get('captured_at')) or not instant(r.get('start')) or instant(r['captured_at'])>=instant(r['start']):continue
  saved.setdefault((r['sport'],str(r.get('event_id',r.get('id')))),r)
 return list(saved.values())
def wilson(w,n):
 if not n:return None
 z=1.959964;p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;return [float(c-h),float(c+h)]
def stats(rows):
 graded=[r for r in rows if (r.get('result') or {}).get('status') in ('Win','Loss')];w=sum(r['result']['status']=='Win' for r in graded);n=len(graded)
 priced=[r for r in graded if decimal(r.get('price')) and number(r['result'].get('unit_profit')) is not None]
 profit=sum(r['result']['unit_profit'] for r in priced);pred=[max(r['p'],1-r['p']) for r in graded if number(r.get('p')) is not None]
 return {'calls':len(rows),'graded':n,'wins':w,'losses':n-w,'pending':sum(not r.get('result') for r in rows),'accuracy':w/n if n else None,'interval':wilson(w,n),'expected':sum(pred)/len(pred) if pred else None,'priced':len(priced),'profit':profit if priced else None,'roi':profit/len(priced) if priced else None,'sample_note':'Descriptive only; fewer than 30 graded calls.' if n<30 else 'Historical sample, not a future profit guarantee.'}
def price_group(r):
 p=number(r.get('price'))
 if not decimal(p):return 'No recorded odds'
 return 'Even money' if abs(p)==100 else 'Favourite' if p<0 else 'Underdog'
def price_band(r):
 p=number(r.get('price'))
 if not decimal(p):return 'No recorded odds'
 if abs(p)==100:return 'Even money'
 if p<=-200:return 'Favourites −200 or shorter'
 if p<0:return 'Favourites −101 to −199'
 if p<200:return 'Underdogs +101 to +199'
 return 'Underdogs +200 or longer'
def groups(rows,key):
 values=defaultdict(list)
 for r in rows:values[key(r)].append(r)
 return [{'label':k,**stats(v)} for k,v in sorted(values.items())]
def drift(rows):
 valid=[r for r in rows if (r.get('result') or {}).get('status') in ('Win','Loss') and number(r.get('p')) is not None and instant(r['result'].get('verified_at'))]
 if len({r.get('version') for r in valid})>1:return {'status':'Choose one model version','note':'Drift comparisons keep model versions separate.'}
 day=lambda r:instant(r['start']).astimezone(ET).date().isoformat()
 dates_available=sorted({day(r) for r in valid})[-20:]
 if len(dates_available)<20:return {'status':'Building the drift record','graded':len(valid),'needed':60,'dates_recorded':len(dates_available),'dates_needed':20,'note':'Needs 20 distinct game dates, split into 10 recent and 10 earlier dates, with at least 30 verified calls in each window.'}
 old=[r for r in valid if day(r) in dates_available[:10]];new=[r for r in valid if day(r) in dates_available[10:]];dates=[len({day(r) for r in part}) for part in (old,new)]
 if min(len(old),len(new))<30:return {'status':'Building the drift record','graded':len(old)+len(new),'needed':60,'note':'Each 10-date window needs at least 30 verified calls. Dates are kept whole so a large Saturday is not split into two tests.'}
 error=lambda r:(max(r['p'],1-r['p'])-int(r['result']['status']=='Win'))**2
 before=sum(map(error,old))/len(old);after=sum(map(error,new))/len(new);ci=None
 if min(dates)>=8:
  rng=np.random.default_rng(64);parts=[]
  for part in (old,new):
   buckets=defaultdict(list)
   for r in part:buckets[day(r)].append(error(r))
   a=list(buckets.values());sums=np.array([sum(x) for x in a]);sizes=np.array([len(x) for x in a]);idx=rng.integers(0,len(a),(1000,len(a)));parts.append(sums[idx].sum(axis=1)/sizes[idx].sum(axis=1))
  ci=[float(x) for x in np.quantile(parts[1]-parts[0],[.025,.975])]
 flag=after-before>=.02 and ci is not None and ci[0]>0
 return {'status':'Review recent errors' if flag else 'Watching recent errors','alert':flag,'graded':len(old)+len(new),'older_brier':before,'recent_brier':after,'change':after-before,'interval':ci,'dates':dates,'note':'Latest 10 game dates versus prior 10 dates of one version, at least 30 calls in each window. Lower probability error is better. An alert needs at least 8 dates per window, a ≥0.02 error increase and a positive date-bootstrap interval. Exploratory repeated monitoring; no causal conclusion or automatic model change.'}
def team_bias(performance,sport,version=None):
 rows=first([dict(r,event_id=r['id']) for r in performance if r['sport']==sport],version);teams=defaultdict(list)
 for r in rows:
  margin,actual=number(r.get('margin')),number(r.get('actual_margin'));names=r.get('matchup','').split(' @ ')
  if margin is None or actual is None or len(names)!=2:continue
  for team,residual in [(names[1],actual-margin),(names[0],margin-actual)]:teams[team].append(residual)
 return sorted([{'team':t,'games':len(v),'bias':sum(v)/len(v),'mae':sum(abs(x) for x in v)/len(v),'reading':('Underestimated' if sum(v)>0 else 'Overestimated' if sum(v)<0 else 'Balanced')+' in these recorded margins','enough':len(v)>=8} for t,v in teams.items()],key=lambda r:(not r['enough'],-abs(r['bias'])))[:24]
def context_category(sides):
 if not sides or any(s.get('missing_report') for s in sides):return 'Missing availability report'
 if any(s.get('role_status')=='uncertain' or s.get('questionable') for s in sides):return 'Uncertain starter or availability'
 if all(s.get('starter_confirmed') for s in sides):return 'Explicitly confirmed starters'
 return 'Expected starters · not confirmed'
def capture_context(root,research,now):
 state=read(root/CONTEXT,{'records':[]});saved={r['id']:r for r in state['records']}
 for g in research.get('games',[]):
  start=instant(g.get('start'));current=next((m for m in g.get('models',[]) if m.get('model')=='current'),None)
  if not start or start<=now or not current:continue
  at=instant(current.get('source_observed_at'))
  if not at or not 0<=(now-at).total_seconds()<=6*3600:continue
  sides=(g.get('availability') or {}).get('sides',[]);clean=[{k:s.get(k) for k in ['side','team','starter','starter_confirmed','role_status','missing_report','questionable','absent','offensive_line_flags','observed_at','source']} for s in sides]
  # Expected-depth-chart names never become confirmed merely by being saved.
  for s in clean:
   stamp=instant(s.get('observed_at'));s['starter_confirmed']=bool(s.get('starter_confirmed') is True and stamp and stamp<=now and s.get('source'))
  fingerprint=hashlib.sha256(json.dumps([g['sport'],g['event_id'],current['version'],[{k:v for k,v in s.items() if k!='observed_at'} for s in clean]],sort_keys=True).encode()).hexdigest()
  saved.setdefault(fingerprint,{'id':fingerprint,'sport':g['sport'],'event_id':str(g['event_id']),'version':current['version'],'matchup':g['matchup'],'start':g['start'],'captured_at':now.isoformat(),'source_at':current['source_observed_at'],'category':context_category(clean),'sides':clean})
 write(root/CONTEXT,{'schema':1,'records':list(saved.values())});return list(saved.values())
def availability_report(log,calls):
 index={(r['sport'],r['event_id'],r['version']):r for r in calls};buckets=defaultdict(list)
 for r in first(log):
  call=index.get((r['sport'],r['event_id'],r['version']))
  if call:buckets[r['category']].append(call)
 return [{'label':k,**stats(v)} for k,v in sorted(buckets.items())]
def weekly(calls,now):
 local=now.astimezone(ET);monday=(local-timedelta(days=local.weekday())).date();start=datetime.combine(monday,datetime.min.time(),ET);previous=start-timedelta(days=7)
 settled=lambda r:instant((r.get('result') or {}).get('verified_at'))
 this=[r for r in calls if settled(r) and start<=settled(r)<=now];last=[r for r in calls if settled(r) and previous<=settled(r)<start];pending=[r for r in calls if not r.get('result') and instant(r.get('start')) and start<=instant(r['start'])<start+timedelta(days=7)]
 a,b=stats(this),stats(last);lines=[f"This week: {a['wins']} correct and {a['losses']} incorrect winner calls with verified result times.",f"{len(pending)} saved calls in this calendar week are still awaiting a verified result."]
 if a['accuracy'] is not None and b['accuracy'] is not None:lines.append(f"Winner accuracy is {100*a['accuracy']:.1f}% versus {100*b['accuracy']:.1f}% last week. The games and prices differ, so this alone does not prove improvement.")
 else:lines.append('There are not enough dated results to compare both weeks yet.')
 lines.append(f"{a['priced']} settled calls this week have an original saved price; all others stay outside simulated returns.")
 return {'week_start':monday.isoformat(),'week_end':(monday+timedelta(days=6)).isoformat(),'current':a,'previous':b,'pending':len(pending),'lines':lines,'leagues':[{'sport':s,**stats([r for r in this if r['sport']==s])} for s in sorted({r['sport'] for r in calls})],'policy':'Monday–Sunday in Toronto time, using verified result-observation timestamps. Unknown result times are not assigned to a week. Cohort and opponent mix can change.'}
def build(root=ROOT,calls=None,performance=None,research=None,capture=False,now=None):
 now=now or datetime.now(timezone.utc);folder=root/'_site/bet-ledger-hq/data';calls=calls or read(folder/'moneyline-records.json',{});performance=performance or read(folder/'performance.json',{});research=research or read(folder/'research/report.json',{});rows=[]
 for original in calls.get('records',[]):
  r=dict(original);start=instant(r.get('start'));verified=instant((r.get('result') or {}).get('verified_at'))
  if r.get('result') and (not start or start>now or verified and not start<=verified<=now):r['result']=None
  rows.append(r)
 log=capture_context(root,research,now) if capture else read(root/CONTEXT,{'records':[]})['records'];sections=[]
 for sport in ['nfl','ncaaf','nhl','mlb','wnba']:
  sport_rows=[r for r in rows if r['sport']==sport];versions=sorted({r['version'] for r in sport_rows})
  for version in [None,*versions]:
   cohort=first(sport_rows,version)
   sections.append({'sport':sport,'version':version or 'all','summary':stats(cohort),'favourites':groups(cohort,price_group),'price_bands':groups(cohort,price_band),'recommendations':groups(cohort,lambda r:r.get('recommendation','Not recorded')),'drift':drift(cohort),'team_bias':team_bias([r for r in performance.get('records',[]) if instant(r.get('start')) and instant(r['start'])<=now and (not instant(r.get('result_at')) or instant(r['start'])<=instant(r['result_at'])<=now)],sport,version),'availability':availability_report([r for r in log if r['sport']==sport and (version is None or r['version']==version)],cohort),'weekly':weekly(cohort,now)})
 source=read(root/'projects/bet-ledger-hq/data/research/football-odds.json',{'leagues':{}})
 for report in source.get('leagues',{}).values():
  at=instant(report.get('checked_at'));report['fresh']=bool(at and 0<=(now-at).total_seconds()<=3*3600)
 return {'schema':1,'generated_at':now.isoformat(),'sections':sections,'source_checks':source,'availability_log':sorted(log,key=lambda r:r['captured_at'],reverse=True)[:120],'college':research.get('coverage',{}).get('ncaaf',{}),'policy':'One first pregame call per event in default views; recorded versions can be inspected separately. Price groups require original observed odds, never reconstructed prices. No automatic model promotion, betting, threshold relaxation or profit claim. Team bias is descriptive; availability groups are associations, not causal injury effects.'}
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--capture',action='store_true');a=p.parse_args();d=build(capture=a.capture);print({'insight_sections':len(d['sections']),'availability_snapshots':len(d['availability_log'])})
