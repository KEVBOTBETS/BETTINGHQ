"""
Regression tests for the 2026-09-26 underdog bias.

Week 3 of 2026 put five big moneyline underdogs (+160 to +455) on the board as
BEST BETs, every one pinned at the 5.5% edge ceiling. Three separate faults
stacked up to do it; each gets a test here so none can come back quietly.

    python -m unittest tests.test_market_anchoring -v
"""

from __future__ import annotations

import json
import os
import random
import statistics
import unittest

from pipeline import build as B, model as M, ratings as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "config", "settings.json"), encoding="utf-8"))


def game(spread_home, ml_home, ml_away, total=45.5):
    return {"game_id": "g1", "date_utc": "2026-09-27T17:00Z", "week": 3,
            "season_type": 2, "home": {"abbr": "MIA"}, "away": {"abbr": "KC"},
            "odds": {"spread_home": spread_home, "spread_price_home": -110,
                     "spread_price_away": -110, "ml_home": ml_home, "ml_away": ml_away,
                     "total": total, "over_price": -110, "under_price": -110}}


def proj_agreeing(spread_home, total=45.5):
    mu = -spread_home
    return {"mu": mu, "market_mu": mu, "gap": 0.0, "proj_total": total,
            "market_total": total, "total_gap": 0.0}


class TestModelThatAgreesWithTheMarketFindsNothing(unittest.TestCase):
    """If the model's line IS the market's line, no side may show an edge."""

    def test_every_side_prices_at_the_market(self):
        for sp, mh, ma in ((10.0, 455, -600), (7.5, 300, -380), (3.0, 135, -160),
                           (-6.5, -290, 235), (-2.5, -135, 115)):
            rows = B.price_game(game(sp, mh, ma), proj_agreeing(sp), CFG, 1.0, False)
            for r in rows:
                self.assertAlmostEqual(r["model_prob"], r["market_fair_prob"], places=3,
                                       msg=f"{r['pick']} at {sp}: {r['model_prob']} vs "
                                           f"{r['market_fair_prob']}")
                self.assertEqual(r["tier"], "PASS", f"{r['pick']} at spread {sp}")

    def test_old_unanchored_curve_really_was_biased(self):
        # Documents the bug the anchoring fixes: at the market's own -7.5 the
        # key-number curve gives the favourite well under 50% to cover.
        w, p, l = M.cover_probability(7.5, 13.2, -7.5)
        self.assertLess(w / (w + l), 0.46)


class TestLongshotsCannotBeLocks(unittest.TestCase):
    def test_power_devig_takes_more_from_the_dog(self):
        be_fav, be_dog = M.american_to_prob(-600), M.american_to_prob(455)
        prop = M.devig(be_fav, be_dog)[1]
        power = M.devig_power(be_fav, be_dog)[1]
        self.assertLess(power, prop)
        a, b = M.devig_power(M.american_to_prob(-110), M.american_to_prob(-110))
        self.assertAlmostEqual(a, 0.5, places=6)

    def test_small_probability_edge_on_long_odds_is_not_a_play(self):
        # +455 dog, model 1.3 points over break-even: ~7% "return", but noise.
        tier, why = M.tier_for(0.055, CFG, 0.9, line_gap=2.0, price=455,
                               model_prob=0.193, prob_edge=0.013)
        self.assertIn(tier, ("LEAN", "PASS"))

    def test_underdog_is_never_best_bet(self):
        tier, why = M.tier_for(0.09, CFG, 0.95, line_gap=2.5, price=120,
                               model_prob=0.49, prob_edge=0.035)
        self.assertEqual(tier, "GOOD")
        self.assertIn("not a lock", why)

    def test_favourite_with_real_edge_can_still_be_best_bet(self):
        tier, why = M.tier_for(0.09, CFG, 0.95, line_gap=2.5, price=-110,
                               model_prob=0.56, prob_edge=0.036)
        self.assertEqual(tier, "BEST BET", why)

    def test_huge_adverse_move_holds_to_lean(self):
        tier, _ = M.tier_for(0.09, CFG, 0.95, line_gap=2.5, price=-110, adverse=5.0,
                             model_prob=0.56, prob_edge=0.036)
        self.assertEqual(tier, "LEAN")


class TestRatingsKeepThePriorsSpread(unittest.TestCase):
    """Two games of results must not squash 32 teams toward average."""

    def test_prior_dispersion_survives_two_weeks(self):
        rng = random.Random(7)
        teams = sorted(json.load(open(os.path.join(ROOT, "config", "divisions.json")))["teams"])
        prior = {t: rng.gauss(0, 3.5) for t in teams}
        mean = sum(prior.values()) / len(prior)
        prior = {t: v - mean for t, v in prior.items()}
        games = []
        for wk in (1, 2):
            order = teams[:]
            rng.shuffle(order)
            for i in range(0, 32, 2):
                h, a = order[i], order[i + 1]
                margin = round(prior[h] - prior[a] + 1.8 + rng.gauss(0, 13))
                games.append({"game_id": f"{wk}-{i}", "date_utc": f"2026-09-{7*wk:02d}T17:00Z",
                              "week": wk, "season_type": 2, "completed": True,
                              "home": {"abbr": h}, "away": {"abbr": a},
                              "home_score": 24 + max(margin, -24) // 2 + (margin % 2),
                              "away_score": 24 - max(margin, -24) // 2})
        solved, _ = R.solve_margin_ratings(games, CFG, prior=prior)
        sd_prior = statistics.pstdev(prior.values())
        sd_solved = statistics.pstdev(solved.values())
        self.assertGreater(sd_solved, 0.8 * sd_prior,
                           f"ratings squashed: prior sd {sd_prior:.2f}, solved {sd_solved:.2f}")


if __name__ == "__main__":
    unittest.main()
