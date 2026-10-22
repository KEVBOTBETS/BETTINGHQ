import datetime as dt
import unittest
from pipeline.nba_research import watchlist
from pipeline.multisport import parse_offers

class NbaResearch(unittest.TestCase):
    now=dt.datetime(2026,10,22,20,tzinfo=dt.timezone.utc)
    game={'game_id':'401','away':'CLE','home':'PHI','date':'2026-10-22T23:00Z'}
    def test_completed_current_team_history_not_a_forecast(self):
        p=dict(player_id='1',team='CLE',game_id='past',name='Player One',start='2026-10-20T23:00Z',state='post',stats={'MIN':'30','PTS':'24','REB':'7','AST':'4','3PT':'3-8'})
        rows=watchlist([self.game],[p,p,{**p,'game_id':'live','state':'in'},{**p,'game_id':'future','start':'2026-10-23T23:00Z'},{**p,'game_id':'other','team':'PHI'},{**p,'game_id':'dnp','stats':{'MIN':'0','PTS':'0'}}],{'CLE':[{'id':'1','player':'Player One'}]},self.now)
        self.assertEqual(len(rows),7)
        pts=next(r for r in rows if r['market']=='Points');self.assertEqual(pts['samples'],1);self.assertEqual(pts['average'],24);self.assertIsNone(pts['model_prob']);self.assertNotIn('line',pts);self.assertNotIn('price',pts)
        self.assertEqual(next(r for r in rows if r['market']=='Threes')['average'],3)
        self.assertEqual(watchlist([self.game],[p],{'CLE':[{'id':'2','player':'Other'}]},self.now)[0]['samples'],0)
    def test_nba_exact_game_and_roster_offer(self):
        card=['POINTS','CLE @ PHI','CLE','P. One','DraftKings logo','o22.5','-115'];roster={'CLE':[{'id':'1','player':'Player One'}]}
        rows=parse_offers([card],[self.game],roster,'NBA',self.now.isoformat());self.assertEqual(len(rows),1);self.assertEqual(rows[0]['market'],'Points');self.assertEqual(rows[0]['price_american'],-115);self.assertIsNone(rows[0]['model_prob'])
        self.assertEqual(parse_offers([card],[self.game,self.game],roster,'NBA',self.now.isoformat()),[])
        self.assertEqual(parse_offers([card],[self.game],{},'NBA',self.now.isoformat()),[])
