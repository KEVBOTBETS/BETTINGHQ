"""Keyless football diagnostics and forward-only public shadow parlay tracking."""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
try:
 from .research.build import read_archive
 from .research.common import read,write,instant,number,decimal
 from .validation import report as validation
except ImportError:
 from research.build import read_archive
 from research.common import read,write,instant,number,decimal
 from validation import report as validation
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=Path('projects/bet-ledger-hq/data/research/college-parlays.json')

def diagnostics(archive,now):
 errors=defaultdict(dict)
 for r in sorted(archive.get('forecasts',[]),key=lambda r:r.get('captured_at','')):
  capture,start,verified=instant(r.get('captured_at')),instant(r.get('start')),instant(r.get('result_observed_at'))
  source_at=instant(r.get('source_observed_at'));margin=number(r.get('margin'));actual=number((r.get('result') or {}).get('margin'))
  if r.get('sport') not in ('nfl','ncaaf') or r.get('model')!='current' or r.get('cohort')!='regular season' or not capture or not start or not verified or not source_at or not source_at<=capture<start<=verified<=now or margin is None or actual is None:continue
  errors[r['sport'],r.get('version','unknown')].setdefault(str(r['event_id']),{**r,'residual':actual-margin})
 bands=[]
 for (sport,version),by_event in errors.items():
  rows=sorted(by_event.values(),key=lambda r:r['start'])[-50:];values=[r['residual'] for r in rows]
  bands.append({'sport':sport,'version':version,'n':len(rows),'dates':len({r['start'][:10] for r in rows}),'mae':sum(abs(x) for x in values)/len(values),'bias':sum(values)/len(values),'residual_90':[float(v) for v in np.quantile(values,[.05,.95])] if len(values)>=20 else None,'label':'Last 50 frozen regular-season forecasts per recorded baseline version; descriptive historical residuals, not a validated prediction interval.'})
 # Reuse the production validity checks. Retain all captures for each of the last
 # 50 observed events so a late alternate line cannot replace its original vote.
 grouped=defaultdict(list)
 for r in archive.get('market_forecasts',[]):
  if r.get('sport') not in ('nfl','ncaaf') or r.get('market') not in ('ML','ATS','TOTAL'):continue
  at=instant((r.get('result') or {}).get('observed_at'))
  if at and at<=now:grouped[r['sport'],r['market'],r.get('baseline_version')].append(r)
 recent=[]
 for rows in grouped.values():
  events=[]
  for r in sorted(rows,key=lambda r:r.get('start',''),reverse=True):
   if r['event_id'] not in events:events.append(r['event_id'])
  keep=set(events[:50]);recent.extend(r for r in rows if r['event_id'] in keep)
 report=validation(recent,now)
 return {'margin_errors':bands,'recent_markets':report['markets'],'recent_policy':'Up to 50 most recent events per sport, market and source version, then the same strict pregame-capture validation as the Performance Center. Small samples are descriptive; no model promotion or qualification changes.'}

def leg_outcome(q,g):
 h,a=number(g.get('home_score')),number(g.get('away_score'))
 if h is None or a is None or h<0 or a<0:return None
 if q['market']=='ML':v=(h-a)*(1 if q['side']=='home' else -1)
 elif q['market']=='ATS':v=(h-a)*(1 if q['side']=='home' else -1)+q['line']
 elif q['market']=='TOTAL':v=(h+a-q['line'])*(1 if q['side']=='over' else -1)
 else:return None
 return 'Push' if abs(v)<1e-8 else 'Win' if v>0 else 'Loss'

def settle(records,results,observed_at,now):
 out=[]
 for original in records:
  r=dict(original)
  if r.get('result'):out.append(r);continue
  at=instant(observed_at);graded=[]
  for q in r['legs']:
   g=results.get(str(q['event_id']));start=instant(q['start'])
   capture=instant(r.get('captured_at'));quote=instant(q.get('observed_at'))
   if not g or not g.get('completed') or g.get('canceled') or g.get('postponed') or instant(g.get('date'))!=start or not at or not start or not capture or not quote or not quote<=capture<start<=at<=now:break
   result=leg_outcome(q,g)
   if not result:break
   graded.append({'game':q['game'],'pick':q['pick'],'status':result,'home_score':g['home_score'],'away_score':g['away_score']})
  if len(graded)==len(r['legs']):
   statuses=[x['status'] for x in graded];status='Loss' if 'Loss' in statuses else 'Win' if all(s=='Win' for s in statuses) else 'Push-reduced' if 'Win' in statuses else 'All push'
   r['result']={'status':status,'full_win':all(s=='Win' for s in statuses),'observed_at':observed_at,'legs':graded}
  out.append(r)
 return out

def freeze(records,tickets,now):
 saved={r['id']:r for r in records}
 for t in tickets:
  day=t.get('day');legs=t.get('legs',[]);books={str(q.get('book','')).lower() for q in legs};games={q.get('game') for q in legs}
  if not day or day=='all' or not 2<=len(legs)<=8 or len(games)!=len(legs) or len(books)!=1 or not all(instant(q.get('observed_at')) and instant(q.get('publication_at')) and instant(q.get('start')) and instant(q['observed_at'])<=now<instant(q['start']) and instant(q['publication_at'])<=now and (now-instant(q['observed_at'])).total_seconds()<=3*3600 and (now-instant(q['publication_at'])).total_seconds()<=6*3600 and decimal(q.get('price')) and number(q.get('probability')) is not None and 0<q['probability']<1 for q in legs):continue
  versions=sorted({q.get('model_version','unversioned') for q in legs});key=json.dumps([day,t['target'],t['book'].lower(),t['version'],versions],sort_keys=True)
  identity=hashlib.sha256(key.encode()).hexdigest()
  if identity not in saved:saved[identity]={**t,'id':identity,'captured_at':now.isoformat(),'result':None,'mode':'Automatic first daily shadow scenario; not an accepted wager'}
 return list(saved.values())

def summary(records):
 rows=[]
 for target in [500,1000,2000,10000]:
  cohort=[r for r in records if r['target']==target];graded=[r for r in cohort if r.get('result')];n=len(graded)
  rows.append({'target':target,'captured':len(cohort),'graded':n,'pending':len(cohort)-n,'dates':len({r['day'] for r in graded}),'wins':sum(r['result']['full_win'] for r in graded),'full_win_rate':sum(r['result']['full_win'] for r in graded)/n if n else None,'predicted':sum(r['metrics']['base']['all_win'] for r in graded)/n if n else None,'brier':sum((r['metrics']['base']['all_win']-r['result']['full_win'])**2 for r in graded)/n if n else None})
 return rows

def build(root=ROOT,system=None,capture=False,now=None,archive=None):
 now=now or datetime.now(timezone.utc);state=read(root/ARCHIVE,{'records':[]});records=state['records'];folder=root/'projects/ncaaf-edge-lab/site/data';games=read(folder/'games.json',[]);meta=read(folder/'meta.json',{})
 if capture:
  records=settle(records,{str(g['game_id']):g for g in games},meta.get('generated_at'),now)
  if system:
   result=subprocess.run(['node','projects/bet-ledger-hq/scripts/game-parlays-snapshot.mjs'],cwd=root,input=json.dumps({'games':system.get('games',[]),'now':now.isoformat()}),text=True,capture_output=True,check=True,timeout=120)
   records=freeze(records,json.loads(result.stdout),now)
  write(root/ARCHIVE,{'schema':1,'generated_at':now.isoformat(),'records':records})
 return {'schema':1,'generated_at':now.isoformat(),**diagnostics(archive if archive is not None else read_archive(root),now),'profiles':summary(records),'records':sorted(records,key=lambda r:r['captured_at'],reverse=True)[:100],'tracking_policy':'First available same-day, single-book spread/total research scenario per target, book and recorded version. Captures never change. Verified final scores only; postponements remain pending. Targets overlap games and are not independent trials. Full payout calibration includes pushes as non-full wins. No real-wager ROI, automatic betting or model promotion.'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--capture',action='store_true');args=p.parse_args();s=read(ROOT/'_site/bet-ledger-hq/data/system.json',{})
 r=build(system=s,capture=args.capture);print({'profiles':r['profiles'],'capture':args.capture})
