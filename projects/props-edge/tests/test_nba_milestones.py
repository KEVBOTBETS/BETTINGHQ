import datetime as dt
import unittest
from pipeline.nba_milestones import game_log, forecasts

class Milestones(unittest.TestCase):
    now=dt.datetime(2026,10,23,tzinfo=dt.timezone.utc)
    def test_log_regular_completed_no_future_dnp_allstar_or_duplicates(self):
        events={str(i):dict(gameDate='2026-04-10T20:00Z',gameResult='W',score='100-90',team={}) for i in range(5)}
        events['1']['gameDate']='2027-04-10T20:00Z';events['2']['team']={'isAllStar':True};events['3']['gameResult']=''
        rows=[{'eventId':str(i),'stats':['30','25','3-7']} for i in range(5)]+[{'eventId':'0','stats':['30','25','3-7']}]
        rows[-2]['stats'][0]='0'
        payload={'labels':['MIN','PTS','3PT'],'events':events,'seasonTypes':[{'displayName':'2025-26 Regular Season','categories':[{'events':rows}]},{'displayName':'2025-26 Postseason','categories':[{'events':[{'eventId':'4','stats':['30','80','8-8']}]}]}]}
        actual=game_log(payload,self.now);self.assertEqual(len(actual),1);self.assertEqual(actual[0]['stats']['PTS'],25);self.assertEqual(actual[0]['stats']['3PT'],3)
    def fixture(self):
        q={'sport':'NBA','event_id':'future','athlete_id':'1','player':'Test Player','team':'CLE','market':'Points','roster_verified':True,'start_time':'2026-10-24T23:00Z'}
        past=[dict(game_id=str(i),start=f'2026-04-{i+1:02}T23:00Z',minutes=30,stats={'PTS':15+i}) for i in range(20)]
        current=[dict(player_id='1',team='CLE',game_id='current',start='2026-10-21T23:00Z',state='post',stats={'MIN':'30','PTS':'30'})]
        return q,past,current
    def test_thresholds_smoothed_and_monotonic_no_book_odds(self):
        q,past,current=self.fixture();rows=forecasts([q],{'1':past},current,[],self.now)
        self.assertTrue(rows);self.assertEqual(rows[0]['current_samples'],1);self.assertEqual(rows[0]['prior_samples'],20)
        byline=sorted(rows,key=lambda q:q['threshold']);self.assertEqual([r['model_prob'] for r in byline],sorted([r['model_prob'] for r in byline],reverse=True))
        for r in rows:self.assertLess(r['ranking_prob'],r['model_prob']);self.assertEqual(r['line'],r['threshold']-.5);self.assertFalse(r['qualified']);self.assertNotIn('price',r)
    def test_sparse_injured_low_minutes_and_future_excluded(self):
        q,past,current=self.fixture()
        self.assertEqual(forecasts([q],{'1':past[:3]},current,[],self.now),[])
        self.assertEqual(forecasts([q],{'1':past},current,[{'name':'Test Player','status':'Out'}],self.now),[])
        self.assertEqual(forecasts([q],{'1':past},[{**current[0],'stats':{'MIN':'8','PTS':'30'}}],[],self.now),[])
        future=[{**p,'start':'2027-01-01T00:00Z'} for p in past]
        self.assertEqual(forecasts([q],{'1':future},current,[],self.now),[])
