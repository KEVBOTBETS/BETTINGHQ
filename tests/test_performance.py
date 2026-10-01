import unittest
from tools.performance import normalize, season_of

class ForecastAudit(unittest.TestCase):
    def row(self, **extra):
        return dict(event_id='1',matchup='AWAY @ HOME',start='2026-10-01T20:00:00Z',captured_at='2026-10-01T18:00:00Z',probability=.7,result='Graded',final_home=20,final_away=10,margin=7,total=35,market_spread=-6,**extra)
    def test_only_pregame_and_resolved_teams(self):
        for change,reason in [({'captured_at':'2026-10-01T20:00:00Z'},'missing or non-pregame snapshot'),({'captured_at':'2026-10-01T18:00:00'},'missing or non-pregame snapshot'),({'matchup':'TBD @ TBD'},'unresolved teams'),({'probability':None},'invalid probability'),({'probability':True},'invalid probability'),({'result':'Pending'},'awaiting verified result'),({'final_home':10},'tied game (no binary winner)')]:
            r,why=normalize('nfl',{**self.row(),**change});self.assertIsNone(r);self.assertEqual(why,reason)
    def test_pair_is_not_inferred_from_spread_or_later_price(self):
        r,_=normalize('nfl',self.row());self.assertIsNone(r['market']);self.assertEqual(r['market_margin'],6)
        pair={'p_home':.6,'observed_at':'2026-10-01T18:01:00Z'}
        r,_=normalize('nfl',self.row(market_snapshot=pair));self.assertIsNone(r['market'])
        pair['observed_at']='2026-10-01T17:59:00Z';r,_=normalize('nfl',self.row(market_snapshot=pair));self.assertEqual(r['market'],.6)
    def test_mlb_uses_latest_snapshot_not_first_seen(self):
        row={'gamePk':1,'home':'HOME','away':'AWAY','start':'2026-10-01T20:00Z','updated_at':'2026-10-01T21:00Z','first_seen':'2026-10-01T18:00Z','p_home':.7,'status':'graded','final_home':4,'final_away':2}
        self.assertEqual(normalize('mlb',row)[1],'missing or non-pregame snapshot')
    def test_malformed_season_does_not_crash_audit(self):
        self.assertIsNone(season_of({"start":"broken", "season":"unknown"}))
        self.assertEqual(season_of({"start":"2026-10-01T20:00Z"}),2026)
    def test_nhl_actual_score_required(self):
        row={'game_id':'1','home':'TOR','away':'MTL','start':'2026-10-01T20:00Z','frozen_at':'2026-10-01T18:00Z','p_home':.6,'result':{'home_won':True}}
        self.assertEqual(normalize('nhl',row)[1],'awaiting verified result')
