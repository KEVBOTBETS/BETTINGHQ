"""Real sportsbook prop LINES from ESPN's public feed — no API key, no scraping.

ESPN publishes the DraftKings prop board for each NFL game on its own public API
(`.../competitions/{id}/odds/{casino}/propBets`). It carries the player, the market
and the number the book is posting, but not the price. That is still the important
half: the model can score the exact line that will be on the bet slip, instead of
inventing its own number. Prices stay model estimates until a price feed or a
pasted line supplies them.
"""
from __future__ import annotations

import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..http import JsonClient, ProviderError

CORE_URL = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
SITE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
DRAFTKINGS_CASINO = 100

# ESPN's prop names, mapped onto the markets this project already models.
MARKETS = {
    "total passing yards": "Passing yards",
    "total pass completions": "Pass completions",
    "total passing attempts": "Pass attempts",
    "total passing touchdowns": "Passing touchdowns",
    "total passing interceptions": "Pass interceptions",
    "longest passing completion": "Longest pass",
    "total carries": "Rush attempts",
    "total rushing yards": "Rushing yards",
    "longest rush": "Longest rush",
    "total receiving yards": "Receiving yards",
    "total receptions": "Receptions",
    "longest reception": "Longest reception",
    "total kicking points": "Kicking points",
    "total field goals made": "Field goals made",
    "total extra points made": "Extra points made",
    "total tackles plus assists": "Tackles + assists",
    "total sacks": "Sacks",
    "anytime touchdown scorer": "Anytime touchdown",
}


def canonical_market(name: str) -> str | None:
    cleaned = re.sub(r"\(.*?\)", "", str(name or "")).strip().casefold()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return MARKETS.get(cleaned)


def athlete_id(reference: str) -> str:
    match = re.search(r"/athletes/(\d+)", str(reference or ""))
    return match.group(1) if match else ""


def parse_prop_items(items: list[dict[str, Any]], names: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    """Turn one page of ESPN prop bets into player/market/line rows."""
    rows: list[dict[str, Any]] = []
    for item in items or []:
        market = canonical_market((item.get("type") or {}).get("name"))
        if not market:
            continue
        who = names.get(athlete_id(item.get("athlete", {}).get("$ref", "")))
        if not who:
            continue
        target = ((item.get("current") or {}).get("target") or {}).get("value")
        opened = ((item.get("open") or {}).get("target") or {}).get("value")
        if market != "Anytime touchdown" and target is None:
            continue
        rows.append({
            "player": who["name"],
            "team": who.get("team", ""),
            "market": market,
            "line": None if market == "Anytime touchdown" else float(target),
            "open_line": None if opened is None or market == "Anytime touchdown" else float(opened),
            "book": "DraftKings",
            "line_source": "DraftKings line via ESPN",
            "updated_at": item.get("lastUpdated"),
        })
    return rows


class EspnPropLines:
    """Keyless prop lines. Prices are not published by this feed."""

    name = "DraftKings lines via ESPN"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.core = JsonClient(self.name, CORE_URL, timeout=20)
        self.site = JsonClient(self.name, SITE_URL, timeout=20)
        self._names: dict[str, dict[str, str]] | None = None

    def roster_names(self) -> dict[str, dict[str, str]]:
        """One call per team maps ESPN athlete ids onto player names."""
        if self._names is not None:
            return self._names
        names: dict[str, dict[str, str]] = {}
        try:
            teams = self.site.get("/teams", {"limit": 40})
        except ProviderError:
            self._names = names
            return names
        entries = ((teams.get("sports") or [{}])[0].get("leagues") or [{}])[0].get("teams") or []
        ids = [str(((entry.get("team") or {}).get("id") or "")) for entry in entries]

        def roster(team_id: str) -> list[tuple[str, dict[str, str]]]:
            if not team_id:
                return []
            try:
                data = self.site.get(f"/teams/{team_id}/roster", None, retries=1)
            except ProviderError:
                return []
            team_name = str((data.get("team") or {}).get("displayName") or "")
            found: list[tuple[str, dict[str, str]]] = []
            for group in data.get("athletes") or []:
                for athlete in group.get("items") or []:
                    identifier = str(athlete.get("id") or "")
                    display = str(athlete.get("displayName") or "")
                    if identifier and display:
                        found.append((identifier, {"name": display, "team": team_name}))
            return found

        with ThreadPoolExecutor(max_workers=6) as pool:
            for found in pool.map(roster, ids):
                names.update(dict(found))
        self._names = names
        return names

    def event_lines(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        event_id = str(event.get("id") or "")
        competition = (event.get("competitions") or [{}])[0]
        competition_id = str(competition.get("id") or event_id)
        if not event_id:
            return []
        names = self.roster_names()
        rows: list[dict[str, Any]] = []
        path = f"/events/{event_id}/competitions/{competition_id}/odds/{DRAFTKINGS_CASINO}/propBets"
        page = 1
        while page <= int(self.settings.get("line_feed", {}).get("max_pages", 8)):
            try:
                data = self.core.get(path, {"limit": 100, "page": page}, retries=1)
            except ProviderError:
                break
            rows.extend(parse_prop_items(data.get("items") or [], names))
            if page >= int(data.get("pageCount") or 1):
                break
            page += 1
        matchup = _matchup(competition)
        for row in rows:
            row["event_id"] = event_id
            row["matchup"] = matchup
            row["start_time"] = str(event.get("date") or competition.get("date") or "")
        return rows

    def fetch(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cfg = self.settings.get("line_feed", {})
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        upcoming = [event for event in events if str(event.get("date") or "") > now]
        upcoming.sort(key=lambda event: str(event.get("date") or ""))
        upcoming = upcoming[: int(cfg.get("max_events", 16))]
        rows: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            for found in pool.map(self.event_lines, upcoming):
                rows.extend(found)
        return rows


def _matchup(competition: dict[str, Any]) -> str:
    teams = {}
    for competitor in competition.get("competitors") or []:
        side = str(competitor.get("homeAway") or "")
        team = competitor.get("team") or {}
        teams[side] = str(team.get("abbreviation") or team.get("displayName") or "")
    if teams.get("away") and teams.get("home"):
        return f"{teams['away']} @ {teams['home']}"
    return ""
