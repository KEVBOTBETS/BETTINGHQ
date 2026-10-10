"""Public DraftKings Network table; exact scheduled contracts only, no credentials.

This is a regional reference feed, not confirmation of the user's local offer.
Unsupported thresholds (such as 50+ yards) are never reinterpreted as O/U bets.
"""
from __future__ import annotations

import datetime as dt
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Any
from zoneinfo import ZoneInfo

from ..http import ProviderError, response_text
from ..schema import Projection, PropQuote, american_to_decimal
from .covers import _clean, _compact, _projection_matchup_key

SOURCE_URL = "https://dknetwork.draftkings.com/draftkings-sportsbook-player-props/"


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.table = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(_clean(" ".join(self.cell)))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def parse_html(html: str, projections: list[Projection], observed_at: str) -> tuple[list[PropQuote], dict[str, Any]]:
    parser = _TableParser()
    parser.feed(html)
    quotes = {}
    diagnostic = {"tables": len(parser.tables), "rows": 0, "unsupported": 0, "unmatched": 0, "source_url": SOURCE_URL}
    for table in parser.tables:
        if not table or [_compact(c) for c in table[0]] != ["event", "eventdate", "market", "betslipline", "odds"]:
            continue
        for cells in table[1:]:
            if len(cells) != 5:
                continue
            diagnostic["rows"] += 1
            event, event_date, market, selection, price = cells
            # Initially support the unambiguous anytime TD contract. Other
            # public table rows include alternate milestones with different rules.
            if _compact(market) not in {"anytimetdscorer", "anytimetouchdownscorer"}:
                diagnostic["unsupported"] += 1
                continue
            if not re.fullmatch(r"[+-]\d{3,5}", price) or abs(int(price)) < 100:
                diagnostic["unsupported"] += 1
                continue
            sides = re.split(r"\s+@\s+", event)
            key = "@".join(side.split()[0].upper() for side in sides) if len(sides) == 2 else ""
            key = key.replace("JAX", "JAC").replace("LAR", "LA").replace("LAC", "LAC")
            candidates = []
            for p in projections:
                if p.sport != "NFL" or p.market != "Anytime touchdown" or _compact(p.player) != _compact(selection) or _projection_matchup_key(p) != key:
                    continue
                try:
                    start = dt.datetime.fromisoformat(p.start_time.replace("Z", "+00:00"))
                    if start.tzinfo is None:
                        continue
                    expected = start.astimezone(ZoneInfo("America/New_York")).strftime("%m/%d, %I:%M%p")
                    if _compact(expected) == _compact(event_date):
                        candidates.append(p)
                except (ValueError, TypeError):
                    continue
            if len(candidates) != 1:
                diagnostic["unmatched"] += 1
                continue
            p = candidates[0]
            q = PropQuote("NFL", p.event_id, p.start_time, p.matchup, p.player, p.market, "yes", None,
                          american_to_decimal(int(price)), int(price), "DraftKings", "DraftKings Network public reference",
                          observed_at, SOURCE_URL, reference_only=True)
            quotes[(q.event_id, q.player, q.market)] = q
    diagnostic["quotes"] = len(quotes)
    return list(quotes.values()), diagnostic


class DraftKingsNetworkProvider:
    name = "DraftKings Network public reference"

    def __init__(self, settings):
        self.settings = settings
        self.diagnostics = {}

    def fetch(self, sport, projections):
        if sport != "NFL":
            return []
        request = urllib.request.Request(SOURCE_URL, headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0 (compatible; KEVBOTBETS/1.0; public-market-reader)"})
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                if "html" not in str(response.headers.get("Content-Type", "")).lower():
                    raise ProviderError("DraftKings Network returned a non-HTML response")
                html = response_text(response, 4_000_000)
            if re.search(r"site unavailable|access denied|captcha|verify (?:that )?you are human", html, re.I):
                raise ProviderError("DraftKings Network public page unavailable; no access retry attempted")
            quotes, self.diagnostics = parse_html(html, projections, dt.datetime.now(dt.timezone.utc).isoformat())
            if not quotes:
                raise ProviderError("DraftKings Network returned no exact scheduled supported offers")
            return quotes
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(f"DraftKings Network request unavailable ({type(exc).__name__})") from exc
