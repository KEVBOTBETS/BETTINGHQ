"""One read-only cross-sport inventory. No network or private wagers in output."""
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path
try:
 from .research.common import read,instant,number,decimal
except ImportError:
 from research.common import read,instant,number,decimal
ROOT=Path(__file__).resolve().parents[1]
SOURCES={'nfl':('nfl-edge-lab','site/data'),'ncaaf':('ncaaf-edge-lab','site/data'),'nhl':('nhl-edge-lab','site/data'),'wnba':('wnba-edge-lab','site/data'),'mlb':('mlb-edge','docs/data')}

def label(g,side):
 r=g.get(side)
 return (r.get('abbr') or r.get('name')) if isinstance(r,dict) else r

def age(at,now,hours):
 t=instant(at)
 return bool(t and 0<=(now-t).total_seconds()<=hours*3600)

def build(root=ROOT,now=None,staged=None):
 now=now or datetime.now(timezone.utc);feeds=[];games=[]
 for sport,(repo,folder) in SOURCES.items():
  path=Path(staged)/repo/'data' if staged else root/'projects'/repo/folder;meta=read(path/'meta.json',{});source=read(path/'games.json',[]);board=read(path/'board.json',[])
  if sport=='mlb':
   meta=read(path/'latest.json',{});source=meta.get('games',[]);board=[]
  if not isinstance(source,list):source=[]
  if not isinstance(board,list):board=[]
  publication=meta.get('generated_at');fresh=age(publication,now,6);upcoming=[];priced=qualified=forecasts=0;book_set=set();reasons=Counter()
  for g in source:
   start=g.get('tipoff') or g.get('start') or g.get('date');at=instant(start)
   if not at or not now<at<now+timedelta(days=14) or g.get('completed') or g.get('canceled') or g.get('postponed') or g.get('state') in ('post','in','unknown'):continue
   if sport=='mlb' and str(g.get('abstract','')).lower() in ('final','live'):continue
   event=str(g.get('game_id') or g.get('gamePk') or g.get('id'));home,away=label(g,'home'),label(g,'away');matchup=str(away)+' @ '+str(home)
   rows=[r for r in board if str(r.get('game_id'))==event]
   if sport=='mlb':rows=g.get('bets') or []
   if not isinstance(rows,list):rows=[]
   observed=[]
   for original in rows:
    r=dict(original)
    if sport=='mlb':
     r['side']=('over' if str(r.get('selection')).lower()=='over' else 'under') if r.get('market')=='TOTAL' else ('home' if r.get('selection')==home else 'away')
     if r.get('market')=='RL':r['market']='ATS'
     r['pick']=r.get('label') or r.get('selection')
     r['odds_observed_at']=r.get('odds_observed_at') or (g.get('odds') or {}).get('fetched_at')
    price=number(r.get('price_american',r.get('price')));book=str(r.get('book') or '').strip();stamp=r.get('odds_observed_at') or r.get('observed_at') or r.get('odds_fetched_at') or r.get('updated_at')
    quote_fresh=age(stamp,now,1.5 if sport=='nhl' else 4)
    valid=decimal(price) is not None and book and r.get('odds_verified') is not False and r.get('price_source')!='model' and not r.get('reference_only') and r.get('quote_status') in (None,'observed')
    passed=r.get('value_policy',{}).get('passes',True) and fresh and quote_fresh and valid and not r.get('held') and not r.get('filtered') and not r.get('validation_policy',{}).get('paused') and (number(r.get('stake')) or 0)>0
    record={'market':r.get('market'),'side':r.get('side'),'line':number(r.get('line')),'pick':r.get('pick') or r.get('selection'),'price':price,'book':book,'observed_at':stamp,
     'probability':number(r.get('model_prob',r.get('p_final'))),'push_prob':number(r.get('push_prob')) or 0,'edge':number(r.get('edge')),'tier':r.get('tier'),'qualified':bool(passed),'fresh':bool(quote_fresh and valid and fresh),
     'reasons':r.get('reasons') or [r.get('value_reason') or r.get('filtered') or ('Source model has not qualified this selection' if not passed else 'Source model qualified; confirm current book offer')],'model_version':r.get('model_version') or meta.get('model_version')}
    observed.append(record)
    if valid and quote_fresh:book_set.add(book)
   projection=g.get('projection') or {};p=number(g.get('p_home',projection.get('p_home')))
   if p is None and sport in ('nfl','ncaaf') and projection.get('ratings_known'):
    try:
     try:from .research.build import current_forecast
     except ImportError:from research.build import current_forecast
     result=current_forecast(root,sport,g,meta)
     p=number((result or {}).get('p_home'))
    except (ImportError,KeyError,ValueError):pass
   if sport=='mlb':p=number((g.get('sim') or {}).get('p_home', (g.get('sim') or {}).get('home_win')))
   if p is None:
    ml=next((r for r in observed if r['market']=='ML' and r['probability'] is not None),None)
    if ml:p=ml['probability'] if ml['side']=='home' else 1-ml['probability']
   margin=number(projection.get('mu',projection.get('margin')))
   ready=p is not None and fresh and not g.get('source_stale')
   priced+=bool(any(r['fresh'] for r in observed));qualified+=bool(any(r['qualified'] for r in observed));forecasts+=bool(ready)
   for r in observed:
    for reason in r['reasons']:
     if reason:reasons[str(reason)]+=1
   chosen=next(iter(sorted([r for r in observed if r['qualified']],key=lambda r:-(r['edge'] or 0))),None)
   if not chosen and ready:
    side='home' if p>=.5 else 'away';offers=sorted([r for r in observed if r['market']=='ML' and r['side']==side and r['fresh']],key=lambda r:r['price'],reverse=True)
    chosen=offers[0] if offers else {'market':'ML','side':side,'pick':str(home if side=='home' else away)+' ML','price':None,'book':None,'probability':p if side=='home' else 1-p,'qualified':False,'fresh':False,'reasons':['Manual research: no verified current price for this forecast']}
   key=sport+'|'+event
   games.append({'id':key,'sport':sport,'event_id':event,'start':start,'matchup':matchup,'home':home,'away':away,'p_home':p if ready else None,'margin':margin if fresh else None,'forecast_available':bool(ready),'publication_at':publication,'publication_fresh':fresh,'selections':observed,'best':chosen,'qualified':bool(any(r['qualified'] for r in observed)),
    'board_url':'../'+repo+'/' if sport!='mlb' else '../mlb-edge/','model_version':meta.get('model_version'),'manual_available':True,
    'decision':{'why':('Published model leans '+str(home if p>=.5 else away)) if ready else 'Forecast unavailable; review the source board',
     'missing':([ 'Forecast publication stale or unavailable'] if not fresh else [])+(['No verified fresh book price'] if not any(r['fresh'] for r in observed) else []),
     'basis':'Research selections remain available; qualification follows the source model and quote checks'}})
   upcoming.append(g)
  failures=[{'name':name,'status':v.get('status'),'observed_at':v.get('observed_at'),'url':v.get('url')} for name,v in meta.get('sources',{}).items() if isinstance(v,dict) and v.get('status') in ('unavailable','retained','no matched prices')]
  feeds.append({'sport':sport,'generated_at':publication,'fresh':fresh,'upcoming':len(upcoming),'forecast_games':forecasts,'priced_games':priced,'qualified_games':qualified,'books':sorted(book_set),'failures':failures,'holds':[{'reason':r,'count':n} for r,n in reasons.most_common(5)]})
 for name,filename,url in [('NFL props','meta.json','../props-edge/'),('NHL props','nhl-props.json','../props-edge/multisport.html?sport=NHL'),('NCAAF props','ncaaf-props.json','../props-edge/multisport.html?sport=NCAAF')]:
  folder=Path(staged)/'props-edge/data' if staged else root/'projects/props-edge/site/data';meta=read(folder/filename,{})
  quotes=read(folder/'legs.json',[]) if name=='NFL props' else meta.get('quotes',[])
  forecasts=read(folder/'legs.json',[]) if name=='NFL props' else meta.get('goal_scorers',[])
  upcoming=[g for g in meta.get('games',[]) if instant(g.get('date')) and instant(g['date'])>now]
  event_ids={q.get('event_id') for q in forecasts if isinstance(q,dict) and instant(q.get('start_time')) and instant(q['start_time'])>now}
  upcoming_count=len(event_ids) if name=='NFL props' else len(upcoming)
  fresh_quotes=[q for q in quotes if isinstance(q,dict) and q.get('price_source')=='book' and not q.get('reference_only') and q.get('quote_status') in (None,'observed') and age(q.get('observed_at') or q.get('updated_at'),now,4) and instant(q.get('start_time')) and instant(q['start_time'])>now]
  feeds.append({'sport':name,'generated_at':meta.get('generated_at'),'fresh':age(meta.get('generated_at'),now,6),'upcoming':upcoming_count,'forecast_games':len(event_ids),'priced_games':len({q.get('event_id') for q in fresh_quotes}),'qualified_games':0,'books':sorted({str(q['book']) for q in fresh_quotes if q.get('book')}),'failures':[],'holds':[{'reason':r,'count':1} for r in meta.get('errors',[])],'board_url':url})
 return {'schema':1,'generated_at':now.isoformat(),'timezone':'America/Toronto','feeds':feeds,'games':sorted(games,key=lambda g:g['start']),
  'policy':'Read-only inventory. Quotes retain original timestamps. Availability is separate from qualification. Wagers and credentials never appear in this public report.'}
