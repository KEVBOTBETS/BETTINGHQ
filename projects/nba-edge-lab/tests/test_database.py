import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from pipeline.database import residual_fit, merge_players, market_lines
from pipeline.build import standings

NOW=dt.datetime(2026,11,9,16,tzinfo=dt.timezone.utc)
class BasketballEvidence(unittest.TestCase):
    def test_standings_do_not_overwrite_overall_with_split_stats(self):
        raw={'season':{'year':2027},'standings':{'entries':[{'team':{'id':'a','abbreviation':'A'},'stats':[{'name':'wins','type':'wins','value':3},{'name':'losses','type':'losses','value':1},{'name':'avgPointsFor','type':'avgpointsfor','value':80},{'name':'wins','type':'home_wins','value':1},{'name':'avgPointsFor','type':'vsconf_avgpointsfor','value':0}]}]}}
        row=standings(raw,2027,NOW.isoformat())['a'];self.assertEqual(row['wins'],3);self.assertEqual(row['games'],4);self.assertEqual(row['points_for'],80)
    def test_fit_only_frozen_completed_forecasts_and_is_bounded(self):
        rows={str(i):{'event_id':str(i),'kind':'game','league':'NBA','version':'nba-scoring-research-1.0','start':'2026-11-01T22:00Z','captured_at':'2026-11-01T12:00Z','result':'Graded','margin':0,'actual_margin':30 if i%2 else -30} for i in range(60)}
        fit=residual_fit({'records':rows},NOW);self.assertTrue(fit['active']);self.assertEqual(fit['games'],60);self.assertEqual(fit['margin_sd'],22)
        for r in rows.values():r['captured_at']='2026-11-02T12:00Z'
        self.assertFalse(residual_fit({'records':rows},NOW)['active'])
    def test_player_database_retains_verified_finals_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);row={'game_id':'1','player_id':'2','team':'A','start':'2026-11-01T22:00Z','state':'post','stats':{'PTS':'21'}}
            self.assertEqual(len(merge_players(root,[row,row,dict(row,game_id='live',state='in')],2027,NOW)),1)
            self.assertEqual(len(merge_players(root,[],2027,NOW)),1)
            self.assertEqual(merge_players(root,[],2028,NOW),[])
    def test_market_benchmark_requires_matching_book_pair(self):
        q={'market':'ATS','side':'home','line':-4,'price':-110,'book':'A','observed_at':NOW.isoformat()};g={'quotes':[q,dict(q,side='away',line=4,book='B')]}
        self.assertEqual(market_lines(g,NOW),{})
        g['quotes'][1]['book']='A';self.assertEqual(market_lines(g,NOW)['spread_home'],-4);self.assertEqual(market_lines(g,NOW)['spread_home_source']['book'],'A')
