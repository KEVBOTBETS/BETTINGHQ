"""Forward-only milestone evidence. Captures are pregame; no backfilled wins or wager ROI."""
import gzip
import json
import math
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from .nba_milestones import number,KEYS

def contract(q):return '|'.join(str(q.get(k,'')) for k in ['event_id','athlete_id','market','line','model_version'])
def offer_key(q):return '|'.join(str(q.get(k,'')) for k in ['event_id','athlete_id','market','line','side'])
def track(archive,props,players,now):
 from .multisport import instant
 records=archive.setdefault('records',[]);seen={r['id']:r for r in records};publication=instant(props.get('generated_at'));source=instant(props.get('source_model_at'))
 fresh=publication and source and 0<=(now-publication).total_seconds()<=6*3600 and 0<=(now-source).total_seconds()<=6*3600
 if fresh:
  for q in props.get('milestone_forecasts',[]):
   start=instant(q.get('start_time'));p=q.get('model_prob');identifier=contract(q)
   if not start or not now<start<=now+timedelta(days=2) or not isinstance(p,(int,float)) or not 0<p<1 or not q.get('model_version') or identifier in seen:continue
   r={k:q.get(k) for k in ['event_id','athlete_id','player','team','market','line','threshold','model_version','samples','current_samples','prior_samples']}
   r.update(id=identifier,start=q['start_time'],probability=p,captured_at=now.isoformat(),publication_at=props['generated_at'],result=None,prices={});records.append(r);seen[identifier]=r
  byoffer=defaultdict(list)
  for q in props.get('quotes',[]):
   at=instant(q.get('observed_at'));price=q.get('price_american')
   if q.get('price_source')!='book' or q.get('reference_only') or q.get('quote_status') not in (None,'observed') or q.get('side')!='over' or not at or not 0<=(now-at).total_seconds()<=90*60 or not isinstance(price,(int,float)) or abs(price)<100 or not q.get('book'):continue
   byoffer[offer_key(q)].append(q)
  for r in records:
   start=instant(r['start'])
   if not start or now>=start or r.get('result') is not None:continue
   for q in byoffer.get(offer_key({**r,'side':'over'}),[]):
    at=instant(q['observed_at'])
    if at>=start:continue
    book=q['book'];prices=r.setdefault('prices',{});old=prices.get(book);current={'price':q['price_american'],'at':q['observed_at'],'source_url':q.get('source_url')}
    if old is None:prices[book]={'first':current,'latest':current}
    elif instant(old['latest']['at'])<at:old['latest']=current
 finals=defaultdict(list)
 for q in players:
  at=instant(q.get('start'));minutes=number((q.get('stats') or {}).get('MIN'))
  if q.get('state')=='post' and at and at<now and minutes and minutes>0:finals[(str(q.get('game_id')),str(q.get('player_id')))].append(q)
 for r in records:
  start=instant(r['start']);captured=instant(r['captured_at'])
  if r.get('result') is not None or not start or not captured or not captured<start<now:continue
  matches=finals.get((str(r['event_id']),str(r['athlete_id'])),[]);values={number((q.get('stats') or {}).get(KEYS.get(r['market']))) for q in matches if q.get('team')==r['team']};values.discard(None)
  if len(values)!=1:continue
  actual=next(iter(values));r.update(result=int(actual>=r['threshold']),actual=actual,graded_at=now.isoformat(),result_source='Completed ESPN box score; minutes played verified')
 return archive

def metrics(rows):
 n=len(rows)
 return {'contracts':n,'events':len({r['event_id'] for r in rows}),'players':len({r['athlete_id'] for r in rows}),'dates':len({r['start'][:10] for r in rows}),
  'hit_rate':sum(r['result'] for r in rows)/n if n else None,'predicted':sum(r['probability'] for r in rows)/n if n else None,
  'brier':sum((r['probability']-r['result'])**2 for r in rows)/n if n else None,
  'log_loss':-sum(math.log(max(1e-12,r['probability'] if r['result'] else 1-r['probability'])) for r in rows)/n if n else None}

def report(archive,now):
 from .multisport import instant
 rows=archive.get('records',[]);settled=[r for r in rows if r.get('result') in (0,1)];market={}
 for name in sorted({r['market'] for r in rows}):market[name]=metrics([r for r in settled if r['market']==name])
 bins=[{'from':lo,'to':hi,**metrics([r for r in settled if lo<=r['probability']<hi])} for lo,hi in [(0,.25),(.25,.5),(.5,.65),(.65,.8),(.8,1)]]
 prices=[]
 for r in rows:
  start=instant(r['start'])
  if not start or start>now:continue
  for book,pair in r.get('prices',{}).items():
   first,last=pair['first'],pair['latest'];at=instant(last['at'])
   if not at or not 0<(start-at).total_seconds()<=30*60 or first['at']==last['at']:continue
   decimal=lambda p:1+(p/100 if p>0 else 100/-p)
   prices.append(decimal(first['price'])/decimal(last['price'])-1)
 return {'generated_at':now.isoformat(),'captured':len(rows),'pending':len(rows)-len(settled),'validated':False,'status':'Collecting prospective evidence',
  'overall':metrics(settled),'by_market':market,'calibration':bins,'near_start_prices':{'pairs':len(prices),'average_decimal_price_advantage':sum(prices)/len(prices) if prices else None},
  'note':'Only forecasts frozen before kickoff are graded. Alternate lines for the same player are correlated evidence; event/player/date counts are shown. Sparse or missing participation stays pending. No betting profit or ROI is inferred.'}

def publish(root,props,players,now):
 root=Path(root);path=root/'state/nba-validation.json.gz'
 try:
  with gzip.open(path,'rt',encoding='utf-8') as f:archive=json.load(f)
 except FileNotFoundError:archive={'schema':1,'records':[]}
 archive=track(archive,props,players,now);path.parent.mkdir(exist_ok=True);temp=path.with_suffix('.tmp')
 with gzip.open(temp,'wt',encoding='utf-8',compresslevel=6) as f:json.dump(archive,f,separators=(',',':'),allow_nan=False)
 temp.replace(path);summary=report(archive,now);dest=root/'site/data/nba-validation.json';tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(summary,separators=(',',':'),allow_nan=False)+'\n');tmp.replace(dest);return summary
