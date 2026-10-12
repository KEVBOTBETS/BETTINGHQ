import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from tools.system_report import build
NOW=datetime(2026,10,12,16,tzinfo=timezone.utc)
class SystemReport(unittest.TestCase):
 def make(self,root,sport,name,obj):
  p=root/'projects'/f'{sport}-edge-lab'/'site/data'/f'{name}.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj))
 def test_all_games_remain_visible_but_stale_prices_never_qualify(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.make(root,'nhl','meta',{'generated_at':NOW.isoformat()});g={'game_id':'g','date':'2026-10-12T23:00Z','state':'pre','home':'BUF','away':'FLA','projection':{'p_home':.6,'mu':.3},'p_home':.6};self.make(root,'nhl','games',[g]);q={'game_id':'g','market':'ML','side':'home','price':110,'book':'Book','model_prob':.6,'stake':1,'held':False,'odds_verified':True,'odds_observed_at':'2026-10-12T10:00Z'};self.make(root,'nhl','board',[q]);r=build(root,NOW);self.assertEqual(len(r['games']),1);self.assertFalse(r['games'][0]['qualified']);self.assertTrue(r['games'][0]['manual_available']);self.assertIsNone(r['games'][0]['best']['price']);self.assertEqual(r['games'][0]['p_home'],.6)
 def test_policy_pause_and_future_timestamps_fail_closed(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.make(root,'nhl','meta',{'generated_at':NOW.isoformat()});self.make(root,'nhl','games',[{'game_id':'g','date':'2026-10-12T23:00Z','state':'pre','home':'BUF','away':'FLA','p_home':.6}]);q={'game_id':'g','market':'ML','side':'home','price':110,'book':'Book','model_prob':.6,'stake':1,'held':False,'odds_verified':True,'odds_observed_at':NOW.isoformat(),'value_policy':{'passes':False}};self.make(root,'nhl','board',[q]);self.assertFalse(build(root,NOW)['games'][0]['qualified']);q['value_policy']['passes']=True;q['odds_observed_at']='2026-10-12T17:00Z';self.make(root,'nhl','board',[q]);self.assertFalse(build(root,NOW)['games'][0]['qualified'])
 def test_started_cancelled_and_unknown_games_excluded(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.make(root,'nhl','meta',{'generated_at':NOW.isoformat()});self.make(root,'nhl','games',[{'game_id':'g','date':'2026-10-12T15:00Z','state':'pre'},{'game_id':'h','date':'2026-10-12T23:00Z','state':'unknown'}]);self.assertEqual(build(root,NOW)['games'],[])
