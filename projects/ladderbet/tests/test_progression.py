import unittest

from ladder.state import Ladder


class LadderProgressionTests(unittest.TestCase):
    def candidate(self, decimal=1.50):
        return {
            "pick": "Test Team",
            "decimal": decimal,
            "american": -200,
            "league": "mlb",
            "matchup": "Away @ Home",
            "side": "home",
            "event_id": "test-event",
            "start_utc": "2099-01-01T00:00:00Z",
        }

    def test_win_advances_and_rolls_full_return(self):
        lad = Ladder(base_stake=5.0, max_rung=10, stake=5.0)
        lad.place(self.candidate(1.50))
        lad.settle("win")
        self.assertEqual(lad.rung, 1)
        self.assertEqual(lad.next_stake(), 7.50)
        self.assertIsNone(lad.pending)

    def test_loss_resets_to_first_rung_and_base_stake(self):
        lad = Ladder(base_stake=5.0, max_rung=10, rung=3, stake=19.15)
        lad.place(self.candidate(1.50), stake=19.15)
        lad.settle("loss")
        self.assertEqual(lad.rung, 0)
        self.assertEqual(lad.next_stake(), 5.00)
        self.assertIsNone(lad.pending)

    def test_push_does_not_move_the_ladder(self):
        lad = Ladder(base_stake=5.0, max_rung=10, rung=4, stake=27.66)
        lad.place(self.candidate(1.50), stake=27.66)
        lad.settle("push")
        self.assertEqual(lad.rung, 4)
        self.assertEqual(lad.next_stake(), 27.66)


if __name__ == "__main__":
    unittest.main()
