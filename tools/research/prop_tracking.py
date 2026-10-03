"""First-capture opportunity comparisons; missing participation never becomes zero."""
from collections import defaultdict
import csv
import math
from .common import instant,number,seed
from .opportunity import MARKETS,identity

def freeze(archive, rows, now):
    saved={r['id']:dict(r) for r in archive if r.get('id')};best={}
    for q in rows:
        at,start=instant(q.get('observed_at')),instant(q.get('start'))
        if not at or not start or not at<=now<start or (now-at).total_seconds()>12*3600:continue
        key=(q['sport'],q['event_id'],q['player'],q['market'],q['side'],q['line'])
        if key not in best or q['decimal']>best[key]['decimal']:best[key]=q
    for contract,q in best.items():
        for model in ['opportunity','current']:
            key=str(seed([*contract,model,'prop-v2']))
            if key in saved:continue
            if model=='opportunity':p=q['probability'];win,push=p['win'],p['push']
            else:
                win=number(q.get('model_prob'));push=number(q.get('push_prob')) or 0
                if win is None:continue
            if not 0<=win<=1 or not 0<=push<1 or win+push>1+1e-8:continue
            saved[key]={'id':key,'sport':q['sport'],'event_id':q['event_id'],'player':q['player'],'market':q['market'],'side':q['side'],'line':q['line'],'start':q['start'],'matchup':q.get('matchup'),'model':model,'version':'prop-v2','p_win':win,'p_push':push,'p_no_push':win/(1-push),'price_decimal':q['decimal'],'book':q['book'],'quote_observed_at':q['observed_at'],'captured_at':now.isoformat(),'result':None}
    return list(saved.values())

def settle(archive, dataset, schedule_path, now):
    observed=instant(dataset.get('observed_at'))
    if not observed or observed>now or not schedule_path.exists():return archive
    with schedule_path.open() as stream:
        ids={str(r.get('espn')):r['game_id'] for r in csv.DictReader(stream) if r.get('espn')}
    completed={r['game_id'] for r in dataset.get('teams',[]) if r.get('result_verified')}
    players=defaultdict(list)
    for p in dataset.get('players',[]):players[p['game_id'],identity(p['name'])].append(p)
    result=[]
    for original in archive:
        r=dict(original);start=instant(r.get('start'));gid=ids.get(str(r['event_id']))
        if r.get('result') is None and start and start<=observed<=now and gid in completed:
            candidates=players[gid,identity(r['player'])]
            identities={p['player_id'] for p in candidates}
            if len(identities)==1:
                stat=MARKETS.get(r['market']);values=[number(p.get(stat)) for p in candidates if stat]
                if len(values)==1 and values[0] is not None:
                    value=values[0];outcome='push' if abs(value-r['line'])<1e-9 else 'win' if ((value>r['line'])==(r['side']=='over')) else 'loss'
                    r['result']={'value':value,'outcome':outcome,'observed_at':dataset['observed_at'],'source':'Verified completed nflverse player opportunities; recorded participation required'}
        result.append(r)
    return result

def report(archive, now):
    groups=defaultdict(list)
    for r in archive:groups[r['sport'],r['model'],r['version']].append(r)
    models=[]
    for (sport,model,version),rows in sorted(groups.items()):
        done=[r for r in rows if r.get('result') and instant(r.get('captured_at')) and instant(r['captured_at'])<instant(r['start']) and instant(r['result'].get('observed_at')) and instant(r['result']['observed_at'])<=now]
        graded=[r for r in done if r['result']['outcome']!='push'];n=len(graded);brier=loss=None
        if n:
            brier=sum((r['p_no_push']-(r['result']['outcome']=='win'))**2 for r in graded)/n
            loss=-sum(math.log(max(1e-9,r['p_no_push'] if r['result']['outcome']=='win' else 1-r['p_no_push'])) for r in graded)/n
        profit=sum(r['price_decimal']-1 if r['result']['outcome']=='win' else -1 if r['result']['outcome']=='loss' else 0 for r in done)
        models.append({'sport':sport,'model':model,'version':version,'contracts':len(rows),'events':len({r['event_id'] for r in rows}),'settled':len(done),'calibration_contracts':n,'wins':sum(r['result']['outcome']=='win' for r in done),'losses':sum(r['result']['outcome']=='loss' for r in done),'pushes':len(done)-n,'pending':len(rows)-len(done),'brier':brier,'log_loss':loss,'roi':profit/len(done) if done else None})
    return {'models':models,'records':len(archive),'policy':'One frozen forecast per event, player, market, side, exact line, model and version; books are not additional samples. No-push calibration excludes pushes. Player absence or missing opportunity evidence stays ungraded. Correlated contracts are not independent games. No promotion test is claimed for props.'}
