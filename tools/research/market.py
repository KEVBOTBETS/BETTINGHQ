"""Exact-market quote comparison. Expert consensus is never treated as betting volume."""
from collections import defaultdict
from .common import instant, number, decimal, seed

def normalize(raw, now):
    q=dict(raw)
    if q.get('price_source')=='model' or q.get('quote_status','observed')!='observed' or q.get('reference_only'):return None
    aliases={'draft kings':'DraftKings','draftkings':'DraftKings','bet 365':'bet365','bet365':'bet365','fan duel':'FanDuel','fanduel':'FanDuel'}
    q['book']=aliases.get(str(q.get('book','')).strip().lower(),str(q.get('book','')).strip())
    q['rules']=str(q.get('rules') or 'full-game').strip().lower()
    at=instant(q.get('observed_at')); start=instant(q.get('start')); price=number(q.get('price'))
    if not q.get('sport') or not q.get('event_id') or not q.get('book') or not q.get('market') or not q.get('side'):return None
    if not at or not start or not at<=now<start or (now-at).total_seconds()>12*3600 or not decimal(price):return None
    binary=q['market'] in ['Anytime touchdown','First touchdown','Last touchdown']
    if q['side'] not in (['home','away'] if q['market'] in ['ML','ATS'] else ['yes','no'] if binary else ['over','under']):return None
    if q['market']!='ML' and not binary and number(q.get('line')) is None:return None
    q['line']=number(q.get('line')) if q['market']!='ML' and not binary else None
    q.update(price=price,decimal=decimal(price),observed_at=at.isoformat(),start=start.isoformat())
    q['contract']=[q['sport'],str(q['event_id']),q['market'],q.get('player_id') or q.get('player',''),q.get('line'),q.get('rules','full-game')]
    q['id']=str(seed([*q['contract'],q['side'],q['book'],q['observed_at'],price]))
    return q

def audit(raw, archive, now):
    valid=[q for r in raw if (q:=normalize(r,now))]; rejected=len(raw)-len(valid)
    # A duplicate scrape does not create additional market evidence.
    saved={q['id']:q for q in archive if q.get('id') and q.get('contract') and instant(q.get('observed_at')) and instant(q.get('start')) and instant(q['observed_at'])<instant(q['start']) and instant(q['observed_at'])<=now}
    for q in valid:saved.setdefault(q['id'],q)
    groups=defaultdict(list)
    for q in valid:groups[tuple(q['contract'])].append(q)
    reports=[]
    for contract,rows in groups.items():
        latest={}
        for q in sorted(rows,key=lambda x:x['observed_at']):latest[q['book'],q['side']]=q
        rows=list(latest.values()); sides=defaultdict(list)
        for q in rows:sides[q['side']].append(q)
        pairs=[]
        for book in sorted({q['book'] for q in rows}):
            bookrows=[q for q in rows if q['book']==book]
            if len(bookrows)==2 and len({q['side'] for q in bookrows})==2 and bookrows[0]['observed_at']==bookrows[1]['observed_at']:
                total=sum(1/q['decimal'] for q in bookrows)
                pairs.append({'book':book,'probabilities':{q['side']:(1/q['decimal'])/total for q in bookrows},'overround':total-1})
        best={side:max(qs,key=lambda q:q['decimal']) for side,qs in sides.items()}
        history=[q for q in saved.values() if tuple(q['contract'])==contract]
        same=[q for q in sorted(history,key=lambda q:q['observed_at']) if q['book']==rows[0]['book'] and q['side']==rows[0]['side']]
        reports.append({'contract':list(contract),'matchup':rows[0].get('matchup'),'quotes':rows,'best':best,'devig_pairs':pairs,'books':len({q['book'] for q in rows}),'first':same[0] if same else None,'latest':same[-1] if same else None,'coverage':'multiple books' if len({q['book'] for q in rows})>=2 else 'single book','actionable':False})
    series=defaultdict(list)
    for q in saved.values():
        if len(q['contract'])!=6:continue
        key=tuple(q['contract'][:4]+q['contract'][5:]+[q['book'],q['side']]);series[key].append(q)
    moves=[]
    for key,values in series.items():
        values=sorted(values,key=lambda q:q['observed_at'])
        if len(values)>1:
            first,last=values[0],values[-1]
            moves.append({'sport':first['sport'],'event_id':first['event_id'],'matchup':first.get('matchup'),'market':first['market'],'player':first.get('player'),'book':first['book'],'side':first['side'],'first_at':first['observed_at'],'latest_at':last['observed_at'],'first_line':first['line'],'latest_line':last['line'],'first_price':first['price'],'latest_price':last['price'],'line_change':last['line']-first['line'] if number(first['line']) is not None and number(last['line']) is not None else None})
    return {'groups':reports,'movements':moves,'accepted':len({q['id'] for q in valid}),'rejected':rejected,'policy':'Compare identical lines and rules only. Movement is tracked separately by book; prices at different lines are never de-vigged together. Missing opposite prices have no de-vigged probability. Archive contains verified pregame observations only.'},list(saved.values())

def closing_value(selection, archive, now):
    """Last observed pregame quote at the same book, side and exact contract."""
    start=instant(selection.get('start')); captured=instant(selection.get('observed_at'))
    if not start or not captured or captured>=start or now<start:return None
    rows=[q for q in archive if q.get('contract')==selection.get('contract') and q.get('book')==selection.get('book') and q.get('side')==selection.get('side') and instant(q.get('observed_at')) and captured<=instant(q['observed_at'])<start]
    if not rows:return None
    last=max(rows,key=lambda q:q['observed_at'])
    return {'last_observed_at':last['observed_at'],'decimal_ratio':selection['decimal']/last['decimal']-1,'minutes_before_start':(start-instant(last['observed_at'])).total_seconds()/60,'label':'last observed pregame price; not guaranteed final close'}
