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
  2. track()        -- the first time a play shows up at LEAN or better, its
     line and price are locked here (early or late, whatever the gate says).  Every later run shows how far
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


TRACK_TIERS = ("BEST BET", "GOOD", "LEAN")
TIER_RANK = {"BEST BET": 0, "GOOD": 1, "LEAN": 2}


def _beat(move: dict | None) -> bool | None:
    """True if the locked number beat the close, False if worse, None if unchanged."""
    move = move or {}
    pts, prob = move.get("points"), move.get("prob")
    if pts:
        return pts > 0
    if prob:
        return prob > 0
    return None


def _stats(locks: list[dict]) -> dict:
    graded = [l for l in locks if l["result"] != "Pending"]
    w = sum(l["result"] == "Win" for l in graded)
    lo = sum(l["result"] == "Loss" for l in graded)
    closed = [l for l in locks if l.get("closing_clv")]
    pts = [l["closing_clv"]["points"] for l in closed if l["closing_clv"].get("points") is not None]
    probs = [l["closing_clv"]["prob"] for l in closed if l["closing_clv"].get("prob") is not None]
    verdicts = [_beat(l["closing_clv"]) for l in closed]
    better, worse = sum(v is True for v in verdicts), sum(v is False for v in verdicts)
    return {
        "tracked": len(locks),
        "closed": len(closed),
        "pending": len(locks) - len(graded),
        "record": f"{w}-{lo}-{len(graded) - w - lo}",
        "win_rate": round(w / (w + lo), 3) if w + lo else None,
        "avg_clv_points": round(sum(pts) / len(pts), 2) if pts else None,
        "avg_clv_prob": round(sum(probs) / len(probs), 4) if probs else None,
        "beat_close": better, "worse_than_close": worse,
        "same_as_close": len(closed) - better - worse,
        "beat_close_pct": round(better / (better + worse), 3) if better + worse else None,
    }


def track(state: dict, board: list[dict], games: list[dict], lines: dict,
          cfg: dict, now: datetime | None = None) -> dict:
    """Lock every qualified play at its first price, annotate the board, grade at the close.

    Runs whether or not the timing gate is on. Each play is locked the first
    time it shows up as LEAN or better, at the line and price it had then, so
    the record cannot be flattered by later, better numbers or by plays that
    quietly drop off the board. Once the game kicks off, the lock is compared
    with the last pregame DraftKings number (closing-line value) and, once
    final, graded at the locked price.
    """
    now = now or datetime.now(timezone.utc)
    locks = state.setdefault("locks", {})
    early_hours = float((cfg.get("timing") or {}).get("track_early_hours", 96))

    for r in board:
        if r.get("tier") not in TRACK_TIERS:
            continue
        lock = locks.get(key(r))
        if lock is None:
            h = r.get("hours_to_kickoff")
            if h is None:
                hk = hours_to_kickoff(r, now)
                h = None if hk is None else round(hk, 1)
            locks[key(r)] = {
                "game_id": r["game_id"], "market": r["market"], "side": r["side"],
                "pick": r["pick"], "matchup": r["matchup"], "game_date": r.get("game_date"),
                "week": r.get("week"), "tier": r["tier"], "best_tier": r["tier"],
                "line": r.get("line"), "price": r.get("price"), "book": r.get("book"),
                "action_edge": round(float(r.get("action_edge", r.get("edge", 0))), 4),
                "hours_to_kickoff": h,
                "window": "early" if h is not None and h >= early_hours else "late",
                "locked_at": now.isoformat(), "result": "Pending",
            }
        elif TIER_RANK[r["tier"]] < TIER_RANK.get(lock.get("best_tier", lock["tier"]), 9):
            lock["best_tier"] = r["tier"]

    for r in board:
        lock = locks.get(key(r))
        if not lock:
            continue
        move = clv(lock, r.get("line"), r.get("price"))
        r["early_lock"] = {**{k: lock.get(k) for k in ("tier", "line", "price", "locked_at", "window")},
                           "clv": move}
        if lock["tier"] in EARLY_TIERS and (r.get("timing_tier") or r.get("tier") != lock["tier"]):
            when = _instant(lock["locked_at"]).astimezone().strftime("%a")
            note = f"Early play: {lock['tier']} {when} at {lock['pick']} ({float(lock['price']):+.0f})"
            if move["points"] is not None:
                note += f" · line moved {move['points']:+.1f} pts your way"
            rest = [f for f in (r.get("risk_flags") or []) if not f.startswith("Late-week price")]
            r["risk_flags"] = list(dict.fromkeys([note, *rest]))
            r["warning"] = " · ".join(r["risk_flags"])

    finals = {g["game_id"]: g for g in games if g.get("completed")}
    for lock in locks.values():
        ko = _instant(lock.get("game_date"))
        hist = lines.get(str(lock["game_id"])) or []
        pre = [s for s in hist if ko is None or (_instant(s.get("ts")) or ko) <= ko]
        close = pre[-1] if pre else None
        m, side = lock["market"], lock["side"]
        if m == "ATS":
            close_line = (close or {}).get("spread_home")
            close_price = (close or {}).get("spread_price_home" if side == "home" else "spread_price_away")
        elif m == "TOTAL":
            close_line = (close or {}).get("total")
            close_price = (close or {}).get("over_price" if side == "over" else "under_price")
        else:
            close_line, close_price = None, (close or {}).get("ml_home" if side == "home" else "ml_away")
        # Closing-line value is known at kickoff; no need to wait for the final.
        if close and ko is not None and now >= ko and not lock.get("closing_clv"):
            lock["closing_clv"] = clv(lock, close_line, close_price)
        g = finals.get(lock["game_id"])
        if lock["result"] != "Pending" or not g:
            continue
        margin = float(g["home_score"]) - float(g["away_score"])
        total = float(g["home_score"]) + float(g["away_score"])
        if m == "ATS":
            cover = margin + float(lock["line"])
            cover = cover if side == "home" else -cover
        elif m == "TOTAL":
            cover = (total - float(lock["line"])) * (1 if side == "over" else -1)
        else:
            cover = margin if side == "home" else -margin
        lock["result"] = "Win" if cover > 0 else "Loss" if cover < 0 else "Push"
        if not lock.get("closing_clv"):
            lock["closing_clv"] = clv(lock, close_line, close_price)
        lock["graded_at"] = now.isoformat()

    every = list(locks.values())
    good = [l for l in every if l["tier"] in EARLY_TIERS]
    overall = _stats(every)
    return {
        **overall,
        "locked": len(every),
        "window_hours": float((cfg.get("timing") or {}).get("full_tier_min_hours") or 0),
        "early_hours": early_hours,
        "by_tier": {"good_or_better": _stats(good),
                    "lean": _stats([l for l in every if l["tier"] == "LEAN"])},
        "by_timing": {"early": _stats([l for l in every if l.get("window") == "early"]),
                      "late": _stats([l for l in every if l.get("window") != "early"])},
        "since": min((l["locked_at"] for l in every), default=None),
        "note": ("Every LEAN-or-better play is locked at the first line and price it was "
                 "published at, then compared with DraftKings' last pregame number. "
                 "Beating the close is the early read; win rate needs 100+ plays to mean much."),
    }
