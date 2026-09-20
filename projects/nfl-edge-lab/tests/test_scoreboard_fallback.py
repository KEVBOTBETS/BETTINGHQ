import datetime as dt
import unittest
from unittest.mock import Mock, patch
from pipeline import espn


class ScoreboardFallbackTests(unittest.TestCase):
    def test_rejected_range_fetches_every_day_and_deduplicates(self):
        calls = []

        def get(url, params):
            day = params['dates']
            calls.append(day)
            if '-' in day:
                raise espn.EspnError('HTTP 400')
            return {'events': [{'id': day}, {'id': 'shared'}]}

        with patch.object(espn, '_get', side_effect=get):
            result = espn.scoreboard(dt.date(2026, 9, 19), dt.date(2026, 9, 21))
        self.assertCountEqual(calls, ['20260919-20260921', '20260919', '20260920', '20260921'])
        self.assertCountEqual([e['id'] for e in result['events']], ['20260919', '20260920', '20260921', 'shared'])

    def test_failed_day_keeps_other_days_without_fabricating_events(self):
        def get(url, params):
            day = params['dates']
            if '-' in day:
                raise espn.EspnError('HTTP 400')
            if day == '20260920':
                raise espn.EspnError('HTTP 503')
            return {'events': [{'id': day}]}

        with patch.object(espn, '_get', side_effect=get):
            result = espn.scoreboard(dt.date(2026, 9, 19), dt.date(2026, 9, 21))
        self.assertCountEqual([e['id'] for e in result['events']], ['20260919', '20260921'])

    def test_single_day_never_uses_range_syntax(self):
        with patch.object(espn, '_get', return_value={'events': []}) as get:
            espn.scoreboard(dt.date(2026, 9, 20), dt.date(2026, 9, 20))
        self.assertEqual(get.call_args.args[1]['dates'], '20260920')

    def test_transient_errors_do_not_expand_into_many_requests(self):
        with patch.object(espn, '_get', side_effect=espn.EspnError('HTTP 503')) as get:
            with self.assertRaises(espn.EspnError):
                espn.scoreboard(dt.date(2026, 9, 19), dt.date(2026, 9, 21))
        self.assertEqual(get.call_count, 1)

    def test_unsupported_query_is_not_retried(self):
        with patch.object(espn.requests, 'get', return_value=Mock(status_code=400)) as get, \
                patch.object(espn.time, 'sleep') as sleep:
            with self.assertRaisesRegex(espn.EspnError, 'HTTP 400'):
                espn._get('https://example.test/scoreboard')
        self.assertEqual(get.call_count, 1)
        sleep.assert_not_called()
