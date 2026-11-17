"""Forward-only college margin scale correction, checked on later game dates."""
import math
from statistics import mean
from zoneinfo import ZoneInfo
from .model import instant, number

def fit_margins(log,now,season):
 rows=[];seen=set()
 for r in sorted(log.get('records',{}).values(),key=lambda x:x.get('captured_at','')):
  start,capture,graded=instant(r.get('start')),instant(r.get('captured_at')),instant(r.get('graded_at'))
  x=number(r.get('raw_margin'));x=x if x is not None else number(r.get('margin')) if r.get('version')=='ncaab-scoring-research-1.0' else None
  y=number(r.get('actual_margin'));identifier=str(r.get('event_id') or '')
  if r.get('kind')!='game' or r.get('league')!='NCAAB' or r.get('result')!='Graded' or r.get('season')!=season or not start or not capture or not graded or not capture<start<=graded<=now or x is None or y is None or not identifier or identifier in seen:continue
  seen.add(identifier);rows.append((start.astimezone(ZoneInfo('America/Toronto')).date().isoformat(),x,y))
 days=sorted({r[0] for r in rows});base={'active':False,'games':len(rows),'scale':1.,'bias':0.,'margin_sd':12,'method':'Frozen completed college games only; bounded scale/bias correction requires a later-date holdout improvement. No sportsbook spread is used as an input.'}
 if len(rows)<150 or len(days)<6:return {**base,'reason':'Needs 150 completed frozen forecasts on at least six game dates.'}
 split=max(4,len(days)*2//3);train=[r for r in rows if r[0] in days[:split]];test=[r for r in rows if r[0] in days[split:]]
 if len(train)<100 or len(test)<30 or len(days[split:])<2:return {**base,'reason':'Needs 100 earlier games and 30 later games on at least two held-out dates.'}
 def coefficients(part):
  mx=mean(r[1] for r in part);my=mean(r[2] for r in part);ridge=2500
  scale=(sum((r[1]-mx)*(r[2]-my) for r in part)+ridge)/(sum((r[1]-mx)**2 for r in part)+ridge)
  scale=max(.75,min(2.,scale));bias=max(-5,min(5,(my-scale*mx)*len(part)/(len(part)+100)))
  return scale,bias
 scale,bias=coefficients(train);baseline=mean(abs(r[2]-r[1]) for r in test);adjusted=mean(abs(r[2]-(scale*r[1]+bias)) for r in test)
 validation={'train_games':len(train),'test_games':len(test),'test_dates':days[split:],'baseline_mae':round(baseline,4),'adjusted_mae':round(adjusted,4),'note':'Internal later-date check, not a guarantee of future accuracy or probability calibration.'}
 if adjusted>=baseline*.95:return {**base,'validation':validation,'reason':'The correction did not improve later-date margin error by at least 5%.'}
 scale,bias=coefficients(rows);sigma=math.sqrt((sum((r[2]-scale*r[1]-bias)**2 for r in rows)+50*12**2)/(len(rows)+50))
 return {**base,'active':True,'scale':round(scale,5),'bias':round(bias,5),'margin_sd':round(max(10,min(24,sigma)),5),'validation':validation,'reason':'Applied to future games only. Earlier frozen predictions are unchanged.'}
