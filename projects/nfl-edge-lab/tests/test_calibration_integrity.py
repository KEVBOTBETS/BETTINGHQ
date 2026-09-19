import copy
import unittest
from pipeline import calibrate


class CalibrationIntegrity(unittest.TestCase):
    def row(self, game='one', market='ML', side='home'):
        return dict(game_id=game, market=market, side=side, result='Win',
                    first_seen='2026-09-01T12:00:00Z', game_date='2026-09-02T12:00:00Z',
                    model_prob=.7, model_prob_uncalibrated=.6,
                    calibration_snapshot_version='pregame-v2')

    def test_opposing_sides_and_duplicate_rows_do_not_inflate_sample(self):
        cfg={'model': {'calibration': {'enabled': True, 'min_samples': 2, 'min_games': 1}}}
        rows={'home': self.row(), 'away': self.row(side='away'), 'duplicate': self.row()}
        fit=calibrate.fit(rows,cfg)
        self.assertFalse(fit['enabled'])
        self.assertEqual(fit['n'],1)

    def test_postkickoff_legacy_and_invalid_observations_are_excluded(self):
        cfg={'model': {'calibration': {'enabled': True}}}
        late=self.row();late['first_seen']=late['game_date']
        legacy=self.row();legacy.pop('model_prob_uncalibrated')
        nan=self.row();nan['model_prob_uncalibrated']=float('nan')
        self.assertEqual(calibrate.fit({'a':late,'b':legacy,'c':nan},cfg)['n'],0)

    def test_independent_game_floor_cannot_be_met_by_more_markets(self):
        cfg={'model': {'calibration': {'enabled': True,'min_samples': 2,'min_games': 2}}}
        fit=calibrate.fit({'a':self.row(), 'b':self.row(market='ATS')},cfg)
        self.assertFalse(fit['enabled']);self.assertEqual(fit['games'],1)

    def test_complementary_probabilities_after_calibration(self):
        params={'enabled':True,'a':.65,'b':.3}
        for p in [.01,.2,.5,.8,.99]:
            self.assertAlmostEqual(calibrate.apply(p,params)+calibrate.apply(1-p,params),1)


if __name__=='__main__': unittest.main()
