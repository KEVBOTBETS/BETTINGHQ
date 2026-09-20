"""A successful rebuild must not make cached bookmaker prices look fresh."""
import datetime as dt
import unittest
from unittest.mock import patch

from pipeline import build, espn
from tests import test_offline as fixtures


class QuoteObservationTests(unittest.TestCase):
    def game(self, observed=None):
        odds = espn.parse_odds(fixtures.TestEspnOddsParsing.CURRENT)
        if observed is not None:
            odds['observed_at'] = observed
        return dict(game_id='1', date_utc='2026-09-20T17:00:00Z', week=2,
                    season_type=2, home={'abbr': 'TEN'}, away={'abbr': 'SEA'}, odds=odds)

    def test_successful_fetch_records_observation_even_without_price_movement(self):
        game = self.game('2026-09-18T12:00:00Z')
        before = dt.datetime.now(dt.timezone.utc)
        with patch.object(espn, 'scoreboard', return_value={'events': [{}]}), \
                patch.object(espn, 'parse_event', return_value=game):
            fresh = espn.fetch_range(dt.date(2026, 9, 20), dt.date(2026, 9, 20), [])
        observed = dt.datetime.fromisoformat(fresh[0]['odds']['observed_at'])
        self.assertGreaterEqual(observed, before)
        self.assertLessEqual(observed, dt.datetime.now(dt.timezone.utc))

    def test_failed_fetch_or_missing_odds_keeps_original_observation(self):
        old = self.game('2026-09-18T12:00:00Z')
        with patch.object(espn, 'scoreboard', side_effect=espn.EspnError('offline')):
            fresh = espn.fetch_range(dt.date(2026, 9, 20), dt.date(2026, 9, 20), [])
        for incoming in [fresh, [{**old, 'odds': {}}]]:
            merged = build.merge_games([old], incoming)
            self.assertEqual(merged[0]['odds']['observed_at'], old['odds']['observed_at'])

    def test_each_market_exports_original_observation_without_inventing_one(self):
        projection = dict(mu=3.5, gap=0, proj_total=37.5, total_gap=0)
        for stamp in [None, '2026-09-18T12:00:00Z']:
            rows = build.price_game(self.game(stamp), projection, fixtures.CFG, 1.0, False)
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(row['odds_observed_at'] == stamp for row in rows))
