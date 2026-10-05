import unittest
from pipeline.multisport import NHL_CODES, nhl_watchlist, MatchupLinks
class Repairs(unittest.TestCase):
 def test_official_team_aliases(self):
  self.assertEqual(NHL_CODES['TB'],'TBL');self.assertEqual(NHL_CODES['SJ'],'SJS');self.assertEqual(NHL_CODES['NJ'],'NJD')
 def test_early_season_history_visible_and_labelled(self):
  g={'game_id':'1','date':'2026-10-06T00:00Z','away':'SJ','home':'DAL'}
  rows=nhl_watchlist(g,{'SJ':[{'id':'1','player':'Real Player'}]}, {'SJ':{'season':20262027,'skaters':[{'playerId':1,'gamesPlayed':2,'shots':9,'goals':0,'assists':0,'points':0}]}},20262027)
  self.assertEqual(rows[0]['average'],4.5);self.assertEqual(rows[0]['samples'],2);self.assertIn('Small current-season sample',rows[0]['history_note']);self.assertIsNone(rows[0]['model_prob'])
 def test_only_advertised_game_links(self):
  p=MatchupLinks('NHL');p.feed('<a href="/sport/hockey/nhl/matchup/382316/odds"><span>PHI</span> at <span>TB</span></a><a href="https://evil.example">fake</a>')
  self.assertEqual(len(p.links),1);self.assertEqual(p.links[0]['label'],'PHI at TB');self.assertEqual(p.links[0]['url'],'https://www.covers.com/sport/hockey/nhl/matchup/382316/odds')
