"""Real ledger regression: forecasts must stop changing before first pitch."""
import copy
import unittest
from unittest.mock import patch
from pipeline import predict as P
from pipeline import grade as G


class PregameIntegrity(unittest.TestCase):
    def setUp(self):
        self.db = {"games": {}}
        self.game = {"gamePk": 1, "date": "2026-09-18", "start": "2026-09-18T20:00:00Z",
                     "away": "TOR", "home": "NYY", "status": "Scheduled", "abstract": "Preview",
                     "sim": {"p_home": .6, "p_raw_home": .65, "mean_away": 4,
                             "mean_home": 5, "mean_total": 9}}
        self.clock = "2026-09-18T19:00:00Z"
        for target, value in [("_load", lambda: copy.deepcopy(self.db)),
                              ("_save", lambda db: setattr(self, "db", copy.deepcopy(db))),
                              ("_now", lambda: self.clock)]:
            ctx = patch.object(P, target, value); ctx.start(); self.addCleanup(ctx.stop)
        ctx = patch.object(P.C, "SEASON", 2026); ctx.start(); self.addCleanup(ctx.stop)

    def record(self):
        return P.record({"games": [self.game]})

    def test_latest_pregame_then_frozen_even_if_feed_says_scheduled(self):
        self.assertEqual(self.record(), 1)
        self.clock = "2026-09-18T19:59:00Z"
        self.game["sim"]["p_home"] = .7
        self.record()
        before = copy.deepcopy(self.db)
        self.clock = "2026-09-18T20:00:00Z"
        self.game["sim"]["p_home"] = .99
        self.assertEqual(self.record(), 0)
        self.assertEqual(self.db, before)
        # A late reschedule must not allow an in-progress row to be overwritten.
        self.game["start"] = "2026-09-19T20:00:00Z"
        self.assertEqual(self.record(), 0)

    def test_no_late_or_live_backfill(self):
        self.clock = "2026-09-18T21:00:00Z"
        self.assertEqual(self.record(), 0)
        self.clock = "2026-09-18T19:00:00Z"
        for state in ["In Progress", "Final", "Postponed", "Cancelled", "Suspended"]:
            self.game["status"] = state
            self.assertEqual(self.record(), 0)
        self.assertEqual(self.db["games"], {})

    def test_contaminated_history_preserved_but_never_scored_or_trained(self):
        self.record()
        row = self.db["games"]["1"]
        row.update(status="graded", correct=True, home_won=True,
                   err_total=0, err_home=0, err_away=0, err_margin=0)
        for i, stamp in enumerate(["2026-09-18T20:00:00Z", "bad", None,
                                    "2026-09-18T19:00:00"], 2):
            self.db["games"][str(i)] = {**row, "gamePk": i, "updated_at": stamp}
        before = copy.deepcopy(self.db)
        report = P.summary()
        self.assertEqual(report["overall"]["n"], 1)
        self.assertEqual(report["scope"]["excluded_graded"], 4)
        self.assertEqual(P.calibration()["n"], 1)
        self.assertEqual(self.db, before)

    def test_valid_first_seen_does_not_rescue_postgame_overwrite(self):
        self.record()
        row = self.db["games"]["1"]
        row["updated_at"] = "2026-09-18T22:00:00Z"
        self.assertFalse(P.eligible(row))

    def test_shadow_prices_tiers_and_lines_freeze_too(self):
        shadow = {"calls": {}}
        game = {**self.game, "bets": [{"market": "ML", "selection": "NYY",
                "label": "NYY ML", "price": -150, "p_final": .6,
                "edge": .02, "tier": "LEAN", "stake": 2}]}
        with patch.object(G, "_load", lambda: shadow), patch.object(G, "_save"):
            G.record_calls({"games": [game]})
            before = copy.deepcopy(shadow)
            self.clock = "2026-09-18T20:01:00Z"
            game["bets"][0].update(price=-900, p_final=.99, tier="BEST BET")
            G.record_calls({"games": [game]})
            self.assertEqual(shadow, before)
            row = next(iter(shadow["calls"].values()))
            row.update(status="graded", result="win", pl=1.33)
            self.assertEqual(G.summarise()["all_calls"]["n"], 1)
            row["close_at"] = self.clock
            self.assertEqual(G.summarise()["all_calls"]["n"], 0)


if __name__ == "__main__":
    unittest.main()
