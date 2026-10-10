"""Offline report build; only --capture changes the prospective research archive."""
import argparse
import base64
from collections import defaultdict
from datetime import datetime,timezone,timedelta
import importlib.util
from pathlib import Path
import numpy as np
from .common import read,write,instant,number,decimal,team,cover,summary,VERSION
from . import market,lineups,efficiency,experiments,opportunity,prop_tracking,calibration,readiness,weather_review,ingest

ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=Path('projects/bet-ledger-hq/data/research/history.json')

def current_forecast(root,sport,g,meta):
    projection=g.get('projection') or {};mu=number(projection.get('mu'));p=number(g.get('p_home'))
    line=number((g.get('odds') or {}).get('spread_home'));c=None
    if sport in ['nfl','ncaaf'] and mu is not None:
        spec=importlib.util.spec_from_file_location('research_'+sport+'_model',root/f'projects/{sport}-edge-lab/pipeline/model.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        cfg=meta.get('settings',{}).get('model',{});sd=cfg.get('margin_sd',13.2 if sport=='nfl' else 13)
        dist=module.margin_distribution(mu,sd,cfg.get('use_key_numbers',True));c=cover(dist,line) if line is not None else None
        if p is None:p=module.moneyline_probability(mu,sd,cfg.get('use_key_numbers',True))
    if p is None:return None
    return {'model':'current','version':meta.get('model_version',f'{sport}-current-v1'),'p_home':p,'margin':mu,'home_spread':line,'cover':c,'source_observed_at':meta.get('generated_at'),'mode':'baseline','probability_basis':'Published probability' if g.get('p_home') is not None else 'Existing production probability function with published forecast margin'}

def quotes_for_games(sport,games):
    rows=[]
    for g in games:
        offered=[*(g.get('odds_quotes') or []),*(g.get('quotes') or [])]
        if g.get('odds'):offered.append(g['odds'])
        for q in offered:
            if not isinstance(q,dict):continue
            common={'sport':sport,'event_id':str(g['game_id']),'matchup':f"{team(g,'away')} @ {team(g,'home')}",'book':q.get('book'),'observed_at':q.get('observed_at'),'start':g.get('date'),'rules':'full-game'}
            if q.get('market') in ['ML','ATS','TOTAL'] and q.get('side') and q.get('price') is not None:
                line=number(q.get('line'))
                if q['market']=='ATS' and q['side']=='away' and line is not None:line=-line
                rows.append({**common,'market':q['market'],'line':line,'side':q['side'],'price':q['price']})
                opposite={'home':'away','away':'home','over':'under','under':'over'}.get(q['side'])
                if opposite and q.get('opposite_price') is not None:rows.append({**common,'market':q['market'],'line':line,'side':opposite,'price':q['opposite_price']})
                continue
            for kind,line,fields in [('ML',None,{'home':'ml_home','away':'ml_away'}),('ATS',q.get('spread_home'),{'home':'spread_price_home','away':'spread_price_away'}),('TOTAL',q.get('total'),{'over':'over_price','under':'under_price'})]:
                for side,key in fields.items():
                    if q.get(key) is not None:rows.append({**common,'market':kind,'line':line,'side':side,'price':q[key]})
    return rows

def attach_market_benchmarks(candidates,by_event,now):
    """Freeze an exact paired benchmark, never infer a missing opposite price."""
    enriched=[]
    for original in candidates:
        q=dict(original);q.pop('market_no_push',None);enriched.append(q)
        normalized=market.normalize(q,now)
        if not normalized:continue
        for group in by_event.get((q['sport'],q['event_id']),[]):
            if group['contract']!=normalized['contract']:continue
            pair=next((p for p in group['devig_pairs'] if p['book']==normalized['book']),None)
            same=next((r for r in group['quotes'] if r['book']==normalized['book'] and r['side']==q['side'] and r['observed_at']==normalized['observed_at'] and r['price']==normalized['price']),None)
            if pair and same:q['market_no_push']=pair['probabilities'].get(q['side'])
    return enriched

def build(root=ROOT,out=None,capture=False,now=None):
    now=now or datetime.now(timezone.utc);old=read(root/ARCHIVE,{'forecasts':[],'quotes':[]});dataset=read(root/'research/inputs/nfl-pbp.json',{})
    dataset=ingest.enrich_workload(dataset,read(root/'research/inputs/nfl-workload.json',{}),now)
    rows=dataset.get('teams',[]);trained=efficiency.fit(rows,now.date().isoformat()) if rows and instant(dataset.get('observed_at')) and instant(dataset['observed_at'])<=now else None
    raw=[];allgames={};metas={};results={};games=[];forecasts=[];gaps=[];diagnostics=[];weather=[];calibration_rows=[]
    for sport in ['nfl','ncaaf','nhl']:
        folder=root/f'projects/{sport}-edge-lab';meta=read(folder/'site/data/meta.json',{});metas[sport]=meta
        source=read(folder/('site/data/games_detail.json' if sport=='nfl' else 'site/data/games.json'),[]);allgames[sport]=source
        board=read(folder/'site/data/board.json',[])
        diagnostics.append(readiness.health(sport,meta,source,board,now))
        # Capture canonical home/over probabilities only; opposite sides are not extra samples.
        for q in board:
            if q.get('side') not in ['home','over'] or q.get('market') not in ['ML','ATS','TOTAL']:continue
            calibration_rows.append({'sport':sport,'event_id':str(q.get('game_id')),'market':q['market'],'side':q['side'],'line':q.get('line') if q['market']!='ML' else None,'p_win':q.get('model_prob'),'probability_basis':'conditional','p_push':q.get('push_prob',0),'price':q.get('price'),'book':q.get('book'),'start':q.get('game_date'),'observed_at':q.get('odds_observed_at'),'generated_at':meta.get('generated_at'),'baseline_version':meta.get('model_version') or q.get('tier_version','current-v1'),'rules':'full-game'})
        graded=read(folder/f"state/games_{meta.get('season',now.year)}.json",[]) if sport=='nfl' else source
        for g in graded:
            if g.get('completed'):results[sport,str(g['game_id'])]={**g,'result_observed_at':meta.get('generated_at')}
        upcoming=[g for g in source if instant(g.get('date')) and now<instant(g['date'])<now+timedelta(days=14) and not g.get('completed') and not g.get('canceled') and not g.get('postponed')]
        raw.extend(quotes_for_games(sport,upcoming))
        at=instant(meta.get('generated_at'));fresh=bool(at and at<=now and (now-at).total_seconds()<12*3600)
        for g in upcoming:
            base={'sport':sport,'event_id':str(g['game_id']),'start':g['date'],'matchup':f"{team(g,'away')} @ {team(g,'home')}",'home_name':g['home'].get('name') if isinstance(g.get('home'),dict) else g.get('home_name'),'away_name':g['away'].get('name') if isinstance(g.get('away'),dict) else g.get('away_name')};comparison=[]
            current=current_forecast(root,sport,g,meta) if fresh and not g.get('source_stale') else None
            if current:comparison.append(current)
            candidate=efficiency.forecast(g,dataset,trained,now) if sport=='nfl' else None
            if candidate:comparison.append({**candidate,'model':'efficiency'})
            shadow=g.get('challenger') or {}
            if sport=='nhl' and fresh and number(shadow.get('p_home')) is not None and instant(shadow.get('observed_at')) and instant(shadow['observed_at'])<=now:
                comparison.append({'model':'lineup-context','version':shadow['version'],'p_home':shadow['p_home'],'margin':shadow['home_goals']-shadow['away_goals'],'source_observed_at':shadow['observed_at'],'mode':'shadow','missing':shadow.get('missing',[])})
            if sport in ['nfl','ncaaf']:weather.append(weather_review.review(sport,g,meta,now))
            availability=readiness.availability(g,meta,now,dataset.get('expected_starters',{}) if sport=='nfl' else {}) if sport!='nhl' else {'sides':[],'confidence_multiplier':None,'status':'See goalie scenarios','actionable':False}
            games.append({**base,'availability':availability,'models':comparison,'scenarios':lineups.scenarios(g,sport,now),'status':'Fresh source' if fresh else 'Stale or missing forecast source','season_type':g.get('season_type')})
    prop_raw=[];projections=read(root/'projects/props-edge/site/data/projections.json',[])
    board=read(root/'projects/props-edge/site/data/board.json',[]);props_meta=read(root/'projects/props-edge/site/data/meta.json',{})
    diagnostics.append(readiness.health('props',read(root/'projects/props-edge/site/data/meta.json',{}),allgames.get('nfl',[]),board,now))
    for q in board:
        calibration_rows.append({'sport':'nfl','event_id':str(q.get('event_id')),'market':q['market'],'player':q.get('player'),'side':q['side'],'line':q.get('line'),'p_win':q.get('model_prob'),'p_push':q.get('push_prob',0),'price':q.get('price_american'),'book':q.get('book'),'price_source':q.get('price_source'),'quote_status':q.get('quote_status','observed'),'reference_only':q.get('reference_only',False),'start':q.get('start_time'),'observed_at':q.get('updated_at'),'generated_at':props_meta.get('generated_at'),'baseline_version':q.get('tier_version','props-current-v1'),'rules':'full-game'})
        prop_raw.append({**q,'sport':'nfl','price':q.get('price_american'),'observed_at':q.get('updated_at'),'start':q.get('start_time'),'rules':'full-game'})
    multisport={}
    for sport in ['nhl','ncaaf']:
        feed=read(root/f'projects/props-edge/site/data/{sport}-props.json',{});multisport[sport]={'history_rows':len(feed.get('watchlist',[])),'quotes':len(feed.get('quotes',[])),'opportunity_status':'Historical statistics available; game-level workload input is missing. No opportunity probability generated.'}
        for q in feed.get('quotes',[]):prop_raw.append({**q,'sport':sport,'player_id':q.get('athlete_id'),'price':q.get('price_american'),'start':q.get('start_time'),'rules':'full-game'})
    raw.extend(prop_raw);prices,quote_archive=market.audit(raw,old.get('quotes',[]),now)
    by_event=defaultdict(list)
    for group in prices['groups']:by_event[group['contract'][0],group['contract'][1]].append(group)
    for game in games:
        for group in by_event[game['sport'],game['event_id']]:
            if group['contract'][2]=='ML' and group['devig_pairs']:
                p=float(np.median([q['probabilities']['home'] for q in group['devig_pairs']]))
                game['models'].append({'model':'market','version':'exact-devig-v1','p_home':p,'margin':None,'source_observed_at':max(q['observed_at'] for q in group['quotes']),'mode':'benchmark','books':len(group['devig_pairs'])})
        index={x['model']:x for x in game['models']}
        weight=experiments.ensemble_weight(old.get('forecasts',[]),game['sport'],now,index.get('efficiency',{}).get('version'),index.get('current',{}).get('version'))
        if weight and 'current' in index and 'efficiency' in index:
            w=weight['efficiency_weight'];b,c=index['current'],index['efficiency']
            game['models'].append({'model':'ensemble','version':'prospective-grid-v1','p_home':w*c['p_home']+(1-w)*b['p_home'],'margin':w*c['margin']+(1-w)*b['margin'],'source_observed_at':now.isoformat(),'mode':'shadow','weights':weight})
        for model in game['models']:
            f={**game,**model};f.pop('models');f.pop('scenarios');f.pop('status');f.pop('availability',None);f['cohort']='preseason' if f.get('season_type')==1 else 'regular season'
            ats=[x for x in by_event[game['sport'],game['event_id']] if x['contract'][2]=='ATS' and x['contract'][4]==f.get('home_spread')]
            # ROI only uses the paired same-book original prices; never cherry-pick each side's book.
            if ats:
                pair=next((x for x in ats[0]['devig_pairs']),None)
                if pair:
                    for q in ats[0]['quotes']:
                        if q['book']==pair['book']:f[q['side']+'_price']=q['decimal']
            forecasts.append(f)
    frozen=experiments.freeze(old.get('forecasts',[]),forecasts,now) if capture else old.get('forecasts',[])
    frozen=experiments.settle(frozen,results,now) if capture else frozen
    props=[];simulated=[];workloads=[]
    valid_props=[q for q in [market.normalize(q,now) for q in prop_raw] if q and q['sport']=='nfl' and q['market'] in opportunity.MARKETS]
    for g in allgames['nfl']:
        offers=[q for q in valid_props if q['event_id']==str(g['game_id'])]
        if not offers:continue
        candidates=[p for p in projections if str(p.get('event_id'))==str(g['game_id']) and p['market'] in opportunity.MARKETS]
        arrays,reviews=opportunity.simulate_event(g,candidates,dataset,now)
        available=readiness.availability(g,metas['nfl'],now,dataset.get('expected_starters',{}))
        workloads.extend([{**r,'event_id':str(g['game_id']),'confidence_multiplier':available['confidence_multiplier']} for r in reviews])
        unique={q['id']:q for q in offers}
        for q in unique.values():
            values=arrays.get(q.get('player'),{}).get(opportunity.MARKETS[q['market']])
            if values is None:continue
            probability,hits,pushes=opportunity.price_outcome(values,q['side'],q['line'])
            row={**q,'probability':probability,'simulations':len(values),'actionable':False,'mode':'unvalidated opportunity challenger','availability_confidence':available['confidence_multiplier'],'breakeven':1/q['decimal'],'conditional_ev':probability['win']*(q['decimal']-1)-probability['loss'],'hit_mask':base64.b64encode(np.packbits(hits,bitorder='little').tobytes()).decode(),'push_mask':base64.b64encode(np.packbits(pushes,bitorder='little').tobytes()).decode()}
            props.append(row);simulated.append({**row,'hits':hits,'pushes':pushes})
    tickets=[]
    for book in sorted({q['book'] for q in simulated}):
        # Positive raw simulation EV is exploratory, never a qualification label.
        choices=sorted([q for q in simulated if q['book']==book],key=lambda q:q['conditional_ev'],reverse=True)
        selected=[];players=set()
        for q in choices:
            if q['player'] in players:continue
            players.add(q['player']);selected.append(q)
            if len(selected)==8:break
        for profile,n in [('Core',3),('Longshot',8)]:
            legs=selected[:n]
            if len(legs)<2:continue
            ticket=opportunity.joint_ticket(legs)
            if ticket:tickets.append({'sport':'nfl','profile':profile,'book':book,**ticket,'legs':[{'player':q['player'],'event_id':q['event_id'],'market':q['market'],'side':q['side'],'line':q['line'],'win':q['probability']['win'],'price':q['price']} for q in legs]})
    close_index=defaultdict(list)
    for q in quote_archive:close_index[tuple(q.get('contract',[])),q.get('book'),q.get('side')].append(q)
    clv=[{'sport':q['sport'],'matchup':q.get('matchup'),'market':q['market'],'side':q['side'],'book':q['book'],**c} for q in old.get('quotes',[]) if (c:=market.closing_value(q,close_index[tuple(q.get('contract',[])),q.get('book'),q.get('side')],now))]
    state={'schema':1,'version':VERSION,'updated_at':now.isoformat(),'forecasts':frozen,'quotes':quote_archive}
    prop_archive=prop_tracking.freeze(old.get('prop_forecasts',[]),props,now) if capture else old.get('prop_forecasts',[])
    if capture:prop_archive=prop_tracking.settle(prop_archive,dataset,root/'projects/nfl-edge-lab/state/nflverse_games.csv',now)
    state['prop_forecasts']=prop_archive
    calibration_rows=attach_market_benchmarks(calibration_rows,by_event,now)
    market_archive=calibration.freeze(old.get('market_forecasts',[]),calibration_rows,now) if capture else old.get('market_forecasts',[])
    if capture:market_archive=calibration.attach_props(calibration.settle(market_archive,results,now),prop_archive,now)
    if capture:market_archive=calibration.attach_verified_props(market_archive,read(root/'projects/props-edge/site/data/parlay-results.json',{}).get('records',[]),now)
    state['market_forecasts']=market_archive
    if capture:write(root/ARCHIVE,state)
    result={'schema':1,'version':VERSION,'generated_at':now.isoformat(),'mode':'Local research · promotion disabled','games':games,'market':prices,'props':props,'workloads':workloads,'tickets':tickets,'lab':experiments.report(frozen,now),'prop_lab':prop_tracking.report(prop_archive,now),'closing_prices':clv,'coverage':{'nfl':{'team_games':len(rows),'player_games':len(dataset.get('players',[])),'observed_at':dataset.get('observed_at'),'efficiency_training_games':trained['games'] if trained else 0,'residual_games':len(trained['residuals']) if trained else 0},**multisport},'upgrades':readiness.completion(),'diagnostics':diagnostics,'weather':weather,'market_calibration':calibration.report(market_archive,now),'workload_coverage':dataset.get('workload_coverage',{}),'notes':['NFL efficiency replay uses corrected public data and is exploratory. Prospective captures provide the real test.','NCAAF EPA and NHL ice-time inputs are unavailable; those opportunity challengers abstain. Existing forecasts and price comparisons remain available.','Lineup sensitivities have no invented availability probabilities and do not add a second injury haircut to production.','All new outputs are shadow research. No automatic model promotion or bet placement. Reports are published by the normal release workflow.'],'sources':[{'name':'nflverse play data','url':'https://github.com/nflverse/nflverse-data/releases/tag/pbp'},{'name':'nflverse update schedule','url':'https://nflverse.nflverse.com/articles/nflverse_data_schedule.html'},{'name':'Observed public prop offers','url':'https://www.covers.com/sport/football/nfl/player-props'}]}
    if out:
        write(out,result)
        write(out.with_name('diagnostics.json'),{'generated_at':now.isoformat(),'boards':diagnostics})
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--capture',action='store_true');parser.add_argument('--out',type=Path,default=ROOT/'_site/bet-ledger-hq/data/research/report.json');args=parser.parse_args()
    r=build(out=args.out,capture=args.capture);print({'games':len(r['games']),'props':len(r['props']),'tickets':len(r['tickets']),'captures':r['lab']['records'],'capture_enabled':args.capture})
