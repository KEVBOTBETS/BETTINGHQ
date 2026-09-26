import unittest
from datetime import datetime, timedelta, timezone

from pipeline import early, clv as CLV

NOW = datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc)   # a Monday
CFG = {"timing": {"full_tier_min_hours": 96, "late_stake_multiplier": 0.6}}


def row(hours, tier="GOOD", market="ATS", side="home", line=7.5, price=-110):
    return {"game_id": "1", "market": market, "side": side, "pick": "HOME +7.5",
            "matchup": "AWAY @ HOME", "tier": tier, "line": line, "price": price,
            "edge": .06, "action_edge": .05, "week": 5,
            "game_date": (NOW + timedelta(hours=hours)).isoformat()}


class TimingGate(unittest.TestCase):
    def test_early_price_keeps_its_tier(self):
        r = early.timing_gate([row(130)], CFG, NOW)[0]
        self.assertEqual(r["tier"], "GOOD")
        self.assertTrue(r["early_window"])

    def test_late_price_is_lean_with_reduced_stake(self):
        r = early.timing_gate([row(20)], CFG, NOW)[0]
        self.assertEqual((r["tier"], r["timing_tier"], r["stake_multiplier"]), ("LEAN", "GOOD", 0.6))
        self.assertIn("Late-week price", r["warning"])

    def test_disabled_window_changes_nothing(self):
        r = early.timing_gate([row(5)], {"timing": {"full_tier_min_hours": 0}}, NOW)[0]
        self.assertEqual(r["tier"], "GOOD")


class Tracking(unittest.TestCase):
    def test_lock_clv_and_grading(self):
        state = {}
        board = early.timing_gate([row(130)], CFG, NOW)
        early.track(state, board, [], {}, CFG, NOW)
        self.assertEqual(len(state["locks"]), 1)

        later = NOW + timedelta(hours=110)                 # Saturday morning
        sat = row(20, line=5.5)
        sat["game_date"] = board[0]["game_date"]
        sat = early.timing_gate([sat], CFG, later)[0]
        early.track(state, [sat], [], {}, CFG, later)
        self.assertEqual(sat["early_lock"]["clv"]["points"], 2.0)   # took +7.5, now +5.5
        self.assertTrue(sat["warning"].startswith("Early play: GOOD"))
        self.assertNotIn("Late-week price", sat["warning"])

        game = {"game_id": "1", "completed": True, "home_score": 20, "away_score": 24}
        lines = {"1": [{"ts": later.isoformat(), "spread_home": 5.5,
                        "spread_price_home": -110, "spread_price_away": -110}]}
        summary = early.track(state, [], [game], lines, CFG, later + timedelta(days=1))
        self.assertEqual(state["locks"]["1|ATS|home"]["result"], "Win")    # lost by 4, +7.5 covers
        self.assertEqual(summary["record"], "1-0-0")
        self.assertEqual(summary["avg_clv_points"], 2.0)

    def test_away_spread_and_total_clv_signs(self):
        self.assertEqual(early.clv({"market": "ATS", "side": "away", "line": -7.5, "price": -110}, -9.0, -110)["points"], -1.5)
        self.assertEqual(early.clv({"market": "TOTAL", "side": "under", "line": 50.5, "price": -110}, 48.5, -110)["points"], 2.0)
        self.assertGreater(early.clv({"market": "ML", "side": "home", "line": None, "price": 150}, None, 120)["prob"], 0)


class TrackingWithoutGate(unittest.TestCase):
    OFF = {"timing": {"full_tier_min_hours": 0}}

    def test_lean_and_late_plays_are_locked_when_gate_is_off(self):
        state = {}
        board = early.timing_gate([row(20, tier="LEAN")], self.OFF, NOW)
        summary = early.track(state, board, [], {}, self.OFF, NOW)
        lock = state["locks"]["1|ATS|home"]
        self.assertEqual((lock["tier"], lock["window"]), ("LEAN", "late"))
        self.assertEqual(summary["locked"], 1)
        self.assertIn("early_lock", board[0])

    def test_first_price_is_kept_and_best_tier_recorded(self):
        state = {}
        early.track(state, early.timing_gate([row(130, tier="LEAN", line=7.5)], self.OFF, NOW), [], {}, self.OFF, NOW)
        later = NOW + timedelta(hours=24)
        up = row(106, tier="GOOD", line=6.5)
        up["game_date"] = (NOW + timedelta(hours=130)).isoformat()
        early.track(state, early.timing_gate([up], self.OFF, later), [], {}, self.OFF, later)
        lock = state["locks"]["1|ATS|home"]
        self.assertEqual((lock["line"], lock["tier"], lock["best_tier"], lock["window"]), (7.5, "LEAN", "GOOD", "early"))

    def test_closing_value_is_measured_at_kickoff_before_the_final(self):
        state = {}
        board = early.timing_gate([row(20, line=7.5)], self.OFF, NOW)
        early.track(state, board, [], {}, self.OFF, NOW)
        ko = NOW + timedelta(hours=20)
        lines = {"1": [{"ts": (ko - timedelta(hours=1)).isoformat(), "spread_home": 6.0,
                        "spread_price_home": -110, "spread_price_away": -110}]}
        s = early.track(state, [], [], lines, self.OFF, ko + timedelta(minutes=5))
        self.assertEqual(s["closed"], 1)
        self.assertEqual(s["beat_close_pct"], 1.0)
        self.assertEqual(s["record"], "0-0-0")          # not final yet


class ForecastClv(unittest.TestCase):
    def test_line_moving_toward_the_frozen_forecast_counts(self):
        ko = NOW + timedelta(days=2)
        recs = {"a": {"kind": "game", "event_id": "9", "start": ko.isoformat(),
                      "captured_at": NOW.isoformat(), "margin": 10.0, "total": 50.0}}
        lines = {"9": [{"ts": (NOW - timedelta(hours=1)).isoformat(), "spread_home": -7.0, "total": 52.0},
                       {"ts": (ko - timedelta(hours=1)).isoformat(), "spread_home": -8.5, "total": 51.0}]}
        out = CLV.forecast_clv(recs, lines, now=ko + timedelta(hours=4))
        self.assertEqual(out["spread"]["toward_model"], 1)
        self.assertEqual(out["spread"]["avg_points"], 1.5)
        self.assertEqual(out["spread_big"]["n"], 1)          # model 10 vs line 7: 3-pt gap
        self.assertEqual(out["total"]["toward_pct"], 1.0)    # model under 52, line fell to 51

    def test_future_games_are_ignored(self):
        recs = {"a": {"kind": "game", "event_id": "9", "start": (NOW + timedelta(days=1)).isoformat(),
                      "captured_at": NOW.isoformat(), "margin": 10.0}}
        self.assertEqual(CLV.forecast_clv(recs, {"9": []}, now=NOW)["spread"]["n"], 0)


if __name__ == "__main__":
    unittest.main()
