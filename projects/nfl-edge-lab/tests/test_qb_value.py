import datetime as dt
import unittest

from pipeline import build as B, injuries as INJ, qb_value as Q

CFG = {"injuries": {"enabled": True, "qb_points_per_epa": 22.5, "qb_min_points": 0.5,
                    "qb_max_points": 8.0, "max_team_points": 9.0, "hold_questionable_qb": True,
                    "qb_hold_release_minutes": 90,
                    "status_weight": {"out": 1.0, "doubtful": 0.65, "questionable": 0.2},
                    "position_points": {"QB_starter": 4.5, "QB_backup": 0.2, "default": 0.25}}}


def stat(pid, name, team, plays, epa, season_type="REG"):
    return {"player_id": pid, "player_display_name": name, "position": "QB", "team": team,
            "season_type": season_type, "attempts": plays, "sacks_suffered": 0, "carries": 0,
            "passing_epa": epa, "rushing_epa": 0}


PLAYERS = [{"gsis_id": "g1", "espn_id": "1", "position": "QB", "display_name": "Star", "status": "ACT"},
           {"gsis_id": "g2", "espn_id": "2", "position": "QB", "display_name": "Vet", "status": "ACT"},
           {"gsis_id": "g3", "espn_id": "3", "position": "QB", "display_name": "Rookie", "status": "ACT"}]
TABLE = Q.build_table(2026, PLAYERS,
                      [stat("g1", "Star", "LA", 120, 30.0), stat("g2", "Vet", "LA", 10, -1.0)],
                      [stat("g1", "Star", "LA", 600, 120.0), stat("g2", "Vet", "LA", 300, -6.0)])


class Quality(unittest.TestCase):
    def test_shrinkage_pulls_small_samples_to_replacement(self):
        self.assertAlmostEqual(Q.quality(0, 0), Q.REPLACEMENT_EPA)
        self.assertTrue(0.1 < Q.quality(600, 120) < 0.2)   # raw 0.20, shrunk toward -0.15

    def test_team_codes_and_usual_starter(self):
        self.assertEqual(TABLE["usual_starter"]["LAR"], "1")      # nflverse LA -> ESPN LAR
        self.assertEqual(TABLE["qbs"]["3"]["q"], Q.REPLACEMENT_EPA)  # rookie with no snaps

    def test_value_is_the_gap_and_clamped(self):
        v = Q.starter_value(TABLE, "1", "2", CFG)
        gap = TABLE["qbs"]["1"]["q"] - TABLE["qbs"]["2"]["q"]
        self.assertAlmostEqual(v["points"], round(min(8.0, 22.5 * gap), 2))
        self.assertIsNone(Q.starter_value(TABLE, "3", "2", CFG))    # under 100 plays: flat fallback

    def test_depth_chart_already_promoted_backup(self):
        rows = [{"athlete_id": "1", "name": "Star", "position": "QB", "status": "Out"}]
        info = Q.team_qb(TABLE, "LAR", ["2", "1"], rows, lambda s: INJ.status_weight(s, CFG))
        self.assertEqual((info["usual"], info["replacement"]), ("1", "2"))
        value = Q.starter_value(TABLE, info["usual"], info["replacement"], CFG)
        imp = INJ.team_impact(rows, CFG, info["usual"], qb_value=value, qb_info=info)
        self.assertTrue(imp["qb_out"])
        self.assertAlmostEqual(imp["points"], min(9.0, value["points"]))


class QuestionableHold(unittest.TestCase):
    def game(self, hours):
        ko = dt.datetime(2026, 9, 27, 17, 0, tzinfo=dt.timezone.utc)
        return {"date_utc": ko.isoformat(), "home": {"abbr": "LAR"}, "away": {"abbr": "SF"}}, ko - dt.timedelta(hours=hours)

    def inj(self):
        return {"home": {"qb": {"questionable": True, "name": "Star", "status": "Questionable"}}, "away": {}}

    def test_held_before_inactives(self):
        g, now = self.game(20)
        rows = B.qb_status_hold([{"tier": "GOOD"}, {"tier": "PASS"}], self.inj(), g, CFG, now)
        self.assertTrue(rows[0]["held"])
        self.assertNotIn("held", rows[1])

    def test_released_at_inactives(self):
        g, now = self.game(1)
        rows = B.qb_status_hold([{"tier": "GOOD"}], self.inj(), g, CFG, now)
        self.assertFalse(rows[0].get("held"))
        self.assertIn("assumed active", rows[0]["risk_flags"][0])


if __name__ == "__main__":
    unittest.main()
