import unittest
from copy import deepcopy
from pipeline import forecast

class ForecastScopeTests(unittest.TestCase):
    def test_regular_season_filter_preserves_archive(self):
        log = {
            "pre": {"season_type": 1, "date": "2026-08-20T17:00Z", "result": "Pending"},
            "reg": {"season_type": 2, "date": "2026-09-20T17:00Z", "result": "Pending"},
            "old": {"season_type": 2, "date": "2025-09-20T17:00Z", "result": "Pending"},
            "unknown": {"season_type": 2, "result": "Pending"},
        }
        original = deepcopy(log)
        result = forecast.report(log, season=2026)
        self.assertEqual(result["total_games"], 1)
        self.assertEqual(result["scope"]["excluded_records"], 3)
        self.assertEqual(log, original)

    def test_january_regular_season_belongs_to_previous_year(self):
        row = {"season_type": 2, "date": "2027-01-03T18:00Z"}
        self.assertTrue(forecast.in_scope(row, 2026))
        self.assertFalse(forecast.in_scope(row, 2027))

    def test_shadow_game_date_and_explicit_season_supported(self):
        self.assertTrue(forecast.in_scope({"season_type": 2, "game_date": "2026-09-20T17:00Z"}, 2026))
        self.assertTrue(forecast.in_scope({"season_type": 2, "season": 2026}, 2026))
        self.assertFalse(forecast.in_scope({"season_type": 3, "season": 2026}, 2026))

    def test_unknown_season_type_is_not_assumed_regular(self):
        self.assertFalse(forecast.in_scope({"game_date": "2026-09-20T17:00Z"}, 2026))

    def test_verdict_does_not_promise_an_edge(self):
        text = forecast._verdict({"games": 32, "margin_vs_market": .3})
        self.assertIn("does not establish", text)
        self.assertNotIn("having a real edge", text)

if __name__ == "__main__":
    unittest.main()
