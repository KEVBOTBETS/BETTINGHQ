"""Describe frozen research outcomes without treating overlapping tickets as trials."""
from collections import Counter, defaultdict
from .grade import identity

def audit(records):
    decided=[r for r in records if r.get('result') in ('Win','Loss')]
    events={str(l.get('event_id')) for r in decided for l in r.get('legs',[]) if l.get('event_id')}
    unique={}
    exposure=Counter()
    for r in decided:
        for l in r.get('legs',[]):
            key=identity(l); exposure[key]+=1
            # A pending copy in a different ticket must not hide a final result.
            if key not in unique or l.get('result') in ('Win','Loss','Push','Void'):unique[key]=l
    groups={}
    for field in ['profile','target','leg_count','scope']:
        counts=defaultdict(Counter)
        for r in decided:counts[str(r.get(field,'legacy-longshot' if field=='profile' else 'unknown'))][r['result']]+=1
        groups[field]=[{'label':k,'wins':v['Win'],'losses':v['Loss']} for k,v in sorted(counts.items())]
    market_counts=defaultdict(Counter)
    for l in unique.values():
        if l.get('result') in ('Win','Loss'):market_counts[l['market']][l['result']]+=1
    top=sorted(unique,key=lambda k:exposure[k],reverse=True)[:8]
    return {'decided':len(decided),'wins':sum(r['result']=='Win' for r in decided),'losses':sum(r['result']=='Loss' for r in decided),'distinct_events':len(events),'unique_legs':len(unique),'estimated_tickets':sum(bool(r.get('estimated_prices')) for r in decided),'same_game_tickets':sum(bool(r.get('same_game')) for r in decided),'groups':groups,'markets':[{'market':k,'wins':v['Win'],'losses':v['Loss']} for k,v in sorted(market_counts.items())],'repeated_legs':[{'pick':unique[k].get('pick'),'result':unique[k].get('result','Pending'),'tickets':exposure[k]} for k in top],'note':'Overlapping published research combinations are not independent bets. A ticket can be lost before its remaining legs settle. Estimated or mixed-book prices cannot establish wager ROI.'}
