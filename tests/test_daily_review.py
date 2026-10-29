import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from tools.daily_review import prop_coverage, review


class DailyReviewTests(unittest.TestCase):
    def test_only_fresh_real_prices_cover_upcoming_games(self):
        now = dt.datetime(2026, 10, 29, 16, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dest = root / 'projects/props-edge/site/data/labs/nba'
            dest.mkdir(parents=True)
            games = [{'game_id': str(i), 'date': '2026-10-29T23:00:00Z'} for i in range(4)]
            games.append({'game_id': 'past', 'date': '2026-10-29T12:00:00Z'})
            base = dict(generated_at=now.isoformat(), source_model_at=now.isoformat())
            manifest = dict(base, games=games, chunks=[{'day': '2026-10-29', 'file': 'day-0.json'}])
            (dest / 'manifest.json').write_text(json.dumps(manifest))
            q = dict(event_id='0', observed_at=now.isoformat(), price_american=140, book='Example', price_source='book')
            data = dict(base, quotes=[q, dict(q, event_id='1', price_source='model'),
                                     dict(q, event_id='2', observed_at='2026-10-29T01:00:00Z'),
                                     dict(q, event_id='3', observed_at='2026-10-29T17:00:00Z')])
            (dest / 'day-0.json').write_text(json.dumps(data))
            result = prop_coverage(root, 'nba', now)
            self.assertEqual(result['upcoming_24h'], 4)
            self.assertEqual(result['with_fresh_observed_props'], 1)
            self.assertEqual(len(result['without_fresh_observed_props']), 3)
            data['generated_at'] = 'old'
            (dest / 'day-0.json').write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'Mixed'):
                prop_coverage(root, 'nba', now)

    def test_failed_refresh_and_missing_health_never_report_healthy(self):
        with tempfile.TemporaryDirectory() as folder:
            result = review(Path(folder), refresh_outcome='failure')
            self.assertEqual(result['status'], 'review')
            self.assertTrue(any('failure' in s for s in result['findings']))

    def test_schedule_keeps_toronto_time_and_forces_browser_review(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / '.github/workflows/release.yml').read_text()
        self.assertIn("- cron: '0 12,18 * * *'\n      timezone: America/Toronto", source)
        self.assertIn("github.event.schedule != '0 12,18 * * *'", source)
        self.assertIn("github.event.schedule == '0 12,18 * * *' && 'kevbot-daily-review'", source)
        self.assertIn("inputs.sport || 'all'", source)
