import unittest
from datetime import datetime,timezone,timedelta
from pipeline.model import project,candidates
from pipeline.quotes import parse_espn
from pipeline.build import standings,parse_summary
from pipeline import model_accuracy as A
class NBA(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,21,tzinfo=timezone.utc);self.stamp=self.now.isoformat();self.team={'current':{'games':0,'observed_at':self.stamp},'prior':{'games':82,'points_for':110,'points_against':110,'observed_at':self.stamp}}
 def test_prior_and_missing_inputs(self):
  self.assertAlmostEqual(project(self.team,self.team,self.now)['mu'],2)
  self.assertFalse(project({},self.team,self.now)['ratings_known'])
  self.team['current']['games']=1
  self.assertFalse(project(self.team,self.team,self.now)['ratings_known'])
 def test_stale_standings_hold_even_zero_game_teams(self):
  self.team['current']['observed_at']=(self.now-timedelta(days=2)).isoformat()
  self.assertFalse(project(self.team,self.team,self.now)['ratings_known'])
 def test_pairs_no_synthetic_prices(self):
  raw=[{'provider':{'name':'DraftKings'},'pointSpread':{'home':{'current':{'line':0,'odds':-110}},'away':{'current':{'line':0,'odds':-110}}}}]
  q=parse_espn(raw,self.stamp);self.assertEqual(len(q),2);self.assertEqual(q[0]['line'],0)
  del raw[0]['pointSpread']['away']['current']['odds'];self.assertEqual(parse_espn(raw,self.stamp),[])
  self.assertEqual(parse_espn([{'provider':{'name':'DK'},'moneyline':{'home':{'open':{'odds':-110}},'away':{'open':{'odds':-110}}}}],self.stamp),[])
 def test_selection_spread_push_stale_started_research(self):
  q={'market':'ATS','side':'away','line':2,'price':-110,'opposite_price':-110,'book':'DK','observed_at':self.stamp}
  game={'game_id':'1','tipoff':(self.now+timedelta(hours=1)).isoformat(),'state':'pre','season':2027,'season_type':2,'home':{'abbr':'BOS'},'away':{'abbr':'NY'},'quotes':[q],'projection':project(self.team,self.team,self.now)}
  row=candidates(game,self.now)[0];self.assertAlmostEqual(row['model_prob'],.5,places=6);self.assertGreater(row['push_prob'],0);self.assertTrue(row['held']);self.assertEqual(row['stake'],0)
  game['state']='in';self.assertEqual(candidates(game,self.now),[]);game['state']='pre';q['observed_at']=(self.now-timedelta(hours=2)).isoformat();self.assertEqual(candidates(game,self.now),[])
 def test_no_retrospective_predictions(self):
  log={'records':{}};A.record(log,[{'kind':'game','league':'NBA','event_id':'1','start':'2020-01-01T00:00:00Z','matchup':'BOS @ NY','probability':.6}]);self.assertFalse(log['records'])
 def test_cross_event_summary_rejected(self):
  self.assertEqual(parse_summary({'header':{'id':'2'}},{'game_id':'1','tipoff':self.stamp,'home':{'id':'1'},'away':{'id':'2'}},self.stamp),([],[]))
 def test_wrong_standings_season(self):self.assertEqual(standings({'season':2026},2027,self.stamp),{})
if __name__=='__main__':unittest.main()
