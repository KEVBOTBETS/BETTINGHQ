import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from tools.refresh_policy import PUBLICATIONS, recovery_projects


class RecoveryPolicy(unittest.TestCase):
    def test_narrow_evening_refresh_recovers_stale_football_and_other_boards(self):
        now = dt.datetime(2026, 11, 1, 16, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, relative in PUBLICATIONS.items():
                p = root / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                age = 8 if name in ['nfl-edge-lab', 'props-edge', 'mlb-edge'] else 1
                p.write_text(json.dumps({'generated_at': (now-dt.timedelta(hours=age)).isoformat()}))
            self.assertEqual(recovery_projects(root, ['nba-edge-lab', 'nhl-edge-lab'], now),
                             ['nfl-edge-lab', 'props-edge', 'mlb-edge'])

    def test_missing_invalid_and_future_publications_recover_without_repeating_selected(self):
        now = dt.datetime(2026, 11, 1, 16, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, relative in PUBLICATIONS.items():
                p = root / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps({'generated_at': (now+dt.timedelta(hours=1)).isoformat()}))
            self.assertEqual(set(recovery_projects(root, ['nfl-edge-lab'], now)),set(PUBLICATIONS)-{'nfl-edge-lab'})
            p.unlink()
            self.assertEqual(set(recovery_projects(root, [], now)),set(PUBLICATIONS))
