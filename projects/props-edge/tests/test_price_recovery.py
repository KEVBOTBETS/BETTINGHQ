import datetime as dt
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import io

from pipeline.price_store import recover
from pipeline.schema import Projection, PropQuote
from pipeline.qualified import quote_block_reason, evaluate_quotes_against_projections
from pipeline.providers.draftkings_network import parse_html, DraftKingsNetworkProvider
from pipeline.providers.covers import parse_html as covers_parse
from pipeline.http import ProviderError

NOW = dt.datetime(2026, 10, 10, 14, 0, tzinfo=dt.timezone.utc)
START = '2026-10-11T17:00:00Z'
SETTINGS = json.loads((Path(__file__).parents[1]/'config/qualification.json').read_text())
PROJECTION = Projection('NFL', 'Jonathan Taylor', 'Indianapolis Colts', 'Indianapolis Colts @ Pittsburgh Steelers',
                        'Anytime touchdown', .75, 8, .8, .4, [1, 1, 1, 1, 0, 1, 1, 1], 0,
                        start_time=START, event_id='401872985', current_season_samples=4)
QUOTE = PropQuote('NFL', PROJECTION.event_id, START, PROJECTION.matchup, PROJECTION.player, PROJECTION.market,
                  'yes', None, 2.0, 100, 'DraftKings', 'Covers public prop comparison', NOW.isoformat())
HTML = '''<table><thead><tr><th>Event</th><th>Event Date</th><th>Market</th><th>Betslip Line</th><th>Odds</th></tr></thead>
<tbody><tr><td>IND Colts @ PIT Steelers</td><td>10/11, 01:00PM</td><td>Anytime TD Scorer</td><td>Jonathan Taylor</td><td><a>−180</a></td></tr>
<tr><td>IND Colts @ PIT Steelers</td><td>10/11, 01:00PM</td><td>2+ TDs</td><td>Jonathan Taylor</td><td>+300</td></tr>
</tbody></table>'''


class PublicFallbackTests(unittest.TestCase):
    def test_exact_player_event_date_market_and_price(self):
        rows, diag = parse_html(HTML, [PROJECTION], NOW.isoformat())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].price_american, -180)
        self.assertTrue(rows[0].reference_only)
        self.assertEqual(rows[0].event_id, '401872985')
        self.assertEqual(diag['unsupported'], 1)
        self.assertIsNotNone(quote_block_reason(rows[0], SETTINGS['projection_model'], NOW))

    def test_mismatches_ambiguous_events_and_invented_odds_are_rejected(self):
        for text in [HTML.replace('IND Colts', 'DEN Broncos'), HTML.replace('10/11', '10/12'), HTML.replace('01:00PM', '02:00PM'),
                     HTML.replace('Jonathan Taylor', 'J. Taylor'), HTML.replace('−180', 'Projected -180')]:
            self.assertEqual(parse_html(text, [PROJECTION], NOW.isoformat())[0], [])
        self.assertEqual(parse_html(HTML, [PROJECTION, replace(PROJECTION, event_id='different')], NOW.isoformat())[0], [])

    def test_unavailable_page_is_not_retried_or_parsed_as_a_price(self):
        response = io.BytesIO(b'<html>Site Unavailable. Unable to access this site.</html>')
        response.headers = {'Content-Type': 'text/html'}
        with patch('urllib.request.urlopen', return_value=response) as request:
            with self.assertRaises(ProviderError):
                DraftKingsNetworkProvider({}).fetch('NFL', [PROJECTION])
        self.assertEqual(request.call_count, 1)

    def test_covers_unicode_minus_and_real_odds_logo(self):
        html = '<section class="picks-card"><h3>ANYTIME TOUCHDOWN</h3><span>IND @ PIT</span><span>Jonathan Taylor</span><img alt="Caesars Odds logo"><b>−180</b></section>'
        rows = covers_parse(html, [PROJECTION], NOW.isoformat())
        self.assertEqual([(q.book, q.price_american) for q in rows], [('Caesars', -180)])


class RetentionTests(unittest.TestCase):
    def recover(self, current=(), previous=(), failed=('Covers public prop comparison',), now=NOW):
        return recover(list(current), {'quotes': [q.to_dict() for q in previous]}, [PROJECTION], SETTINGS, set(failed), now)

    def test_outage_retains_exact_price_line_and_original_time_without_qualification(self):
        active, state, health = self.recover(previous=[QUOTE], now=NOW+dt.timedelta(hours=1))
        self.assertEqual(active[0].updated_at, QUOTE.updated_at)
        self.assertEqual(active[0].price_american, QUOTE.price_american)
        self.assertEqual(active[0].quote_status, 'retained')
        self.assertEqual(health['retained'], 1)
        rows = evaluate_quotes_against_projections(active, [PROJECTION], SETTINGS)
        self.assertTrue(rows)
        self.assertTrue(all(row['tier']=='PASS' and row['recommended_stake']==0 for row in rows))

    def test_expiry_excludes_current_quotes_but_keeps_history(self):
        active, state, health = self.recover(previous=[QUOTE], now=NOW+dt.timedelta(hours=4))
        self.assertEqual(active, [])
        self.assertEqual(state['quotes'][0]['updated_at'], QUOTE.updated_at)
        self.assertEqual(state['quotes'][0]['quote_status'], 'expired')
        self.assertEqual(health['expired'], 1)

    def test_success_does_not_restore_an_offer_missing_from_that_source(self):
        active, state, health = self.recover(previous=[QUOTE], failed=[])
        self.assertEqual(active, [])
        self.assertEqual(state['quotes'], [])

    def test_recovered_source_replaces_cached_offer_and_clears_retention(self):
        new = replace(QUOTE, price_american=120, price_decimal=2.2, updated_at=(NOW+dt.timedelta(minutes=5)).isoformat())
        active, state, health = self.recover(current=[new], previous=[QUOTE], now=NOW+dt.timedelta(minutes=10))
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].quote_status, 'observed')
        self.assertEqual(active[0].price_american, 120)
        self.assertEqual(health['observed'], 1)

    def test_bad_timestamps_prices_contracts_and_rosters_cannot_be_recovered(self):
        bad=[replace(QUOTE, updated_at=None), replace(QUOTE, updated_at=(NOW+dt.timedelta(hours=1)).isoformat()),
             replace(QUOTE, event_id='other'), replace(QUOTE, start_time='2026-10-11T18:00:00Z'),
             replace(QUOTE, price_decimal=9), replace(QUOTE, line=1)]
        for q in bad:
            self.assertEqual(self.recover(previous=[q])[0], [])
        self.assertEqual(recover([], {'quotes':[QUOTE.to_dict()]}, [replace(PROJECTION,roster_verified=False)], SETTINGS, {QUOTE.provider}, NOW)[0], [])


if __name__ == '__main__':
    unittest.main()
