import datetime as dt
import unittest
from tools.public_watchdog import FEEDS, assess

class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 11, 11, tzinfo=dt.timezone.utc)
        self.health = {'checked_at': self.now.isoformat(), 'feeds': {s: {'published_at': self.now.isoformat()} for s in FEEDS}}
        self.runs = [{'head_branch': 'main', 'event': 'schedule', 'status': 'completed', 'conclusion': 'success'}]

    def test_saved_fresh_label_cannot_hide_old_feed(self):
        self.health['feeds']['nhl'].update(published_at=(self.now-dt.timedelta(hours=5)).isoformat(), freshness='recent')
        self.assertTrue(assess(self.health, self.runs, self.now)['request_refresh'])

    def test_no_duplicate_recovery_while_release_active(self):
        self.runs.insert(0, {'head_branch': 'main', 'event': 'schedule', 'status': 'queued'})
        self.assertFalse(assess({}, self.runs, self.now)['request_refresh'])

    def test_coverage_warning_is_not_refresh_failure(self):
        self.health['feeds']['ncaab']['warnings'] = ['Games have no posted prices.']
        result = assess(self.health, self.runs, self.now)
        self.assertFalse(result['errors'])
        self.assertTrue(result['warnings'])
        self.assertFalse(result['request_refresh'])

    def test_failed_release_needs_recovery(self):
        self.runs[0]['conclusion'] = 'failure'
        self.assertTrue(assess(self.health, self.runs, self.now)['request_refresh'])

    def test_missing_future_and_naive_timestamps_are_rejected(self):
        for value in (None, '2026-11-11T00:00:00', (self.now+dt.timedelta(hours=1)).isoformat()):
            self.health['feeds']['nba']['published_at'] = value
            self.assertTrue(assess(self.health, self.runs, self.now)['errors'])

if __name__ == '__main__':
    unittest.main()
