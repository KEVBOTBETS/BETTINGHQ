"""Freeze whole-sheet margin forecasts and qualified ATS picks before games.

Historical lines are imported only from timestamped original forecast snapshots.
They have no assumed price. Fresh qualified picks start prospectively; originals
are immutable and one event is counted once in each distinct cohort.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
try:
    from performance import instant, number, LEAGUES
except ImportError:
    from tools.performance import instant, number, LEAGUES

ROOT=Path(__file__).resolve().parents[1]

def read(path,default):
    return json.loads(path.read_text()) if path.exists() else default

def candidate(sport,row):
    mlb=sport=='mlb';nhl=sport=='nhl'
    event=row.get('gamePk') if mlb else (row.get('nhl_game_id') or str(row.get('game_id','')).removeprefix('nhl:')) if nhl else row.get('event_id')
    start=instant(row.get('start'));at=instant(row.get('updated_at') if mlb else row.get('frozen_at') if nhl else row.get('captured_at'))
    margin=number((row.get('projection') or {}).get('mu')) if nhl else number(row.get('margin'))
    if mlb:
        h=number(row.get('proj_home'));a=number(row.get('proj_away'));margin=h-a if h is not None and a is not None else None
    matchup=f"{row.get('away','')} @ {row.get('home','')}" if mlb or nhl else row.get('matchup','')
    if not event or not start or not at or at>=start or margin is None or not matchup or any(t in matchup for t in ['TBD','TBA','Unknown','None']):return None
    spread=number(row.get('market_spread'))
    return dict(id=f'{sport}:{event}:prediction',event_id=str(event),sport=sport,cohort='prediction',matchup=matchup,start=start.isoformat(),captured_at=at.isoformat(),model_margin=margin,home_spread=spread,line_captured_at=at.isoformat() if spread is not None else None,line_observed_at=None,line_origin='Original pregame forecast archive' if spread is not None else None,price=None,book=None,version=row.get('model_version') or row.get('version') or row.get('snapshot_policy') or 'legacy',season=row.get('season') or start.year,status='Pending',audit='Imported frozen forecast; historic quote freshness and price are unavailable.')

def quote_valid(observed,at,start):
    observed=instant(observed)
    return bool(observed and observed<=at<start and (at-observed).total_seconds()<=12*3600)

def call(row):
    gap=row['model_margin']+row['home_spread'] if row.get('home_spread') is not None else None
    return row.get('side') or ('home' if gap is not None and gap>0 else 'away' if gap is not None and gap<0 else None)

def settle(row,home,away,verified_at):
    if row.get('final_home') is not None:return
    h=number(home);a=number(away);at=instant(verified_at);start=instant(row['start'])
    if h is None or a is None or min(h,a)<0 or not at or at<start:return
    row.update(final_home=h,final_away=a,result_at=at.isoformat(),margin_error=round(abs(row['model_margin']-(h-a)),4))
    side=call(row);spread=row.get('home_spread')
    if spread is None:row['status']='No line';return
    if not side:row['status']='No call';return
    cover=h-a+spread
    row['status']='Push' if abs(cover)<1e-9 else 'Win' if (cover>0)==(side=='home') else 'Loss'
    price=number(row.get('price'))
    if price is not None and abs(price)>=100 and row.get('book'):
        row['unit_profit']=0 if row['status']=='Push' else -1 if row['status']=='Loss' else price/100 if price>0 else 100/abs(price)

def fresh_quote(sport,g,at,start):
    odds=g.get('odds') or {}
    if sport=='wnba':
        quotes=odds.get('quotes') or {};h=quotes.get('home_spread') or {};a=quotes.get('away_spread') or {}
        spread=number(h.get('line'));hp=number(h.get('price'));ap=number(a.get('price'));observed=odds.get('fetched_at');book=odds.get('book')
        if spread is None or number(a.get('line')) != -spread:return None
    else:
        spread=number(odds.get('spread_home'));hp=number(odds.get('spread_price_home'));ap=number(odds.get('spread_price_away'));observed=odds.get('observed_at');book=odds.get('book')
    if spread is None or not book or not quote_valid(observed,at,start):return None
    return dict(home_spread=spread,line_captured_at=at.isoformat(),line_observed_at=observed,line_origin='Public book quote',book=book,home_price=hp,away_price=ap)

def update(root=ROOT,now=None):
    now=now or datetime.now(timezone.utc);stamp=now.isoformat();dest=root/'projects/bet-ledger-hq/data/spreads/history.json'
    state=read(dest,{'schema':1,'records':[]});saved={r['id']:r for r in state['records']};coverage={}
    for sport,label in LEAGUES.items():
        folder=root/'projects'/(f'{sport}-edge-lab' if sport!='mlb' else 'mlb-edge')
        raw=read(folder/('data/predictions.json' if sport=='mlb' else 'site/data/accuracy.json'),{})
        snapshots=list(raw.get('games',{}).values()) if sport=='mlb' else [r for r in raw.get('records',[]) if r.get('kind','game')=='game']
        excluded=0
        for r in sorted(snapshots,key=lambda r:str(r.get('captured_at') or r.get('frozen_at') or r.get('updated_at') or '')):
            entry=candidate(sport,r)
            if not entry or instant(entry['captured_at'])>now:excluded+=1;continue
            saved.setdefault(entry['id'],entry)
            final=r.get('result') if sport=='nhl' else None
            final=final if isinstance(final,dict) else {}
            done=bool(final) if sport=='nhl' else r.get('status')=='graded' if sport=='mlb' else r.get('result')=='Graded'
            if done:
                checked=final.get('verified_at') if sport=='nhl' else r.get('graded_at')
                if instant(checked) and instant(checked)<=now:
                    for cohort in ['prediction','qualified']:
                        row=saved.get(entry['id'].replace(':prediction',':'+cohort))
                        if row:settle(row,final.get('home') if sport=='nhl' else r.get('final_home'),final.get('away') if sport=='nhl' else r.get('final_away'),checked)
        meta=read(folder/'site/data/meta.json',{}) if sport!='mlb' else {}
        model_at=instant(meta.get('generated_at'))
        games=read(folder/('site/data/games_detail.json' if sport=='nfl' else 'site/data/games.json'),[]) if sport!='mlb' else []
        board=read(folder/'site/data/board.json',[]) if sport!='mlb' else []
        for g in games:
            event=str(g.get('nhl_game_id') or g.get('game_id')) if sport=='nhl' else str(g.get('game_id'));start=instant(g.get('tipoff') or g.get('date'));key=f'{sport}:{event}:prediction'
            if not start:continue
            # Verified scores can settle an existing frozen forecast, never create a postgame one.
            if g.get('completed') and start<=now:
                def score(side):return (g.get(side) or {}).get('score') if isinstance(g.get(side),dict) else g.get(side+'_score')
                for cohort in ['prediction','qualified']:
                    row=saved.get(f'{sport}:{event}:{cohort}')
                    if row:settle(row,score('home'),score('away'),stamp)
                continue
            if start<=now or g.get('canceled') or g.get('postponed') or not model_at or not model_at<=now<start:continue
            projection=g.get('projection') or {};margin=number(projection.get('margin') if sport=='wnba' else projection.get('mu'))
            if margin is None:continue
            def team(side):return g[side].get('abbr') if isinstance(g.get(side),dict) else g.get(side)
            if not team('home') or not team('away'):continue
            saved.setdefault(key,dict(id=key,event_id=event,sport=sport,cohort='prediction',matchup=f"{team('away')} @ {team('home')}",start=start.isoformat(),captured_at=stamp,source_model_at=model_at.isoformat(),model_margin=margin,home_spread=None,line_captured_at=None,line_observed_at=None,price=None,book=None,version=meta.get('model_version') or meta.get('version') or 'prospective',season=g.get('season') or start.year,status='Pending',audit='First whole-sheet margin captured before game start.'))
            quote=fresh_quote(sport,g,now,start)
            row=saved[key]
            if quote and row.get('home_spread') is None:
                row.update({k:v for k,v in quote.items() if k not in ['home_price','away_price']})
                price=quote.get(call(row)+'_price') if call(row) else None
                if price is not None and abs(price)>=100:row['price']=price
            # A qualified pick is its own frozen cohort. Never retrofit qualification into an old prediction.
            bets=[b for b in board if str(b.get('game_id'))==event and b.get('market')=='ATS' and b.get('side') in ['home','away'] and not b.get('held') and b.get('tier') in ['LEAN','GOOD','BEST'] and (number(b.get('action_edge',b.get('edge_real',b.get('edge')))) or 0)>0]
            for b in bets:
                observed=b.get('odds_observed_at') or b.get('odds_fetched_at');price=number(b.get('price'))
                # Use the game's signed home line: legacy NCAAF board.line uses a home-line convention even for away picks.
                if not quote or b.get('book')!=quote['book'] or not quote_valid(observed,now,start) or observed!=quote['line_observed_at'] or price is None or abs(price)<100 or price!=quote[b['side']+'_price']:continue
                betkey=f'{sport}:{event}:qualified'
                saved.setdefault(betkey,dict(id=betkey,event_id=event,sport=sport,cohort='qualified',matchup=f"{team('away')} @ {team('home')}",start=start.isoformat(),captured_at=stamp,model_margin=margin,side=b['side'],**{k:v for k,v in quote.items() if k not in ['home_price','away_price']},price=price,tier=b['tier'],version=b.get('tier_version') or b.get('model_version') or 'prospective',season=g.get('season') or start.year,status='Pending',audit='First fresh, positive-edge, unheld qualified ATS pick. One unit illustration, not a wager.'))
                break
        coverage[sport]={'label':label,'excluded_snapshots':excluded,'note':'Run/puck lines are tracked only when actually recorded; missing lines remain unscored.' if sport in ['nhl','mlb'] else 'All frozen margin predictions; qualified picks begin with this release.'}
    result={'schema':1,'generated_at':stamp,'records':sorted(saved.values(),key=lambda r:r['start'],reverse=True),'coverage':coverage,'policy':'One first pregame margin per sport/event and one first qualified ATS pick. Frozen selections, lines and prices are never replaced. Historic archived spreads have no assumed price. Wins/(wins+losses); pushes excluded. One-unit quoted-price returns are simulated, not actual wager profit.'}
    dest.parent.mkdir(parents=True,exist_ok=True);temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n');temp.replace(dest)
    return result

if __name__=='__main__':
    data=update();print('Spread audit:',len(data['records']),'frozen records')
