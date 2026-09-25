"""Keyless ESPN client.

ESPN's public scoreboard JSON needs no key, no signup, no quota. It is
undocumented and unsupported, so it can change without warning. Be polite:
one call per league per run, and cache.

  https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard

Odds live at events[].competitions[].odds[]. Moneyline is a string under
.moneyline.home.close.odds and may be "OFF" when the book has not posted or
has taken the market down. Older payloads use homeTeamOdds.moneyLine as an
int, so both shapes are handled.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from functools import lru_cache

SITE = "https://site.api.espn.com/apis/site/v2/sports"

# label -> ESPN {sport}/{league} path
LEAGUES = {
    "nfl": "football/nfl",
    "ncaaf": "football/college-football",
    "mlb": "baseball/mlb",
    "nba": "basketball/nba",
    "wnba": "basketball/wnba",
    "ncaab": "basketball/mens-college-basketball",
    "nhl": "hockey/nhl",
    "mls": "soccer/usa.1",
    "epl": "soccer/eng.1",
    "ucl": "soccer/uefa.champions",
    "atp": "tennis/atp",
    "wta": "tennis/wta",
}

# Leagues where a draw is a distinct outcome, so the market is three-way.
THREE_WAY = {"mls", "epl", "ucl"}

UA = "Mozilla/5.0 (compatible; ca-ladder/0.2; +https://github.com)"


class ESPNError(RuntimeError):
    pass


def _get(url: str, timeout: int = 25) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise ESPNError(f"HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise ESPNError(f"network error for {url}: {e.reason}") from e


@lru_cache(maxsize=128)
def scoreboard(league: str, date: str | None = None) -> dict:
    """date is YYYYMMDD. Omit for ESPN's default window (today / current week)."""
    if league not in LEAGUES:
        raise ESPNError(f"unknown league {league!r}; known: {', '.join(LEAGUES)}")
    url = f"{SITE}/{LEAGUES[league]}/scoreboard"
    if date:
        url += f"?dates={date}"
    return _get(url)


def events(league: str, date: str | None = None) -> list[dict]:
    return scoreboard(league, date).get("events", []) or []


# ------------------------------------------------------------------ parsing
def _clean_american(v) -> float | None:
    """ESPN gives '-2400', '+1200', 'OFF', 'EVEN', or an int. Normalize."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        n = float(v)
        return n if abs(n) >= 100 else None
    s = str(v).strip().upper().replace(",", "")
    if s in {"", "OFF", "N/A", "-", "PK", "NL"}:
        return None
    if s in {"EVEN", "EV"}:
        return 100.0
    try:
        n = float(s.replace("+", ""))
    except ValueError:
        return None
    return n if abs(n) >= 100 else None


def _side(block: dict) -> float | None:
    """Prefer the closing line, fall back to the open."""
    if not isinstance(block, dict):
        return None
    for key in ("close", "open", "current"):
        node = block.get(key)
        if isinstance(node, dict):
            v = _clean_american(node.get("odds"))
            if v is not None:
                return v
    return _clean_american(block.get("odds"))


def _side_at(block: dict, when: str) -> float | None:
    """Price at 'open' or 'close' specifically, no fallback."""
    if not isinstance(block, dict):
        return None
    node = block.get(when)
    if isinstance(node, dict):
        return _clean_american(node.get("odds"))
    return None


def moneylines(comp: dict) -> list[dict]:
    """Every provider's moneyline for one competition.

    Returns [{provider, home, away, draw}] with American odds or None.
    """
    out = []
    for o in comp.get("odds", []) or []:
        prov = (o.get("provider") or {}).get("name", "unknown")
        ml = o.get("moneyline") or {}
        home = _side(ml.get("home") or {})
        away = _side(ml.get("away") or {})
        draw = _side(ml.get("draw") or {})
        # legacy flat shape
        if home is None:
            home = _clean_american((o.get("homeTeamOdds") or {}).get("moneyLine"))
        if away is None:
            away = _clean_american((o.get("awayTeamOdds") or {}).get("moneyLine"))
        if draw is None:
            draw = _clean_american((o.get("drawOdds") or {}).get("moneyLine"))
        if home is None and away is None:
            continue
        out.append({
            "provider": prov,
            "home": home, "away": away, "draw": draw,
            "home_open": _side_at(ml.get("home") or {}, "open"),
            "away_open": _side_at(ml.get("away") or {}, "open"),
            "draw_open": _side_at(ml.get("draw") or {}, "open"),
        })
    return out


def teams(comp: dict) -> dict:
    """{'home': {...}, 'away': {...}} with id, name, score, winner."""
    d = {}
    for c in comp.get("competitors", []) or []:
        side = c.get("homeAway")
        if side not in ("home", "away"):
            continue
        t = c.get("team") or {}
        d[side] = {
            "id": t.get("id"),
            "name": t.get("displayName") or t.get("name") or "?",
            "abbr": t.get("abbreviation") or "",
            "score": c.get("score"),
            "winner": c.get("winner"),
        }
    return d


def status(comp_or_event: dict) -> dict:
    st = (comp_or_event.get("status") or {}).get("type") or {}
    return {
        "state": st.get("state"),          # pre | in | post
        "completed": bool(st.get("completed")),
        "detail": st.get("shortDetail") or st.get("description") or "",
    }


def starts_in_hours(event: dict) -> float | None:
    ts = event.get("date")
    if not ts:
        return None
    try:
        start = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (start - datetime.now(timezone.utc)).total_seconds() / 3600.0


def find_event(league: str, event_id: str, date: str | None = None) -> dict | None:
    for ev in events(league, date):
        if str(ev.get("id")) == str(event_id):
            return ev
    return None


def grade(event: dict, side: str, league: str = "") -> tuple[str, str]:
    """Grade a moneyline bet from a finished event.

    Returns (result, detail) where result is win | loss | push | pending.
    Free auto-settlement: ESPN marks competitor.winner and status.completed.
    """
    comps = event.get("competitions") or []
    if not comps:
        return "pending", "no competition data"
    comp = comps[0]

    st = status(comp)
    if not st.get("state"):
        st = status(event)
    if not st.get("completed"):
        return "pending", st.get("detail") or "not final"

    tm = teams(comp)
    if "home" not in tm or "away" not in tm:
        return "pending", "missing competitors"

    hs, as_ = tm["home"].get("score"), tm["away"].get("score")
    score = f"{tm['away']['abbr']} {as_} @ {tm['home']['abbr']} {hs}"

    home_won = bool(tm["home"].get("winner"))
    away_won = bool(tm["away"].get("winner"))

    # Two-way moneylines refund ties; three-way soccer treats draw as a side.
    if not home_won and not away_won:
        try:
            drawn = float(hs) == float(as_)
        except (TypeError, ValueError):
            return "pending", f"no winner flag ({score})"
        if not drawn:
            return "pending", f"final but no winner flag ({score})"
        if side == "draw" or league.lower() in THREE_WAY:
            return ("win" if side == "draw" else "loss"), f"draw — {score}"
        if not league:
            return "pending", f"tied final; league required to determine settlement — {score}"
        return "push", f"tie — {score}"

    winner = "home" if home_won else "away"
    return ("win" if side == winner else "loss"), score


def date_of(iso: str) -> str | None:
    """YYYYMMDD (UTC) from an ISO timestamp, for ESPN's ?dates= parameter."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(
            iso.replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y%m%d")
    except ValueError:
        return None


def grade_bet(league: str, event_id: str, side: str, date: str | None = None,
              start_utc: str | None = None) -> tuple[str, str]:
    """Look the game up by ITS OWN date, not by guessing today.

    ESPN's default scoreboard window rolls forward, so a game that finished
    last night is often already gone from it. Searching by the event's own
    start date is what makes settlement reliable.
    """
    tried: list[str | None] = []
    for d in (date, date_of(start_utc), None):
        if d in tried:
            continue
        tried.append(d)
        ev = find_event(league, event_id, d)
        if ev is not None:
            return grade(ev, side, league)

    # Last resort: sweep a few days either side of the start.
    from datetime import timedelta
    anchor = None
    if start_utc:
        try:
            anchor = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
        except ValueError:
            anchor = None
    anchor = anchor or datetime.now(timezone.utc)
    for off in (-1, 1, -2, 2):
        d = (anchor + timedelta(days=off)).strftime("%Y%m%d")
        if d in tried:
            continue
        ev = find_event(league, event_id, d)
        if ev is not None:
            return grade(ev, side, league)

    return "pending", "event not found in ESPN's scoreboard windows"
