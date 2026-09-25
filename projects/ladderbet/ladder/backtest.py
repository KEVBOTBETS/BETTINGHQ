"""Replay the selector over past days using real closing odds and real results.

ESPN's scoreboard accepts ?dates=YYYYMMDD and returns, for finished games, both
the closing moneyline and the final score. That is enough to ask the only
question that matters: in YOUR leagues, in YOUR odds window, how often does the
top-ranked favourite actually win, and what would the ladder have done?

Two honest caveats on the numbers this produces.

1. LOOK-AHEAD BIAS. Selection here uses the *closing* price, which is the
   sharpest number of the day and is not knowable when you would actually bet.
   Real results will be modestly worse than the backtest. The `--use-open` flag
   selects and prices on the opening line instead, which is pessimistic in the
   other direction. The truth sits between the two, so run both.

2. SURVIVORSHIP IN THE FEED. ESPN keeps odds only for games it still serves,
   and postponed or voided games simply vanish. Days with no data are skipped,
   not counted as losses.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean

from . import espn
from .selector import screen_event, rank
from . import stats

CACHE = Path(".cache")


def _cache_path(league: str, d: str) -> Path:
    return CACHE / league / f"{d}.json"


def fetch_day(league: str, d: str, sleep: float = 0.6, use_cache: bool = True) -> list[dict]:
    """Fetch one league-day, cached to disk so re-runs cost nothing."""
    p = _cache_path(league, d)
    if use_cache and p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    try:
        evs = espn.events(league, d)
    except espn.ESPNError:
        evs = []
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(evs))
    time.sleep(sleep)          # be polite to a free, unsupported endpoint
    return evs


def _daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


@dataclass
class DayResult:
    day: str
    picked: bool
    league: str = ""
    matchup: str = ""
    pick: str = ""
    decimal: float = 0.0
    fair_prob: float = 0.0
    result: str = ""           # win | loss | skipped
    detail: str = ""
    n_candidates: int = 0


@dataclass
class Backtest:
    days: list[DayResult] = field(default_factory=list)

    def graded(self) -> list[DayResult]:
        return [d for d in self.days if d.result in ("win", "loss")]

    def simulate(self, base: float, max_rung: int) -> dict:
        """Walk the graded days through the ladder rules."""
        net, rung, stake = 0.0, 0, base
        busts = cashouts = 0
        best = run = 0
        for d in self.graded():
            if d.result == "win":
                stake *= d.decimal
                rung += 1
                run += 1
                best = max(best, run)
                if rung >= max_rung:
                    net += stake - base
                    cashouts += 1
                    rung, stake = 0, base
            else:
                net -= base
                busts += 1
                run = 0
                rung, stake = 0, base
        return {"max_rung": max_rung, "net": round(net, 2), "cashouts": cashouts,
                "busts": busts, "best_streak": best,
                "open_stack": round(stake - base, 2) if rung else 0.0}

    def sequence(self) -> list[tuple[str, float]]:
        return [(d.result, d.decimal) for d in self.graded()]

    def summary(self, base: float) -> dict:
        g = self.graded()
        if not g:
            return {"graded": 0}
        wins = [d for d in g if d.result == "win"]
        predicted = mean(d.fair_prob for d in g)
        actual = len(wins) / len(g)
        avg_dec = mean(d.decimal for d in g)
        breakeven = mean(1.0 / d.decimal for d in g)

        streaks, run = [], 0
        for d in g:
            if d.result == "win":
                run += 1
            else:
                streaks.append(run)
                run = 0
        streaks.append(run)

        k, n = len(wins), len(g)
        ci_lo, ci_hi = stats.wilson(k, n)
        seq = self.sequence()

        by_league = {}
        for d in g:
            b = by_league.setdefault(d.league, {"n": 0, "w": 0})
            b["n"] += 1
            b["w"] += 1 if d.result == "win" else 0
        leagues_out = []
        for lg, b in sorted(by_league.items(), key=lambda x: -x[1]["n"]):
            lo, hi = stats.wilson(b["w"], b["n"])
            leagues_out.append({"league": lg, "n": b["n"], "wins": b["w"],
                                "hit_rate": round(b["w"] / b["n"], 4),
                                "ci_low": round(lo, 4), "ci_high": round(hi, 4)})

        return {
            "days_scanned": len(self.days),
            "days_with_a_bet": len(g),
            "no_bet_days": len(self.days) - len(g),
            "graded": len(g),
            "wins": len(wins),
            "actual_hit_rate": round(actual, 4),
            "model_predicted": round(predicted, 4),
            "calibration_gap": round(actual - predicted, 4),
            "break_even_needed": round(breakeven, 4),
            "edge_vs_breakeven": round(actual - breakeven, 4),
            "avg_decimal": round(avg_dec, 4),
            "longest_streak": max(streaks),
            "ci_low": round(ci_lo, 4),
            "ci_high": round(ci_hi, 4),
            "ci_width_pts": round((ci_hi - ci_lo) * 100, 1),
            "beats_breakeven_significantly": ci_lo > breakeven,
            "worse_than_breakeven_significantly": ci_hi < breakeven,
            "n_needed_for_2pt_edge": stats.required_n(breakeven, 0.02),
            "n_needed_for_5pt_edge": stats.required_n(breakeven, 0.05),
            "by_league": leagues_out,
            "by_price": stats.buckets(
                [(d.decimal, d.result) for d in g],
                [min_d := 1.50, 1.55, 1.60, 1.667]),
            "ladders": [self.simulate(base, n) for n in (3, 4, 5, 6, 8, 10)],
            "bootstrap": [stats.bootstrap_ladder(seq, base, n)
                          for n in (3, 4, 5, 6, 8, 10)],
        }


def run(leagues: list[str], start: date, end: date, min_decimal: float,
        max_decimal: float, max_hold: float = 0.10, use_open: bool = False,
        sleep: float = 0.6, use_cache: bool = True, progress=None) -> Backtest:
    bt = Backtest()

    for d in _daterange(start, end):
        ds = d.strftime("%Y%m%d")
        cands = []
        finished: dict[str, dict] = {}

        for lg in leagues:
            for ev in fetch_day(lg, ds, sleep, use_cache):
                comp = (ev.get("competitions") or [{}])[0]
                st = espn.status(comp)
                if not st.get("state"):
                    st = espn.status(ev)
                if not st.get("completed"):
                    continue
                finished[str(ev.get("id"))] = ev
                for c in screen_event(ev, lg, min_decimal, max_decimal,
                                      max_hold, require_pre=False,
                                      use_open=use_open):
                    cands.append(c)

        if not cands:
            bt.days.append(DayResult(day=ds, picked=False, result="skipped",
                                     detail="no qualifying bet"))
            if progress:
                progress(ds, None)
            continue

        top = rank(cands)[0]
        ev = finished.get(top.event_id)
        res, detail = espn.grade(ev, top.side, top.league) if ev else ("pending", "missing")

        dr = DayResult(day=ds, picked=True, league=top.league,
                       matchup=top.matchup, pick=top.pick, decimal=top.decimal,
                       fair_prob=top.fair_prob,
                       result=res if res in ("win", "loss") else "skipped",
                       detail=detail, n_candidates=len(cands))
        bt.days.append(dr)
        if progress:
            progress(ds, dr)

    return bt


def to_csv(bt: Backtest) -> str:
    import csv
    from io import StringIO
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["day", "league", "matchup", "pick", "decimal", "fair_prob",
                "result", "detail", "n_candidates"])
    for d in bt.days:
        w.writerow([d.day, d.league, d.matchup, d.pick, d.decimal or "",
                    d.fair_prob or "", d.result, d.detail, d.n_candidates])
    return buf.getvalue()
