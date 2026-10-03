import copy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import unittest
import numpy as np
from tools.research import common,market,lineups,experiments,efficiency,opportunity,ingest,prop_tracking
from tools.research.build import quotes_for_games

NOW=datetime(2026,10,2,23,30,tzinfo=timezone.utc)
START=(NOW+timedelta(days=1)).isoformat()

def quote(**kw):
    return dict(sport='nfl',event_id='g',book='A',market='ATS',side='home',line=-3,price=-110,observed_at=NOW.isoformat(),start=START,**kw)

def forecast(**kw):
    return dict(sport='nfl',event_id='g',model='current',version='v1',start=START,p_home=.6,margin=3,source_observed_at=NOW.isoformat(),**kw)

class MarketIntegrity(unittest.TestCase):
    def test_nhl_quotes_retain_observation_and_opposite_price(self):
        game={'game_id':'g','date':START,'home':'A','away':'B','quotes':[{'market':'ATS','side':'away','line':1.5,'price':110,'opposite_price':-120,'book':'Book','observed_at':NOW.isoformat()}]}
        rows=quotes_for_games('nhl',[game]);self.assertEqual(len(rows),2);self.assertTrue(all(q['line']==-1.5 for q in rows))
        result,_=market.audit(rows,[],NOW);self.assertEqual(len(result['groups'][0]['devig_pairs']),1)

    def test_line_movement_is_separate_from_same_line_comparison(self):
        q=market.normalize(quote(),NOW)
        now=NOW+timedelta(hours=1)
        r={**quote(),'line':-3.5,'observed_at':now.isoformat()}
        report,_=market.audit([r],[q],now)
        self.assertEqual(report['movements'][0]['line_change'],-.5)
        self.assertEqual(len(report['groups']),1);self.assertFalse(report['groups'][0]['devig_pairs'])
    def test_devig_requires_exact_contract_and_timestamp(self):
        h=quote();a={**h,'side':'away','price':100};result,archive=market.audit([h,a,h],[],NOW)
        self.assertEqual(len(archive),2);self.assertEqual(len(result['groups']),1)
        self.assertAlmostEqual(sum(result['groups'][0]['devig_pairs'][0]['probabilities'].values()),1)
        for changed in [{**a,'line':3},{**a,'rules':'regulation-only'},{**a,'observed_at':(NOW-timedelta(seconds=1)).isoformat()}]:
            result,_=market.audit([h,changed],[],NOW)
            self.assertFalse(any(g['devig_pairs'] for g in result['groups']))

    def test_rejects_future_stale_started_and_unknown_sides(self):
        for q in [{**quote(),'observed_at':(NOW+timedelta(seconds=1)).isoformat()},{**quote(),'observed_at':(NOW-timedelta(hours=13)).isoformat()},{**quote(),'start':NOW.isoformat()},{**quote(),'side':'draw'},{**quote(),'price':-50}]:self.assertIsNone(market.normalize(q,NOW))

    def test_best_price_does_not_mean_best_line(self):
        result,_=market.audit([quote(),{**quote(),'book':'B','price':120},{**quote(),'book':'C','line':-2.5,'price':130}],[],NOW)
        self.assertEqual(len(result['groups']),2);self.assertEqual(result['groups'][0]['best']['home']['book'],'B')

    def test_closing_archive_uses_original_times(self):
        first=market.normalize(quote(),NOW);last={**first,'observed_at':(NOW+timedelta(hours=23)).isoformat(),'decimal':2.1}
        self.assertIsNone(market.closing_value(first,[last],NOW))
        result=market.closing_value(first,[last,{**last,'observed_at':START,'decimal':5}],NOW+timedelta(days=2))
        self.assertAlmostEqual(result['decimal_ratio'],first['decimal']/2.1-1);self.assertEqual(result['minutes_before_start'],60)

class ForecastIntegrity(unittest.TestCase):
    def test_first_capture_is_immutable_and_never_backfilled(self):
        saved=experiments.freeze([], [forecast()],NOW)
        again=experiments.freeze(saved,[{**forecast(),'p_home':.9}],NOW+timedelta(hours=1))
        self.assertEqual(saved,again);self.assertFalse(experiments.freeze([], [forecast()],NOW+timedelta(days=2)))
        self.assertFalse(experiments.freeze([], [{**forecast(),'source_observed_at':(NOW+timedelta(seconds=1)).isoformat()}],NOW))

    def test_settlement_requires_verified_final_and_result_timestamp(self):
        saved=experiments.freeze([], [forecast()],NOW);future=NOW+timedelta(days=2)
        result={'completed':True,'home_score':21,'away_score':17,'result_observed_at':future.isoformat()}
        self.assertIsNone(experiments.settle(saved,{('nfl','g'):result},NOW)[0]['result'])
        self.assertIsNone(experiments.settle(saved,{('nfl','g'):{**result,'completed':False}},future)[0]['result'])
        settled=experiments.settle(saved,{('nfl','g'):result},future)
        self.assertEqual(settled[0]['result']['margin'],4)
        self.assertEqual(experiments.settle(settled,{('nfl','g'):{**result,'home_score':0}},future),settled)

    def test_push_roi_and_metrics_are_distinct(self):
        r={**forecast(),'result':{'home_win':1,'margin':3},'home_spread':-3,'cover':{'win':.6,'loss':.35,'push':.05},'home_price':2}
        m=experiments.metrics([r]);self.assertEqual(m['ats']['push'],1);self.assertEqual(m['roi'],0);self.assertAlmostEqual(m['brier'],.16)
        self.assertIsNone(experiments.metrics([{**r,'home_price':None}])['roi'])

    def test_no_ensemble_before_settled_pairs(self):
        self.assertIsNone(experiments.ensemble_weight(experiments.freeze([], [forecast()],NOW),'nfl',NOW))

    def test_pairing_rejects_different_capture_times(self):
        a={**forecast(),'captured_at':NOW.isoformat(),'result':{'home_win':1,'margin':3}}
        b={**a,'model':'efficiency','captured_at':(NOW+timedelta(hours=1)).isoformat()}
        self.assertEqual(experiments.paired([a,b],'efficiency')['games'],0)

    def test_model_versions_and_preseason_have_separate_metrics(self):
        rows=experiments.freeze([], [forecast()],NOW)
        final=NOW+timedelta(days=2);result={('nfl','g'):{'completed':True,'home_score':21,'away_score':17,'result_observed_at':final.isoformat()}}
        rows=experiments.settle(rows,result,final)
        extra={**rows[0],'id':'other','version':'v2','cohort':'preseason'}
        report=experiments.report(rows+[extra],final)
        self.assertEqual(len(report['models']),2);self.assertTrue(all(x['games']==1 for x in report['models']))

class DeepInputs(unittest.TestCase):
    def test_future_dates_do_not_affect_team_ratings(self):
        row={'game_id':'x','date':'2026-09-20','team':'A','opponent':'B','plays':60,'pass_plays':40,'rush_plays':20,'pass_epa':8,'rush_epa':2,'success':30,'explosive':5}
        base=efficiency.profiles([row],'2026-10-01')
        later={**row,'game_id':'future','date':'2026-10-01','pass_epa':5000}
        self.assertEqual(base,efficiency.profiles([row,later],'2026-10-01'))

    def test_distribution_respects_home_spread_sign_and_push(self):
        r=common.cover({2:.2,3:.3,4:.5},-3);self.assertEqual(r,{'win':.5,'push':.3,'loss':.2})
        dist=common.margin_distribution(3,13,[4]*50);self.assertAlmostEqual(sum(dist.values()),1);self.assertAlmostEqual(common.summary(dist)['mean'],3,places=4)

    def test_lineup_scenarios_are_unweighted_sensitivities(self):
        g={'projection':{'mu':2,'proj_total':44},'injuries':{'home':{'items':[{'name':'QB','status':'Questionable','points':1}]}}}
        rows=lineups.scenarios(g,'nfl',NOW)
        self.assertEqual([r['margin'] for r in rows],[2,3,1]);self.assertTrue(all(r['probability'] is None for r in rows))
        nhl=lineups.scenarios({'projection':{'mu':.2}},'nhl',NOW)
        self.assertEqual(len([r for r in nhl if r['margin'] is None]),2)

    def test_ingestion_requires_verified_completion_for_training(self):
        p={'season_type':'REG','game_id':'x','game_date':'2026-09-01','posteam':'A','defteam':'B','home_team':'A','away_team':'B','total_home_score':'7','total_away_score':'0','play_type':'run','epa':'1','yards_gained':'5'}
        self.assertFalse(ingest.aggregate([p],{})['teams'])
        self.assertFalse(ingest.aggregate([p],{'x':{'home_score':14,'away_score':10,'neutral':True}})['teams'])
        p['game_seconds_remaining']='0'
        d=ingest.aggregate([p],{'x':{'home_score':14,'away_score':10,'neutral':True}})
        self.assertEqual(d['teams'][0]['home_score'],14);self.assertTrue(d['teams'][0]['neutral']);self.assertTrue(d['teams'][0]['result_verified'])
        self.assertIsNone(efficiency.fit(ingest.aggregate([p])['teams']))

class ImportFailure(unittest.TestCase):
    def test_failed_import_does_not_refresh_old_timestamp(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);schedule=root/'projects/nfl-edge-lab/state/nflverse_games.csv';schedule.parent.mkdir(parents=True);schedule.write_text('game_id,home_score,away_score,espn,location\n')
            dest=root/'research/inputs/nfl-pbp.json';old={'observed_at':'2026-09-01T00:00:00+00:00','teams':[{'game_id':'2026_01_A_B'}],'players':[],'sources':[]};common.write(dest,old);before=dest.read_bytes()
            with patch('tools.research.ingest.urllib.request.urlopen',side_effect=OSError('offline')),patch('builtins.print'):
                self.assertEqual(ingest.collect(root,(2026,)),old)
            self.assertEqual(dest.read_bytes(),before)

class SharedOpportunities(unittest.TestCase):
    def test_unknown_quarterback_role_abstains(self):
        g={'game_id':'g','date':START,'home':'A','away':'B'}
        c={'player':'Quarterback Example','team':'A','position':'QB','roster_verified':True}
        d={'observed_at':NOW.isoformat(),'teams':[],'players':[]}
        arrays,notes=opportunity.simulate_event(g,[c],d,NOW,10)
        self.assertFalse(arrays);self.assertIn('starting role',notes[0]['reason'])
    def test_related_leg_joint_probability_uses_shared_draws(self):
        hits=np.array([True,True,False,False]);pushes=np.zeros(4,dtype=bool)
        a={'event_id':'x','player':'A','market':'Receptions','hits':hits,'pushes':pushes,'probability':{'win':.5}}
        b={**a,'player':'B'};ticket=opportunity.joint_ticket([a,b])
        self.assertEqual(ticket['win'],.5);self.assertEqual(ticket['independent_comparison'],.25);self.assertIsNone(ticket['ev'])
        self.assertEqual(opportunity.joint_ticket([a,{**b,'event_id':'y'}])['win'],.25)
        self.assertIsNone(opportunity.joint_ticket([a,a]))

    def test_opportunities_are_nonnegative_and_receptions_bounded(self):
        players=[];teams=[]
        for i in range(4):
            game_id=f'2026_{i:02}_A_B';day=f'2026-09-{i+1:02}'
            teams.extend([{'game_id':game_id,'date':day,'team':t} for t in ['A','B']])
            for t in ['A','B']:
                for pid,name in [(t+'Q','Q.Quarterback'+t),(t+'R','R.Receiver'+t)]:
                    players.append({'game_id':game_id,'date':day,'team':t,'player_id':pid,'name':name,'pass_attempts':30 if pid.endswith('Q') else 0,'passing_yards':250 if pid.endswith('Q') else 0,'targets':8 if pid.endswith('R') else 0,'receptions':6 if pid.endswith('R') else 0,'receiving_yards':90 if pid.endswith('R') else 0,'carries':2,'rush_yards':10})
        d={'observed_at':NOW.isoformat(),'players':players,'teams':teams}
        candidates=[{'player':'ReceiverA R'}] # Explicit names below match the source fingerprint.
        candidates=[{'player':p['name'],'team':p['team'],'roster_verified':True} for p in players[:4]]
        game={'game_id':'future','date':START,'home':'A','away':'B','projection':{'mu':0}}
        arrays,reviews=opportunity.simulate_event(game,candidates,d,NOW,1000)
        self.assertTrue(arrays)
        for values in arrays.values():
            self.assertTrue(np.all(values['receptions']<=values['targets']));self.assertTrue(np.all(values['carries']>=0));self.assertTrue(np.all(values['pass_attempts']>=0))
            for k in ['receiving_yards','rush_yards','passing_yards']:self.assertTrue(np.all(values[k]==np.rint(values[k])))
        self.assertFalse(opportunity.simulate_event(game,candidates,{**d,'observed_at':(NOW+timedelta(seconds=1)).isoformat()},NOW,100)[0])

    def test_missing_opportunity_games_are_not_invented_zeros(self):
        rows=[{'date':'2026-09-01','targets':8},{'date':'2026-09-07','targets':10}]
        self.assertIsNone(opportunity.workload(rows,'2026-10-01'))
        self.assertEqual(opportunity.identity('Tony Pollard'),opportunity.identity('T.Pollard'))

class FrozenProps(unittest.TestCase):
    def offered(self):
        return {**quote(),'sport':'nfl','market':'Rushing yards','player':'Tony Pollard','side':'over','line':50.,'decimal':2.,'probability':{'win':.6,'push':.1,'loss':.3},'model_prob':.5,'push_prob':.1}

    def test_multiple_books_are_one_contract_and_first_prediction_stays_frozen(self):
        q=self.offered();rows=prop_tracking.freeze([], [q,{**q,'book':'B','decimal':2.1}],NOW)
        self.assertEqual(len(rows),2);self.assertTrue(all(r['book']=='B' for r in rows))
        self.assertEqual(prop_tracking.freeze(rows,[{**q,'probability':{'win':.9,'push':0,'loss':.1}}],NOW+timedelta(hours=1)),rows)
        self.assertFalse(prop_tracking.freeze([], [q],NOW+timedelta(days=2)))

    def test_absence_is_not_a_zero_and_pushes_do_not_enter_calibration(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'schedule.csv';path.write_text('game_id,espn\nx,g\n')
            rows=prop_tracking.freeze([], [self.offered()],NOW);later=NOW+timedelta(days=2)
            d={'observed_at':later.isoformat(),'teams':[{'game_id':'x','result_verified':True}],'players':[]}
            self.assertTrue(all(r['result'] is None for r in prop_tracking.settle(rows,d,path,later)))
            d['players']=[{'game_id':'x','name':'T.Pollard','player_id':'p','rush_yards':50}]
            done=prop_tracking.settle(rows,d,path,later);self.assertTrue(all(r['result']['outcome']=='push' for r in done))
            report=prop_tracking.report(done,later)
            self.assertTrue(all(r['brier'] is None and r['pushes']==1 and r['roi']==0 for r in report['models']))
            d['players'].append({'game_id':'x','name':'T.Pollard','player_id':'other','rush_yards':80})
            self.assertTrue(all(r['result'] is None for r in prop_tracking.settle(rows,d,path,later)))

class RealReport(unittest.TestCase):
    def test_real_feed_is_strict_json_and_all_experiments_abstain_from_actions(self):
        root=Path(__file__).resolve().parents[1];path=root/'_site/bet-ledger-hq/data/research/report.json'
        if not path.exists():self.skipTest('Build the site first')
        d=json.loads(path.read_text());self.assertEqual(d['schema'],1);self.assertTrue(d['games'])
        self.assertTrue(all(q['actionable'] is False for q in d['props']));self.assertTrue(all(t['ev'] is None and t['combined_price'] is None for t in d['tickets']))
        self.assertTrue(all(instant_time<common.instant(q['start']) for g in d['market']['groups'] for q in g['quotes'] if (instant_time:=common.instant(q['observed_at']))))

if __name__=='__main__':unittest.main()
