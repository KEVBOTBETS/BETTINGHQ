import datetime as dt
import unittest
from tools.newsletters import active_week, edition, factors

class NewsletterTests(unittest.TestCase):
    now=dt.datetime(2026,10,1,12,tzinfo=dt.timezone.utc)
    def games(self):
        return [{'game_id':'1','date':'2026-10-02T00:00Z','week':5,'season_type':2,'home':'H','away':'A','home_conference':'ACC','away_conference':'ACC'}, {'game_id':'2','date':'2026-09-26T00:00Z','week':4,'season_type':2,'home':'H','away':'B','completed':True,'home_score':20,'away_score':10}, {'game_id':'3','date':'2026-10-10T00:00Z','week':6,'season_type':2,'home':'H','away':'A','completed':True,'home_score':100,'away_score':0}]
    def test_college_week_and_no_future_result_leakage(self):
        self.assertEqual(active_week(self.games(),{},self.now)[0],5)
        notes,context=factors(self.games()[0],self.games(),{},'ncaaf')
        self.assertIn('6.0 days',' '.join(notes));self.assertNotIn('100',' '.join(notes));self.assertIn('ACC',context)
    def test_dated_news_and_exact_week(self):
        news=[{'headline':'Current','published':'2026-10-01T10:00Z','url':'https://example.com'}, {'headline':'Old','published':'2026-09-21T10:00Z','url':'https://example.com'}, {'headline':'Future','published':'2026-10-03T10:00Z','url':'https://example.com'}]
        result=edition('ncaaf',self.games(),{'season':2026},news,self.now)
        self.assertEqual(result['week'],5);self.assertEqual(result['games_count'],1);self.assertEqual([n['headline'] for n in result['headlines']],['Current'])
    def test_nfl_own_calendar(self):
        meta={'current_week':{'week':4,'season_type':2,'start':'2026-09-30T07:00Z','end':'2026-10-07T06:59Z'}}
        self.assertEqual(active_week(self.games(),meta,self.now)[0],4)
        self.assertIsNone(active_week([],{},self.now))

    def test_prior_meeting_and_no_future_meeting(self):
        past={'date':'2025-10-01T00:00Z','season_type':2,'completed':True,'home':'A','away':'H','home_score':10,'away_score':20}
        notes,_=factors(self.games()[0],self.games(),{},'ncaaf',[past])
        self.assertIn('2025-10-01',' '.join(notes))
        self.assertIn('H 20–A 10',' '.join(notes))
