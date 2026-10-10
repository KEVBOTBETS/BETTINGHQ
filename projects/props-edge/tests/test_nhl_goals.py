import copy
import unittest
from pipeline.nhl_goals import forecasts
SEASON=20262027
GAME={'game_id':'g1','date':'2026-10-10T23:00:00Z','home':'TOR','away':'BOS','season_type':2,'projection':{'ratings_known':True,'home_goals':3.2,'away_goals':3.0},'home_stats':{'current':{'gp':2,'gf_pg':3.5},'prior':{'gp':82,'gf_pg':3.1}}}
ROSTER={'TOR':[{'id':'1','player':'Player One','position':'R'},{'id':'2','player':'Goalie','position':'G'}]}
STATS={'TOR':{'season':SEASON,'skaters':[{'playerId':1,'gamesPlayed':2,'goals':3}],'prior':{'skaters':[{'playerId':1,'gamesPlayed':82,'goals':40}]}}}
class Scorers(unittest.TestCase):
 def test_current_sample_shrunk_and_binary(self):
  r=forecasts(GAME,ROSTER,STATS,SEASON)[0]
  self.assertTrue(.25<r['model_prob']<.5);self.assertIsNone(r['line']);self.assertEqual(r['side'],'yes');self.assertEqual(r['prior_games'],82);self.assertEqual(r['inputs']['prior_weight_games'],30);self.assertFalse(r['actionable']);self.assertTrue(r['research_only']);self.assertNotIn('price_american',r);self.assertIn('shootout excluded',r['probability_basis'])
 def test_goalies_missing_history_preseason_unavailable(self):
  self.assertEqual(forecasts(GAME,{'TOR':[ROSTER['TOR'][1]]},STATS,SEASON),[]);self.assertEqual(forecasts(GAME,ROSTER,{},SEASON),[]);self.assertEqual(forecasts({**GAME,'season_type':1},ROSTER,STATS,SEASON),[]);self.assertEqual(forecasts({**GAME,'projection':{'ratings_known':False}},ROSTER,STATS,SEASON),[])
 def test_zero_current_goals_keep_prior_information(self):
  s=copy.deepcopy(STATS);s['TOR']['skaters'][0]['goals']=0;p=forecasts(GAME,ROSTER,s,SEASON)[0]['model_prob'];self.assertTrue(.2<p<.4);s['TOR']['skaters'][0]['gamesPlayed']=60;self.assertLess(forecasts(GAME,ROSTER,s,SEASON)[0]['model_prob'],p)
 def test_partial_roster_not_inflated_total_rates_bounded(self):
  roster={'TOR':[{'id':str(i),'player':'P'+str(i),'position':'R'} for i in range(20)]};s={'TOR':{'season':SEASON,'skaters':[{'playerId':i,'gamesPlayed':60,'goals':50} for i in range(20)]}};self.assertLessEqual(sum(r['expected_goals'] for r in forecasts(GAME,roster,s,SEASON)),3.201);self.assertLess(forecasts(GAME,ROSTER,STATS,SEASON)[0]['expected_goals'],3.2)
 def test_opponent_adjustment_bounded(self):
  lo={**GAME,'projection':{**GAME['projection'],'home_goals':1.7}};hi={**GAME,'projection':{**GAME['projection'],'home_goals':4.6}};l,h=forecasts(lo,ROSTER,STATS,SEASON)[0],forecasts(hi,ROSTER,STATS,SEASON)[0];self.assertLess(l['model_prob'],h['model_prob']);self.assertEqual(l['inputs']['matchup_factor'],.75);self.assertEqual(h['inputs']['matchup_factor'],1.25)
