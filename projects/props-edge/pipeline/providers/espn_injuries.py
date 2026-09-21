"""The NFL injury report from ESPN's public feed, keyed by player.

A prop on a player who is ruled out is dead weight — worse inside a parlay, where
one dead leg kills the whole ticket. This keeps those players off the board and
flags the ones who are still a question mark on game day.
"""
from __future__ import annotations

import re
from typing import Any

from ..http import JsonClient, ProviderError

SITE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

# Statuses that remove a player from the board entirely.
BLOCKING = {"out", "injured reserve", "ir", "suspended", "doubtful", "practice squad", "physically unable to perform"}
# Statuses worth showing next to a leg without removing it.
FLAGGING = {"questionable", "probable", "day-to-day"}


def name_key(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z]+", str(value or "")) if part]
    parts = [part for part in parts if part.casefold() not in {"jr", "sr", "ii", "iii", "iv", "v"}]
    return (parts[0][:1] + parts[-1]).casefold() if parts else ""


def parse_report(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    """{player key: {status, detail, team}} for every player on the report."""
    report: dict[str, dict[str, str]] = {}
    for team in payload.get("injuries") or []:
        team_name = str(team.get("displayName") or "")
        for entry in team.get("injuries") or []:
            athlete = entry.get("athlete") or {}
            player = str(athlete.get("displayName") or "")
            status = str(entry.get("status") or "").strip()
            if not player or not status:
                continue
            key = name_key(player)
            lowered = status.casefold()
            if key in report and lowered not in BLOCKING:
                continue  # keep the most serious status a player carries
            report[key] = {
                "player": player,
                "team": team_name,
                "status": status,
                "detail": str(((entry.get("type") or {}).get("description")) or entry.get("shortComment") or ""),
                "blocking": "yes" if lowered in BLOCKING else "no",
            }
    return report


class EspnInjuries:
    name = "ESPN injury report"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.client = JsonClient(self.name, SITE_URL, timeout=20)

    def fetch(self) -> dict[str, dict[str, str]]:
        try:
            return parse_report(self.client.get("/injuries", None, retries=1))
        except ProviderError:
            return {}
