"""Immutable whole-sheet moneyline calls, separate from recommended or actual bets."""
from datetime import datetime,timezone
from pathlib import Path
import argparse,json
try:
 from .research.common import read,write,instant,number,decimal
except ImportError:
 from research.common import read,write,instant,number,decimal
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=Path('projects/bet-ledger-hq/data/research/moneyline-calls.json')

def freeze(records,games,now):
 saved={(r['sport'],r['event_id'],r['version']):r for r in records}
 for g in games:
  start,pub=instant(g.get('start')),instant(g.get('publication_at'))
  if not start or not pub or not pub<=now<start or (now-pub).total_seconds()>6*3600:continue
  p=number(g.get('p_home'))
  if not g.get('forecast_available') or p is None or not 0<p<1 or p==.5:continue
  side='home' if p>.5 else 'away'
  qs=[q for q in g.get('selections',[]) if q.get('market')=='ML' and q.get('side')==side]
  q=max(qs,key=lambda q:instant(q.get('observed_at')) or datetime.min.replace(tzinfo=timezone.utc)) if qs else {}
  q={**q,'side':side,'probability':p if side=='home' else 1-p,'pick':str(g.get(side) or side)+' ML'}
  version=g.get('model_version') or q.get('model_version') or 'unversioned';key=(g['sport'],str(g['event_id']),version)
  if key in saved:continue
  quoted=instant(q.get('observed_at'));fresh=bool(q.get('fresh') and quoted and quoted<=now and (now-quoted).total_seconds()<=3*3600 and decimal(q.get('price')) and q.get('book') and not q.get('reference_only') and q.get('price_source')!='model' and q.get('quote_status','observed')=='observed')
  saved[key]={'sport':g['sport'],'event_id':str(g['event_id']),'version':version,'matchup':g['matchup'],'start':g['start'],'captured_at':now.isoformat(),'source_at':g['publication_at'],'p':q['probability'] if q['side']=='home' else 1-q['probability'],'side':q['side'],'pick':q.get('pick'),'price':q['price'] if fresh else None,'book':q.get('book') if fresh else None,'quote_at':q.get('observed_at') if fresh else None,'recommendation':'Recommended' if q.get('qualified') else 'Research only','result':None,'origin':'First whole-sheet capture; not an actual wager'}
 return list(saved.values())

def settle(records,performance,now):
 finals={(r['sport'],r['id']):r for r in performance.get('records',[])};out=[]
 for r in records:
  r=dict(r);f=finals.get((r['sport'],r['event_id']));verified=instant(f.get('result_at')) if f else None
  if not r.get('result') and f and instant(f['start'])==instant(r['start']) and verified and instant(r['start'])<=verified<=now:
   win=(r['p']>.5)==(f['y']==1);d=decimal(r.get('price'))
   r['result']={'status':'Win' if win else 'Loss','verified_at':f['result_at'],'home_score':f['home_score'],'away_score':f['away_score'],'unit_profit':(d-1 if win else -1) if d else None}
  out.append(r)
 return out

def build(root=ROOT,system=None,performance=None,capture=False,now=None):
 now=now or datetime.now(timezone.utc);records=read(root/ARCHIVE,{'records':[]})['records'];performance=performance or read(root/'_site/bet-ledger-hq/data/performance.json',{})
 if capture:
  records=settle(freeze(records,(system or {}).get('games',[]),now),performance,now);write(root/ARCHIVE,{'schema':1,'records':records})
 # Reuse validated historical pregame calls. Historical prices are never backfilled.
 keys={(r['sport'],r['event_id'],r['version']) for r in records};combined=list(records)
 for f in performance.get('records',[]):
  if (f['sport'],f['id'],f['version']) in keys:continue
  combined.append({'sport':f['sport'],'event_id':f['id'],'version':f['version'],'matchup':f['matchup'],'start':f['start'],'captured_at':f['captured_at'],'p':f['p'],'side':'home' if f['p']>.5 else 'away' if f['p']<.5 else None,'pick':None,'price':None,'book':None,'recommendation':'Not recorded','origin':'Validated pregame archive; historical price unavailable','result':{'status':'No call' if f['p']==.5 else 'Win' if (f['p']>.5)==(f['y']==1) else 'Loss','home_score':f['home_score'],'away_score':f['away_score'],'verified_at':f.get('result_at'),'unit_profit':None}})
 return {'schema':1,'generated_at':now.isoformat(),'records':sorted(combined,key=lambda r:r['start'],reverse=True),'policy':'Every available published winner call, whether recommended or not. First pregame call per event and recorded model version. Versions stay separate. Historical accuracy can be scored without odds; simulated one-unit profit requires an original fresh recorded price. These are research calls, not placed bets. Missing forecasts remain missing.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--capture',action='store_true');a=p.parse_args();d=build(system=read(ROOT/'_site/bet-ledger-hq/data/system.json',{}),capture=a.capture);print({'moneyline_records':len(d['records']),'capture':a.capture})
