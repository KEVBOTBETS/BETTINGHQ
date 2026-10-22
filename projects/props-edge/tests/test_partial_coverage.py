import unittest
from types import SimpleNamespace
from pipeline.build import unpriced_game_projections


class PartialCoverageTests(unittest.TestCase):
    def test_partial_primary_does_not_skip_other_games(self):
        projections = [SimpleNamespace(event_id=str(i), player=p) for i in range(14) for p in ("A", "B")]
        primary = [SimpleNamespace(event_id=str(i)) for i in range(9)]
        missing = unpriced_game_projections(projections, primary)
        self.assertEqual({row.event_id for row in missing}, {str(i) for i in range(9, 14)})
        self.assertEqual(len(missing), 10)
        self.assertEqual(unpriced_game_projections(projections, []), projections)
        self.assertEqual(unpriced_game_projections(projections, [SimpleNamespace(event_id=str(i)) for i in range(14)]), [])

    def test_ids_normalized_without_matchup_guessing(self):
        projections = [SimpleNamespace(event_id="401"), SimpleNamespace(event_id="402")]
        self.assertEqual(unpriced_game_projections(projections, [SimpleNamespace(event_id=401)]), projections[1:])
