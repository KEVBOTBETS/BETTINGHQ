import unittest
from pipeline.multisport import parse_offers
from pipeline.public_markets import parse_game,match_game,advertised
from datetime import datetime,timezone
class Markets(unittest.TestCase):
 now=datetime(2026,10,29,12,tzinfo=timezone.utc)
 g={'game_id':'1','date':'2026-10-29T23:00Z','away':'WPG','home':'TB'}
 def test_modern_nba_card_matches_roster_without_team_abbreviation(self):
  g={**self.g,'away':'LAL','home':'LAC'};rosters={'LAC':[{'id':'1','player':'Brook Lopez'}]}
  card=['POINTS SCORED','LAL @ LAC','Brook Lopez logo','LA Clippers image thumbnail','B. Lopez','(C)','u11.5 Points Scored','9.45 UNDER','PROJECTION','DraftKings logo','u10.5','-101']
  q=parse_offers([card],[g],rosters,'NBA',self.now.isoformat());self.assertEqual(len(q),1);self.assertEqual(q[0]['line'],10.5);self.assertEqual(q[0]['price_american'],-101);self.assertIsNone(q[0]['model_prob'])
  self.assertEqual(parse_offers([card],[g],{**rosters,'LAL':rosters['LAC']},'NBA',self.now.isoformat()),[]);self.assertEqual(parse_offers([card],[{**g,'date':'2026-10-28T23:00Z'}],rosters,'NBA',self.now.isoformat()),[])
 def html(self):return '<title>Jets vs Lightning Odds For October 29, 2026 - NHL</title><article><header>Goals Scored Collapse Card</header><div><a href="/sport/hockey/nhl/players/1/player-one">Player One</a><table class="compareOddsTable"><tr><th class="sportsbookLogoContainer"><img alt="DraftKings logo"></th><td class="compareOddsSide">o0.5 +190</td></tr><tr><th class="sportsbookLogoContainer"><img alt="Consensus"></th><td class="compareOddsSide">o0.5 +999</td></tr></table></div></article>'
 def test_named_book_goal_market_and_unique_roster(self):
  q=parse_game(self.html(),self.g,{'TB':[{'id':'9','player':'Player One'}]},'NHL',self.now.isoformat(),'https://www.covers.com/sport/hockey/nhl/matchup/1/odds');self.assertEqual(len(q),1);self.assertEqual(q[0]['market'],'Anytime goal');self.assertEqual(q[0]['side'],'yes');self.assertIsNone(q[0]['line']);self.assertEqual(q[0]['price_american'],190)
  self.assertEqual(parse_game(self.html(),self.g,{},'NHL',self.now.isoformat(),'url'),[])
 def test_game_page_requires_date_pair_and_clock(self):
  self.assertEqual(match_game('WIN at TB 19:00 ET',self.html(),[self.g],self.now),self.g)
  self.assertIsNone(match_game('WIN at TB 20:00 ET',self.html(),[self.g],self.now));self.assertIsNone(match_game('WIN at TB 19:00 ET',self.html().replace('October 29','October 28'),[self.g],self.now));self.assertIsNone(match_game('WIN at TB 19:00 ET',self.html(),[self.g,self.g],self.now))
  self.assertEqual(advertised('<a href="https://evil.com/matchup/1/odds">link</a>','NHL'),{})

 def test_known_nhl_inactive_and_questionable_statuses_follow_the_source(self):
  from pipeline.multisport import nhl_availability
  rows=[{'team':'TB','player':'Victor Hedman'},{'team':'TB','player':'Jake Guentzel'}];inputs={'lineups':{'TBL':{'players':[{'name':'Victor Hedman','available':False},{'name':'Jake Guentzel','available':True,'questionable':True}],'updated_at':'2026-10-29T11:00Z'}}}
  nhl_availability(rows,inputs);self.assertEqual(rows[0]['status'],'inactive');self.assertEqual(rows[1]['status'],'questionable');self.assertNotIn('model_prob',rows[0])
