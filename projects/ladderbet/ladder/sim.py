"""Monte Carlo the ladder so you can see the shape before you fund it."""
from __future__ import annotations

import random
from statistics import mean


def simulate(
    base: float = 5.0,
    decimal: float = 1.55,
    true_prob: float | None = None,
    max_rung: int = 8,
    days: int = 365,
    trials: int = 20000,
    seed: int | None = 42,
) -> dict:
    """true_prob defaults to the fair (no-vig) probability implied by `decimal`
    minus a 2.2% bookmaker edge, which is roughly what a sharp price on a
    -150/-200 favourite costs you in practice."""
    if true_prob is None:
        true_prob = max(0.0, (1.0 / decimal) - 0.022)

    rng = random.Random(seed)
    finals, busts, cashouts, best_rungs = [], [], [], []

    for _ in range(trials):
        net, rung, stake, bust, cash, best = 0.0, 0, base, 0, 0, 0
        for _ in range(days):
            if rng.random() < true_prob:
                stake *= decimal
                rung += 1
                best = max(best, rung)
                if rung >= max_rung:
                    net += stake - base
                    cash += 1
                    rung, stake = 0, base
            else:
                net -= base
                bust += 1
                rung, stake = 0, base
        finals.append(round(net, 2))
        busts.append(bust)
        cashouts.append(cash)
        best_rungs.append(best)

    finals.sort()
    q = lambda f: finals[int(f * (len(finals) - 1))]
    return {
        "assumed_true_prob": round(true_prob, 4),
        "break_even_prob": round(1.0 / decimal, 4),
        "per_bet_ev": round(true_prob * decimal - 1.0, 4),
        "trials": trials,
        "days": days,
        "mean_net": round(mean(finals), 2),
        "median_net": q(0.50),
        "p05": q(0.05),
        "p25": q(0.25),
        "p75": q(0.75),
        "p95": q(0.95),
        "pct_profitable": round(sum(1 for f in finals if f > 0) / len(finals), 4),
        "mean_busts_per_year": round(mean(busts), 1),
        "mean_cashouts_per_year": round(mean(cashouts), 2),
        "mean_best_streak": round(mean(best_rungs), 2),
    }
