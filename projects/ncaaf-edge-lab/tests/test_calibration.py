"""Home field, rating scale and totals variance -- the 2026-09-26 calibration fixes."""
import json
import os
import random
import unittest

from pipeline import build as B, ratings as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cfg():
    with open(os.path.join(ROOT, 'config', 'settings.json')) as fh:
        return json.load(fh)


def game(i, home, away, hs, as_, neutral=False):
    return {'game_id': str(i), 'date_utc': '2026-09-%02dT17:00Z' % (1 + i % 25),
            'completed': True, 'neutral': neutral,
            'home': {'abbr': home}, 'away': {'abbr': away},
            'home_score': hs, 'away_score': as_}


class HomeFieldTests(unittest.TestCase):
    def setUp(self):
        rng = random.Random(7)
        self.truth = {f'F{i:02d}': rng.gauss(0, 12) for i in range(40)}
        self.games, n = [], 0
        teams = list(self.truth)
        for _ in range(6):
            rng.shuffle(teams)
            for h, a in zip(teams[::2], teams[1::2]):
                m = self.truth[h] - self.truth[a] + 2.5 + rng.gauss(0, 10)
                self.games.append(game(n, h, a, 30 + round(m / 2), 30 - round(m / 2))); n += 1
        # Buy games: every FBS team hosts an FCS school once and wins big.
        for i, h in enumerate(teams):
            self.games.append(game(n, h, f'C{i:02d}', 45, 10)); n += 1
        self.fbs = set(self.truth)
        self.prior = dict(self.truth)

    def test_buy_games_inflate_home_field_without_the_fbs_filter(self):
        _, polluted = R.solve_margin_ratings(self.games, cfg(), prior=self.prior)
        _, clean = R.solve_margin_ratings(self.games, cfg(), prior=self.prior, hfa_teams=self.fbs)
        self.assertGreater(polluted, 4.0)
        self.assertLess(abs(clean - 2.5), 1.0)

    def test_default_keeps_old_behaviour(self):
        a = R.solve_margin_ratings(self.games, cfg(), prior=self.prior)
        b = R.solve_margin_ratings(self.games, cfg(), prior=self.prior, hfa_teams=None)
        self.assertEqual(a[1], b[1])


class PriorScaleTests(unittest.TestCase):
    def test_shrunk_internal_prior_no_longer_squeezes_fpi(self):
        fpi = {f'T{i:02d}': {'fpi': (i - 15) * 1.0} for i in range(31)}
        tiny = {t: row['fpi'] * 0.1 for t, row in fpi.items()}   # 10x too narrow
        blended, _ = R.blend_preseason_ratings(tiny, fpi, 0.85)
        spread = max(blended.values()) - min(blended.values())
        self.assertAlmostEqual(spread, 30.0, delta=0.5)   # FPI's own range, not 0.865x of it


class ScaleToMarketTests(unittest.TestCase):
    def test_margin_only_leaves_totals_alone(self):
        fit = B.fit_projection_scale([
            {'market_mu': x, 'mu_raw': 0.85 * x, 'market_total': 50 + x / 10,
             'proj_total_raw': 40 + 0.4 * (50 + x / 10)} for x in range(-30, 31, 3)])
        proj = {'market_mu': 30.0, 'mu_raw': 25.5, 'mu': 27.75, 'market_total': 53.0,
                'proj_total_raw': 61.2, 'proj_total': 57.0}
        out = B.debias_projection(proj, fit, cfg(), margin=True, total=False)
        self.assertLess(abs(out['mu'] - 30.0), 0.5)       # squeeze removed
        self.assertEqual(out['proj_total'], 57.0)          # totals untouched

    def test_settings(self):
        m = cfg()['model']
        self.assertTrue(m['scale_margin_to_market'])
        self.assertGreaterEqual(m['total_sd'], 13.5)


if __name__ == '__main__':
    unittest.main()
