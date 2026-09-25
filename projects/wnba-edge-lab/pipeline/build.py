"""Build the automatic WNBA Edge feed from live keyless ESPN data.

Usage:
    python -m pipeline.build
    python -m pipeline.build --date 2026-08-25 --days 8
    python -m pipeline.build --offline

There is deliberately no sample/demo fallback. If ESPN and the last real cache
are both unavailable, the site publishes an honest no-live-data state.
"""

from __future__ import annotations

from . import game_history

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import espn, ledger, model

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
SITE = ROOT / "site" / "data"
ET = ZoneInfo("America/Toronto")


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _capture_lines(games: list[dict], previous: dict) -> dict:
    snapshots = previous or {"games": {}}
    snapshots.setdefault("games", {})
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for game in games:
        odds = game.get("odds")
        if not odds:
            continue
        rows = snapshots["games"].setdefault(game["game_id"], [])
        fingerprint = json.dumps(odds.get("quotes") or {}, sort_keys=True)
        if not rows or rows[-1].get("fingerprint") != fingerprint:
            rows.append({
                "captured_at": now,
                "book": odds.get("book"),
                "quotes": odds.get("quotes"),
                "fingerprint": fingerprint,
            })
            del rows[:-40]
    snapshots["updated_at"] = now
    return snapshots


def _line_move(game: dict, line_state: dict) -> dict:
    rows = (line_state.get("games") or {}).get(game["game_id"]) or []
    current = ((game.get("odds") or {}).get("quotes") or {})
    opened = (rows[0].get("quotes") or {}) if rows else {}
    output = {"snapshots": len(rows)}
    for key in ("away_spread", "home_spread", "over", "under", "away_ml", "home_ml"):
        cur, old = current.get(key) or {}, opened.get(key) or {}
        output[key] = {
            "current_line": cur.get("line"),
            "open_line": old.get("line") if old else cur.get("open_line"),
            "current_price": cur.get("price"),
            "open_price": old.get("price") if old else cur.get("open_price"),
        }
    return output


def settlement_results(previous: list[dict], games: list[dict]) -> list[dict]:
    """Retain public final scores beyond the display window and season rollover."""
    by_id = {str(game["game_id"]): game for game in previous}
    for game in games:
        away, home = game.get("away") or {}, game.get("home") or {}
        if not game.get("completed") or away.get("score") is None or home.get("score") is None:
            continue
        by_id[str(game["game_id"])] = {
            "game_id": str(game["game_id"]), "date": game["date"], "completed": True,
            "away": {"abbr": away.get("abbr"), "score": away["score"]},
            "home": {"abbr": home.get("abbr"), "score": home["score"]},
        }
    return sorted(by_id.values(), key=lambda game: (game["date"], str(game["game_id"])))


def build(target_date: str | None = None, days: int | None = None, offline: bool = False) -> dict:
    cfg = read_json(ROOT / "config" / "settings.json", {})
    season = int(cfg.get("season") or datetime.now(ET).year)
    selected = _date(target_date) if target_date else datetime.now(ET).date()
    lookback = int(cfg["refresh"]["lookback_days"])
    lookahead = int(days or cfg["refresh"]["lookahead_days"])
    start, end = selected - timedelta(days=lookback), selected + timedelta(days=lookahead - 1)
    cache_path = STATE / f"games_{season}.json"
    cached = read_json(cache_path, {"games": [], "fetched_at": None})
    errors: list[str] = []

    if offline:
        all_games = cached.get("games") or []
        source_status = "cached-live-data" if all_games else "no-live-data"
    else:
        try:
            all_games = espn.fetch_season(season)
            source_status = "live"
            write_json(cache_path, {
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "ESPN public feed",
                "games": all_games,
            })
        except Exception as exc:  # retain only a previous real cache
            all_games = cached.get("games") or []
            source_status = "cached-live-data" if all_games else "no-live-data"
            errors.append(f"Schedule refresh failed: {exc}")

    window_games = [game for game in all_games if start <= _date(game["date"]) <= end]
    contexts: dict[str, dict] = {}
    if not offline and source_status == "live":
        for game in window_games:
            if game["status"] == "post":
                continue
            try:
                context = espn.fetch_game_context(game, cfg)
                contexts[game["game_id"]] = context
                if context.get("odds"):
                    game["odds"] = context["odds"]
            except Exception as exc:
                errors.append(f'{game["away"]["abbr"]} @ {game["home"]["abbr"]}: context refresh failed ({exc})')

    # Persist the refreshed price/context merge as the only cache used offline.
    if not offline and source_status == "live":
        by_id = {game["game_id"]: game for game in all_games}
        for game in window_games:
            by_id[game["game_id"]] = game
        all_games = sorted(by_id.values(), key=lambda game: (game["tipoff"], game["game_id"]))
        write_json(cache_path, {
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "ESPN public feed",
            "games": all_games,
        })

    history = [game for game in all_games if game.get("completed") and game.get("season_type") == 2]
    ratings = model.solve_ratings(history, cfg)
    calibration = model.rolling_calibration(history, cfg)
    lines = _capture_lines(window_games, read_json(STATE / "lines.json", {"games": {}}))
    write_json(STATE / "lines.json", lines)

    published_games, board = [], []
    for game in window_games:
        if game.get("season_type") not in {2, 3}:
            continue
        prior = [row for row in history if row["tipoff"] < game["tipoff"]]
        game["days_out"] = (_date(game["date"]) - selected).days
        venue_team = game["home"]["abbr"]
        away_profile = model.team_profile(game["away"]["abbr"], prior, game["tipoff"], ratings, venue_team)
        home_profile = model.team_profile(game["home"]["abbr"], prior, game["tipoff"], ratings, venue_team)
        context = contexts.get(game["game_id"]) or {}
        injuries = context.get("injuries") or {}
        projection = model.project_game(game, away_profile, home_profile, injuries, cfg, context, calibration)
        candidates = model.price_game(game, projection, cfg) if game.get("odds") else []
        board.extend(candidates)
        published_games.append({
            **game,
            "projection": projection,
            "injuries": injuries,
            "line_move": _line_move(game, lines),
        })

    model.allocate_portfolio(board, cfg)
    by_game: dict[str, list[dict]] = {}
    for row in board:
        by_game.setdefault(row["game_id"], []).append(row)
    tier_order = {"BEST BET": 0, "GOOD": 1, "LEAN": 2, "AVOID": 3}
    for game in published_games:
        candidates = sorted(by_game.get(game["game_id"], []), key=lambda row: (tier_order[row["tier"]], -row["edge"]))
        game["best_candidate"] = candidates[0] if candidates else None
        game["rationale"] = model.rationale(game, game["projection"], game["best_candidate"])
        game["markets_priced"] = len(candidates)

    ledger_state, shadow_state = ledger.sync(
        board,
        all_games,
        read_json(STATE / "ledger.json", {"bets": []}),
        read_json(STATE / "shadow.json", {"calls": []}),
    )
    write_json(STATE / "ledger.json", ledger_state)
    write_json(STATE / "shadow.json", shadow_state)
    perf = ledger.performance(ledger_state, shadow_state, float(cfg["bankroll"]["starting"]))
    for forecast_game in published_games:
        proj = forecast_game["projection"]
        forecast_game["p_home"] = model.normal_cdf(proj["margin"] / proj["spread_sigma"])
    game_history.update(STATE / "model_accuracy.json", SITE / "accuracy.json",
                        board, published_games, all_games, "WNBA",
                        historical=shadow_state.get("calls", []))

    dates = sorted({game["date"] for game in published_games})
    current = selected.strftime("%Y-%m-%d")
    if current not in dates and dates:
        future = [value for value in dates if value >= current]
        current = future[0] if future else dates[-1]
    plays = [row for row in board if row["tier"] != "AVOID" and row.get("stake", 0) > 0]
    day_summary = {}
    for value in dates:
        day_games = [game for game in published_games if game["date"] == value]
        day_rows = [row for row in board if row["date"] == value]
        day_plays = [row for row in plays if row["date"] == value]
        day_summary[value] = {
            "games": len(day_games),
            "priced": sum(game.get("odds") is not None for game in day_games),
            "markets": len(day_rows),
            "plays": len(day_plays),
            "staked": round(sum(float(row["stake"]) for row in day_plays), 2),
        }

    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    priced_games = sum(game.get("odds") is not None for game in published_games if game["status"] == "pre")
    upcoming_games = sum(game["status"] == "pre" for game in published_games)
    meta = {
        "league": "WNBA",
        "season": season,
        "generated_at": generated,
        "built_for": selected.strftime("%Y-%m-%d"),
        "source": "ESPN schedule, box-score/team efficiency, predictor, injuries and DraftKings prices",
        "source_status": source_status,
        "live_data": bool(all_games),
        "key_required": False,
        "errors": errors,
        "odds_health": {
            "status": "ok" if upcoming_games and priced_games == upcoming_games else "partial" if priced_games else "waiting",
            "upcoming_games": upcoming_games,
            "priced_games": priced_games,
            "provider": "ESPN public feed / DraftKings",
        },
        "calibration": calibration,
    }
    summary = {
        "bankroll": perf["current_bankroll"],
        "starting_bankroll": cfg["bankroll"]["starting"],
        "games": len(published_games),
        "upcoming_games": upcoming_games,
        "priced_games": priced_games,
        "markets_priced": len(board),
        "qualified": len(plays),
        "exposure": round(sum(float(row["stake"]) for row in plays if row["date"] == current), 2),
        "daily_cap": round(float(cfg["bankroll"]["starting"]) * float(cfg["bankroll"]["max_daily_exposure_pct"]), 2),
        "by_tier": {tier: sum(row["tier"] == tier for row in board) for tier in tier_order},
        "day_summary": day_summary,
    }
    simulator = {
        "generated_at": generated,
        "home_court": cfg["model"]["home_court_points"],
        "power_weight": cfg["model"]["classic_power_weight"],
        "margin_bias": calibration["margin_bias"],
        "total_bias": calibration["total_bias"],
        "spread_sigma": calibration["spread_sigma"],
        "total_sigma": calibration["total_sigma"],
        "teams": {team: model.team_profile(team, history, generated, ratings, team) for team in sorted(ratings)},
    }
    index = {
        "generated_at": generated,
        "built_for": current,
        "dates": dates,
        "lookback_days": lookback,
        "lookahead_days": lookahead,
        "day_summary": day_summary,
        "source_status": source_status,
    }

    outputs = {
        "board.json": board,
        "games.json": published_games,
        "results.json": settlement_results(read_json(SITE / "results.json", []), all_games),
        "summary.json": summary,
        "meta.json": meta,
        "index.json": index,
        "ledger.json": ledger_state,
        "performance.json": perf,
        "simulator.json": simulator,
        "news.json": espn.fetch_news(20) if not offline and source_status == "live" else [],
        "calibration.json": calibration,
    }
    for name, payload in outputs.items():
        write_json(SITE / name, payload)
    print(f"WNBA Edge: {len(published_games)} live games, {priced_games} priced, {len(plays)} qualified; source={source_status}")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="first slate date, YYYY-MM-DD")
    parser.add_argument("--days", type=int, help="future days to publish")
    parser.add_argument("--offline", action="store_true", help="rebuild from the last real cache")
    args = parser.parse_args()
    build(args.date, args.days, args.offline)


if __name__ == "__main__":
    main()
