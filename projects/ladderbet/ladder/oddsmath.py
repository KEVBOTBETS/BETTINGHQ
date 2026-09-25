"""Odds conversion, de-vigging, and ladder expectation math."""
from __future__ import annotations


def american_to_decimal(a: float) -> float:
    if a >= 100:
        return 1.0 + a / 100.0
    if a <= -100:
        return 1.0 + 100.0 / abs(a)
    raise ValueError(f"invalid american odds: {a}")


def decimal_to_american(d: float) -> float:
    if d <= 1.0:
        raise ValueError(f"invalid decimal odds: {d}")
    if d >= 2.0:
        return round((d - 1.0) * 100.0, 1)
    return round(-100.0 / (d - 1.0), 1)


def implied(d: float) -> float:
    """Raw implied probability, vig included."""
    return 1.0 / d


def devig(decimals: list[float]) -> list[float]:
    """Proportional (multiplicative) de-vig across a complete market."""
    raw = [implied(d) for d in decimals]
    total = sum(raw)
    if total <= 0:
        raise ValueError("empty market")
    return [r / total for r in raw]


def hold(decimals: list[float]) -> float:
    """Bookmaker hold / overround, e.g. 0.045 == 4.5%."""
    return sum(implied(d) for d in decimals) - 1.0


def edge(fair_prob: float, price_decimal: float) -> float:
    """Expected return per unit staked. 0.02 == +2% EV."""
    return fair_prob * price_decimal - 1.0


def ladder_stakes(base: float, decimals: list[float]) -> list[float]:
    """Stake on each rung when the full return is rolled forward."""
    stakes, s = [], base
    for d in decimals:
        stakes.append(round(s, 2))
        s = s * d
    return stakes


def ladder_payout(base: float, decimals: list[float]) -> float:
    p = base
    for d in decimals:
        p *= d
    return round(p, 2)


def survival(p: float, rungs: int) -> float:
    """Probability of winning `rungs` straight legs at true prob p."""
    return p ** rungs


def ladder_ev(base: float, p: float, d: float, rungs: int) -> float:
    """EV of a full ladder run that cashes out after `rungs` wins.

    You lose the base stake unless every leg wins, so
    EV = base * (p * d) ** rungs.  If p * d < 1 (always true once the
    bookmaker's hold is priced in), more rungs means less EV.
    """
    return base * (p * d) ** rungs
