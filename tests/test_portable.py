import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PortableRelease(unittest.TestCase):
    def test_only_recovered_sports_are_active(self):
        registry=json.loads((ROOT/'projects/bet-ledger-hq/sports.json').read_text())
        self.assertEqual({r['key'] for r in registry if r['active']},{'nfl','ncaaf','mlb','wnba','props','ladder'})

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

    def test_ladder_public_page_never_imports_repo_wagers(self):
        page=(ROOT/'_site/ladderbet/index.html').read_text()
        data=json.loads(re.search(r'<script type="application/json" id="ladder-data">(.*?)</script>',page,re.S)[1])
        self.assertEqual(data['history'],[])
        self.assertEqual(data['state']['rung'],0)

    def test_restored_props_accuracy_has_all_original_forecasts(self):
        data=json.loads((ROOT/'projects/props-edge/state/model_accuracy.json').read_text())
        self.assertGreaterEqual(len(data['records']),26506)
        summary=json.loads((ROOT/'_site/props-edge/data/accuracy-summary.json').read_text())
        self.assertIn('props',summary)
        self.assertNotIn('records',summary)

    def test_shared_sync_engine_is_identical(self):
        reference=(ROOT/'projects/bet-ledger-hq/betsync.js').read_bytes()
        for p in ['wnba-edge-lab/site','props-edge/site','ladderbet/docs']:
            self.assertEqual((ROOT/'projects'/p/'betsync.js').read_bytes(),reference)

    def test_recovered_history_stays_present(self):
        for repo,file in [('nfl-edge-lab','state/model_accuracy.json'),('ncaaf-edge-lab','state/model_accuracy.json'),('mlb-edge','data/predictions.json')]:
            self.assertTrue((ROOT/'projects'/repo/file).is_file())

if __name__=='__main__':unittest.main()
