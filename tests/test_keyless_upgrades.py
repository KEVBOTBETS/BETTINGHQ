from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest
from tools.research import calibration, ingest, readiness, weather_review, efficiency, market

NOW=datetime(2026,10,8,18,tzinfo=timezone.utc)
START=(NOW+timedelta(days=1)).isoformat()

def candidate(**changes):
    return dict(sport='nfl',event_id='game',market='ATS',side='home',line=-3,
                p_win=.6,p_push=.02,price=-110,book='Book',start=START,
                observed_at=NOW.isoformat(),generated_at=NOW.isoformat(),
                baseline_version='v1',rules='full-game',**changes)

class ProspectiveCalibration(unittest.TestCase):
    def test_capture_is_immutable_and_rejects_future_stale_and_started(self):
        rows=calibration.freeze([], [candidate()], NOW)
        self.assertEqual(len(rows),1)
        self.assertEqual(calibration.freeze(rows,[{**candidate(),'p_win':.9}],NOW),rows)
        for changes in [{'start':NOW.isoformat()},{'observed_at':(NOW+timedelta(seconds=1)).isoformat()},
                        {'generated_at':(NOW-timedelta(hours=13)).isoformat()},{'price':-50}]:
            self.assertEqual(calibration.freeze([],[{**candidate(),**changes}],NOW),[])

    def test_training_excludes_future_results_versions_and_duplicate_alternates(self):
        row=calibration.freeze([], [candidate()], NOW)[0]
        row['result']={'outcome':'win','observed_at':(NOW+timedelta(days=2)).isoformat()}
        self.assertEqual(calibration.training([row],('nfl','ATS','v1'),NOW),[])
        later=NOW+timedelta(days=3)
        self.assertEqual(len(calibration.training([row,{**row,'line':-4}],('nfl','ATS','v1'),later)),1)
        self.assertEqual(calibration.training([row],('nfl','ATS','v2'),later),[])
        self.assertFalse(calibration.fit([row],('nfl','ATS','v1'),later)['enabled'])

    def test_push_and_result_timestamp_are_preserved(self):
        rows=calibration.freeze([], [candidate()], NOW)
        later=NOW+timedelta(days=2)
        result={('nfl','game'):{'completed':True,'home_score':24,'away_score':21,'result_observed_at':later.isoformat()}}
        self.assertIsNone(calibration.settle(rows,result,NOW)[0]['result'])
        settled=calibration.settle(rows,result,later)
        self.assertEqual(settled[0]['result']['outcome'],'push')
        self.assertEqual(calibration.report(settled,later)['markets'][0]['graded'],0)

    def test_fixed_slope_preserves_opposites(self):
        for p in [.02,.2,.5,.95]:
            for slope in [.5,.75,1,1.25]:
                self.assertAlmostEqual(calibration.transform(p,slope)+calibration.transform(1-p,slope),1)

class WorkloadIntegrity(unittest.TestCase):
    def test_snap_join_rejects_ambiguous_stale_and_future_data(self):
        dataset={'players':[{'game_id':'g','team':'KC','name':'Patrick Mahomes'}]}
        row={'game_id':'g','team':'KC','player':'Patrick Mahomes','offense_snaps':'60','offense_pct':'.9'}
        feed={'snap_counts':{'rows':[row],'observed_at':NOW.isoformat()}}
        self.assertEqual(ingest.enrich_workload(dataset,feed,NOW)['workload_coverage']['matched_player_games'],1)
        self.assertNotIn('snap_share',dataset['players'][0])
        for stamp,rows in [(NOW.isoformat(),[row,row]),((NOW+timedelta(hours=1)).isoformat(),[row]),((NOW-timedelta(days=8)).isoformat(),[row])]:
            self.assertEqual(ingest.enrich_workload(dataset,{'snap_counts':{'rows':rows,'observed_at':stamp}},NOW)['workload_coverage']['matched_player_games'],0)

    def test_collector_failure_retains_original_source_and_timestamp(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);path=root/'research/inputs/nfl-workload.json';path.parent.mkdir(parents=True)
            original={'snap_counts':{'rows':[{'player':'Old'}],'observed_at':'2026-10-01T00:00:00Z'}}
            path.write_text(json.dumps(original))
            with patch('urllib.request.urlopen',side_effect=OSError('offline')):
                result=ingest.collect_workload(root,now=NOW)
            self.assertEqual(result['snap_counts'],original['snap_counts'])
            self.assertEqual(len(result['errors']),2)

    def test_depth_is_expected_role_and_expires(self):
        row={'dt':NOW.isoformat(),'team':'KC','pos_abb':'QB','pos_rank':'1','player_name':'Patrick Mahomes'}
        feed={'depth_charts':{'observed_at':NOW.isoformat(),'rows':[row]}}
        enriched=ingest.enrich_workload({},feed,NOW)
        self.assertEqual(enriched['expected_starters']['KC']['player'],'Patrick Mahomes')
        self.assertEqual(ingest.enrich_workload({},feed,NOW+timedelta(days=2))['expected_starters'],{})
        status=readiness.availability({'home':'KC','away':'BUF'},{'generated_at':NOW.isoformat()},NOW,enriched['expected_starters'])
        self.assertFalse(status['sides'][0]['starter_confirmed'])

class CoverageIntegrity(unittest.TestCase):
    def test_diagnosis_distinguishes_missing_prices_expired_held_pass_and_qualified(self):
        base={'game_date':START,'odds_observed_at':NOW.isoformat(),'price':-110,'tier':'GOOD','game_id':'g'}
        rows=[base,{**base,'price':None},{**base,'odds_observed_at':(NOW-timedelta(hours=7)).isoformat()},
              {**base,'held':True},{**base,'tier':'PASS'},{**base,'odds_verified':False}]
        report=readiness.health('nfl',{'generated_at':NOW.isoformat()},[{'game_id':'g','date':START},{'game_id':'missing','date':START}],rows,NOW)
        self.assertEqual(report['qualified'],1)
        self.assertEqual(len(report['reasons']),7)

    def test_weather_misalignment_roof_and_unknown_values(self):
        game={'game_id':'g','home':'KC','away':'BUF','date':START,'weather':{'observed_at':NOW.isoformat(),'roof':'open','forecast':{'time_utc':START,'wind_mph':10}}}
        report=weather_review.review('nfl',game,{},NOW)
        self.assertEqual(report['hour_gap'],0)
        self.assertIn('gust_mph',report['missing'])
        game['weather']['forecast']['time_utc']=(NOW+timedelta(days=1,hours=2)).isoformat()
        self.assertEqual(weather_review.review('nfl',game,{},NOW)['status'],'wrong forecast hour')
        game['weather']['roof']='dome'
        self.assertEqual(weather_review.review('nfl',game,{},NOW)['status'],'indoors')

    def test_binary_quotes_require_exact_rule_and_opposite_book_time(self):
        q={'sport':'nfl','event_id':'g','player':'Player','market':'Anytime touchdown','side':'yes','book':'Draft Kings','price':120,'start':START,'observed_at':NOW.isoformat()}
        report,_=market.audit([q,{**q,'side':'no','price':-140,'book':'DraftKings'}],[],NOW)
        self.assertEqual(len(report['groups'][0]['devig_pairs']),1)
        self.assertIsNone(market.normalize({**q,'price_source':'model'},NOW))

    def test_efficiency_shrinks_and_future_games_cannot_change_profiles(self):
        base={'team':'KC','opponent':'BUF','plays':60,'pass_plays':30,'rush_plays':30,'pass_epa':15,'rush_epa':3,'success':30,'explosive':8}
        rows=[{**base,'date':f'2026-09-{i:02d}'} for i in [1,8,15]]
        profile=efficiency.profiles(rows,'2026-10-08')['KC']
        self.assertEqual(profile['current_season_games'],3)
        self.assertLess(profile['efficiency_data_weight'],1)
        self.assertEqual(efficiency.profiles(rows+[{**base,'date':'2026-10-09','pass_epa':9999}],'2026-10-08')['KC'],profile)

if __name__=='__main__':unittest.main()
