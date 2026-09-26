"""
Quarterback value: how many points a team actually loses when its starter sits.

The injury model used to charge a flat 4.5 points for any starting QB who was
out, with a comment admitting it "has no way to know how good the backup is".
That flat number is wrong in both directions: losing an elite starter to a
street free agent is worth far more than 4.5; losing an average starter to a
competent veteran backup is worth far less.

This module prices the gap between the two players who matter:

    points = PTS_PER_EPA * (quality(usual starter) - quality(replacement))

  * quality = expected points added per play (dropbacks + sacks + QB runs),
    from nflverse's free weekly player stats (no key, published on GitHub).
    Last season counts at half weight per play, this season at full weight.
    Every QB is shrunk toward REPLACEMENT_EPA (-0.15, what 2025 QBs with
    under 250 plays actually produced) by SHRINK_PLAYS phantom plays, so a
    backup with 40 career snaps reads as replacement level, not as his lucky
    two drives.

  * PTS_PER_EPA was measured, not guessed: a regression of every 2019-2025
    regular-season closing spread on team-season ratings plus the quality gap
    of whoever actually started (574 non-primary starts) gives 0.593 spread
    points per EPA-point per game, i.e. ~22.5 points per 1.0 EPA/play of
    quality gap at 38 QB plays a game. At that rate an average starter
    (+0.07) to replacement (-0.15) is worth ~5 points, an elite starter
    ~9 before the cap -- in line with how books move numbers.

  * The "usual starter" is whoever has taken the most QB plays for the team
    this season, not the depth chart's QB1. Teams update depth charts when a
    starter goes down, so QB1 can already BE the backup -- which used to make
    a starter's Out designation count as a 0.2-point backup injury.

Fetched at most every `refresh_hours`; on any failure the last cached values
are kept, and with no cache at all the old flat 4.5 is used and labelled.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from typing import Iterable

BASE = "https://github.com/nflverse/nflverse-data/releases/download"
PLAYERS_URL = f"{BASE}/players/players.csv"
WEEK_URL = BASE + "/stats_player/stats_player_week_{season}.csv"
REG_URL = BASE + "/stats_player/stats_player_reg_{season}.csv"

REPLACEMENT_EPA = -0.15
SHRINK_PLAYS = 150.0
PTS_PER_EPA = 22.5
LAST_SEASON_WEIGHT = 0.5

# nflverse -> ESPN team codes (only the ones that differ).
TEAM_ALIASES = {"LA": "LAR", "WAS": "WSH"}


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _get_csv(url: str, timeout: int = 60) -> list[dict]:
    import requests
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))


def _qb_rows(rows: Iterable[dict], weight: float, acc: dict, teams: dict | None = None) -> None:
    for x in rows:
        if (x.get("position") or "").upper() != "QB":
            continue
        if x.get("season_type") and x["season_type"] != "REG":
            continue
        pid = x.get("player_id")
        if not pid:
            continue
        plays = _f(x.get("attempts")) + _f(x.get("sacks_suffered")) + _f(x.get("carries"))
        epa = _f(x.get("passing_epa")) + _f(x.get("rushing_epa"))
        a = acc.setdefault(pid, {"plays": 0.0, "epa": 0.0, "raw_plays": 0.0,
                                 "name": x.get("player_display_name") or x.get("player_name")})
        a["plays"] += weight * plays
        a["epa"] += weight * epa
        a["raw_plays"] += plays
        if teams is not None:
            team = x.get("team") or x.get("recent_team") or ""
            team = TEAM_ALIASES.get(team, team)
            if team:
                teams.setdefault(team, {}).setdefault(pid, 0.0)
                teams[team][pid] += plays


def quality(plays: float, epa: float) -> float:
    """Shrunk EPA per play."""
    return (epa + REPLACEMENT_EPA * SHRINK_PLAYS) / (plays + SHRINK_PLAYS)


def build_table(season: int, players: list[dict], this_season: list[dict],
                last_season: list[dict]) -> dict:
    """ESPN athlete id -> quality, plus each team's usual starter (by plays)."""
    acc: dict = {}
    team_plays: dict = {}
    _qb_rows(last_season, LAST_SEASON_WEIGHT, acc)
    _qb_rows(this_season, 1.0, acc, team_plays)
    by_gsis = {p.get("gsis_id"): p for p in players if p.get("espn_id")}
    qbs: dict[str, dict] = {}
    for gsis, a in acc.items():
        p = by_gsis.get(gsis)
        if not p:
            continue
        qbs[str(p["espn_id"])] = {
            "name": a["name"] or p.get("display_name"),
            "gsis": gsis,
            "q": round(quality(a["plays"], a["epa"]), 4),
            "plays": round(a["plays"], 1),
        }
    # Rookies and other QBs with no snaps yet still need an entry so a lookup
    # by ESPN id succeeds (at replacement level).
    for p in players:
        if (p.get("position") or "").upper() == "QB" and p.get("espn_id") \
                and str(p["espn_id"]) not in qbs and (p.get("status") or "").upper() in ("ACT", "RES", "INA", "DEV"):
            qbs[str(p["espn_id"])] = {"name": p.get("display_name"), "gsis": p.get("gsis_id"),
                                      "q": REPLACEMENT_EPA, "plays": 0.0}
    gsis_to_espn = {v["gsis"]: k for k, v in qbs.items()}
    usual = {}
    for team, plays in team_plays.items():
        top = max(plays.items(), key=lambda kv: kv[1])
        if top[0] in gsis_to_espn and top[1] >= 20:
            usual[team] = gsis_to_espn[top[0]]
    return {"season": season, "qbs": qbs, "usual_starter": usual,
            "method": f"shrunk EPA/play toward {REPLACEMENT_EPA} by {SHRINK_PLAYS:.0f} plays; "
                      f"{PTS_PER_EPA} pts per 1.0 EPA/play gap"}


def refresh(cache: dict, season: int, now: dt.datetime | None = None,
            refresh_hours: float = 12.0) -> dict:
    """Return a fresh table, or the cache if it is recent or the fetch fails."""
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp = cache.get("fetched_at")
    if stamp and cache.get("season") == season:
        try:
            age = (now - dt.datetime.fromisoformat(stamp)).total_seconds() / 3600
            if age < refresh_hours:
                return cache
        except ValueError:
            pass
    try:
        players = [p for p in _get_csv(PLAYERS_URL) if (p.get("position") or "").upper() == "QB"]
        try:
            this_season = _get_csv(WEEK_URL.format(season=season))
        except Exception:        # before Week 1 the file may not exist yet
            this_season = []
        last_season = _get_csv(REG_URL.format(season=season - 1))
        table = build_table(season, players, this_season, last_season)
        table["fetched_at"] = now.replace(microsecond=0).isoformat()
        print(f"   QB quality: {len(table['qbs'])} QBs, usual starters for "
              f"{len(table['usual_starter'])} teams (nflverse)")
        return table
    except Exception as exc:     # network, parse -- keep the last good table
        print(f"   QB quality refresh unavailable; using cached table ({exc})")
        return cache


def starter_value(table: dict, starter_id: str | None, replacement_id: str | None,
                  cfg: dict) -> dict | None:
    """Points lost when `starter_id` sits and `replacement_id` plays."""
    inj = cfg.get("injuries") or {}
    lo = float(inj.get("qb_min_points", 0.5))
    hi = float(inj.get("qb_max_points", 8.0))
    scale = float(inj.get("qb_points_per_epa", PTS_PER_EPA))
    qbs = (table or {}).get("qbs") or {}
    s = qbs.get(str(starter_id or ""))
    if not s or s.get("plays", 0) < 100:
        return None          # not enough evidence on the starter: caller uses the flat number
    r = qbs.get(str(replacement_id or "")) or {"name": None, "q": REPLACEMENT_EPA, "plays": 0.0}
    gap = float(s["q"]) - float(r["q"])
    pts = max(lo, min(hi, scale * gap))
    return {"points": round(pts, 2), "starter": s.get("name"), "starter_q": s["q"],
            "replacement": r.get("name") or "replacement-level QB", "replacement_q": r["q"],
            "basis": (f"{s.get('name')} {s['q']:+.2f} vs {r.get('name') or 'replacement'} "
                      f"{float(r['q']):+.2f} EPA/play × {scale:g}")}


def team_qb(table: dict, team_abbr: str, depth_qbs: list[str] | None,
            rows: list[dict], status_weight) -> dict:
    """Who normally starts, who replaces him, and what that costs.

    `status_weight(status) -> 0..1` is the injury model's own table, so
    Questionable/Doubtful are weighted exactly as every other position is.
    """
    depth_qbs = [str(x) for x in (depth_qbs or []) if x]
    usual = ((table or {}).get("usual_starter") or {}).get(team_abbr) or (depth_qbs[0] if depth_qbs else None)
    by_id = {str(r.get("athlete_id")): r for r in rows or [] if r.get("athlete_id")}
    out_ids = {aid for aid, r in by_id.items() if status_weight(r.get("status", "")) >= 1.0}
    replacement = next((q for q in depth_qbs if q != usual and q not in out_ids), None)
    row = by_id.get(str(usual)) if usual else None
    w = status_weight(row.get("status", "")) if row else 0.0
    return {"usual": usual, "replacement": replacement, "status": (row or {}).get("status"),
            "weight": w, "questionable": 0.0 < w < 1.0,
            "name": (((table or {}).get("qbs") or {}).get(str(usual)) or {}).get("name")
                    or (row or {}).get("name")}
