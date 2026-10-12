import copy,unittest
from datetime import datetime,timezone,timedelta
from tools.nhl_tracking import capture,grade,report
NOW=datetime(2026,10,12,16,tzinfo=timezone.utc)
GAME={'game_id':'g','nhl_game_id':'2026020087','date':'2026-10-12T17:00Z','state':'pre','completed':False}
Q={'event_id':'g','athlete_id':'1','player':'Player One','team':'BUF','matchup':'FLA @ BUF','start_time':GAME['date'],'model_prob':.3,'model_version':'nhl-anytime-gamma-1.0','shadow':{'version':'nhl-role-xg-1.0','model_prob':.35}}
PROPS={'generated_at':NOW.isoformat(),'goal_scorers':[Q]}
class Tracking(unittest.TestCase):
 def test_first_capture_immutable_and_no_post_start_backfill(self):
  a={'records':[]};capture(a,PROPS,[GAME],NOW);self.assertEqual(len(a['records']),2);changed=copy.deepcopy(PROPS);changed['goal_scorers'][0]['model_prob']=.8;capture(a,changed,[GAME],NOW+timedelta(minutes=20));self.assertEqual(a['records'][0]['probability'],.3)
  empty={'records':[]};capture(empty,PROPS,[GAME],NOW+timedelta(hours=2));self.assertEqual(empty['records'],[])
 def test_missing_participation_never_becomes_a_loss(self):
  a={'records':[]};capture(a,PROPS,[GAME],NOW);later=NOW+timedelta(hours=5);final={**GAME,'state':'post','completed':True};result={'gameId':GAME['nhl_game_id'],'playerId':'1','icetime':'0','I_F_goals':'0'}
  grade(a,[final],[result],later.isoformat(),later.isoformat(),later);self.assertIsNone(a['records'][0]['result']);result['icetime']='1200';result['I_F_goals']='1';grade(a,[final],[result],later.isoformat(),later.isoformat(),later);self.assertEqual(a['records'][0]['result'],1)
  r=report(a,later);self.assertEqual(r['paired']['players'],1);self.assertFalse(r['validated']);self.assertIsNone(r['paired']['game_cluster_95_interval'])
 def test_unofficial_or_ambiguous_results_do_not_grade(self):
  a={'records':[]};capture(a,PROPS,[GAME],NOW);later=NOW+timedelta(hours=5);r={'gameId':GAME['nhl_game_id'],'playerId':'1','icetime':'1200','I_F_goals':'1'}
  grade(a,[GAME],[r],later.isoformat(),later.isoformat(),later);self.assertIsNone(a['records'][0]['result'])
  grade(a,[{**GAME,'state':'post','completed':True}],[r,{**r,'I_F_goals':'0'}],later.isoformat(),later.isoformat(),later);self.assertIsNone(a['records'][0]['result'])
