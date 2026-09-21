from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from pipeline.http import ProviderError
from pipeline.model import evaluate_quotes, evaluate_quotes_against_projections
from pipeline.providers.odds_api_io import OddsApiIoProvider
from pipeline.providers.odds_api_io import parse_event as parse_odds_api_io_event
from pipeline.providers.espn import parse_summaries
from pipeline.providers.the_odds_api import parse_event as parse_the_odds_api_event
from pipeline.build import load_settings
from pipeline.schema import Projection, PropQuote


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


class ProviderParsingTests(unittest.TestCase):
    def test_primary_provider_parses_two_sided_props(self) -> None:
        self.assertLessEqual(len(load_settings()["bookmakers"]["primary_consensus"]), 2)
        quotes = parse_odds_api_io_event(fixture("odds_api_io_event.json"), "NFL")
        self.assertEqual(len(quotes), 6)
        self.assertEqual({row.book for row in quotes}, {"DraftKings", "FanDuel", "BetMGM"})
        board = evaluate_quotes(quotes, load_settings())
        over = next(row for row in board if row["side"] == "over")
        self.assertIn(over["tier"], {"GOOD", "BEST"})
        self.assertEqual(over["consensus_books"], 3)

    def test_primary_generic_market_splits_player_and_prop_type(self) -> None:
        event = {
            "id": 22,
            "home": "Toronto",
            "away": "Boston",
            "bookmakers": {
                "DraftKings": [
                    {
                        "name": "Player Props",
                        "odds": [
                            {
                                "label": "Alex Example (Hits)",
                                "hdp": 1.5,
                                "over": 2.1,
                                "under": 1.7,
                            }
                        ],
                    }
                ]
            },
        }
        quotes = parse_odds_api_io_event(event, "MLB")
        self.assertEqual({row.player for row in quotes}, {"Alex Example"})
        self.assertEqual({row.market for row in quotes}, {"Batter hits"})

    def test_primary_generic_market_normalizes_nfl_targets_and_touchdowns(self) -> None:
        event = {
            "id": 23,
            "home": "Toronto",
            "away": "Buffalo",
            "bookmakers": {
                "DraftKings": [
                    {
                        "name": "Player Props",
                        "odds": [
                            {"label": "Sam Receiver (Receiving Targets)", "hdp": 7.5, "over": 1.91, "under": 1.91},
                            {"label": "Sam Receiver (Anytime Touchdown Scorer)", "yes": 2.5},
                        ],
                    }
                ]
            },
        }
        quotes = parse_odds_api_io_event(event, "NFL")
        self.assertEqual({row.player for row in quotes}, {"Sam Receiver"})
        self.assertEqual({row.market for row in quotes}, {"Targets", "Anytime touchdown"})

    def test_primary_provider_retries_without_rejected_bookmaker(self) -> None:
        settings = json.loads(json.dumps(load_settings()))
        settings["bookmakers"]["primary_consensus"].append("Pinnacle")
        provider = OddsApiIoProvider("fixture-key", settings)

        class FakeClient:
            calls: list[str] = []

            def get(self, path, params, retries=2):
                if path == "/events":
                    return [{"id": 1001, "league": {"name": "NFL"}}]
                self.calls.append(params["bookmakers"])
                if "Pinnacle" in params["bookmakers"]:
                    raise ProviderError(
                        'Odds-API.io request failed (HTTP 400: {"error":"Pinnacle is not a valid bookmaker"})'
                    )
                return [fixture("odds_api_io_event.json")]

        fake = FakeClient()
        provider.client = fake
        quotes = provider.fetch("NFL")
        self.assertEqual(len(quotes), 6)
        self.assertIn("Pinnacle", fake.calls[0])
        self.assertNotIn("Pinnacle", fake.calls[1])

    def test_draftkings_price_can_use_espn_projection(self) -> None:
        draftkings = [
            row
            for row in parse_odds_api_io_event(fixture("odds_api_io_event.json"), "NFL")
            if row.book == "DraftKings"
        ]
        projections = [
            Projection(
                sport="NFL",
                player="Jordan Example",
                team="Kansas City",
                matchup="Buffalo @ Kansas City",
                market="Passing yards",
                projection=315.0,
                samples=4,
                confidence=0.56,
                standard_deviation=12.0,
                recent=[298.0, 311.0, 320.0, 326.0],
                trend=4.0,
            )
        ]
        board = evaluate_quotes_against_projections(draftkings, projections, load_settings())
        over = next(row for row in board if row["side"] == "over")
        self.assertEqual(over["tier"], "BEST")
        self.assertEqual(over["mode"], "projection-priced")
        self.assertEqual(over["projection"], 315.0)

    def test_secondary_provider_parses_american_prices(self) -> None:
        quotes = parse_the_odds_api_event(fixture("the_odds_api_event.json"), "MLB")
        self.assertEqual(len(quotes), 4)
        draftkings_over = next(
            row for row in quotes if row.book == "DraftKings" and row.side == "over"
        )
        self.assertEqual(draftkings_over.price_american, 110)
        self.assertAlmostEqual(draftkings_over.price_decimal, 2.1)

    def test_secondary_provider_normalizes_anytime_touchdown(self) -> None:
        event = {
            "id": "nfl-1",
            "commence_time": "2026-09-10T00:00:00Z",
            "away_team": "Buffalo Bills",
            "home_team": "Kansas City Chiefs",
            "bookmakers": [
                {
                    "title": "DraftKings",
                    "markets": [
                        {
                            "key": "player_anytime_td",
                            "outcomes": [
                                {"description": "Sam Receiver", "name": "Yes", "price": 220}
                            ],
                        }
                    ],
                }
            ],
        }
        quotes = parse_the_odds_api_event(event, "NFL")
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0].market, "Anytime touchdown")
        self.assertEqual(quotes[0].side, "yes")

    def test_espn_nfl_projection_builds_targets_and_anytime_touchdown(self) -> None:
        def summary(rush_td, rush_yards, rush_attempts, rec_td, rec_yards, receptions, targets, completions_attempts):
            return {
                "boxscore": {
                    "players": [
                        {
                            "team": {"displayName": "Toronto Northmen"},
                            "statistics": [
                                {
                                    "type": "passing",
                                    "keys": ["completions/passingAttempts", "passingYards", "passingTouchdowns", "interceptions"],
                                    "athletes": [{"athlete": {"displayName": "Sam Quarterback"}, "stats": [completions_attempts, 225, 2, 1]}],
                                },
                                {
                                    "type": "rushing",
                                    "keys": ["rushingTouchdowns", "rushingYards", "rushingAttempts"],
                                    "athletes": [{"athlete": {"displayName": "Sam Receiver"}, "stats": [rush_td, rush_yards, rush_attempts]}],
                                },
                                {
                                    "type": "receiving",
                                    "keys": ["receivingTouchdowns", "receivingYards", "receptions", "targets"],
                                    "athletes": [{"athlete": {"displayName": "Sam Receiver"}, "stats": [rec_td, rec_yards, receptions, targets]}],
                                },
                            ],
                        }
                    ]
                }
            }

        schedule = {"torontonorthmen": [{"matchup": "Buffalo @ Toronto", "start_time": "2026-09-10T00:00:00Z"}]}
        rows = parse_summaries(
            [summary(1, 50, 10, 0, 20, 2, 3, "17/28"), summary(0, 30, 8, 1, 40, 4, 6, "20/30")],
            "NFL",
            schedule,
        )
        targets = next(row for row in rows if row.market == "Targets")
        touchdown = next(row for row in rows if row.market == "Anytime touchdown")
        self.assertAlmostEqual(targets.projection, 5.0)
        self.assertEqual(targets.recent, [3.0, 6.0])
        self.assertAlmostEqual(touchdown.projection, 1.0)
        self.assertEqual(touchdown.recent, [1.0, 1.0])
        completions = next(row for row in rows if row.market == "Pass completions")
        attempts = next(row for row in rows if row.market == "Pass attempts")
        self.assertAlmostEqual(completions.projection, 19.0)
        self.assertAlmostEqual(attempts.projection, 29.33)

    def test_anytime_touchdown_yes_price_can_qualify(self) -> None:
        quote = PropQuote(
            sport="NFL",
            event_id="nfl-1",
            start_time="2026-09-10T00:00:00Z",
            matchup="Buffalo @ Toronto",
            player="Sam Receiver",
            market="Anytime touchdown",
            side="yes",
            line=None,
            price_decimal=3.2,
            price_american=220,
            book="DraftKings",
            provider="fixture",
        )
        projection = Projection(
            sport="NFL",
            player="Sam Receiver",
            team="Toronto Northmen",
            matchup="Buffalo @ Toronto",
            market="Anytime touchdown",
            projection=0.8,
            samples=4,
            confidence=0.56,
            standard_deviation=0.5,
            recent=[1.0, 0.0, 1.0, 0.0],
            trend=0.0,
        )
        row = evaluate_quotes_against_projections([quote], [projection], load_settings())[0]
        self.assertEqual(row["tier"], "GOOD")
        self.assertGreater(row["recommended_stake"], 0)
        self.assertLessEqual(row["recommended_stake"], 50)

    def test_espn_projection_fallback_has_no_odds(self) -> None:
        summaries = fixture("espn_summaries.json")
        schedule = {
            "torontotempo": [
                {"matchup": "Montreal @ Toronto", "start_time": "2026-08-25T23:00:00Z"},
                {"matchup": "Toronto @ New York", "start_time": "2026-08-26T23:00:00Z"},
            ]
        }
        rows = parse_summaries(summaries, "WNBA", schedule)
        point_rows = [row for row in rows if row.player == "Alex Example" and row.market == "Points"]
        self.assertEqual(len(point_rows), 2)
        points = point_rows[0]
        self.assertEqual(points.samples, 2)
        self.assertAlmostEqual(points.projection, 22.0)
        self.assertAlmostEqual(points.standard_deviation, 3.0)
        self.assertEqual(points.recent, [18.0, 24.0])
        self.assertEqual(
            {row.start_time for row in point_rows},
            {"2026-08-25T23:00:00Z", "2026-08-26T23:00:00Z"},
        )
        pra_rows = [
            row
            for row in rows
            if row.player == "Alex Example" and row.market == "Points + Rebounds + Assists"
        ]
        self.assertEqual(len(pra_rows), 2)
        self.assertAlmostEqual(pra_rows[0].projection, 36.67)
        self.assertEqual(pra_rows[0].recent, [30.0, 40.0])


class SecurityTests(unittest.TestCase):
    def test_repository_has_no_embedded_secret_shaped_hex_tokens(self) -> None:
        suspicious = re.compile(r"(?<![A-Za-z0-9])[a-f0-9]{32,}(?![A-Za-z0-9])", re.I)
        allowed_suffixes = {".json", ".py", ".js", ".html", ".css", ".md", ".yml", ".yaml", ".example", ".txt"}
        hits = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix not in allowed_suffixes:
                continue
            if suspicious.search(path.read_text(errors="ignore")):
                hits.append(str(path.relative_to(ROOT)))
        self.assertEqual(hits, [], f"secret-looking token found in: {hits}")


if __name__ == "__main__":
    unittest.main()


class EspnDateRangeFallbackTests(unittest.TestCase):
    def test_scoreboard_falls_back_to_single_days_when_ranges_are_rejected(self):
        import datetime as dt
        from pipeline.http import ProviderError
        from pipeline.providers.espn import EspnProjectionProvider

        calls = []

        class FakeClient:
            def get(self, path, params, retries=2):
                calls.append(params["dates"])
                if "-" in params["dates"]:
                    raise ProviderError("ESPN public statistics request failed (HTTP 400)")
                return {"events": [{"id": params["dates"]}, {"id": "shared"}]}

        provider = EspnProjectionProvider({"sports": {}, "fetch": {}})
        provider.client = FakeClient()
        board = provider._scoreboard("football/nfl", dt.date(2026, 9, 17), dt.date(2026, 9, 19))
        self.assertEqual(sorted(e["id"] for e in board["events"]), ["20260917", "20260918", "20260919", "shared"])
        self.assertEqual(calls[0], "20260917-20260919")

    def test_gzip_error_bodies_are_readable(self):
        import gzip
        from pipeline.http import _unzip
        self.assertEqual(_unzip(gzip.compress(b'{"code":400}')), b'{"code":400}')
        self.assertEqual(_unzip(b"plain"), b"plain")


class LegAndParlayTests(unittest.TestCase):
    def setUp(self):
        import json as _json
        from pathlib import Path
        self.settings = _json.loads((Path(__file__).resolve().parents[1] / "config" / "settings.json").read_text())

    def _projections(self):
        from pipeline.schema import Projection
        import datetime as _dt
        start = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=18)).isoformat()
        rows = []
        for game, (away, home) in enumerate([("BUF", "HOU"), ("DAL", "NYG"), ("NO", "DET"), ("PHI", "WAS")]):
            for team in (away, home):
                for index in range(5):
                    for market, base, deviation in [
                        ("Passing yards", 245, 45), ("Receiving yards", 61, 22), ("Receptions", 5, 2),
                        ("Rushing yards", 58, 20), ("Rush attempts", 13, 4), ("Anytime touchdown", 0.6, 0.5),
                    ]:
                        # Vary each player so the fixture has a realistic spread of prices.
                        scale = 0.55 + 0.22 * index + 0.08 * game
                        base = base * scale
                        recent = [round(base * (0.7 + 0.12 * ((step + index) % 6)), 1) for step in range(6)]
                        rows.append(Projection(
                            sport="NFL", player=f"{team} P{index}", team=team, matchup=f"{away} @ {home}",
                            market=market, projection=base, samples=6, confidence=0.6,
                            standard_deviation=deviation, recent=recent, trend=0.4, start_time=start))
        return rows

    def test_only_nfl_is_configured(self):
        self.assertEqual(list(self.settings["sports"]), ["NFL"])

    def test_model_legs_carry_price_probability_and_a_reason(self):
        from pipeline.legs import build_legs
        legs = build_legs([], self._projections(), self.settings)
        self.assertTrue(legs)
        for leg in legs:
            self.assertEqual(leg["sport"], "NFL")
            self.assertEqual(leg["price_source"], "model")
            self.assertTrue(leg["reason"])
            self.assertGreaterEqual(leg["model_prob"], self.settings["legs"]["min_model_prob"])
            self.assertLessEqual(leg["model_prob"], self.settings["legs"]["max_model_prob"])
        self.assertTrue(any(leg["market"] == "Anytime touchdown" for leg in legs))

    def test_estimated_price_keeps_the_book_margin(self):
        from pipeline.legs import estimated_price
        decimal, american = estimated_price(0.5, 0.045)
        self.assertLess(decimal, 2.0, "an estimated price must sit below the fair price")
        self.assertLess(american, 0)

    def test_parlays_hit_every_target_in_each_scope(self):
        from pipeline.legs import build_legs
        from pipeline.parlays import build_parlays
        result = build_parlays(build_legs([], self._projections(), self.settings), self.settings)
        self.assertTrue(result["tickets"])
        for scope in ("slate", "game"):
            targets = {ticket["target"] for ticket in result["tickets"] if ticket["scope"] == scope}
            self.assertEqual(targets, set(self.settings["parlays"]["targets"]), scope)
        tolerance = float(self.settings["parlays"]["tolerance"])
        for ticket in result["tickets"]:
            target_decimal = 1 + ticket["target"] / 100
            span = tolerance * (2 if ticket["off_target"] else 1)
            self.assertGreaterEqual(ticket["price_decimal"], target_decimal * (1 - span) - 1e-9)
            self.assertLessEqual(ticket["price_decimal"], target_decimal * (1 + span) + 1e-9)
            self.assertGreaterEqual(ticket["leg_count"], 2)
            self.assertGreater(ticket["model_prob"], 0)
            self.assertLess(ticket["model_prob"], 1)
            players = [(leg["player"], leg["market"]) for leg in ticket["legs"]]
            self.assertEqual(len(players), len(set(players)), "a ticket must not repeat a player's market")
            self.assertFalse(any(key.startswith("_") for leg in ticket["legs"] for key in leg))

    def test_bigger_targets_cost_win_chance(self):
        from pipeline.legs import build_legs
        from pipeline.parlays import build_parlays
        result = build_parlays(build_legs([], self._projections(), self.settings), self.settings)
        best = {}
        for ticket in result["tickets"]:
            if ticket["scope"] != "slate":
                continue
            best[ticket["target"]] = max(best.get(ticket["target"], 0), ticket["model_prob"])
        ordered = [best[target] for target in sorted(best)]
        self.assertEqual(ordered, sorted(ordered, reverse=True))

    def test_same_game_legs_are_correlated_but_capped(self):
        from pipeline.parlays import joint_probability
        cfg = self.settings["parlays"]["correlation"]
        qb = {"event_id": "g1", "team": "BUF", "player": "QB", "market": "Passing yards", "side": "over", "model_prob": 0.5}
        wr = {"event_id": "g1", "team": "BUF", "player": "WR", "market": "Receiving yards", "side": "over", "model_prob": 0.5}
        other = {"event_id": "g2", "team": "DAL", "player": "RB", "market": "Rushing yards", "side": "over", "model_prob": 0.5}
        self.assertGreater(joint_probability([qb, wr], cfg), 0.25)
        self.assertAlmostEqual(joint_probability([qb, other], cfg), 0.25, places=6)
        self.assertLessEqual(joint_probability([qb, wr], cfg), 0.25 * float(cfg["cap"]) + 1e-9)


class EspnPropLineTests(unittest.TestCase):
    """The keyless DraftKings line feed ESPN publishes (numbers, not prices)."""

    def setUp(self):
        import json as _json
        from pathlib import Path
        self.settings = _json.loads((Path(__file__).resolve().parents[1] / "config" / "settings.json").read_text())
        self.names = {
            "3139477": {"name": "Patrick Mahomes", "team": "Kansas City Chiefs"},
            "4362628": {"name": "Rashee Rice", "team": "Kansas City Chiefs"},
        }
        core = "http://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
        self.items = [
            {"athlete": {"$ref": f"{core}/seasons/2026/athletes/3139477?lang=en"},
             "type": {"id": "8", "name": "Total Passing Yards (incl. overtime)"},
             "current": {"target": {"value": 274.5}}, "lastUpdated": "2026-09-20T20:03Z"},
            {"athlete": {"$ref": f"{core}/seasons/2026/athletes/4362628?lang=en"},
             "type": {"id": "31", "name": "Anytime Touchdown Scorer"}, "current": {}},
            {"athlete": {"$ref": f"{core}/seasons/2026/athletes/4362628?lang=en"},
             "type": {"id": "9", "name": "Total Receptions (incl. overtime)"},
             "current": {"target": {"value": 5.5}}},
            {"athlete": {"$ref": f"{core}/seasons/2026/athletes/999999?lang=en"},
             "type": {"id": "8", "name": "Total Passing Yards (incl. overtime)"},
             "current": {"target": {"value": 210.5}}},
            {"athlete": {"$ref": f"{core}/seasons/2026/athletes/3139477?lang=en"},
             "type": {"id": "77", "name": "Player to score 3 or more touchdowns"},
             "current": {"target": {"value": 1.5}}},
            {"athlete": {"$ref": f"{core}/seasons/2026/athletes/3139477?lang=en"},
             "type": {"id": "8", "name": "Total Passing Yards (incl. overtime)"}, "current": {}},
        ]

    def test_market_names_are_mapped_and_unknown_ones_are_dropped(self):
        from pipeline.providers.espn_props import canonical_market
        self.assertEqual(canonical_market("Total Receiving Yards (incl. overtime)"), "Receiving yards")
        self.assertEqual(canonical_market("Anytime Touchdown Scorer"), "Anytime touchdown")
        self.assertEqual(canonical_market("Total Tackles Plus Assists (incl. overtime)"), "Tackles + assists")
        self.assertIsNone(canonical_market("Player to score 3 or more touchdowns"))

    def test_prop_items_become_player_market_line_rows(self):
        from pipeline.providers.espn_props import parse_prop_items
        rows = parse_prop_items(self.items, self.names)
        self.assertEqual(len(rows), 3, "unknown players, unknown markets and missing lines are skipped")
        passing = next(row for row in rows if row["market"] == "Passing yards")
        self.assertEqual(passing["player"], "Patrick Mahomes")
        self.assertEqual(passing["line"], 274.5)
        self.assertEqual(passing["book"], "DraftKings")
        touchdown = next(row for row in rows if row["market"] == "Anytime touchdown")
        self.assertIsNone(touchdown["line"], "a touchdown scorer has no number")

    def test_the_books_line_is_kept_and_scored(self):
        from pipeline.legs import legs_from_lines
        from pipeline.schema import Projection
        projection = Projection(
            sport="NFL", player="Rashee Rice", team="KC", matchup="KC @ BUF", market="Receptions",
            projection=6.4, samples=6, confidence=0.6, standard_deviation=1.6,
            recent=[5, 7, 8, 6, 4, 9], trend=0.3, start_time="2026-12-20T18:00:00Z")
        rows = [{"player": "Rashee Rice", "market": "Receptions", "line": 5.5, "book": "DraftKings",
                 "line_source": "DraftKings line via ESPN", "event_id": "1", "matchup": "KC @ BUF",
                 "start_time": "2026-12-20T18:00:00Z"}]
        legs = legs_from_lines(rows, [projection], self.settings)
        self.assertTrue(legs)
        for leg in legs:
            self.assertEqual(leg["line"], 5.5, "the model must not move the book's number")
            self.assertEqual(leg["line_source"], "DraftKings line via ESPN")
            self.assertEqual(leg["price_source"], "model", "no price is published with the line")
            self.assertIn("DraftKings posts 5.5", leg["reason"])
        self.assertEqual({leg["side"] for leg in legs}, {"over", "under"})
        over = next(leg for leg in legs if leg["side"] == "over")
        under = next(leg for leg in legs if leg["side"] == "under")
        self.assertAlmostEqual(over["model_prob"] + under["model_prob"], 1.0, places=3)

    def test_a_book_line_replaces_the_models_own_line_for_that_market(self):
        from pipeline.legs import build_legs
        from pipeline.schema import Projection
        projection = Projection(
            sport="NFL", player="Rashee Rice", team="KC", matchup="KC @ BUF", market="Receptions",
            projection=6.4, samples=6, confidence=0.6, standard_deviation=1.6,
            recent=[5, 7, 8, 6, 4, 9], trend=0.3, start_time="2026-12-20T18:00:00Z")
        rows = [{"player": "Rashee Rice", "market": "Receptions", "line": 5.5, "book": "DraftKings",
                 "line_source": "DraftKings line via ESPN", "event_id": "1", "matchup": "KC @ BUF",
                 "start_time": "2026-12-20T18:00:00Z"}]
        legs = build_legs([], [projection], self.settings, rows)
        receptions = [leg for leg in legs if leg["market"] == "Receptions"]
        self.assertTrue(receptions)
        self.assertTrue(all(leg.get("line_source") for leg in receptions), "invented lines give way to the book's")
        self.assertEqual({leg["line"] for leg in receptions}, {5.5})


class NameMatchingTests(unittest.TestCase):
    def test_a_suffix_does_not_break_the_match(self):
        from pipeline.legs import _name_key
        self.assertEqual(_name_key("Patrick Mahomes II"), _name_key("Patrick Mahomes"))
        self.assertEqual(_name_key("Marvin Harrison Jr."), _name_key("Marvin Harrison"))
        self.assertEqual(_name_key("De'Von Achane"), "dachane")
        self.assertNotEqual(_name_key("Josh Allen"), _name_key("Keenan Allen"))

    def test_the_book_line_finds_a_player_listed_with_a_suffix(self):
        from pipeline.legs import legs_from_lines
        from pipeline.schema import Projection
        import json as _json
        from pathlib import Path
        settings = _json.loads((Path(__file__).resolve().parents[1] / "config" / "settings.json").read_text())
        projection = Projection(
            sport="NFL", player="Patrick Mahomes II", team="KC", matchup="IND @ KC", market="Passing yards",
            projection=268.0, samples=6, confidence=0.6, standard_deviation=42.0,
            recent=[240, 310, 255, 288, 201, 314], trend=0.2, start_time="2026-12-20T18:00:00Z")
        rows = [{"player": "Patrick Mahomes", "market": "Passing yards", "line": 274.5, "book": "DraftKings",
                 "line_source": "DraftKings line via ESPN", "event_id": "1", "matchup": "IND @ KC",
                 "start_time": "2026-12-20T18:00:00Z"}]
        legs = legs_from_lines(rows, [projection], settings)
        self.assertTrue(legs, "the suffix must not stop the book line from being scored")
        self.assertEqual({leg["line"] for leg in legs}, {274.5})


class InjuryAndMovementTests(unittest.TestCase):
    def setUp(self):
        import json as _json
        from pathlib import Path
        from pipeline.schema import Projection
        self.settings = _json.loads((Path(__file__).resolve().parents[1] / "config" / "settings.json").read_text())
        self.projections = [
            Projection(sport="NFL", player=name, team="KC", matchup="IND @ KC", market="Receiving yards",
                       projection=58.0, samples=6, confidence=0.6, standard_deviation=18.0,
                       recent=[40, 62, 71, 55, 48, 66], trend=0.2, start_time="2026-12-20T18:00:00Z")
            for name in ("Rashee Rice", "Travis Kelce")
        ]
        self.lines = [
            {"player": "Rashee Rice", "market": "Receiving yards", "line": 54.5, "open_line": 49.5,
             "book": "DraftKings", "line_source": "DraftKings line via ESPN", "event_id": "1",
             "matchup": "IND @ KC", "start_time": "2026-12-20T18:00:00Z"},
            {"player": "Travis Kelce", "market": "Receiving yards", "line": 60.5, "open_line": 60.5,
             "book": "DraftKings", "line_source": "DraftKings line via ESPN", "event_id": "1",
             "matchup": "IND @ KC", "start_time": "2026-12-20T18:00:00Z"},
        ]

    def test_the_report_is_read_and_the_worst_status_wins(self):
        from pipeline.providers.espn_injuries import parse_report
        report = parse_report({"injuries": [{"displayName": "Kansas City Chiefs", "injuries": [
            {"status": "Questionable", "athlete": {"displayName": "Rashee Rice"}, "type": {"description": "Hamstring"}},
            {"status": "Out", "athlete": {"displayName": "Rashee Rice"}, "type": {"description": "Hamstring"}},
            {"status": "Questionable", "athlete": {"displayName": "Travis Kelce"}},
        ]}]})
        self.assertEqual(report["rrice"]["blocking"], "yes", "Out must override an earlier Questionable")
        self.assertEqual(report["tkelce"]["blocking"], "no")

    def test_a_player_who_is_out_never_reaches_the_board(self):
        from pipeline.legs import legs_from_lines
        injuries = {"rrice": {"player": "Rashee Rice", "status": "Out", "blocking": "yes", "detail": "Hamstring"}}
        legs = legs_from_lines(self.lines, self.projections, self.settings, injuries)
        self.assertTrue(legs)
        self.assertFalse(any(leg["player"] == "Rashee Rice" for leg in legs))

    def test_a_questionable_player_stays_but_is_flagged(self):
        from pipeline.legs import legs_from_lines
        injuries = {"tkelce": {"player": "Travis Kelce", "status": "Questionable", "blocking": "no", "detail": "Knee"}}
        legs = [leg for leg in legs_from_lines(self.lines, self.projections, self.settings, injuries)
                if leg["player"] == "Travis Kelce"]
        self.assertTrue(legs)
        for leg in legs:
            self.assertEqual(leg["status"], "Questionable")
            self.assertIn("Questionable", leg["reason"])

    def test_line_movement_is_reported_when_the_number_moved(self):
        from pipeline.legs import legs_from_lines
        legs = legs_from_lines(self.lines, self.projections, self.settings)
        moved = [leg for leg in legs if leg["player"] == "Rashee Rice"]
        still = [leg for leg in legs if leg["player"] == "Travis Kelce"]
        self.assertTrue(moved and still)
        self.assertIn("Line moved up from 49.5", moved[0]["reason"])
        self.assertEqual(moved[0]["open_line"], 49.5)
        self.assertNotIn("Line moved", still[0]["reason"])


class GradingTests(unittest.TestCase):
    def _summary(self):
        return {"boxscore": {"players": [{"statistics": [
            {"name": "passing", "keys": ["completions/passingAttempts", "passingYards", "passingTouchdowns"],
             "athletes": [{"athlete": {"displayName": "Patrick Mahomes II"}, "stats": ["24/33", "287", "2"]}]},
            {"name": "receiving", "keys": ["receptions", "receivingYards", "receivingTouchdowns"],
             "athletes": [
                 {"athlete": {"displayName": "Rashee Rice"}, "stats": ["6", "72", "1"]},
                 {"athlete": {"displayName": "Travis Kelce"}, "stats": ["4", "41", "0"]}]},
        ]}]}}

    def test_box_score_values_cover_every_market_we_price(self):
        from pipeline.grade import market_values
        values = market_values(self._summary())
        self.assertEqual(values[("pmahomes", "Pass completions")], 24)
        self.assertEqual(values[("pmahomes", "Pass attempts")], 33)
        self.assertEqual(values[("pmahomes", "Passing yards")], 287)
        self.assertEqual(values[("rrice", "Receptions")], 6)
        self.assertEqual(values[("rrice", "Anytime touchdown")], 1)
        self.assertEqual(values[("tkelce", "Anytime touchdown")], 0)

    def test_legs_are_graded_win_loss_and_push(self):
        from pipeline.grade import grade_leg, market_values
        values = market_values(self._summary())
        over = {"player": "Rashee Rice", "market": "Receiving yards", "side": "over", "line": 58.5}
        under = {"player": "Rashee Rice", "market": "Receiving yards", "side": "under", "line": 58.5}
        push = {"player": "Travis Kelce", "market": "Receptions", "side": "over", "line": 4.0}
        touchdown = {"player": "Travis Kelce", "market": "Anytime touchdown", "side": "yes", "line": None}
        missing = {"player": "Nobody Here", "market": "Receptions", "side": "over", "line": 2.5}
        self.assertEqual(grade_leg(over, values)[0], "Win")
        self.assertEqual(grade_leg(under, values)[0], "Loss")
        self.assertEqual(grade_leg(push, values)[0], "Push")
        self.assertEqual(grade_leg(touchdown, values)[0], "Loss")
        self.assertIsNone(grade_leg(missing, values), "a player who did not appear stays ungraded")

    def test_accuracy_reports_record_buckets_and_a_shrink(self):
        from pipeline.grade import accuracy_from
        # A model that says 70% but only hits 50% must be told to shrink.
        rows = [{"market": "Receptions", "model_prob": 0.7, "result": "Win" if index % 2 else "Loss"}
                for index in range(300)]
        accuracy = accuracy_from(rows)
        self.assertEqual(accuracy["settled"], 300)
        self.assertTrue(accuracy["calibration_active"])
        self.assertLess(accuracy["calibration_shrink"], 1.0)
        self.assertAlmostEqual(accuracy["hit_rate"], 0.5, places=2)
        self.assertTrue(any(bucket["legs"] for bucket in accuracy["buckets"]))
        self.assertIn("Receptions", accuracy["by_market"])

    def test_a_short_record_never_moves_the_model(self):
        from pipeline.grade import accuracy_from
        rows = [{"market": "Receptions", "model_prob": 0.7, "result": "Loss"} for _ in range(20)]
        accuracy = accuracy_from(rows)
        self.assertFalse(accuracy["calibration_active"])
        self.assertEqual(accuracy["calibration_shrink"], 1.0)

    def test_calibration_pulls_probabilities_toward_a_coin_flip(self):
        from pipeline.legs import calibrated
        self.assertEqual(calibrated(0.8, 1.0), 0.8)
        self.assertAlmostEqual(calibrated(0.8, 0.5), 0.65, places=3)
        self.assertAlmostEqual(calibrated(0.2, 0.5), 0.35, places=3)

    def test_a_snapshot_is_written_and_graded_once_the_game_is_final(self):
        import json as _json, tempfile
        from pathlib import Path
        from pipeline.grade import Grader
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            grader = Grader(root, {})
            legs = [{"id": "leg-1", "event_id": "401", "player": "Rashee Rice", "market": "Receiving yards",
                     "side": "over", "line": 58.5, "model_prob": 0.56, "price_american": -115,
                     "start_time": "2020-01-01T00:00:00Z", "matchup": "IND @ KC", "line_source": "DK"}]
            path = grader.snapshot(legs, "2026-09-20")
            self.assertTrue(path.exists())
            saved = _json.loads(path.read_text())
            self.assertEqual(saved["legs"][0]["player"], "Rashee Rice")

            grader.client = type("Stub", (), {"get": lambda self, *a, **k: {
                "header": {"competitions": [{"status": {"type": {"completed": True}}}]},
                "boxscore": {"players": [{"statistics": [{"name": "receiving", "keys": ["receptions", "receivingYards"],
                    "athletes": [{"athlete": {"displayName": "Rashee Rice"}, "stats": ["6", "72"]}]}]}]}}})()
            accuracy = grader.run()
            graded = _json.loads(grader.graded_path.read_text())
            self.assertEqual(len(graded), 1)
            self.assertEqual(graded[0]["result"], "Win")
            self.assertEqual(graded[0]["actual"], 72)
            self.assertEqual(accuracy["record"], "1-0")
            grader.run()
            self.assertEqual(len(_json.loads(grader.graded_path.read_text())), 1, "a leg is graded once")


class PostedLineParlayTests(unittest.TestCase):
    """Every leg on a parlay card has to be a number a sportsbook actually posts.

    The model can invent a line to score a player, which is useful on the board but
    useless on a bet slip, so once enough real lines are in hand the parlay builder
    uses nothing else.
    """

    def setUp(self):
        import json as _json
        from pathlib import Path
        self.settings = _json.loads((Path(__file__).resolve().parents[1] / "config" / "settings.json").read_text())

    def _fixture(self, posted_players: int):
        """Projections for 24 players plus book lines for the first ``posted_players``."""
        from pipeline.schema import Projection
        import datetime as _dt
        start = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=18)).isoformat()
        markets = [("Passing yards", 250.0, 46.0), ("Receiving yards", 62.0, 23.0),
                   ("Receptions", 5.0, 2.0), ("Rushing yards", 60.0, 21.0)]
        projections: list[Projection] = []
        lines: list[dict[str, object]] = []
        seat = 0
        for game, (away, home) in enumerate([("BUF", "HOU"), ("DAL", "NYG"), ("NO", "DET")]):
            for team in (away, home):
                for index in range(4):
                    player = f"{team} P{index}"
                    market, base, deviation = markets[(index + game) % len(markets)]
                    scale = 0.6 + 0.2 * index + 0.1 * game
                    projection = base * scale
                    recent = [round(projection * (0.7 + 0.12 * ((step + index) % 6)), 1) for step in range(6)]
                    projections.append(Projection(
                        sport="NFL", player=player, team=team, matchup=f"{away} @ {home}", market=market,
                        projection=projection, samples=6, confidence=0.6, standard_deviation=deviation,
                        recent=recent, trend=0.3, start_time=start))
                    if seat < posted_players:
                        step = 0.5 if market == "Receptions" else 0.5
                        lines.append({
                            "player": player, "market": market,
                            "line": round(projection * 2) / 2 + step, "book": "DraftKings",
                            "line_source": "DraftKings line via ESPN", "event_id": f"g{game}",
                            "matchup": f"{away} @ {home}", "start_time": start,
                        })
                    seat += 1
        return projections, lines

    def test_a_parlay_only_uses_lines_the_book_posts(self):
        from pipeline.legs import build_legs
        from pipeline.parlays import build_parlays, posted
        projections, lines = self._fixture(posted_players=18)
        legs = build_legs([], projections, self.settings, lines)
        self.assertTrue(any(not posted(leg) for leg in legs), "the board still carries model-only lines")
        result = build_parlays(legs, self.settings)
        self.assertTrue(result["tickets"])
        for ticket in result["tickets"]:
            self.assertTrue(ticket["all_posted"], ticket["id"])
            for leg in ticket["legs"]:
                self.assertTrue(posted(leg), f"{leg['pick']} is not a number the book posts")

    def test_a_thin_book_feed_falls_back_to_the_whole_board(self):
        from pipeline.legs import build_legs
        from pipeline.parlays import build_parlays
        projections, lines = self._fixture(posted_players=2)
        result = build_parlays(build_legs([], projections, self.settings, lines), self.settings)
        self.assertTrue(result["tickets"], "a near-empty line feed must not empty the parlay lab")

    def test_posted_recognises_a_real_price_as_well_as_a_real_line(self):
        from pipeline.parlays import posted
        self.assertTrue(posted({"line_source": "DraftKings line via ESPN", "price_source": "model"}))
        self.assertTrue(posted({"price_source": "book"}))
        self.assertFalse(posted({"price_source": "model"}))
