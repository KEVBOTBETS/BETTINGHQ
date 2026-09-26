"""
Early-week locks and closing-line value for NFL plays.

Ported from ncaaf-edge-lab/pipeline/early.py, where a walk-forward check on
2026 weeks 3-4 found college plays priced 120h+ before kickoff went 54% ATS
and saw the line move +0.92 pts toward the model, versus 44-48% inside 72h.

The NFL market is sharper, so that finding is NOT assumed to carry over. Here
the timing gate ships switched off (`timing.full_tier_min_hours: 0`) and only
the tracking half runs:

  track()  -- the first time a bettable play shows up at LEAN or better, its
     line and price are locked. Every later run shows how far the market has
     moved toward (or away from) that lock; at kickoff it is compared with the
     last pregame DraftKings number (closing-line value); once final it is
     graded at the locked price. Locks are split into an early window
     (>= `timing.track_early_hours` before kickoff) and a late one, so the
     NFL's own record decides whether early-week betting deserves your money.

  timing_gate()  -- identical to college. Turn it on by setting
     `timing.full_tier_min_hours` once the early/late split shows a real gap.

Plays held outside the bet window are never locked: the model does not stake
them, so grading them would score prices nobody was told to take.
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

# --------------------------------------------------------------------------- #
# Closing-line gate: tiers are earned by beating the close, not by edge size.
# --------------------------------------------------------------------------- #
#
# The 2011-2025 nflverse backtest (pipeline/history_backtest.py) found the
# model's disagreement with the CLOSING line carries no reliable signal: log
# loss slightly worse than the market in every market, win rate flat across
# every edge bucket, and totals losing 5% a play. Whatever edge the board has
# must come from betting numbers before they move -- which is exactly what the
# locked-play CLV record measures. So:
#
#   unproven (fewer than `min_closed` tracked plays have reached kickoff)
#       BEST BET is capped at GOOD. Groups listed in `untiered_until_proven`
#       (totals) are priced and shown but not tiered at all -- they are still
#       locked as research plays so they can earn their way back.
#   proven   (beat the close >= `unlock_pct` of the time)  -- tiers as priced.
#   failing  (beat the close <  `fail_pct`)  -- everything capped at LEAN with
#       a reduced stake: the market is consistently ahead of the model.
#   neutral  (in between) -- BEST BET stays capped at GOOD.

GROUPS = {"ATS": "sides", "ML": "sides", "TOTAL": "totals"}
GROUP_LABEL = {"sides": "sides (spreads & moneylines)", "totals": "totals"}


def group_of(market: str | None) -> str:
    return GROUPS.get(market or "", "sides")


def gate_status(state: dict, cfg: dict) -> dict:
    """Where each market group stands, from locks already on file."""
    g = cfg.get("clv_gate") or {}
    need = int(g.get("min_closed", 100))
    unlock, fail = float(g.get("unlock_pct", .53)), float(g.get("fail_pct", .47))
    locks = list((state.get("locks") or {}).values())
    out = {}
    for name in ("sides", "totals"):
        s = _stats([l for l in locks if group_of(l.get("market")) == name])
        pct = s["beat_close_pct"]
        if not g.get("enabled"):
            status = "off"
        elif s["closed"] < need or pct is None:
            status = "unproven"
        elif pct >= unlock:
            status = "proven"
        elif pct < fail:
            status = "failing"
        else:
            status = "neutral"
        out[name] = {"status": status, "closed": s["closed"], "need": need,
                     "beat_close_pct": pct, "unlock_pct": unlock, "fail_pct": fail,
                     "untiered": name in (g.get("untiered_until_proven") or []) and status != "proven"}
    return out


def clv_gate(rows: list[dict], cfg: dict, status: dict) -> list[dict]:
    g = cfg.get("clv_gate") or {}
    if not g.get("enabled"):
        return rows
    research = set(g.get("untiered_until_proven") or [])
    fail_stake = float(g.get("failing_stake_multiplier", 0.5))
    for r in rows:
        tier = r.get("tier")
        if tier not in TRACK_TIERS:
            continue
        grp = group_of(r.get("market"))
        st = status.get(grp) or {}
        s = st.get("status", "unproven")
        pct = st.get("beat_close_pct")
        where = (f"{st.get('closed', 0)}/{st.get('need', 100)} tracked {grp} have closed"
                 + (f", {pct:.0%} beat the closing line" if pct is not None else ""))
        if grp in research and s != "proven":
            r["research_tier"], r["tier"], r["research"] = tier, "PASS", True
            r["filtered"] = (f"research only — model says {tier}, but 15 seasons of NFL totals at the "
                             f"close lost 5% a play. Totals are tiered again once tracked totals beat the "
                             f"closing line {float(g.get('unlock_pct', .53)):.0%} of the time ({where}).")
        elif s == "failing" and tier in ("BEST BET", "GOOD"):
            r["gate_tier"], r["tier"] = tier, "LEAN"
            r["stake_multiplier"] = min(float(r.get("stake_multiplier", 1.0)), fail_stake)
            r["tier_note"] = (f"capped at LEAN: the market has been ahead of the model — {where}")
        elif s != "proven" and tier == "BEST BET":
            r["gate_tier"], r["tier"] = tier, "GOOD"
            r["tier_note"] = (f"BEST BET is earned by beating the close, not by edge size — "
                              f"unlocks at {float(g.get('unlock_pct', .53)):.0%} ({where})")
    return rows


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
        # Research plays are locked too, flagged, and kept out of the headline
        # record since nobody was told to bet them: totals while untiered, and
        # plays the model rated but the one-per-game / weekly caps dropped.
        # They still count toward their group's closing-line gate -- CLV
        # judges the model's prices, and the caps would otherwise take most
        # of a season to produce 100 closed plays.
        research = bool(r.get("research") or r.get("capped_tier"))
        tier = r.get("research_tier") or r.get("capped_tier") if research else r.get("tier")
        if tier not in TRACK_TIERS or r.get("held"):
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
                "week": r.get("week"), "tier": tier, "best_tier": tier,
                "research": research,
                "line": r.get("line"), "price": r.get("price"), "book": r.get("book"),
                "action_edge": round(float(r.get("action_edge", r.get("edge", 0))), 4),
                "hours_to_kickoff": h,
                "window": "early" if h is not None and h >= early_hours else "late",
                "locked_at": now.isoformat(), "result": "Pending",
            }
        elif TIER_RANK[tier] < TIER_RANK.get(lock.get("best_tier", lock["tier"]), 9):
            lock["best_tier"] = tier

    for r in board:
        lock = locks.get(key(r))
        if not lock:
            continue
        move = clv(lock, r.get("line"), r.get("price"))
        r["early_lock"] = {**{k: lock.get(k) for k in ("tier", "line", "price", "locked_at", "window")},
                           "clv": move}
        if (lock["tier"] in EARLY_TIERS and not lock.get("research")
                and (r.get("timing_tier") or r.get("tier") != lock["tier"])):
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

    everything = list(locks.values())
    every = [l for l in everything if not l.get("research")]
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
        "by_group": {name: _stats([l for l in everything if group_of(l.get("market")) == name])
                     for name in ("sides", "totals")},
        "research": _stats([l for l in everything if l.get("research")]),
        "since": min((l["locked_at"] for l in everything), default=None),
        "note": ("Every LEAN-or-better play is locked at the first line and price it was "
                 "published at, then compared with DraftKings' last pregame number. "
                 "Beating the close is the early read; win rate needs 100+ plays to mean much."),
    }
