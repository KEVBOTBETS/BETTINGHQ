import copy
from datetime import datetime, timezone, timedelta
import unittest
from pipeline import challenger as C
from pipeline.model import project, update_accuracy, candidates

NOW=datetime(2026,10,10,16,tzinfo=timezone.utc)

class ContextChallengerTests(unittest.TestCase):
    def setUp(self):
        self.team={'current':{'gp':10,'gf_pg':3,'ga_pg':3},'prior':{'gp':82,'gf_pg':3,'ga_pg':3},'stats_season':2027,
                   'context_features':{'observed_at':NOW.isoformat(),'gp':10,'ga_pg':3,'shots_pg':32,'shots_against_pg':30,'pp_pct':.25,'pk_pct':.8,'ot_wins':3,'ot_losses':1}}
        self.game={'game_id':'1','season':2027,'season_type':2,'state':'pre','completed':False,'home':'TOR','away':'MTL','date':(NOW+timedelta(hours=4)).isoformat(),
                   'home_stats':copy.deepcopy(self.team),'away_stats':copy.deepcopy(self.team),'home_goalie':{'name':'Test Goalie','confirmed':True},'away_goalie':{'name':'Test Goalie','confirmed':True},'quotes':[]}
        self.game['projection']=project(self.team,self.team);self.game['p_home']=self.game['projection']['p_home']
        raw={'data':[{'goalieFullName':'Test Goalie','playerId':1,'saves':950,'shotsAgainst':1000}]}
        self.goalies={2027:C.goalie_index(raw,NOW.isoformat(),2027)}
    def test_bounded_adjustments_and_no_input_mutation(self):
        before=copy.deepcopy(self.game);r=C.project(self.game,self.goalies,2027,NOW)
        self.assertEqual(before,self.game);self.assertEqual(r['mode'],'shadow-only')
        self.assertGreater(r['adjustments']['home']['shots'],0)
        self.assertGreater(r['adjustments']['home']['special_teams'],0)
        self.assertLess(r['adjustments']['home']['opponent_goalie'],0)
        self.assertTrue(0<r['p_home']<1)
    def test_goalie_requires_confirmation_and_unambiguous_name(self):
        self.game['away_goalie']['confirmed']=False
        r=C.project(self.game,self.goalies,2027,NOW);self.assertEqual(r['adjustments']['home']['opponent_goalie'],0)
        raw={'data':[{'goalieFullName':'Same','playerId':i,'saves':90,'shotsAgainst':100} for i in (1,2)]}
        self.assertEqual(C.goalie_index(raw,NOW.isoformat(),2027),{})
    def test_stale_and_future_features_are_not_used(self):
        for stamp in [(NOW-timedelta(hours=7)).isoformat(),(NOW+timedelta(minutes=1)).isoformat()]:
            for s in ('home','away'):self.game[s+'_stats']['context_features']['observed_at']=stamp
            r=C.project(self.game,{},2027,NOW)
            self.assertEqual(r['adjustments']['home']['shots'],0);self.assertEqual(r['ot_home_probability'],.5)
            self.assertTrue(r['missing'])
    def test_ot_learns_with_shrinkage_from_known_results(self):
        self.game['away_stats']['context_features'].update(ot_wins=0,ot_losses=4)
        r=C.project(self.game,{},2027,NOW);self.assertTrue(.5<r['ot_home_probability']<=.65)
    def test_shadow_freezes_once_and_never_backfills_old_record(self):
        self.game['challenger']=C.project(self.game,self.goalies,2027,NOW)
        records=update_accuracy({},[self.game],[],NOW.isoformat());saved=copy.deepcopy(records['1']['challenger'])
        self.game['challenger']['p_home']=.99
        update_accuracy(records,[self.game],[],(NOW+timedelta(minutes=1)).isoformat())
        self.assertEqual(records['1']['challenger'],saved)
        del records['1']['challenger'];update_accuracy(records,[self.game],[],NOW.isoformat())
        self.assertNotIn('challenger',records['1'])
    def test_stale_baseline_produces_no_shadow(self):
        self.game['stats_stale']=True;self.assertIsNone(C.project(self.game,{},2027,NOW))
    def test_result_observation_time_stays_stable_until_score_correction(self):
        records=update_accuracy({},[self.game],[],NOW.isoformat())
        final={**self.game,'completed':True,'state':'post','home_score':4,'away_score':3}
        first=(NOW+timedelta(hours=8)).isoformat();later=(NOW+timedelta(days=1)).isoformat()
        update_accuracy(records,[final],[],first);update_accuracy(records,[final],[],later)
        self.assertEqual(records['1']['result']['verified_at'],first)
        update_accuracy(records,[{**final,'home_score':5}],[],later)
        self.assertEqual(records['1']['result']['verified_at'],later)
    def test_tickets_ignore_challenger(self):
        self.game['quotes']=[{'market':'ML','side':'home','line':None,'price':110,'opposite_price':-120,'book':'Book','observed_at':NOW.isoformat()}]
        self.game['day']='2026-10-10';before=candidates(self.game,NOW)
        self.game['challenger']={'p_home':.99};self.assertEqual(candidates(self.game,NOW),before)
