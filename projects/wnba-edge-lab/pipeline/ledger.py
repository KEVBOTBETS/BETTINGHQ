"""Model shadow-book grading from final ESPN scores.

The published site never auto-adds a model pick to the user's ledger. Actual
wagers live only in the browser ledger after the user clicks Add. This module
keeps the separate shadow book needed to audit every model tier honestly.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone


def _result(row: dict, game: dict) -> str | None:
    if not game.get("completed"):
        return None
    away_score = game["away"].get("score")
    home_score = game["home"].get("score")
    if away_score is None or home_score is None:
        return None
    away_score, home_score = float(away_score), float(home_score)
    market, side = row["market"], row["side"]
    if market == "ML":
        mine, theirs = (away_score, home_score) if side == "away" else (home_score, away_score)
        return "Win" if mine > theirs else "Loss" if mine < theirs else "Push"
    if market == "ATS":
        mine, theirs = (away_score, home_score) if side == "away" else (home_score, away_score)
        adjusted = mine + float(row.get("line") or 0.0)
        return "Win" if adjusted > theirs else "Loss" if adjusted < theirs else "Push"
    if market == "TOTAL":
        total = away_score + home_score
        line = float(row.get("line") or 0.0)
        if total == line:
            return "Push"
        return "Win" if (side == "over") == (total > line) else "Loss"
    return None


def _profit(stake: float, price: float, result: str) -> float:
    if result in {"Push", "Void"}:
        return 0.0
    if result == "Loss":
        return -stake
    return stake * (price / 100.0 if price > 0 else 100.0 / -price)


def _lock(row: dict, tracked_at: str, shadow: bool = False) -> dict:
    return {
        "id": row["candidate_id"],
        "game_id": row["game_id"],
        "date": row["date"],
        "tipoff": row["tipoff"],
        "matchup": row["matchup"],
        "market": row["market"],
        "side": row["side"],
        "pick": row["pick"],
        "line": row.get("line"),
        "price": row["price"],
        "book": row.get("book"),
        "model_prob": row["model_prob"],
        "breakeven": row["breakeven"],
        "edge": row["edge"],
        "confidence": row["confidence"],
        "tier": row["tier"],
        "stake": 1.0 if shadow else row["stake"],
        "tracked_at": tracked_at,
        "result": "Pending",
        "profit": 0.0,
        "shadow": shadow,
    }


def sync(candidates: list[dict], games: list[dict], ledger_state: dict | None,
         shadow_state: dict | None, now: str | None = None) -> tuple[dict, dict]:
    now = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    game_map = {game["game_id"]: game for game in games}
    # Previous releases wrote qualifying model picks here automatically. Clear
    # that generated list during the first refresh after this migration. The
    # actual wager ledger is now explicit browser-local state, like MLB Edge.
    ledger = {"bets": [], "mode": "manual-browser"}
    shadow = shadow_state or {"calls": []}
    shadow.setdefault("calls", [])

    # The shadow book records every priced side so tier quality can be tested.
    shadow_existing = {row["id"] for row in shadow["calls"]}
    for row in candidates:
        from .model_accuracy import instant
        start = instant(row.get("tipoff"))
        if not start or start <= instant(now) or (game_map.get(row["game_id"]) or {}).get("completed"):
            continue
        if row["candidate_id"] not in shadow_existing:
            shadow["calls"].append(_lock(row, now, shadow=True))
            shadow_existing.add(row["candidate_id"])

    for row in shadow["calls"]:
        if row.get("result") not in {None, "Pending"}:
            continue
        game = game_map.get(row["game_id"])
        if not game:
            continue
        result = _result(row, game)
        if result:
            row["result"] = result
            row["profit"] = round(_profit(float(row["stake"]), float(row["price"]), result), 2)
            row["graded_at"] = now
            row["final_score"] = f'{int(game["away"]["score"])}-{int(game["home"]["score"])}'
    ledger["updated_at"] = now
    shadow["updated_at"] = now
    return ledger, shadow


def performance(ledger: dict, shadow: dict, starting_bankroll: float) -> dict:
    bets = ledger.get("bets") or []
    settled = [row for row in bets if row.get("result") != "Pending"]
    profit = round(sum(float(row.get("profit") or 0.0) for row in settled), 2)
    risked = round(sum(float(row.get("stake") or 0.0) for row in settled), 2)

    def groups(rows: list[dict], key: str) -> dict:
        buckets: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            buckets[str(row.get(key) or "Unknown")].append(row)
        output = {}
        for name, bucket in buckets.items():
            graded = [row for row in bucket if row.get("result") != "Pending"]
            wins = sum(row.get("result") == "Win" for row in graded)
            losses = sum(row.get("result") == "Loss" for row in graded)
            pushes = sum(row.get("result") == "Push" for row in graded)
            wagered = sum(float(row.get("stake") or 0.0) for row in graded)
            pnl = sum(float(row.get("profit") or 0.0) for row in graded)
            output[name] = {
                "record": f"{wins}-{losses}-{pushes}",
                "settled": len(graded),
                "win_pct": round(wins / (wins + losses), 4) if wins + losses else None,
                "profit": round(pnl, 2),
                "roi": round(pnl / wagered, 4) if wagered else None,
            }
        return output

    calls = shadow.get("calls") or []
    return {
        "starting_bankroll": starting_bankroll,
        "current_bankroll": round(starting_bankroll + profit, 2),
        "pending_bets": sum(row.get("result") == "Pending" for row in bets),
        "settled_bets": len(settled),
        "profit": profit,
        "risked": risked,
        "roi": round(profit / risked, 4) if risked else None,
        "by_tier": groups(calls, "tier"),
        "by_market": groups(calls, "market"),
    }
