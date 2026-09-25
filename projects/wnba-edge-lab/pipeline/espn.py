"""Keyless ESPN data adapter for WNBA schedules, prices, injuries and news."""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard?dates={dates}&limit=1000"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary?event={event_id}"
NEWS = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/news?limit={limit}"
ET = ZoneInfo("America/Toronto")


def fetch_json(url: str, attempts: int = 3) -> dict:
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "WNBA-Edge-Lab/2.0 (+https://github.com/)"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except Exception as exc:  # pragma: no cover - exercised on network failure
            error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"ESPN request failed after {attempts} attempts: {error}")


def _num(value):
    try:
        if value is None or value == "":
            return None
        text = str(value).strip().lower().replace("+", "").replace("o", "").replace("u", "")
        if text in {"ev", "even"}:
            return 100.0
        return float(text)
    except (TypeError, ValueError):
        return None


def _close(block: dict | None) -> dict:
    block = block or {}
    value = block.get("close") or block.get("current") or block
    return value if isinstance(value, dict) else {}


def _open(block: dict | None) -> dict:
    block = block or {}
    value = block.get("open") or {}
    return value if isinstance(value, dict) else {}


def _quote(block: dict | None, fallback_line=None, fallback_price=None) -> dict | None:
    if not isinstance(block, dict):
        return None
    close, opened = _close(block), _open(block)
    price = _num(close.get("odds") or close.get("american") or block.get("odds"))
    line = _num(close.get("line") or close.get("pointSpread") or fallback_line)
    if price is None and fallback_price is not None:
        price = _num(fallback_price)
    if price is None or not (100 <= abs(price) <= 5000):
        return None
    return {
        "line": line,
        "price": int(round(price)),
        "open_line": _num(opened.get("line") or opened.get("pointSpread")),
        "open_price": _num(opened.get("odds") or opened.get("american")),
    }


def parse_odds(odds_list: list | None, away: str, home: str) -> dict | None:
    """Normalize the current ESPN/DraftKings basketball odds payload."""
    choices = [row for row in (odds_list or []) if isinstance(row, dict)]
    if not choices:
        return None
    choices.sort(key=lambda row: int((row.get("provider") or {}).get("priority") or 999))
    odds = choices[0]
    book = (odds.get("provider") or {}).get("name") or "ESPN consensus"
    ml = odds.get("moneyline") or {}
    spread = odds.get("pointSpread") or {}
    total = odds.get("total") or {}

    away_ml = _quote(ml.get("away"), None, None)
    home_ml = _quote(ml.get("home"), None, None)
    away_spread = _quote(spread.get("away"), None, None)
    home_spread = _quote(spread.get("home"), None, None)
    over = _quote(total.get("over"), odds.get("overUnder"), None)
    under = _quote(total.get("under"), odds.get("overUnder"), None)

    # A line without an offered price is reference information only. Do not
    # invent the traditional -110 price: an unpriced side cannot create edge.

    quotes = {
        "away_ml": away_ml,
        "home_ml": home_ml,
        "away_spread": away_spread,
        "home_spread": home_spread,
        "over": over,
        "under": under,
    }
    if not any(quotes.values()):
        return None
    for quote in quotes.values():
        if quote is not None:
            quote["book"] = book
    return {
        "book": book,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quotes": quotes,
    }


def _team(competitor: dict) -> dict:
    team = competitor.get("team") or {}
    stats = {row.get("name"): _num(row.get("displayValue"))
             for row in competitor.get("statistics") or []}
    records = {row.get("name", "").lower(): row.get("summary")
               for row in competitor.get("records") or []}
    return {
        "id": str(team.get("id") or ""),
        "abbr": str(team.get("abbreviation") or "").upper(),
        "name": team.get("displayName") or team.get("name") or "Unknown",
        "logo": team.get("logo"),
        "score": _num(competitor.get("score")),
        "winner": bool(competitor.get("winner")),
        "records": records,
        "stats": stats,
    }


def parse_event(event: dict) -> dict:
    competition = (event.get("competitions") or [{}])[0]
    competitors = {row.get("homeAway"): row for row in competition.get("competitors") or []}
    away = _team(competitors.get("away") or {})
    home = _team(competitors.get("home") or {})
    status = (competition.get("status") or event.get("status") or {}).get("type") or {}
    tip = event.get("date") or competition.get("date")
    local = datetime.fromisoformat(tip.replace("Z", "+00:00")).astimezone(ET)
    odds = parse_odds(competition.get("odds"), away["abbr"], home["abbr"])
    return {
        "game_id": str(event.get("id") or competition.get("id") or ""),
        "date": local.strftime("%Y-%m-%d"),
        "tipoff": tip,
        "start_local": local.strftime("%-I:%M %p"),
        "season_type": int((event.get("season") or {}).get("type") or 2),
        "away": away,
        "home": home,
        "status": status.get("state") or "pre",
        "status_detail": status.get("shortDetail") or status.get("detail") or status.get("description") or "Scheduled",
        "completed": bool(status.get("completed")),
        "venue": (competition.get("venue") or {}).get("fullName"),
        "broadcast": ", ".join(name for row in competition.get("broadcasts") or [] for name in row.get("names") or []),
        "odds": odds,
    }


def fetch_season(season: int) -> list[dict]:
    data = fetch_json(SCOREBOARD.format(dates=season))
    return sorted((parse_event(event) for event in data.get("events") or []),
                  key=lambda game: (game["tipoff"], game["game_id"]))


def _leader_impacts(summary: dict, cfg: dict) -> dict[str, float]:
    rules = cfg["injuries"]
    weights = {
        "pointsPerGame": float(rules["leader_points_weight"]),
        "assistsPerGame": float(rules["leader_assists_weight"]),
        "reboundsPerGame": float(rules["leader_rebounds_weight"]),
    }
    impacts: dict[str, float] = {}
    for team in summary.get("leaders") or []:
        for category in team.get("leaders") or []:
            weight = weights.get(category.get("name"), 0.0)
            for leader in category.get("leaders") or []:
                athlete = leader.get("athlete") or {}
                athlete_id = str(athlete.get("id") or "")
                if athlete_id and weight:
                    impacts[athlete_id] = impacts.get(athlete_id, 0.0) + float(leader.get("value") or 0.0) * weight
    return impacts


def parse_team_stats(summary: dict) -> dict[str, dict]:
    output: dict[str, dict] = {}
    for block in (summary.get("boxscore") or {}).get("teams") or []:
        team = block.get("team") or {}
        abbr = str(team.get("abbreviation") or "").upper()
        if abbr:
            output[abbr] = {row.get("name"): _num(row.get("displayValue")) for row in block.get("statistics") or []}
    return output


def parse_predictor(summary: dict) -> dict:
    block = summary.get("predictor") or {}
    home = _num((block.get("homeTeam") or {}).get("gameProjection"))
    away = _num((block.get("awayTeam") or {}).get("gameProjection"))
    if home is None:
        return {}
    total = home + away if away is not None else 100.0
    return {"home_prob": round(home / total, 4) if total else None, "away_prob": round(away / total, 4) if total else None}


def parse_injuries(summary: dict, cfg: dict) -> dict[str, dict]:
    rules = cfg["injuries"]
    leader_impacts = _leader_impacts(summary, cfg)
    ignored_details = {str(value).lower() for value in rules.get("ignore_details") or []}
    out: dict[str, dict] = {}
    for team_block in summary.get("injuries") or []:
        team = team_block.get("team") or {}
        abbr = str(team.get("abbreviation") or "").upper()
        rows, total, uncertain, uncertain_points = [], 0.0, False, 0.0
        for item in team_block.get("injuries") or []:
            athlete = item.get("athlete") or {}
            status = str(item.get("status") or (item.get("type") or {}).get("description") or "unknown")
            key = status.lower()
            position = ((athlete.get("position") or {}).get("abbreviation") or "default").upper()
            detail = item.get("details") or {}
            detail_text = str(detail.get("type") or detail.get("detail") or "")
            ignored = detail_text.lower() in ignored_details
            athlete_id = str(athlete.get("id") or "")
            role_points = max(float(rules["default_rotation_points"]), float(leader_impacts.get(athlete_id, 0.0)))
            points = 0.0 if ignored else role_points * float(rules["status_weight"].get(key, 0.25))
            is_uncertain = not ignored and key in {"questionable", "day-to-day", "game time decision", "doubtful"}
            uncertain = uncertain or is_uncertain
            uncertain_points += points if is_uncertain else 0.0
            rows.append({
                "name": athlete.get("displayName") or "Unknown player",
                "position": position,
                "status": status,
                "detail": detail_text,
                "points": round(points, 2),
                "counted": not ignored,
                "impact_basis": "team leader" if athlete_id in leader_impacts else "rotation baseline",
            })
            total += points
        out[abbr] = {
            "team": team.get("displayName") or abbr,
            "points": round(min(total, float(rules["max_team_points"])), 2),
            "uncertain": uncertain,
            "uncertain_points": round(uncertain_points, 2),
            "players": rows,
        }
    return out


def fetch_game_context(game: dict, cfg: dict) -> dict:
    summary = fetch_json(SUMMARY.format(event_id=game["game_id"]))
    header = ((summary.get("header") or {}).get("competitions") or [{}])[0]
    live_odds = parse_odds(summary.get("pickcenter") or summary.get("odds") or header.get("odds"),
                           game["away"]["abbr"], game["home"]["abbr"])
    return {
        "injuries": parse_injuries(summary, cfg),
        "odds": live_odds,
        "team_stats": parse_team_stats(summary),
        "predictor": parse_predictor(summary),
    }


def fetch_news(limit: int = 20) -> list[dict]:
    try:
        data = fetch_json(NEWS.format(limit=limit))
    except RuntimeError:
        return []
    rows = []
    for article in data.get("articles") or []:
        links = article.get("links") or {}
        web = (links.get("web") or {}).get("href")
        rows.append({
            "headline": article.get("headline"),
            "description": article.get("description"),
            "published": article.get("published"),
            "link": web,
        })
    return rows
