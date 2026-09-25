import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from pipeline.providers.covers import CoversProvider, parse_html
from pipeline.http import ProviderError
from pipeline.schema import Projection


def projection(player="Patrick Mahomes", market="Rushing yards", event_id="401872931"):
    return Projection(
        sport="NFL",
        player=player,
        team="Kansas City Chiefs",
        matchup="Denver Broncos @ Kansas City Chiefs",
        market=market,
        projection=23.5,
        samples=8,
        confidence=0.65,
        standard_deviation=10.0,
        recent=[12, 18, 24, 31],
        trend=0.0,
        start_time="2026-09-15T00:15:00+00:00",
        event_id=event_id,
    )


HTML = """
<html><body>
  <section class="prop-card">
    <h3>RUSHING YARDS</h3>
    <a>DEN @ KC</a>
    <img alt="Patrick Mahomes logo">
    <span>P. Mahomes</span><span>(QB)</span>
    <strong>o13.5 Rushing Yards</strong>
    <div><img alt="BetMGM logo"><b>o13.5</b> -130</div>
    <div><img alt="DraftKings logo"><b>o13.5</b> -115</div>
    <div><img alt="Unavailable Book logo"><b>o13.5</b> -105</div>
  </section>
  <section class="prop-card">
    <h3>RUSHING YARDS</h3>
    <a>DEN @ KC</a>
    <img alt="Patrick Mahomes logo">
    <span>P. Mahomes</span><span>(QB)</span>
    <strong>u13.5 Rushing Yards</strong>
    <div><img alt="BetMGM Sportsbook logo"><b>u13.5</b> +105</div>
    <div><img alt="DraftKings logo"><b>u13.5</b> -105</div>
  </section>
  <section class="prop-card">
    <h3>ANYTIME TOUCHDOWN</h3>
    <a>DEN @ KC</a>
    <img alt="Patrick Mahomes logo">
    <span>P. Mahomes</span><span>(QB)</span>
    <strong>Anytime Touchdown</strong>
    <div><img alt="FanDuel logo"><b>+700</b></div>
  </section>
</body></html>
"""


class CoversParserTests(unittest.TestCase):
    def test_extracts_real_books_lines_sides_and_prices(self):
        rows = parse_html(
            HTML,
            [projection(), projection(market="Anytime touchdown")],
            observed_at="2026-09-14T12:00:00+00:00",
        )
        self.assertEqual(len(rows), 5)
        by_offer = {(row.book, row.side, row.line): row for row in rows}
        self.assertEqual(by_offer[("BetMGM", "over", 13.5)].price_american, -130)
        self.assertEqual(by_offer[("DraftKings", "under", 13.5)].price_american, -105)
        self.assertEqual(by_offer[("FanDuel", "yes", None)].price_american, 700)
        self.assertTrue(all(row.event_id == "401872931" for row in rows))
        self.assertTrue(all(row.updated_at == "2026-09-14T12:00:00+00:00" for row in rows))
        self.assertNotIn("Unavailable Book", {row.book for row in rows})

    def test_requires_a_unique_scheduled_projection(self):
        self.assertEqual(parse_html(HTML, [], observed_at="2026-09-14T12:00:00+00:00"), [])
        duplicate = projection(event_id="different")
        rows = parse_html(
            HTML,
            [projection(), duplicate],
            observed_at="2026-09-14T12:00:00+00:00",
        )
        self.assertEqual(rows, [])

    def test_deduplicates_repeated_page_cards(self):
        rows = parse_html(
            HTML + HTML,
            [projection(), projection(market="Anytime touchdown")],
            observed_at="2026-09-14T12:00:00+00:00",
        )
        self.assertEqual(len(rows), 5)

    def test_rejects_other_sports_at_provider_boundary(self):
        from pipeline.providers.covers import CoversProvider

        self.assertEqual(CoversProvider({}).fetch("NBA", []), [])

    def test_single_player_still_requires_the_correct_matchup(self):
        self.assertEqual(parse_html(HTML.replace('DEN @ KC','IND @ KC'),[projection()]),[])

    def test_unknown_book_cannot_lend_its_price_to_a_missing_known_offer(self):
        html='<section class="picks-card"><h3>RUSHING YARDS</h3><span>DEN @ KC</span><span>Patrick Mahomes</span><img alt="DraftKings logo"><span>-</span><img alt="UnknownBook logo"><b>o13.5</b> -110</section>'
        self.assertEqual(parse_html(html,[projection()]),[])

    def test_prices_cannot_leak_from_a_later_team_total_card(self):
        html='<section class="picks-card"><h3>RUSHING YARDS</h3><span>DEN @ KC</span><span>Patrick Mahomes</span><img alt="DraftKings logo"><span>-</span></section><section class="picks-card"><h3>TOTAL</h3><span>DEN @ KC</span><img alt="DraftKings logo"><b>o43.5</b> -110</section>'
        self.assertEqual(parse_html(html,[projection()]),[])


class CoversFetchTests(unittest.TestCase):
    @staticmethod
    def response(html):
        response = io.BytesIO(html.encode())
        response.headers = {'Content-Type': 'text/html; charset=utf-8'}
        return response

    def test_transient_empty_page_retries_then_returns_only_observed_quotes(self):
        with patch('urllib.request.urlopen', side_effect=[self.response('<html>Loading prices</html>'), self.response(HTML)]) as request, patch('pipeline.providers.covers.time.sleep') as pause:
            quotes = CoversProvider({}).fetch('NFL', [projection()])
        self.assertEqual(len(quotes), 4)
        self.assertEqual(request.call_count, 2)
        pause.assert_called_once_with(1.5)

    def test_persistent_empty_page_has_bounded_retries_and_shape_diagnostics(self):
        with patch('urllib.request.urlopen', side_effect=[self.response(HTML) for _ in range(3)]) as request, patch('pipeline.providers.covers.time.sleep') as pause:
            with self.assertRaisesRegex(ProviderError, '3 cards, 3 recognized prop cards, 0 scheduled-player matches'):
                CoversProvider({}).fetch('NFL', [])
        self.assertEqual(request.call_count, 3)
        self.assertEqual(pause.call_count, 2)

    def test_access_denial_is_not_retried(self):
        for response in [self.response('<html>Access denied. Verify you are human.</html>'), HTTPError('https://www.covers.com',403,'Forbidden',{},None)]:
            with self.subTest(response=type(response).__name__), patch('urllib.request.urlopen', side_effect=[response]) as request, patch('pipeline.providers.covers.time.sleep') as pause:
                with self.assertRaises(ProviderError):
                    CoversProvider({}).fetch('NFL', [projection()])
                self.assertEqual(request.call_count, 1)
                pause.assert_not_called()


if __name__ == "__main__":
    unittest.main()
