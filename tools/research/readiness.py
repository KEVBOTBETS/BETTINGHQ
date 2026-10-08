"""Inspectable forecast/price/availability health and ten-upgrade completion state."""
from collections import Counter
from .common import instant,number,team

def age_status(stamp,now,hours=6):
    at=instant(stamp)
    return 'missing' if not at else 'future' if at>now else 'stale' if (now-at).total_seconds()>hours*3600 else 'fresh'

def availability(game,meta,now,depth=None):
    stamp=meta.get('generated_at');fresh=age_status(stamp,now,6)=='fresh';inj=game.get('injuries') or (game.get('context') or {}).get('injuries') or {};sides=[]
    for side in ['home','away']:
        details=inj.get(side) or {};qb=details.get('qb') or {};value=qb.get('value') or {};status=str(qb.get('status','')).lower()
        starter=value.get('replacement') if qb.get('weight')==1 or status in ['out','inactive','injured reserve'] else qb.get('name') or value.get('starter')
        declaration=(depth or {}).get(team(game,side),{})
        if not starter and declaration.get('fresh'):starter=declaration.get('player')
        uncertain=not starter or qb.get('questionable') or status in ['questionable','doubtful'] or not fresh or not details
        items=details.get('items',[]);out=[x.get('name') for x in items if str(x.get('status','')).lower() in ['out','inactive','injured reserve','suspended']]
        questionable=[x.get('name') for x in items if str(x.get('status','')).lower() in ['questionable','doubtful']]
        uncertain=uncertain or starter in out+questionable or details.get('qb_confident') is False
        line=[x.get('name') for x in items if str(x.get('position','')).upper() in ['OT','T','OG','G','C','OL'] and x.get('name') in out+questionable]
        sides.append({'side':side,'team':team(game,side),'starter':starter,'starter_confirmed':False,'role_status':'uncertain' if uncertain else 'expected starter; verify gameday inactives','missing_report':not bool(details),'absent':out,'questionable':questionable,'offensive_line_flags':line,'observed_at':stamp,'confidence_multiplier':.65 if uncertain else .85 if questionable else 1.,'source':'Published ESPN report / current depth chart; expected role is not a confirmed inactive list'})
    return {'sides':sides,'confidence_multiplier':min(x['confidence_multiplier'] for x in sides),'status':'review' if any(x['missing_report'] or x['role_status']=='uncertain' for x in sides) else 'available','actionable':False}

def health(sport,meta,games,board,now):
    upcoming=[g for g in games if not g.get('completed') and instant(g.get('date')) and instant(g['date'])>now]
    reasons=Counter();fresh=age_status(meta.get('generated_at'),now,6)
    for r in board:
        start=r.get('game_date') or r.get('start_time');when=instant(start)
        if not when or when<=now:reasons['started or unknown kickoff']+=1;continue
        quote=r.get('odds_observed_at') or r.get('updated_at');price=r.get('price',r.get('price_american'))
        if number(price) is None or abs(float(price))<100:reasons['missing usable price']+=1
        elif age_status(quote,now,6)!='fresh':reasons['expired or unknown quote time']+=1
        elif fresh!='fresh':reasons['forecast publication is not fresh']+=1
        elif r.get('held'):reasons['held until betting window']+=1
        elif r.get('tier')=='PASS':reasons[r.get('filtered') or 'model value threshold not met']+=1
        elif r.get('odds_verified') is False:reasons['unverified quote']+=1
        elif r.get('tier') in ['LEAN','GOOD','BEST BET']:reasons['qualified with fresh price']+=1
        else:reasons['research projection only']+=1
    offered={str(r.get('game_id',r.get('event_id'))) for r in board}
    missing=sum(str(g['game_id']) not in offered for g in upcoming)
    if missing:reasons['scheduled games without a market row']=missing
    return {'sport':sport,'publication':fresh,'generated_at':meta.get('generated_at'),'scheduled_games':len(upcoming),'market_rows':len(board),'reasons':[{'reason':r,'count':n} for r,n in reasons.most_common()],'qualified':reasons['qualified with fresh price'],'empty_reason':'No qualified plays; review the breakdown below' if not reasons['qualified with fresh price'] else 'Qualified plays available','note':'Counts describe market rows; missing-market count describes games. PASS is distinct from an outage.'}

def completion():
    return [{'id':i+1,'name':name,'status':'implemented','detail':detail} for i,(name,detail) in enumerate([
      ('Prospective evidence','Immutable captures, market-specific results, date-clustered comparison; promotion disabled.'),
      ('Opponent-adjusted efficiency','Recency and season-weighted pass/rush EPA, success, explosives and pace challenger.'),
      ('Early-season shrinkage','Prior season downweighted; current sample/effective weight and shrinkage displayed.'),
      ('Player workload','Keyless offensive snaps joined to observed targets/carries; shared opportunity simulation.'),
      ('Starter and absence checks','Timestamped expected QB, missing reports, uncertain players and offensive-line flags.'),
      ('Market calibration','Independent sport/market/version slope fits trained only on earlier verified results.'),
      ('Exact quote comparison','Same line, player, book, rules and original observation; opposite prices required for de-vig.'),
      ('Kickoff weather','Hourly time alignment, forecast provenance, gusts/rain and roof status; missing inputs visible.'),
      ('Parlay dependence','Shared game masks, duplicate-contract rejection, explicit supported-market coverage.'),
      ('Empty-board diagnosis','Freshness and exclusion counts distinguish PASS, missing prices, held and expired quotes.')])]
