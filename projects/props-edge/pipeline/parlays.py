"""Target-payout NFL parlays built from candidate legs.

Three scopes are produced:

* **slate**   – anything on the board inside the lookahead window.
* **day**     – one set per game day.
* **game**    – same-game parlays (SGP), where legs from one game are allowed to
                correlate with each other.

For each scope the builder aims at fixed payout targets (+1000, +5000, …). It is
a search for the combination whose price lands closest to the target while the
model's own joint probability stays as high as possible, so a long-shot ticket is
still the *best* version of that long shot rather than a random pile of legs.
Reaching a big number always costs probability; that trade is shown on every card.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import math
import re
from typing import Any, Iterable

from .legs import PASS_CATCHER_MARKETS, market_group
from .schema import decimal_to_american


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _american(decimal: float) -> int:
    return decimal_to_american(max(1.0001, decimal))


def pair_correlation(a: dict[str, Any], b: dict[str, Any], cfg: dict[str, Any]) -> float:
    """How much two legs in the same game move together. 1.0 means independent."""
    if a.get("event_id") != b.get("event_id"):
        return 1.0
    same_team = _norm(a.get("team", "")) == _norm(b.get("team", "")) and a.get("team")
    a_over = a.get("side") in ("over", "yes")
    b_over = b.get("side") in ("over", "yes")
    groups = {market_group(a["market"]), market_group(b["market"])}
    if same_team and groups == {"passing", "receiving"} and a_over and b_over:
        return float(cfg["qb_to_pass_catcher"])
    if same_team and "touchdown" in groups and a_over and b_over:
        return float(cfg["qb_td_to_anytime"])
    if _norm(a.get("player", "")) == _norm(b.get("player", "")) and a_over == b_over:
        return float(cfg["same_player_stack"])
    if same_team and a["market"] == b["market"] and a_over and b_over:
        return float(cfg["same_team_same_market"])
    if not same_team and a_over and b_over:
        return float(cfg["shootout"])
    return 1.0


def joint_probability(legs: list[dict[str, Any]], cfg: dict[str, Any]) -> float:
    """Independent product, then a correlation adjustment for same-game pairs."""
    probability = 1.0
    for leg in legs:
        probability *= float(leg["model_prob"])
    factor = 1.0
    for i, a in enumerate(legs):
        for b in legs[i + 1 :]:
            factor *= pair_correlation(a, b, cfg)
    factor = max(1 / float(cfg["cap"]), min(float(cfg["cap"]), factor))
    return max(1e-9, min(0.97, probability * factor))


def _allowed(leg: dict[str, Any], chosen: list[dict[str, Any]], limits: dict[str, Any]) -> bool:
    if any(_norm(leg["player"]) == _norm(row["player"]) and leg["market"] == row["market"] for row in chosen):
        return False
    if any(
        _norm(leg["player"]) == _norm(row["player"]) and leg["side"] != row["side"] and leg["market"] == row["market"]
        for row in chosen
    ):
        return False
    per_player = sum(_norm(leg["player"]) == _norm(row["player"]) for row in chosen)
    if per_player >= int(limits.get("max_legs_per_player", 2)):
        return False
    per_game = sum(leg["event_id"] == row["event_id"] for row in chosen)
    if per_game >= int(limits["max_legs_per_game"]):
        return False
    per_market = sum(leg["market"] == row["market"] for row in chosen)
    if per_market >= int(limits.get("max_legs_per_market", 3)):
        return False
    return True


def _corr_log(leg: dict[str, Any], chosen: list[dict[str, Any]], cfg: dict[str, Any]) -> float:
    total = 0.0
    for row in chosen:
        factor = pair_correlation(leg, row, cfg)
        if factor != 1.0:
            # Each extra correlated pair counts a little less than the one before it.
            total += math.log(1 + (factor - 1) * 0.75)
    return total


def _search(
    pool: list[dict[str, Any]], target: float, settings: dict[str, Any], limits: dict[str, Any],
    tolerance: float | None = None,
) -> list[list[dict[str, Any]]]:
    """Beam search for leg sets whose combined price lands on the payout target."""
    cfg = settings["parlays"]
    corr = cfg["correlation"]
    tolerance = float(cfg["tolerance"]) if tolerance is None else float(tolerance)
    target_log = math.log(1 + target / 100)
    low, high = target_log + math.log(1 - tolerance), target_log + math.log(1 + tolerance)
    width = int(cfg["beam_width"])
    branch = int(cfg.get("branch", 10))
    max_legs = int(limits["max_legs"])
    min_legs = max(int(cfg["min_legs"]), int(limits.get("min_legs", 0)), int(cfg.get("min_legs_by_target", {}).get(str(int(target)), 0)))
    if not pool:
        return []
    best_leg_log = max(leg["_log_dec"] for leg in pool)
    beam: list[tuple[list[dict[str, Any]], float, float]] = [([], 0.0, 0.0)]  # legs, log price, log model prob
    finished: list[tuple[list[dict[str, Any]], float, float]] = []
    for depth in range(max_legs):
        remaining = max_legs - depth
        nxt: list[tuple[list[dict[str, Any]], float, float]] = []
        for chosen, log_dec, log_p in beam:
            added = 0
            for leg in pool:
                if added >= branch:
                    break
                combined = log_dec + leg["_log_dec"]
                if combined > high:
                    continue
                # Prune: the target has to still be reachable with the legs that are left.
                if combined + (remaining - 1) * best_leg_log < low:
                    continue
                if not _allowed(leg, chosen, limits):
                    continue
                added += 1
                legs = chosen + [leg]
                probability = log_p + leg["_log_p"] + _corr_log(leg, chosen, corr)
                if combined >= low and len(legs) >= min_legs:
                    finished.append((legs, combined, probability))
                    continue
                nxt.append((legs, combined, probability))
        if not nxt:
            break
        # Keep the partial tickets with the best model chance for the payout reached so far.
        nxt.sort(key=lambda item: -(item[2] + 0.35 * item[1]))
        beam = nxt[:width]
    cap = math.log(float(corr["cap"]))
    finished.sort(key=lambda item: -min(item[2], item[2] + cap))
    picked: list[list[dict[str, Any]]] = []
    used: list[frozenset[str]] = []
    for legs, _log_dec, _log_p in finished:
        signature = frozenset(leg["id"] for leg in legs)
        # Keep the alternatives genuinely different, not one leg swapped out.
        if any(len(signature & other) >= max(2, len(signature) - 1) for other in used):
            continue
        used.append(signature)
        picked.append(legs)
        if len(picked) >= int(cfg["per_target"]):
            break
    return picked


def _find(
    pool: list[dict[str, Any]], target: float, settings: dict[str, Any], limits: dict[str, Any]
) -> list[list[dict[str, Any]]]:
    """Try the normal tolerance first, then a wider one so a target is not silently skipped."""
    found = _search(pool, target, settings, limits)
    if found:
        return found
    return _search(pool, target, settings, limits, float(settings["parlays"]["tolerance"]) * 2)


def _ticket(
    legs: list[dict[str, Any]], scope: str, label: str, target: int, settings: dict[str, Any]
) -> dict[str, Any]:
    corr = settings["parlays"]["correlation"]
    decimal = 1.0
    for leg in legs:
        decimal *= float(leg["price_decimal"])
    probability = joint_probability(legs, corr)
    independent = 1.0
    for leg in legs:
        independent *= float(leg["model_prob"])
    american = _american(decimal)
    payout = round(10 * decimal, 2)
    estimated = any(leg["price_source"] == "model" for leg in legs)
    legs = [{key: value for key, value in leg.items() if not key.startswith("_")} for leg in legs]
    signature = hashlib.sha256("|".join(sorted(leg["id"] for leg in legs)).encode()).hexdigest()[:10]
    return {
        "id": f"{scope}-{target}-{signature}",
        "scope": scope,
        "label": label,
        "target": target,
        "legs": legs,
        "leg_count": len(legs),
        "price_decimal": round(decimal, 4),
        "price_american": american,
        "payout_on_10": payout,
        "model_prob": round(probability, 6),
        "independent_prob": round(independent, 6),
        "correlation_applied": round(probability / independent, 3) if independent else 1.0,
        "fair_american": _american(1 / probability),
        "expected_value_on_10": round(probability * payout - 10, 2),
        "one_in": round(1 / probability) if probability > 0 else None,
        "estimated_prices": estimated,
        "off_target": abs(decimal - (1 + target / 100)) > (1 + target / 100) * float(settings["parlays"]["tolerance"]),
        "games": sorted({leg["matchup"] for leg in legs}),
        "start_time": min((leg.get("start_time") or "" for leg in legs), default=""),
    }


def _pool(legs: Iterable[dict[str, Any]], settings: dict[str, Any]) -> list[dict[str, Any]]:
    """A price-diverse shortlist: a ticket needs short legs AND long legs to hit a target."""
    cfg = settings["legs"]
    buckets = [(-100000, -250), (-250, -150), (-150, -110), (-110, 110), (110, 200), (200, 400), (400, 900), (900, 100000)]
    graded: dict[int, list[dict[str, Any]]] = {index: [] for index in range(len(buckets))}
    for leg in legs:
        probability = float(leg["model_prob"])
        if not (float(cfg["min_model_prob"]) <= probability <= float(cfg["max_model_prob"])):
            continue
        price = float(leg["price_american"])
        for index, (low, high) in enumerate(buckets):
            if low <= price < high:
                row = dict(leg)
                row["_log_dec"] = math.log(float(leg["price_decimal"]))
                row["_log_p"] = math.log(probability)
                # Probability kept per unit of payout bought: the best legs to build on.
                row["_efficiency"] = row["_log_p"] / row["_log_dec"] if row["_log_dec"] > 0 else -99
                # Prefer the legs a bettor would actually take: a real sample behind
                # the number, and the skill-position markets books price deepest.
                samples = int(leg.get("samples") or 0)
                quality = min(0.10, 0.035 * max(0, samples - 1))
                quality += {"touchdown": 0.06, "receiving": 0.05, "rushing": 0.04, "passing": 0.04}.get(leg.get("group"), 0.0)
                row["_rank"] = row["_efficiency"] + quality
                graded[index].append(row)
                break
    pool: list[dict[str, Any]] = []
    for index in graded:
        rows = sorted(graded[index], key=lambda leg: (-(leg["price_source"] == "book"), -leg["_rank"]))
        pool.extend(rows[:40])
    return sorted(pool, key=lambda leg: (-(leg["price_source"] == "book"), -leg["_rank"]))


def build_parlays(legs: list[dict[str, Any]], settings: dict[str, Any], now: dt.datetime | None = None) -> dict[str, Any]:
    cfg = settings["parlays"]
    now = now or dt.datetime.now(dt.timezone.utc)
    upcoming = [leg for leg in legs if (leg.get("start_time") or "9999") > now.isoformat()]
    tickets: list[dict[str, Any]] = []

    slate_limits = {"max_legs": int(cfg["max_legs"]), "max_legs_per_game": int(cfg["max_legs_per_game"]), "max_legs_per_player": 1}
    seen_signatures: set[frozenset[str]] = set()

    def keep(ticket_legs: list[dict[str, Any]]) -> bool:
        signature = frozenset(leg["id"] for leg in ticket_legs)
        if signature in seen_signatures:
            return False
        seen_signatures.add(signature)
        return True
    pool = _pool(upcoming, settings)
    for target in cfg["targets"]:
        for ticket_legs in _find(pool, float(target), settings, slate_limits):
            if not keep(ticket_legs):
                continue
            tickets.append(_ticket(ticket_legs, "slate", "Full slate", int(target), settings))

    by_day: dict[str, list[dict[str, Any]]] = {}
    for leg in upcoming:
        day = str(leg.get("start_time") or "")[:10]
        if day:
            by_day.setdefault(day, []).append(leg)
    for day in sorted(by_day)[:4]:
        day_pool = _pool(by_day[day], settings)
        if len({leg["event_id"] for leg in day_pool}) < 2:
            continue
        for target in cfg["targets"]:
            for ticket_legs in _find(day_pool, float(target), settings, slate_limits):
                if not keep(ticket_legs):
                    continue
                tickets.append(_ticket(ticket_legs, "day", day, int(target), settings))

    sgp_limits = {
        "max_legs": int(cfg["sgp_max_legs"]),
        "max_legs_per_game": int(cfg["sgp_max_legs"]),
        "max_legs_per_player": 2,
        "min_legs": int(cfg["sgp_min_legs"]),
    }
    by_game: dict[str, list[dict[str, Any]]] = {}
    for leg in upcoming:
        by_game.setdefault(str(leg["event_id"]), []).append(leg)
    for event_id, rows in by_game.items():
        game_pool = _pool(rows, settings)
        if len(game_pool) < 3:
            continue
        label = rows[0].get("matchup") or event_id
        for target in cfg["sgp_targets"]:
            for ticket_legs in _find(game_pool, float(target), settings, sgp_limits):
                if not keep(ticket_legs):
                    continue
                tickets.append(_ticket(ticket_legs, "game", label, int(target), settings))

    tickets.sort(key=lambda ticket: (ticket["scope"], ticket["target"], -ticket["model_prob"]))
    return {
        "generated_at": now.isoformat(),
        "targets": list(cfg["targets"]),
        "counts": {
            scope: sum(ticket["scope"] == scope for ticket in tickets) for scope in ("slate", "day", "game")
        },
        "estimated_prices": any(ticket["estimated_prices"] for ticket in tickets),
        "tickets": tickets,
    }
