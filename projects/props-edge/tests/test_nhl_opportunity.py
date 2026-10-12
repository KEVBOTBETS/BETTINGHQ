import unittest,copy
from pipeline.nhl_opportunity import forecasts
GAME={'game_id':'g','home':'BUF','away':'FLA','public_context':{'projection':{'ratings_known':True,'home_goals':3,'away_goals':3},'team_rates':{'home':{'xgf':3,'shots_for':30},'away':{'shots_against':30}}}}
BASE=[{'event_id':'g','athlete_id':'1','team':'BUF','player':'Player One','position':'R'}]
INPUT={'year':2026,'lineups':{'BUF':{'observed_at':'2026-10-12T16:00Z','updated_at':'2026-10-12T15:00Z','players':[{'name':'Player One','available':True,'line':'f1','power_play':'pp1','season':{'gamesPlayed':5,'toiMinutes':100,'toiSeconds':0},'last5':{'gamesPlayed':5,'toiMinutes':110,'toiSeconds':0}}]}},'statistics':{'2026':{'skaters':{'rows':[{'playerId':'1','name':'Player One','team':'BUF','situation':'all','games_played':5,'icetime':6000,'I_F_xGoals':2,'I_F_goals':3,'I_F_shotsOnGoal':15}]}},'2025':{'skaters':{'rows':[{'playerId':'1','name':'Player One','team':'BUF','situation':'all','games_played':80,'icetime':86400,'I_F_xGoals':30,'I_F_goals':35,'I_F_shotsOnGoal':240}]}}}}
class Opportunity(unittest.TestCase):
 def test_real_role_and_shot_counts_give_bounded_research(self):
  r=forecasts(GAME,BASE,INPUT)[('g','1')];self.assertTrue(0<r['model_prob']<.7);self.assertEqual(r['line'],'f1');self.assertGreater(r['expected_shots'],r['expected_goals']);self.assertFalse(r['validated']);self.assertTrue(r['research_only'])
 def test_missing_roles_injuries_and_ambiguous_player_abstain(self):
  self.assertEqual(forecasts(GAME,BASE,{}),{})
  data=copy.deepcopy(INPUT);data['lineups']['BUF']['players'][0]['available']=False;self.assertEqual(forecasts(GAME,BASE,data),{})
  data=copy.deepcopy(INPUT);data['statistics']['2026']['skaters']['rows'][0]['name']='Different Player';data['statistics']['2025']['skaters']['rows']=[];self.assertEqual(forecasts(GAME,BASE,data),{})
 def test_more_minutes_changes_chance_without_a_fixed_pp_boost(self):
  old=forecasts(GAME,BASE,INPUT)[('g','1')]['model_prob'];data=copy.deepcopy(INPUT);data['lineups']['BUF']['players'][0]['last5']['toiMinutes']=70
  self.assertLess(forecasts(GAME,BASE,data)[('g','1')]['model_prob'],old)
