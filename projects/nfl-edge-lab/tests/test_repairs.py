import json
import unittest
from pathlib import Path
from pipeline import model

CFG = json.loads((Path(__file__).resolve().parents[1] / 'config/settings.json').read_text())

class StakeRegressionTests(unittest.TestCase):
    def test_compressed_roi_longshot(self):
        self.assertEqual(model.stake_for(.224, 440, 500, CFG, edge=.055), 1.5)

    def test_push_adjustment_and_half_up_rounding(self):
        self.assertEqual(model.stake_for(.7, 100, 500, CFG, edge=.04, push_prob=.2), 6.5)
        self.assertEqual(model.stake_for(.7, 100, 500, CFG, edge=.04, push_prob=1), 0)

    def test_cap_survives_rounding(self):
        self.assertEqual(model.stake_for(.95, -110, 199, CFG), 9.5)
