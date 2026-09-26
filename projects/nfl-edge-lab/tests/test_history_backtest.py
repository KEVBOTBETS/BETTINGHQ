import datetime as dt
import unittest

from pipeline import build as B, history_backtest as H


ROW = {"game_id": "2025_01_DAL_PHI", "season": "2025", "game_type": "REG", "week": "1",
       "gameday": "2025-09-04", "gametime": "20:20", "away_team": "DAL", "home_team": "PHI",
       "away_score": "20", "home_score": "24", "location": "Home", "spread_line": "7.0",
       "total_line": "47.5", "home_moneyline": "-395", "away_moneyline": "310",
       "home_spread_odds": "-110", "away_spread_odds": "-110", "over_odds": "-110", "under_odds": "-110"}


class Conversion(unittest.TestCase):
    def test_signs_and_codes(self):
        g = H.to_game(ROW)
        self.assertEqual(g["odds"]["spread_home"], -7.0)     # PHI favoured by 7
        self.assertEqual(g["date_utc"], "2025-09-05T00:20Z")
        self.assertTrue(g["completed"])
        self.assertEqual(H.to_game({**ROW, "home_team": "LA", "away_team": "WAS"})["home"]["abbr"], "LAR")

    def test_settle_matches_board(self):
        g = H.to_game(ROW)
        self.assertEqual(H._settle({"market": "ATS", "side": "away", "line": -7.0}, g), "Win")  # lost by 4 at +7
        self.assertEqual(H._settle({"market": "TOTAL", "side": "under", "line": 47.5}, g), "Win")


class MoneylineCap(unittest.TestCase):
    def test_long_moneyline_is_passed(self):
        cfg = {"filters": {"min_price": -350, "max_price": 300, "ml_max_price": 120}}
        g = {"season_type": 2, "date_utc": "2026-09-27T17:00Z"}
        rows = B.apply_filters([{"market": "ML", "tier": "GOOD", "price": 180, "ev": .05},
                                {"market": "ML", "tier": "GOOD", "price": 110, "ev": .05},
                                {"market": "ATS", "tier": "GOOD", "price": 150, "ev": .05}],
                               cfg, g, dt.date(2026, 9, 27))
        self.assertEqual([r["tier"] for r in rows], ["PASS", "GOOD", "GOOD"])


if __name__ == "__main__":
    unittest.main()
