"""Recorded workloads and shared-game simulations. These are unvalidated challengers."""
from collections import defaultdict
import re
import numpy as np
from .common import instant, number, key_team, team, seed

MARKETS={'Targets':'targets','Receptions':'receptions','Receiving yards':'receiving_yards','Rush attempts':'carries','Rushing yards':'rush_yards','Pass attempts':'pass_attempts','Passing yards':'passing_yards'}

def identity(name):
    words=re.findall(r'[a-z]+',str(name).lower())
    words=[w for w in words if w not in ['jr','sr','ii','iii','iv']]
    return (words[0][0],words[-1]) if len(words)>1 else None

def workload(history, day):
    eligible=sorted([r for r in history if r.get('date','9999')<day],key=lambda r:r['date'])[-8:]
    if len(eligible)<3:return None
    weights=np.array([.85**(len(eligible)-i-1) for i in range(len(eligible))]);weights/=weights.sum()
    means={k:float(sum(w*r.get(k,0) for w,r in zip(weights,eligible))) for k in set(MARKETS.values())}
    snaps=[r['snap_share'] for r in eligible if number(r.get('snap_share')) is not None]
    recent=snaps[-3:];base=sum(snaps)/len(snaps) if snaps else None
    factor=float(np.clip((sum(recent)/len(recent))/base,.7,1.3)) if base and recent else 1.
    return {'samples':len(eligible),'through':eligible[-1]['date'],'means':means,'history':eligible,'snap_samples':len(snaps),'snap_share':sum(recent)/len(recent) if recent else None,'workload_factor':factor,'workload_note':'Recent offensive snap share scales historical opportunity shares, capped at ±30%' if snaps else 'Snap history unavailable; historical opportunity shares only'}

def count(rng, mean, size, variability=.15):
    # A mixture models uncertain volume without negative opportunities.
    return rng.poisson(rng.gamma(1/variability,max(.01,mean)*variability,size=size))

def simulate_event(game, candidates, dataset, now, size=6000):
    start=instant(game.get('date')); observed=instant(dataset.get('observed_at'))
    live=instant(dataset.get('live_observed_at') or dataset.get('observed_at'))
    if not start or start<=now or not observed or observed>now or not live or live>now or (now-live).total_seconds()>7*86400:return {},[]
    rng=np.random.default_rng(seed([game.get('game_id'),'joint-opportunity-v3',dataset['observed_at']]))
    histories=defaultdict(list)
    for r in dataset.get('players',[]):histories[r['player_id']].append(r)
    ids=defaultdict(set)
    for pid,rows in histories.items():
        for row in rows:ids[identity(row['name'])].add(pid)
    totals=defaultdict(lambda:defaultdict(float))
    for r in dataset.get('players',[]):
        for key in ['targets','carries','pass_attempts']:totals[r['game_id'],r['team']][key]+=r.get(key,0)
    matched=[]; gaps=[]
    for c in candidates:
        if not c.get('roster_verified') or str(c.get('injury_status','')).lower() in ['out','inactive','injured reserve']:continue
        if c.get('position')=='QB':
            side=next((s for s in ['home','away'] if c.get('team') in [team(game,s),(game.get(s) or {}).get('name') if isinstance(game.get(s),dict) else game.get(s+'_name')]),None)
            qb=((game.get('injuries') or {}).get(side,{}) or {}).get('qb') or {}
            value=qb.get('value') or {};status=str(qb.get('status') or '').lower()
            expected=value.get('replacement') if qb.get('weight')==1 or status=='out' else qb.get('name') or value.get('starter')
            if not expected:expected=dataset.get('expected_starters',{}).get(key_team(team(game,side)),{}).get('player') if side else None
            if str(c.get('injury_status','')).lower() in ['questionable','doubtful'] or not expected or qb.get('questionable') or status in ['questionable','doubtful'] or identity(c['player'])!=identity(expected):
                gaps.append({'player':c['player'],'reason':'Quarterback starting role missing, uncertain, or assigned to another player'});continue
            c={**c,'expected_starter':True}
        options=ids.get(identity(c.get('player')),set())
        if len(options)!=1:
            gaps.append({'player':c.get('player'),'reason':'Missing or ambiguous player identity'});continue
        pid=next(iter(options)); w=workload(histories[pid],now.date().isoformat())
        if not w:
            gaps.append({'player':c.get('player'),'reason':'Fewer than three recorded-opportunity games'});continue
        if any(x['player_id']==pid for x in matched):continue
        matched.append({**c,**w,'player_id':pid})
    # Every participant in an event receives the same pace and game-script draws.
    pace=rng.lognormal(-.5*.12**2,.12,size)
    mu=number((game.get('projection') or {}).get('mu')) or 0
    margin=rng.normal(mu,14,size);arrays={}; reviews=[]
    for side in ['home','away']:
        abbr=key_team(team(game,side));name=(game.get(side) or {}).get('name') if isinstance(game.get(side),dict) else game.get(side+'_name')
        active=[c for c in matched if c.get('team') in [abbr,name]]
        if not active:continue
        eligible={r['game_id'] for r in dataset.get('teams',[]) if r['date']<now.date().isoformat()}
        past=sorted([(key,v) for key,v in totals.items() if key[1]==abbr and key[0] in eligible],key=lambda x:x[0][0])[-8:]
        if len(past)<3:continue
        pass_mean=float(np.mean([v['pass_attempts'] for _,v in past])); rush_mean=float(np.mean([v['carries'] for _,v in past]))
        script=np.clip((margin if side=='home' else -margin)/14,-2,2)
        attempts=count(rng,pass_mean,size,.04);attempts=np.rint(attempts*pace*np.exp(-.07*script)).astype(int)
        carries=count(rng,rush_mean,size,.06);carries=np.rint(carries*pace*np.exp(.10*script)).astype(int)
        def shares(key):
            if key=='pass_attempts' and any(c.get('expected_starter') for c in active):
                return np.array([1. if c.get('expected_starter') else 0. for c in active]+[0.])
            values=[]
            for c in active:
                numerator=sum(r.get(key,0) for r in c['history']);denominator=sum(totals[r['game_id'],r['team']][key] for r in c['history'])
                values.append((numerator/denominator if denominator else 0)*c['workload_factor'])
            # Keep an explicit 'other players' bucket; never invent their identities.
            used=sum(values); factor=min(1.,.98/max(used,.00001))
            values=[x*factor for x in values];return np.array(values+[1-sum(values)])
        # Multinomial allocation conserves each simulated team's opportunities.
        ts,rs,qs=shares('targets'),shares('carries'),shares('pass_attempts')
        target_mean=float(np.mean([v['targets'] for _,v in past]))
        targeted=rng.binomial(attempts,min(1.,max(0.,target_mean/max(1,pass_mean))))
        target_counts=np.array([rng.multinomial(n,ts) for n in targeted])
        rush_counts=np.array([rng.multinomial(n,rs) for n in carries])
        qb_counts=np.array([rng.multinomial(n,qs) for n in attempts])
        receiving=[]
        for i,c in enumerate(active):
            h=c['history']; targets=target_counts[:,i];rushes=rush_counts[:,i]
            catches=sum(r.get('receptions',0) for r in h);tries=sum(r.get('targets',0) for r in h)
            catch_rate=(catches+6.5)/(tries+10);rec=rng.binomial(targets,min(1,max(0,catch_rate)))
            ypc=(sum(r.get('receiving_yards',0) for r in h)+60)/(catches+5)
            ypr=(sum(r.get('rush_yards',0) for r in h)+40)/(sum(r.get('carries',0) for r in h)+10)
            recyards=np.rint(rng.gamma(np.maximum(rec*2,.001),max(.1,ypc)/2));recyards[rec==0]=0
            rushyards=np.rint(rng.normal(rushes*ypr,np.sqrt(rushes)*max(2,abs(ypr))));rushyards[rushes==0]=0
            receiving.append(recyards)
            arrays[c['player']]={'targets':targets,'receptions':rec,'receiving_yards':recyards,'carries':rushes,'rush_yards':rushyards,'pass_attempts':qb_counts[:,i]}
            reviews.append({'player':c['player'],'team':abbr,'samples':c['samples'],'through':c['through'],'means':c['means'],'snap_samples':c['snap_samples'],'snap_share':c['snap_share'],'workload_note':c['workload_note'],'expected_snaps':float((attempts+carries).mean()*c['snap_share']) if c['snap_share'] is not None else None,'expected_targets':float(targets.mean()),'expected_carries':float(rushes.mean()),'policy':'Conditional on being active. Missing games are not recorded as zero. Historical shares are normalized across the verified current roster.'})
        other_rec=rng.binomial(target_counts[:,-1],.65);other_yards=np.rint(rng.gamma(np.maximum(other_rec*2,.001),6.));other_yards[other_rec==0]=0
        totalyards=sum(receiving)+other_yards
        for i,c in enumerate(active):
            fraction=np.divide(qb_counts[:,i],attempts,out=np.zeros(size),where=attempts>0)
            arrays[c['player']]['passing_yards']=np.rint(totalyards*fraction)
    return arrays,reviews+gaps

def price_outcome(values, side, line):
    values=np.asarray(values);push=np.isclose(values,line,atol=1e-9)
    win=(values>line) if side=='over' else (values<line)
    return {'win':float(win.mean()),'push':float(push.mean()),'loss':float((~win&~push).mean()),'mean':float(values.mean()),'low':float(np.quantile(values,.1)),'high':float(np.quantile(values,.9))},win,push

def joint_ticket(legs):
    """Within-event masks share draw indices; distinct events have independent outcomes."""
    if not legs:return None
    seen=set();groups=defaultdict(list)
    for leg in legs:
        contract=(leg['event_id'],leg['player'],leg['market'])
        if contract in seen:return None  # No duplicated or contradictory market in a ticket.
        seen.add(contract);groups[leg['event_id']].append(leg)
    probability=1.; independent=1.; no_loss=1.
    for event,rows in groups.items():
        probability*=float(np.logical_and.reduce([r['hits'] for r in rows]).mean())
        no_loss*=float(np.logical_and.reduce([r['hits']|r['pushes'] for r in rows]).mean())
    for leg in legs:independent*=leg['probability']['win']
    return {'win':probability,'no_loss':no_loss,'independent_comparison':independent,'difference':probability-independent,'games':len(groups),'simulations':len(legs[0]['hits']),'combined_price':None,'ev':None,'status':'Research simulation · sportsbook combined price unavailable','policy':'Shared opportunities within a game; independent game outcomes. Push settlement and a verified combined book price are required before ticket EV.'}
