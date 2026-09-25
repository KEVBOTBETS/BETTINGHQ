from __future__ import annotations

import json
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

from pipeline import espn, ledger, model

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config" / "settings.json").read_text())


NOW = datetime(2026, 8, 25, 18, tzinfo=timezone.utc)
CLOCK = patch.object(model, "_utc_now", return_value=NOW)
def setUpModule():
    CLOCK.start()
def tearDownModule():
    CLOCK.stop()


def game(game_id="1", date="2026-08-25", status="pre", completed=False):
    return {
        "game_id": game_id,
        "date": date,
        "tipoff": f"{date}T23:00:00Z",
        "start_local": "7:00 PM",
        "season_type": 2,
        "away": {"abbr": "SEA", "score": None},
        "home": {"abbr": "NY", "score": None},
        "status": status,
        "completed": completed,
        "odds": {
            "fetched_at": NOW.isoformat(),
            "book": "DraftKings",
            "quotes": {
                "away_ml": {"price": 150, "line": None, "book": "DraftKings"},
                "home_ml": {"price": -175, "line": None, "book": "DraftKings"},
                "away_spread": {"price": -110, "line": 4.0, "book": "DraftKings"},
                "home_spread": {"price": -110, "line": -4.0, "book": "DraftKings"},
                "over": {"price": -110, "line": 160.5, "book": "DraftKings"},
                "under": {"price": -110, "line": 160.5, "book": "DraftKings"},
            },
        },
    }


def profile(team, *, ppg, papg, rating=0.0, home=.5, road=.5, recent=.5, rest=2.0):
    return {
        "team": team,
        "games": 20,
        "ppg": ppg,
        "papg": papg,
        "l10_ppg": ppg,
        "l10_papg": papg,
        "win_pct": .5,
        "l10_pct": recent,
        "home_pct": home,
        "road_pct": road,
        "rest_days": rest,
        "power_rating": rating,
    }


def projection(g=None):
    g = g or game()
    return model.project_game(
        g,
        profile("SEA", ppg=81, papg=83, road=.45),
        profile("NY", ppg=86, papg=78, rating=3, home=.7, recent=.7),
        {},
        CFG,
    )


class TestOdds(unittest.TestCase):
    def test_minus_110_break_even(self):
        self.assertAlmostEqual(model.american_to_prob(-110), 0.52381, places=4)

    def test_devig_sums_to_one(self):
        away, home = model.devig(150, -175)
        self.assertAlmostEqual(away + home, 1.0, places=9)

    def test_incomplete_market_has_no_fair_probability(self):
        self.assertEqual(model.devig(-110, None), (None, None))

    def test_positive_kelly_only_for_value(self):
        self.assertGreater(model.kelly_fraction(.60, -110), 0)
        self.assertEqual(model.kelly_fraction(.45, -110), 0)


class TestProjection(unittest.TestCase):
    def test_opponent_defense_changes_projection(self):
        g = game()
        away = profile("SEA", ppg=81, papg=83)
        home = profile("NY", ppg=86, papg=78)
        baseline = model.project_game(g, away, home, {}, CFG)
        home["papg"] += 10
        changed = model.project_game(g, away, home, {}, CFG)
        self.assertLess(changed["margin"], baseline["margin"])

    def test_score_margin_and_total_reconcile(self):
        result = projection()
        self.assertAlmostEqual(result["home_score"] - result["away_score"], result["margin"], delta=.11)
        self.assertAlmostEqual(result["home_score"] + result["away_score"], result["total"], delta=.11)

    def test_market_anchor_limits_extreme_gap(self):
        result = projection()
        self.assertLessEqual(abs(result["kept_line_gap"]), CFG["model"]["max_spread_disagreement"])

    def test_schedule_adjusted_ratings_are_centered(self):
        history = []
        for idx, margin in enumerate((8, -2, 5)):
            row = game(str(idx), f"2026-06-0{idx + 1}", "post", True)
            row["away"]["score"] = 80
            row["home"]["score"] = 80 + margin
            history.append(row)
        ratings = model.solve_ratings(history, CFG)
        self.assertAlmostEqual(sum(ratings.values()), 0, places=2)


class TestPricingAndPortfolio(unittest.TestCase):
    def test_unpriced_game_has_no_candidates(self):
        g = game()
        g["odds"] = None
        self.assertEqual(model.price_game(g, projection(game()), CFG), [])

    def test_started_game_cannot_be_selected(self):
        g = game(status="in")
        rows = model.price_game(g, projection(g), CFG)
        self.assertTrue(all(row["tier"] == "AVOID" for row in rows))

    def test_negative_edges_do_not_force_a_play(self):
        g = game()
        p = projection(g)
        p.update({"margin": 0.0, "total": 160.5, "market_total": 160.5, "line_gap": -4.0})
        rows = model.price_game(g, p, CFG)
        model.allocate_portfolio(rows, CFG)
        self.assertTrue(all(row["stake"] == 0 for row in rows if row["tier"] == "AVOID"))

    def test_edge_is_measured_against_no_vig_market(self):
        g = game()
        p = projection(g)
        p.update({"margin": 0.0, "total": 160.5, "market_total": 160.5, "line_gap": -4.0})
        rows = model.price_game(g, p, CFG)
        home = next(row for row in rows if row["market"] == "ML" and row["side"] == "home")
        self.assertAlmostEqual(home["edge_raw"], home["model_prob"] / home["market_fair_prob"] - 1, places=4)
        self.assertIn("edge_real", home)

    def test_daily_exposure_and_one_side_plus_one_total_per_game(self):
        rows = []
        for idx in range(4):
            g = game(str(idx))
            rows.extend(model.price_game(g, projection(g), CFG))
        model.allocate_portfolio(rows, CFG)
        selected = [row for row in rows if row["stake"] > 0]
        cap = CFG["bankroll"]["starting"] * CFG["bankroll"]["max_daily_exposure_pct"]
        self.assertLessEqual(sum(row["stake"] for row in selected), cap)
        slots={(row["game_id"],"TOTAL" if row["market"]=="TOTAL" else "SIDE") for row in selected}
        self.assertEqual(len(slots),len(selected))
        self.assertLessEqual(sum(row["game_id"]=="0" for row in selected),1)
        self.assertLessEqual(len(selected), CFG["filters"]["max_bets_per_day"])


class TestLedger(unittest.TestCase):
    def selected_row(self):
        g = game()
        p = projection(g)
        p.update({"margin": 9.0, "line_gap": 5.0, "total": 168.0, "confidence": .86})
        rows = model.price_game(g, p, CFG)
        model.allocate_portfolio(rows, CFG)
        return next(row for row in rows if row["stake"] > 0)

    def test_qualified_play_is_not_auto_added(self):
        row = self.selected_row()
        first, shadow = ledger.sync([row], [game()], {"bets": []}, {"calls": []}, now=NOW.isoformat())
        self.assertEqual(first["bets"], [])
        self.assertEqual(first["mode"], "manual-browser")
        self.assertEqual(len(shadow["calls"]), 1)

    def test_shadow_call_is_duplicate_proof_and_graded(self):
        row = self.selected_row()
        state, shadow = ledger.sync([row], [game()], {"bets": []}, {"calls": []}, now=NOW.isoformat())
        _, shadow = ledger.sync([row], [game()], state, shadow, now=NOW.isoformat())
        self.assertEqual(len(shadow["calls"]), 1)
        final = game(status="post", completed=True)
        final["away"]["score"], final["home"]["score"] = 75, 90
        _, graded_shadow = ledger.sync([], [final], state, shadow)
        self.assertIn(graded_shadow["calls"][0]["result"], {"Win", "Loss", "Push"})


class TestFeedParser(unittest.TestCase):
    def test_odds_parser_requires_a_real_price_block(self):
        self.assertIsNone(espn.parse_odds([], "SEA", "NY"))

    def test_line_without_price_does_not_invent_minus_110(self):
        payload = [{"provider": {"name": "Feed", "priority": 1}, "spread": 4.5, "details": "NY -4.5"}]
        parsed = espn.parse_odds(payload, "SEA", "NY")
        self.assertIsNone(parsed)

    def test_administrative_absence_is_not_an_injury_penalty(self):
        summary = {"injuries": [{"team": {"abbreviation": "NY"}, "injuries": [{
            "status": "Out", "athlete": {"id": "9", "displayName": "Reserve", "position": {"abbreviation": "G"}},
            "details": {"type": "Coach's Decision"},
        }]}]}
        parsed = espn.parse_injuries(summary, CFG)["NY"]
        self.assertEqual(parsed["points"], 0.0)
        self.assertFalse(parsed["players"][0]["counted"])

    def test_team_leader_absence_gets_role_weighted_impact(self):
        summary = {
            "leaders": [{"leaders": [{"name": "pointsPerGame", "leaders": [{"value": 20, "athlete": {"id": "1"}}]}]}],
            "injuries": [{"team": {"abbreviation": "NY"}, "injuries": [{
                "status": "Out", "athlete": {"id": "1", "displayName": "Star", "position": {"abbreviation": "G"}},
                "details": {"type": "Knee"},
            }]}],
        }
        parsed = espn.parse_injuries(summary, CFG)["NY"]
        self.assertGreater(parsed["points"], CFG["injuries"]["default_rotation_points"])
        self.assertEqual(parsed["players"][0]["impact_basis"], "team leader")


if __name__ == "__main__":
    unittest.main()
