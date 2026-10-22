import datetime as dt
import json
import unittest
from copy import deepcopy
from pathlib import Path
from pipeline.parlays import build_parlays, single_game_extras
from pipeline.schema import american_to_decimal


class TonightExtrasTests(unittest.TestCase):
    now = dt.datetime(2026, 10, 22, 19, tzinfo=dt.timezone.utc)

    def setUp(self):
        self.settings = json.loads((Path(__file__).parents[1]/'config/settings.json').read_text())
        self.legs = [dict(id=str(i), sport='NFL', event_id='401873010', player='Player '+str(i),
                         team='Team', matchup='New England Patriots @ Chicago Bears',
                         market='Receiving yards', side='over', line=35.5, model_prob=.6,
                         price_american=price, price_decimal=american_to_decimal(price),
                         price_source='book', book='DraftKings', samples=8, confidence=.7,
                         tier='PASS', held=True, updated_at=self.now.isoformat(),
                         start_time='2026-10-23T00:15Z')
                     for i, price in enumerate([100,100,150,150,200,200])]

    def test_exact_event_date_targets_and_honest_research(self):
        tickets = single_game_extras(self.legs, self.settings, self.now)
        self.assertEqual({t['target'] for t in tickets}, {300,400,500})
        for t in tickets:
            self.assertLessEqual(abs(t['price_american']-t['target']), .02*t['target'])
            self.assertTrue(t['tonight_extra'])
            self.assertEqual(t['scope'], 'game')
            self.assertFalse(t['actionable'])
            self.assertFalse(t['combined_quote_verified'])
            self.assertIsNone(t['model_prob'])
            self.assertIsNone(t['expected_value_on_10'])
            self.assertIsNone(t['one_in'])
            self.assertLessEqual(t['leg_count'], 3)
            self.assertEqual(len({l['player'] for l in t['legs']}), t['leg_count'])
            self.assertEqual({l['event_id'] for l in t['legs']}, {'401873010'})

    def test_other_games_and_existing_tickets_unchanged(self):
        legs = self.legs + [{**l, 'id':'other-'+l['id'], 'event_id':'999', 'matchup':'Other @ Game'} for l in self.legs]
        original = deepcopy(legs)
        baseline = deepcopy(self.settings)
        baseline['parlays'].pop('single_game_extras')
        before = build_parlays(legs, baseline, self.now)
        after = build_parlays(legs, self.settings, self.now)
        self.assertEqual([t for t in after['tickets'] if not t.get('tonight_extra')], before['tickets'])
        self.assertEqual(after['targets'], before['targets'])
        self.assertEqual(after['profiles'], before['profiles'])
        self.assertEqual(set(after['game_target_extras']), {'New England Patriots @ Chicago Bears'})
        self.assertEqual(legs, original)

    def test_expiry_wrong_event_date_and_unsupported_rows(self):
        for changes in [dict(event_id='999'), dict(start_time='2026-10-24T00:15Z'),
                        dict(start_time='2026-10-22T18:00Z'), dict(samples=3),
                        dict(samples=5), dict(confidence=.5), dict(status='Questionable'), dict(roster_verified=False),
                        dict(price_source='model', line_source=None), dict(book='Other'),
                        dict(reference_only=True), dict(quote_status='retained'),
                        dict(updated_at='2026-10-22T17:00Z'), dict(updated_at='2026-10-22T20:00Z'),
                        dict(model_prob=float('nan')), dict(market='Anytime touchdown')]:
            self.assertEqual(single_game_extras([{**l, **changes} for l in self.legs], self.settings, self.now), [], changes)
        self.assertEqual(single_game_extras(self.legs, self.settings, dt.datetime(2026,10,23,0,15,tzinfo=dt.timezone.utc)), [])
        self.assertEqual(single_game_extras(self.legs, self.settings, self.now-dt.timedelta(days=1)), [])

    def test_posted_model_lines_stay_estimated_and_no_forced_target(self):
        legs = [{**l, 'price_source':'model', 'line_source':'DraftKings line via ESPN', 'updated_at':None} for l in self.legs]
        tickets = single_game_extras(legs, self.settings, self.now)
        self.assertTrue(tickets)
        self.assertTrue(all(t['estimated_prices'] for t in tickets))
        self.assertEqual(single_game_extras(legs[:1], self.settings, self.now), [])
