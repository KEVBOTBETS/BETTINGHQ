import datetime as dt
import unittest
from pipeline.build import ROOT
from basketball_shared.model import project
from basketball_shared.build import normalize
from basketball_shared.game_history import call,repair_college_lines

class CollegeModel(unittest.TestCase):
    def test_college_model_has_its_own_version_and_prior(self):
        now=dt.datetime(2026,11,9,16,tzinfo=dt.timezone.utc);stamp=now.isoformat();team={'current':{'games':3,'points_for':80,'points_against':70,'observed_at':stamp},'prior':{'games':30,'points_for':72,'points_against':68,'observed_at':stamp}}
        p=project(team,team,now,college=True);self.assertTrue(p['ratings_known']);self.assertEqual(p['model_version'],'ncaab-scoring-research-1.0');self.assertEqual(p['prior_weight'],.8)
        self.assertFalse(project({},team,now,college=True)['ratings_known'])
        self.assertEqual(ROOT.name,'ncaab-edge-lab')
    def test_away_spread_keeps_its_selection_sign_and_repairs_pending_encoding_once(self):
        self.assertEqual(call({'market':'ATS','side':'away','line':4},'NCAAB')['line'],4)
        row={'league':'NCAAB','kind':'call','market':'ATS','side':'away','line':-4,'result':'Pending','version':'ncaab-scoring-research-1.0','captured_at':'2026-11-09T05:00Z','probability':.6}
        log={'records':{'a':row}};repair_college_lines(log);repair_college_lines(log)
        self.assertEqual(row['line'],4);self.assertEqual(row['line_encoding_repair']['original_line'],-4);self.assertEqual(row['probability'],.6);self.assertEqual(row['captured_at'],'2026-11-09T05:00Z')
