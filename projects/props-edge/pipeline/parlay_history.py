"""Durable, forward-only model parlay archive. No user wagers or bankrolls."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from .grade import identity, instant

FINALS = {'Win', 'Loss', 'Push', 'Void'}

def outcome(legs):
    results=[leg.get('result','Pending') for leg in legs]
    if not results: return 'Pending'
    if all(r=='Void' for r in results): return 'Void'
    # A sportsbook may void a whole SGP or reprice it. Never guess its rules.
    if any(r in ('Push','Void','Review') for r in results): return 'Review'
    if 'Loss' in results: return 'Loss'
    if all(r=='Win' for r in results): return 'Win'
    return 'Pending'

def update(root, tickets, now=None):
    now=now or datetime.now(timezone.utc);stamp=now.isoformat()
    path=root/'state/parlay_history.json'
    # Corruption must fail the isolated refresh instead of erasing history.
    state=json.loads(path.read_text()) if path.exists() else {'schema':1,'records':{}}
    if state.get('schema')!=1 or not isinstance(state.get('records'),dict):
        raise ValueError('Invalid parlay history; original archive retained')
    for ticket in tickets:
        legs=deepcopy(ticket.get('legs') or [])
        if len(legs)<2: continue
        for leg in legs:leg['event_id']=str(leg.get('result_event_id') or leg.get('event_id') or '')
        if any(not l['event_id'].isdigit() or not l.get('player') or not l.get('market') or not instant(l.get('start_time')) or instant(l['start_time'])<=now for l in legs):continue
        keys=sorted(identity(l) for l in legs)
        if len(set(keys))!=len(keys):continue
        key='parlay-'+hashlib.sha256('|'.join(keys).encode()).hexdigest()[:24]
        if key in state['records']:continue
        saved={k:deepcopy(ticket.get(k)) for k in ('id','scope','label','target','price_american','price_decimal','model_prob','independent_prob','estimated_prices','same_game','probability_method','games')}
        saved.update(id=key,source_ticket_id=ticket.get('id'),captured_at=stamp,start_time=min(l['start_time'] for l in legs),
                     leg_count=len(legs),legs=legs,result='Pending',research_only=True)
        state['records'][key]=saved
    history_path=root/'state/leg_history.json'
    history=json.loads(history_path.read_text()) if history_path.exists() else {'records':{}}
    results=history.get('records',{})
    compact=[]
    for leg in results.values():
        at=instant(leg.get('graded_at'));start=instant(leg.get('start_time'))
        if leg.get('result') not in FINALS or not at or not start or not start<=at<=now:continue
        compact.append({k:leg.get(k) for k in ('event_id','player','team','market','side','line','start_time','result','actual','graded_at')})
    resolved={identity(l):l for l in compact}
    for record in state['records'].values():
        for leg in record['legs']:
            result=resolved.get(identity(leg))
            if result and result.get('team')==leg.get('team'):
                leg.update({k:result.get(k) for k in ('result','actual','graded_at')})
        result=outcome(record['legs'])
        if result!=record['result']:
            record['result']=result
            record['result_updated_at']=stamp
    rows=sorted(state['records'].values(),key=lambda r:r['captured_at'],reverse=True)
    summary={name:sum(r['result']==name for r in rows) for name in ('Win','Loss','Pending','Void','Review')}
    decided=summary['Win']+summary['Loss']
    public={'schema':1,'generated_at':stamp,'records':rows,'summary':{**summary,'total':len(rows),'hit_rate':summary['Win']/decided if decided else None},
      'note':'Unique published leg combinations frozen before their first game. Overlapping tickets are not independent trials. Research outcomes are not wager ROI. Push/void legs require book-rule review. Tracking starts with this release; old tickets are not reconstructed.'}
    for target,data in [(path,state),(root/'site/data/parlay-history.json',public),(root/'site/data/parlay-results.json',{'schema':1,'generated_at':stamp,'records':compact})]:
        target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_suffix('.tmp')
        temp.write_text(json.dumps(data,separators=(',',':'),allow_nan=False)+'\n');temp.replace(target)
    return public['summary']
