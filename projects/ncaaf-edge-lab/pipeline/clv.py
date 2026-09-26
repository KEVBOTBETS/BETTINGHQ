"""Closing-line value for the model's own frozen forecasts.

Win/loss needs a season to say anything. Line movement needs weeks: if the
model has real information, DraftKings' number should drift toward the model's
projection between the moment the forecast was frozen and kickoff more often
than away from it. This reads only what is already stored -- the frozen game
forecasts (state/model_accuracy.json) and the line snapshots (state/lines.json)
-- so it covers every forecast from the start of the season, not just plays.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _t(stamp):
    if not stamp:
        return None
    try:
        d = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _summary(moves: list[float]) -> dict:
    toward = sum(m > 0 for m in moves)
    away = sum(m < 0 for m in moves)
    return {
        "n": len(moves),
        "toward_model": toward,
        "away_from_model": away,
        "unchanged": len(moves) - toward - away,
        "toward_pct": round(toward / (toward + away), 3) if toward + away else None,
        "avg_points": round(sum(moves) / len(moves), 2) if moves else None,
    }


def forecast_clv(records: dict, lines: dict, now: datetime | None = None,
                 min_gap: float = 0.5, big_gap: float = 2.0) -> dict:
    """Did the line move toward each frozen forecast before kickoff?

    Reference line: the last snapshot at or before the forecast was frozen, or
    the opener if the forecast came first. Close: the last snapshot before
    kickoff. Forecasts within `min_gap` points of the reference line have no
    side and are skipped.
    """
    now = now or datetime.now(timezone.utc)
    spread_moves, spread_big, total_moves = [], [], []
    for r in (records or {}).values():
        if r.get("kind") != "game":
            continue
        ko, cap = _t(r.get("start")), _t(r.get("captured_at"))
        if ko is None or cap is None or ko > now:
            continue
        snaps = [s for s in (lines.get(str(r.get("event_id"))) or []) if _t(s.get("ts"))]
        pre = [s for s in snaps if _t(s["ts"]) <= ko]
        if not pre:
            continue
        before = [s for s in pre if _t(s["ts"]) <= cap]
        ref, close = (before[-1] if before else pre[0]), pre[-1]
        if r.get("margin") is not None and ref.get("spread_home") is not None \
                and close.get("spread_home") is not None:
            ref_margin, close_margin = -float(ref["spread_home"]), -float(close["spread_home"])
            gap = float(r["margin"]) - ref_margin
            if abs(gap) >= min_gap:
                move = (close_margin - ref_margin) * (1 if gap > 0 else -1)
                spread_moves.append(move)
                if abs(gap) >= big_gap:
                    spread_big.append(move)
        if r.get("total") is not None and ref.get("total") is not None \
                and close.get("total") is not None:
            gap = float(r["total"]) - float(ref["total"])
            if abs(gap) >= min_gap:
                total_moves.append((float(close["total"]) - float(ref["total"])) * (1 if gap > 0 else -1))
    return {
        "spread": _summary(spread_moves),
        "spread_big": {**_summary(spread_big), "min_gap": big_gap},
        "total": _summary(total_moves),
        "note": ("Line movement between the frozen forecast and kickoff, from the model's side. "
                 "Moving toward the model more often than away is the quickest sign of a real edge; "
                 "about 50/50 means the market already knew what the model knew."),
    }
