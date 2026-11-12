"""Evidence-based weekly roles; no invented injury redistribution or snap counts."""
from collections import defaultdict
from datetime import timedelta
from .weekly_nfl import instant, norm, finite


def depth_slots(payload):
    slots=[]
    for unit in payload.get('depthchart',[]):
        for key,position in (unit.get('positions') or {}).items():
            # Returners/holders may already have an offensive role; don't turn
            # special-team depth into an offensive starter designation.
            if key.lower() in ('h','pr','kr'):continue
            ids=[str(a.get('id')) for a in position.get('athletes',[]) if a.get('id')]
            if ids:slots.append((key.lower(),ids))
    return slots


def assign_roles(rows, payloads, summaries, now):
    by_team=defaultdict(dict)
    for r in rows:by_team[r['team_id']][r['player_id']]=r
    evidence=defaultdict(list)
    for s in summaries:
        h=s.get('header') or {};c=(h.get('competitions') or [{}])[0]
        at=instant(c.get('date') or s.get('_weekly_event_date'))
        done=((c.get('status') or {}).get('type') or {}).get('completed',s.get('_weekly_completed',False))
        if not done or not at or not now-timedelta(days=28)<=at<=now:continue
        for b in (s.get('boxscore') or {}).get('players',[]):
            tid=str((b.get('team') or {}).get('id') or '')
            counts=defaultdict(dict)
            for group in b.get('statistics',[]):
                kind=norm(group.get('name') or group.get('type'))
                keys=[norm(k) for k in group.get('keys',[])]
                for a in group.get('athletes',[]):
                    pid=str((a.get('athlete') or {}).get('id') or '')
                    for k,v in zip(keys,a.get('stats',[])):
                        v=finite(v)
                        if v is not None:counts[pid][kind+':'+k]=v
            for pid,v in counts.items():evidence[tid,pid].append((at,v))
    for r in rows:
        r.update(role_eligible=False,role='Role unconfirmed',role_checked_at=now.isoformat())
    for tid,roster in by_team.items():
        slots=depth_slots(payloads.get(tid,{ }))
        for slot,ids in slots:
            available=[pid for pid in ids if pid in roster and not roster[pid]['unavailable']]
            if not available:continue
            pid=available[0];r=roster[pid]
            # A doubtful starter does not confirm an injury replacement.
            r.update(role_eligible=norm(r['availability'])!='doubtful',role='Expected starter' if pid==ids[0] else 'Injury replacement candidate')
        for pid,r in roster.items():
            if r['unavailable'] or norm(r['availability'])=='doubtful':
                r['role_eligible']=False;continue
            recent=sorted(evidence[tid,pid],key=lambda v:v[0],reverse=True)[:3]
            def meaningful(v):
                if r['position']=='QB':return False # Depth chart required for QB1.
                thresholds={'rushing:rushingAttempts':5,'receiving:receivingTargets':3,'receiving:receptions':2,'defensive:totalTackles':3}
                return any(v.get(norm(k.split(':')[0])+':'+norm(k.split(':')[1]),0)>=n for k,n in thresholds.items())
            if not r['role_eligible'] and len(recent)>=2 and (now-recent[0][0]).days<=14 and sum(meaningful(v) for _,v in recent)>=2:
                # Only an actual depth-chart member can become a contributor
                # when the chart is available; failed feeds use recent usage.
                listed=any(pid in ids[:3] for _,ids in slots)
                if listed or not slots:r.update(role_eligible=True,role='Regular contributor' if slots else 'Recent contributor · depth unverified')
            r['role_evidence']='Public depth chart + recent completed-game usage' if slots else 'Depth chart unavailable; recent usage only'
    return rows
