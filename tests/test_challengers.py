import copy
from datetime import datetime, timedelta, timezone
import unittest
from tools.challengers import evaluate, calibrate, compare

class ChronologicalTests(unittest.TestCase):
    def records(self, count=45):
        base=datetime(2026,1,1,tzinfo=timezone.utc)
        rows=[]
        for i in range(count):
            start=base+timedelta(days=i,hours=20)
            rows.append(dict(id=str(i),sport='nfl',version='v1',start=start.isoformat(),captured_at=(start-timedelta(hours=2)).isoformat(),result_at=(start+timedelta(hours=4)).isoformat(),p=.8,y=i%2,market=.5))
        return rows
    def report(self, rows):
        return evaluate(rows)['leagues']['nfl']['models'][0]
    def test_no_future_results_and_same_game_never_trains(self):
        rows=self.records(); first=self.report(rows)['predictions'][0]
        self.assertEqual(first['id'],'40');self.assertEqual(first['training_games'],40)
        future=copy.deepcopy(rows)
        for r in future[40:]:r['y']=1
        self.assertEqual(self.report(future)['predictions'][0],first)
    def test_delayed_results_not_assumed_available_at_start(self):
        rows=self.records()
        for r in rows:r['result_at']='2026-12-01T00:00:00Z'
        self.assertEqual(self.report(rows)['n'],0)
    def test_missing_result_times_excluded(self):
        rows=self.records();rows[0]['result_at']=None
        result=evaluate(rows)['leagues']['nfl'];self.assertEqual(result['excluded_result_time'],1)
        self.assertEqual(result['models'][0]['n'],4)
    def test_versions_and_leagues_never_pool_training(self):
        rows=self.records()
        for r in rows[20:]:r['version']='v2'
        self.assertTrue(all(m['n']==0 for m in evaluate(rows)['leagues']['nfl']['models']))
        for r in rows[20:]:r['sport']='mlb';r['version']='v1'
        self.assertTrue(all(m['n']==0 for s in ('nfl','mlb') for m in evaluate(rows)['leagues'][s]['models']))
    def test_shadow_snapshot_after_original_forecast_is_rejected(self):
        row=self.records(1)[0];row['sport']='nhl'
        row['challenger']={'version':'test','p_home':.7,'observed_at':row['start']}
        reports=evaluate([row])['leagues']['nhl']['models']
        self.assertFalse(any(m['version']=='test' for m in reports))
        row['challenger']['observed_at']=row['captured_at']
        reports=evaluate([row])['leagues']['nhl']['models']
        self.assertEqual(next(m for m in reports if m['version']=='test')['n'],1)
    def test_same_day_samples_do_not_pass_evidence_gate(self):
        rows=[dict(r,challenger=.5,start='2026-01-01T20:00Z') for r in self.records(150)]
        self.assertEqual(compare(rows)['status'],'insufficient-evidence')
        self.assertFalse(compare(rows)['promotion_enabled'])
    def test_symmetric_calibration(self):
        self.assertAlmostEqual(calibrate(.3,.75)+calibrate(.7,.75),1)
        self.assertEqual(calibrate(.5,.5),.5)

