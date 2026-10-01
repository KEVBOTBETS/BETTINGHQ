import unittest
from tools.release_fingerprint import publication

class ReleaseCertificate(unittest.TestCase):
    def test_data_only_paths(self):
        for p in ['projects/nhl-edge-lab/site/data/meta.json', 'projects/nfl-edge-lab/state/history_2026.json', 'projects/mlb-edge/data/predictions.json', 'projects/ladderbet/docs/index.html']:
            self.assertTrue(publication(p), p)
    def test_code_and_configuration_always_invalidate(self):
        for p in ['.github/workflows/release.yml', 'tools/verify.py', 'requirements-lock.txt', 'projects/bet-ledger-hq/package-lock.json', 'projects/nhl-edge-lab/config/settings.json', 'projects/nhl-edge-lab/state/helper.py', 'projects/ncaaf-edge-lab/site/index.html', 'projects/bet-ledger-hq/sports.json']:
            self.assertFalse(publication(p), p)
