"""
Early-week plays: where this model's college football edge actually lives.

Walk-forward check on 2026 weeks 3-4 (107 FBS-vs-FBS games, ratings frozen at
the start of each week, prices from state/lines.json, no look-ahead lines):

    hours before kickoff   ATS (gap > 4 pts)   avg line move toward model
    120h+  (Sun/Mon)       54%                 +0.92 pts
     96-120h               49%                 +0.50
     72-96h                47%                 +0.40
     48-72h                44%                 +0.28
      0-48h  (Fri/Sat)     48%                 +0.18

The model sees something the Sunday/Monday number has not priced yet; by
Saturday the market has mostly moved to it.  Two consequences, both here:

  1. timing_gate()  -- a play priced inside `timing.full_tier_min_hours` can be
     at most LEAN.  Its GOOD/BEST label belongs to the early price, not today's.
  2. track()        -- the first time a play earns GOOD/BEST inside the early
     window, its line and price are locked here.  Every later run shows how far
     the market has moved toward (or away from) that lock, and once the game is
     final the lock is graded.  That record -- not a backtest of two weeks --
     is what should decide whether the early window deserves your money.

Sample is small.  Treat the table above as a hypothesis this file tests live.
"""
from __future__ import annotations

from datetime import datetime, timezone

EARLY_TIERS = ("BEST BET", "GOOD")


def _instant(stamp):
    if not stamp:
        return None
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def hours_to_kickoff(row: dict, now: datetime) -> float | None:
    ko = _instant(row.get("game_date"))
    return None if ko is None else (ko - now).total_seconds() / 3600.0


def key(row: dict) -> str:
    return f"{row['game_id']}|{row['market']}|{row['side']}"


def _implied(price: float) -> float:
    price = float(price)
    return 100.0 / (price + 100.0) if price > 0 else -price / (-price + 100.0)


def clv(lock: dict, line: float | None, price: float | None) -> dict:
    """How far the market has moved toward the locked side. Positive = good."""
    out = {"points": None, "prob": None}
    m, side = lock["market"], lock["side"]
    if m == "ATS" and line is not None and lock.get("line") is not None:
        # `line` is always the home spread on this board.
        d = float(lock["line"]) - float(line)
        out["points"] = round(d if side == "home" else -d, 2)
    elif m == "TOTAL" and line is not None and lock.get("line") is not None:
        d = float(line) - float(lock["line"])
        out["points"] = round(d if side == "over" else -d, 2)
    if price is not None and lock.get("price") is not None:
        out["prob"] = round(_implied(price) - _implied(lock["price"]), 4)
    return out


def timing_gate(rows: list[dict], cfg: dict, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    t = cfg.get("timing") or {}
    min_h = float(t.get("full_tier_min_hours") or 0)
    late_stake = float(t.get("late_stake_multiplier", 0.6))
    for r in rows:
        h = hours_to_kickoff(r, now)
        r["hours_to_kickoff"] = None if h is None else round(h, 1)
        r["early_window"] = bool(min_h and h is not None and h >= min_h)
        if not min_h or h is None or h >= min_h or r.get("tier") not in EARLY_TIERS:
            continue
        r["timing_tier"] = r["tier"]
        r["tier"] = "LEAN"
        r["stake_multiplier"] = min(float(r.get("stake_multiplier", 1.0)), late_stake)
        flag = (f"Late-week price — {r['timing_tier']} earlier in the week; "
                "the edge is mostly priced in by kickoff")
        r["risk_flags"] = list(dict.fromkeys([*(r.get("risk_flags") or []), flag]))
        r["warning"] = " · ".join(r["risk_flags"])
    return rows


def track(state: dict, board: list[dict], games: list[dict], lines: dict,
          cfg: dict, now: datetime | None = None) -> dict:
    """Lock new early plays, annotate the board with CLV, grade finished locks."""
    now = now or datetime.now(timezone.utc)
    locks = state.setdefault("locks", {})

    for r in board:
        if r.get("early_window") and r.get("tier") in EARLY_TIERS and key(r) not in locks:
            locks[key(r)] = {
                "game_id": r["game_id"], "market": r["market"], "side": r["side"],
                "pick": r["pick"], "matchup": r["matchup"], "game_date": r.get("game_date"),
                "week": r.get("week"), "tier": r["tier"], "line": r.get("line"),
                "price": r.get("price"), "book": r.get("book"),
                "action_edge": round(float(r.get("action_edge", r.get("edge", 0))), 4),
                "hours_to_kickoff": r.get("hours_to_kickoff"),
                "locked_at": now.isoformat(), "result": "Pending",
            }

    for r in board:
        lock = locks.get(key(r))
        if not lock:
            continue
        move = clv(lock, r.get("line"), r.get("price"))
        r["early_lock"] = {**{k: lock[k] for k in ("tier", "line", "price", "locked_at")}, "clv": move}
        if r.get("timing_tier") or r.get("tier") != lock["tier"]:
            when = _instant(lock["locked_at"]).astimezone().strftime("%a")
            note = f"Early play: {lock['tier']} {when} at {lock['pick']} ({float(lock['price']):+.0f})"
            if move["points"] is not None:
                note += f" · line moved {move['points']:+.1f} pts your way"
            rest = [f for f in (r.get("risk_flags") or []) if not f.startswith("Late-week price")]
            r["risk_flags"] = list(dict.fromkeys([note, *rest]))
            r["warning"] = " · ".join(r["risk_flags"])

    finals = {g["game_id"]: g for g in games if g.get("completed")}
    for lock in locks.values():
        g = finals.get(lock["game_id"])
        if lock["result"] != "Pending" or not g:
            continue
        hist = lines.get(str(lock["game_id"])) or []
        ko = _instant(lock.get("game_date"))
        pre = [s for s in hist if ko is None or (_instant(s.get("ts")) or ko) <= ko]
        close = pre[-1] if pre else None
        margin = float(g["home_score"]) - float(g["away_score"])
        total = float(g["home_score"]) + float(g["away_score"])
        m, side = lock["market"], lock["side"]
        if m == "ATS":
            cover = margin + float(lock["line"])
            cover = cover if side == "home" else -cover
            close_line = (close or {}).get("spread_home")
            close_price = (close or {}).get("spread_price_home" if side == "home" else "spread_price_away")
        elif m == "TOTAL":
            cover = (total - float(lock["line"])) * (1 if side == "over" else -1)
            close_line = (close or {}).get("total")
            close_price = (close or {}).get("over_price" if side == "over" else "under_price")
        else:
            cover = margin if side == "home" else -margin
            close_line, close_price = None, (close or {}).get("ml_home" if side == "home" else "ml_away")
        lock["result"] = "Win" if cover > 0 else "Loss" if cover < 0 else "Push"
        lock["closing_clv"] = clv(lock, close_line, close_price)
        lock["graded_at"] = now.isoformat()

    graded = [l for l in locks.values() if l["result"] != "Pending"]
    w = sum(l["result"] == "Win" for l in graded)
    lo = sum(l["result"] == "Loss" for l in graded)
    pts = [l["closing_clv"]["points"] for l in graded if (l.get("closing_clv") or {}).get("points") is not None]
    probs = [l["closing_clv"]["prob"] for l in graded if (l.get("closing_clv") or {}).get("prob") is not None]
    return {
        "window_hours": float((cfg.get("timing") or {}).get("full_tier_min_hours") or 0),
        "locked": len(locks),
        "pending": len(locks) - len(graded),
        "record": f"{w}-{lo}-{len(graded) - w - lo}",
        "win_rate": round(w / (w + lo), 3) if w + lo else None,
        "avg_clv_points": round(sum(pts) / len(pts), 2) if pts else None,
        "avg_clv_prob": round(sum(probs) / len(probs), 4) if probs else None,
        "beat_close_pct": round(sum(p > 0 for p in probs) / len(probs), 3) if probs else None,
        "note": ("Plays locked Sun–Tue at GOOD or better, graded at their locked price. "
                 "Closing-line value is the early read; win rate needs 100+ plays to mean much."),
    }
