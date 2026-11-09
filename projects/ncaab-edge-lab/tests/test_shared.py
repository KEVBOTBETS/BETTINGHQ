import datetime as dt
import unittest
from pipeline.build import ROOT
from basketball_shared.model import project
from basketball_shared.build import normalize

class CollegeModel(unittest.TestCase):
    def test_college_model_has_its_own_version_and_prior(self):
        now=dt.datetime(2026,11,9,16,tzinfo=dt.timezone.utc);stamp=now.isoformat();team={'current':{'games':3,'points_for':80,'points_against':70,'observed_at':stamp},'prior':{'games':30,'points_for':72,'points_against':68,'observed_at':stamp}}
        p=project(team,team,now,college=True);self.assertTrue(p['ratings_known']);self.assertEqual(p['model_version'],'ncaab-scoring-research-1.0');self.assertEqual(p['prior_weight'],.8)
        self.assertFalse(project({},team,now,college=True)['ratings_known'])
        self.assertEqual(ROOT.name,'ncaab-edge-lab')
