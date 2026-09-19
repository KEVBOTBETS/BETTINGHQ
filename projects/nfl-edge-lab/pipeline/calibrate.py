"""
Self-calibration: feed the tracked accuracy back into the probabilities.

The Accuracy tab measures whether a 58% call wins 58% of the time. This module
does the obvious next thing with that measurement, which almost no home-made
model bothers to do: it corrects the probabilities.

The method is symmetric temperature scaling fitted on
the model's own graded history:

    calibrated = sigmoid( a * logit(raw) )

`a` is sharpness. Below 1 flattens probabilities; above 1 sharpens them.
The intercept stays zero so opposing-side probabilities remain complementary.

Three guards, because a recalibration fitted on thin data is worse than none.

  * It needs `min_samples` graded calls before it does anything at all, and the
    default is deliberately high. Fitting a correction to forty results is
    fitting to noise.
  * `a` is clamped and `b` stays zero. A wild fit means something upstream is broken; the
    right response is to nudge the probabilities and leave a message in the log,
    not to let one strange month invert the whole model.
  * The fit uses verified raw pregame observations, including passes, with
    one canonical side per event/market and a distinct-game minimum. Legacy
    rows without the necessary provenance are retained but not used to fit.

The fitted parameters are published in `meta.json` and shown on the site, so a
correction being applied is never invisible.
"""

from __future__ import annotations

import math


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def fit(shadow: dict, cfg: dict) -> dict:
    """
    Fit (a, b) by Newton-Raphson on the log-likelihood. Returns a status dict
    that is always safe to hand to `apply`.
    """
    conf = (cfg.get("model") or {}).get("calibration") or {}
    off = {"enabled": False, "a": 1.0, "b": 0.0, "n": 0,
           "reason": "calibration disabled in settings"}
    if not conf.get("enabled", False):
        return off

    # One canonical side per event/market. Opposite sides are the same outcome,
    # and legacy calibrated probabilities must never train their own correction.
    from .model_accuracy import instant, number
    selected = {}
    for r in shadow.values():
        market = r.get("market")
        canonical = "over" if market == "TOTAL" else "home"
        if market not in {"ML", "ATS", "TOTAL"} or r.get("side") != canonical:
            continue
        captured, kickoff = instant(r.get("first_seen")), instant(r.get("game_date"))
        p = number(r.get("model_prob_uncalibrated"))
        if (r.get("calibration_snapshot_version") != "pregame-v2"
                or not captured or not kickoff or captured >= kickoff
                or p is None or not 0 < p < 1
                or r.get("result") not in {"Win", "Loss"} or not r.get("game_id")):
            continue
        key = (str(r["game_id"]), market)
        previous = selected.get(key)
        if previous is None or captured < previous[0]:
            selected[key] = (captured, p, 1.0 if r["result"] == "Win" else 0.0)
    rows = [(p, y) for _, p, y in selected.values()]
    games = len({gid for gid, _ in selected})
    need = int(conf.get("min_samples", 400))
    need_games = int(conf.get("min_games", 100))
    if len(rows) < need or games < need_games:
        return {"enabled": False, "a": 1.0, "b": 0.0, "n": len(rows), "games": games,
                "reason": f"needs {need} unique pregame event/markets and {need_games} games; has {len(rows)} and {games}"}

    xs = [_logit(p) for p, _ in rows]
    ys = [y for _, y in rows]

    # Fit sharpness only. A shared intercept applied to both opposing sides
    # makes P(home) + P(away) differ from one. Symmetric temperature scaling
    # preserves the probability identity exactly.
    a, b = 1.0, 0.0
    for _ in range(60):
        gradient = curvature = 0.0
        for x, y in zip(xs, ys):
            p = _sigmoid(a * x)
            gradient += (p - y) * x
            curvature += p * (1 - p) * x * x
        if curvature < 1e-12:
            break
        delta = max(-0.5, min(0.5, gradient / curvature))
        a -= delta
        if abs(delta) < 1e-9:
            break
    lo_a, hi_a = float(conf.get("min_slope", 0.5)), float(conf.get("max_slope", 1.6))
    clamped = not lo_a <= a <= hi_a
    a = min(max(a, lo_a), hi_a)

    return {
        "enabled": True, "a": round(a, 4), "b": round(b, 4), "n": len(rows),
        "clamped": clamped, "games": games, "method": "symmetric temperature scaling",
        "reason": ("fit hit the safety clamps — check the Accuracy tab, something "
                   "upstream may be wrong" if clamped else
                   "fitted on unique verified pregame event/markets, passes included"),
        "interpretation": _describe(a, b),
    }


def _describe(a: float, b: float) -> str:
    bits = []
    if a < 0.95:
        bits.append("the model has been overconfident, so probabilities are being "
                    "pulled toward the middle")
    elif a > 1.05:
        bits.append("the model has been underconfident, so probabilities are being "
                    "pushed outward")
    else:
        bits.append("sharpness is about right")
    if b > 0.05:
        bits.append("and it has been leaning slightly too far against its own picks")
    elif b < -0.05:
        bits.append("and it has been leaning slightly too far toward its own picks")
    return ", ".join(bits) + "."


def apply(p: float, params: dict) -> float:
    """Calibrate one probability. A disabled or missing fit returns it unchanged."""
    if not params or not params.get("enabled"):
        return p
    return _sigmoid(float(params.get("a", 1.0)) * _logit(p))
