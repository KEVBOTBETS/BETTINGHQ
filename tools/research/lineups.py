"""Scenario sensitivity around existing forecasts, with no invented participation weights."""
from .common import number, instant

def scenarios(game, sport, now):
    projection=game.get('projection') or {}; base=number(projection.get('mu')); total=number(projection.get('proj_total',projection.get('total')))
    if base is None:return []
    rows=[{'label':'Current forecast','margin':base,'total':total,'kind':'baseline','probability':None,'changes':[]}]
    if sport=='nhl':
        for side in ['home','away']:
            goalie=game.get(side+'_goalie') or {}
            if not goalie.get('confirmed'):
                rows.append({'label':side.title()+' goalie unconfirmed','margin':None,'total':None,'kind':'availability','probability':None,'changes':[goalie.get('name') or 'Starter unknown'],'reason':'No verified replacement-goalie effect. Forecast remains conditional.'})
        challenger=game.get('challenger') or {}
        at=instant(challenger.get('observed_at'))
        if at and at<=now and number(challenger.get('home_goals')) is not None and number(challenger.get('away_goals')) is not None:
            h,a=challenger['home_goals'],challenger['away_goals']
            rows.append({'label':'Existing NHL context experiment','margin':h-a,'total':h+a,'probability':None,'kind':'shadow','changes':challenger.get('missing',[]),'reason':'Unvalidated goalie / special-teams corrections; no promotion.'})
        return rows
    injuries=game.get('injuries') or (game.get('context') or {}).get('injuries') or {}
    for side in ['home','away']:
        details=injuries.get(side) or {}; uncertain=[x for x in details.get('items',[]) if str(x.get('status','')).lower() in ['questionable','doubtful','day-to-day']]
        for item in uncertain[:2]:
            # The existing recorded haircut is used as a sensitivity increment,
            # not misrepresented as a fitted full player value.
            shift=number(item.get('points'))
            if not shift or shift<0:continue
            sign=1 if side=='home' else -1
            for label,direction in [('More available',1),('Less available',-1)]:
                rows.append({'label':item.get('name','Player')+' · '+label,'margin':base+sign*shift*direction,'total':None,'kind':'sensitivity','probability':None,'changes':[item.get('status')],'delta':sign*shift*direction,'reason':'Sensitivity of ± the recorded injury adjustment, not a full replacement value or a participation estimate.'})
    return rows
