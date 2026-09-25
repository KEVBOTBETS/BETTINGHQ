"""Statistics for reading a backtest without fooling yourself.

A 90-day backtest yields perhaps 60-80 graded bets. On that sample a hit rate
of 66% against a predicted 62% looks like an edge and is almost certainly
noise. Everything here exists to keep that mistake visible.
"""
from __future__ import annotations

import random
from math import sqrt
from statistics import mean


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion.

    Preferred over the normal approximation because it stays inside [0,1] and
    behaves at small n, which is exactly the regime a backtest lives in.
    """
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - spread) / d), min(1.0, (centre + spread) / d))


def required_n(p: float, delta: float, alpha_z: float = 1.96,
               power_z: float = 0.84) -> int:
    """Bets needed to detect a true edge of `delta` at ~95% / 80% power."""
    if delta <= 0:
        return 0
    return int(((alpha_z + power_z) ** 2) * p * (1 - p) / (delta ** 2)) + 1


def significant(k: int, n: int, baseline: float, z: float = 1.96) -> bool:
    """Is the observed rate distinguishable from `baseline` at all?"""
    lo, hi = wilson(k, n, z)
    return lo > baseline or hi < baseline


def run_ladder(seq: list[tuple[str, float]], base: float, max_rung: int) -> float:
    """Net from one ordered sequence of (result, decimal)."""
    net, rung, stake = 0.0, 0, base
    for res, dec in seq:
        if res == "win":
            stake *= dec
            rung += 1
            if rung >= max_rung:
                net += stake - base
                rung, stake = 0, base
        else:
            net -= base
            rung, stake = 0, base
    return net


def bootstrap_ladder(seq: list[tuple[str, float]], base: float, max_rung: int,
                     trials: int = 4000, seed: int | None = 7) -> dict:
    """Resample the same bets in different orders.

    A ladder's net depends heavily on the ORDER results arrive in — the same
    bets rearranged can cash out twice or never. The single historical ordering
    is one draw from that distribution, so reporting only its net overstates
    what you know. This resamples with replacement to show the spread.
    """
    if not seq:
        return {}
    rng = random.Random(seed)
    n = len(seq)
    nets = []
    for _ in range(trials):
        sample = [seq[rng.randrange(n)] for _ in range(n)]
        nets.append(run_ladder(sample, base, max_rung))
    nets.sort()

    def q(f: float) -> float:
        return round(nets[int(f * (len(nets) - 1))], 2)

    return {
        "max_rung": max_rung,
        "actual": round(run_ladder(seq, base, max_rung), 2),
        "median": q(0.50),
        "p05": q(0.05),
        "p95": q(0.95),
        "mean": round(mean(nets), 2),
        "pct_profitable": round(sum(1 for x in nets if x > 0) / len(nets), 4),
    }


def buckets(rows: list[tuple[float, str]], edges: list[float]) -> list[dict]:
    """Group (decimal, result) by price band, with a Wilson interval each."""
    out = []
    for lo, hi in zip(edges, edges[1:]):
        sel = [r for d, r in rows if lo <= d < hi]
        if not sel:
            continue
        k = sum(1 for r in sel if r == "win")
        n = len(sel)
        wlo, whi = wilson(k, n)
        mid = (lo + hi) / 2
        out.append({
            "range": f"{lo:.2f}-{hi:.2f}",
            "n": n, "wins": k,
            "hit_rate": round(k / n, 4),
            "ci_low": round(wlo, 4), "ci_high": round(whi, 4),
            "break_even": round(1.0 / mid, 4),
            "beats_breakeven": wlo > 1.0 / mid,
        })
    return out
