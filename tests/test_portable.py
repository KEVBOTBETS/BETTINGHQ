import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PortableRelease(unittest.TestCase):
    def test_only_recovered_sports_are_active(self):
        registry=json.loads((ROOT/'projects/bet-ledger-hq/sports.json').read_text())
        self.assertEqual({r['key'] for r in registry if r['active']},{'nfl','ncaaf','mlb'})

    def test_public_site_has_no_old_account_dependency(self):
        for p in (ROOT/'_site').rglob('*'):
            if p.suffix in {'.html','.js','.css','.webmanifest'}:
                self.assertNotIn('chillychilly14.github.io',p.read_text().lower(),str(p))

    def test_all_hub_board_targets_exist(self):
        hub=ROOT/'_site/bet-ledger-hq'
        targets=re.findall(r'url:"([^"]+)"',(hub/'hub.js').read_text())
        self.assertGreaterEqual(len(targets),8)
        for target in targets:
            p=hub/target
            self.assertTrue(p.exists(),str(p))

    def test_no_public_financial_ledgers(self):
        for p in (ROOT/'_site').glob('*/data/ledger.json'):
            self.assertEqual(json.loads(p.read_text()),[],str(p))

    def test_recovered_history_stays_present(self):
        for repo,file in [('nfl-edge-lab','state/model_accuracy.json'),('ncaaf-edge-lab','state/model_accuracy.json'),('mlb-edge','data/predictions.json')]:
            self.assertTrue((ROOT/'projects'/repo/file).is_file())

if __name__=='__main__':unittest.main()
