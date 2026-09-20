"""Candidate NFL prop legs: every leg the parlay builder is allowed to use.

A leg is either **priced** (a real sportsbook price came back from a provider) or
**model** (no book feed, so the price shown is derived from the model's own
probability plus a normal sportsbook hold). Model prices are estimates and are
labelled as such everywhere they are shown; they are never presented as a price
a book is currently offering.
"""
from __future__ import annotations

import math
import re
from typing import Any

from .schema import Projection, PropQuote, american_to_decimal, decimal_to_american

# Markets the model can price from ESPN box-score history, and how volatile they are.
COUNTING_MARKETS = {
    "Pass attempts": 1.0,
    "Pass completions": 1.0,
    "Rush attempts": 1.0,
    "Receptions": 1.0,
    "Targets": 1.0,
    "Field goals made": 1.0,
    "Extra points made": 1.0,
    "Kicking points": 1.0,
    "Tackles + assists": 1.0,
    "Sacks": 1.0,
}
YARDAGE_MARKETS = {
    "Passing yards": 1.0,
    "Rushing yards": 1.0,
    "Receiving yards": 1.0,
    "Longest pass": 1.0,
    "Longest rush": 1.0,
    "Longest reception": 1.0,
}
TOUCHDOWN_MARKETS = {"Anytime touchdown", "Passing touchdowns", "Rushing touchdowns", "Receiving touchdowns"}
GROUP = {
    **{m: "passing" for m in ("Passing yards", "Pass attempts", "Pass completions", "Passing touchdowns", "Pass interceptions", "Longest pass")},
    **{m: "rushing" for m in ("Rushing yards", "Rush attempts", "Rushing touchdowns", "Longest rush")},
    **{m: "receiving" for m in ("Receiving yards", "Receptions", "Targets", "Receiving touchdowns", "Longest reception")},
    **{m: "kicking" for m in ("Field goals made", "Extra points made", "Kicking points")},
    **{m: "defense" for m in ("Tackles + assists", "Sacks")},
    "Anytime touchdown": "touchdown",
}
PASS_CATCHER_MARKETS = {"Receiving yards", "Receptions", "Targets", "Receiving touchdowns", "Longest reception"}

# Sportsbooks only post a prop once a player's number is big enough to matter.
# Without these floors the board fills up with lines no book would offer
# ("under 0.5 tackles"), which would be useless on a real bet slip.
MARKET_RULES = {
    "Passing yards": {"min_line": 99.5, "min_projection": 120},
    "Pass attempts": {"min_line": 14.5, "min_projection": 18},
    "Pass completions": {"min_line": 9.5, "min_projection": 12},
    "Rushing yards": {"min_line": 9.5, "min_projection": 14},
    "Rush attempts": {"min_line": 3.5, "min_projection": 5},
    "Receiving yards": {"min_line": 9.5, "min_projection": 14},
    "Receptions": {"min_line": 1.5, "min_projection": 2.2},
    "Targets": {"min_line": 2.5, "min_projection": 3.2},
    "Longest pass": {"min_line": 19.5, "min_projection": 24},
    "Longest rush": {"min_line": 5.5, "min_projection": 8},
    "Longest reception": {"min_line": 9.5, "min_projection": 12},
    "Kicking points": {"min_line": 4.5, "min_projection": 5.5},
    "Field goals made": {"min_line": 0.5, "min_projection": 1.0},
    "Extra points made": {"min_line": 1.5, "min_projection": 2.0},
    "Tackles + assists": {"min_line": 2.5, "min_projection": 3.5},
    "Sacks": {"min_line": 0.5, "min_projection": 0.6},
    "Anytime touchdown": {"min_line": 0, "min_projection": 0.12},
}


def market_group(market: str) -> str:
    return GROUP.get(market, "other")


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _name_key(value: str) -> str:
    """First initial plus surname, so "Patrick Mahomes II" and "Patrick Mahomes" match."""
    parts = [part for part in re.split(r"[^A-Za-z]+", str(value or "")) if part]
    parts = [part for part in parts if part.casefold() not in {"jr", "sr", "ii", "iii", "iv", "v"}]
    if not parts:
        return ""
    return (parts[0][:1] + parts[-1]).casefold()


def _normal_cdf(value: float) -> float:
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def _half_point(value: float) -> float:
    """Sportsbook lines sit on a half point so a leg cannot push."""
    return math.floor(value) + 0.5 if value >= 1 else 0.5


def estimated_price(probability: float, hold: float) -> tuple[float, int]:
    """A fair price with a normal two-way hold applied, as a book would quote it."""
    priced = max(0.01, min(0.985, probability * (1 + hold)))
    decimal = max(1.02, 1 / priced)
    american = decimal_to_american(decimal)
    # Books quote in 5-cent steps either side of even money.
    american = int(5 * round(american / 5))
    if -100 < american < 100:
        american = 100 if american >= 0 else -100
    return american_to_decimal(american), american


def over_probability(projection: Projection, line: float) -> float:
    """Blend a normal model around the projection with how often the player actually cleared it."""
    recent = list(projection.recent or [])
    deviation = max(float(projection.standard_deviation), max(0.75, 0.22 * max(projection.projection, 1.0)))
    normal_over = 1 - _normal_cdf((line - projection.projection) / deviation)
    hits = sum(value > line for value in recent)
    empirical_over = (hits + 1) / (len(recent) + 2)
    raw = (normal_over + empirical_over) / 2
    confidence = max(0.25, min(0.75, float(projection.confidence)))
    # Shrink toward a coin flip: a short sample cannot claim a large edge.
    return 0.5 + (raw - 0.5) * (0.55 + 0.45 * confidence)


def touchdown_probability(projection: Projection) -> float:
    recent = list(projection.recent or [])
    hits = sum(value >= 1 for value in recent)
    empirical = (hits + 0.5) / (len(recent) + 2)
    poisson = 1 - math.exp(-max(0.0, float(projection.projection)))
    raw = (empirical + poisson) / 2
    confidence = max(0.2, min(0.72, float(projection.confidence)))
    return max(0.03, min(0.86, 0.2 + (raw - 0.2) * (0.6 + 0.4 * confidence)))


def _reason(projection: Projection, market: str, side: str, line: float, probability: float) -> str:
    recent = [round(value, 1) for value in (projection.recent or [])]
    games = len(recent)
    average = sum(recent) / games if games else projection.projection
    best = max(recent) if recent else projection.projection
    if market == "Anytime touchdown":
        scored = sum(value >= 1 for value in (projection.recent or []))
        return (
            f"Projected {projection.projection:.2f} touchdowns; found the end zone in "
            f"{scored} of his last {games} game{'' if games == 1 else 's'}."
        )
    cleared = sum((value > line) if side == "over" else (value < line) for value in (projection.recent or []))
    trend = "trending up" if projection.trend > 0.5 else "trending down" if projection.trend < -0.5 else "steady"
    return (
        f"Averaging {average:.1f} over his last {games} game{'' if games == 1 else 's'} (best {best:.1f}); "
        f"model projects {projection.projection:.1f} and he went {'over' if side == 'over' else 'under'} "
        f"{line:g} in {cleared} of {games} — usage {trend}."
    )


def _leg(**fields: Any) -> dict[str, Any]:
    leg = dict(fields)
    leg["id"] = "-".join(
        str(leg.get(key, "")) for key in ("event_id", "player", "market", "side", "line")
    ).replace(" ", "_").casefold()
    leg["group"] = market_group(str(leg["market"]))
    return leg


def legs_from_projections(
    projections: list[Projection], settings: dict[str, Any], priced_keys: set[tuple[str, str, str]] | None = None
) -> list[dict[str, Any]]:
    cfg = settings["legs"]
    hold = float(cfg["hold_per_side"])
    low, high = float(cfg["min_model_prob"]), float(cfg["max_model_prob"])
    out: list[dict[str, Any]] = []
    for projection in projections:
        if projection.sport != "NFL":
            continue
        if int(projection.samples) < int(cfg["min_samples"]):
            continue
        market = projection.market
        if priced_keys and (projection.sport, _norm(projection.player), _norm(market)) in priced_keys:
            continue
        candidates: list[tuple[str, float, float]] = []  # side, line, probability
        rules = MARKET_RULES.get(market)
        if rules is None or float(projection.projection) < float(rules["min_projection"]):
            continue
        if market == "Anytime touchdown":
            probability = touchdown_probability(projection)
            if probability >= float(cfg["anytime_td_min_prob"]):
                candidates.append(("yes", 0.5, probability))
        elif market in YARDAGE_MARKETS or market in COUNTING_MARKETS:
            if projection.projection < float(rules["min_projection"]):
                continue
            for offset in cfg["line_offsets"]:
                line = _half_point(projection.projection * (1 + float(offset)))
                if line < float(rules["min_line"]):
                    continue
                probability = over_probability(projection, line)
                candidates.append(("over", line, probability))
                candidates.append(("under", line, 1 - probability))
        else:
            continue
        seen: set[tuple[str, float]] = set()
        kept = 0
        for side, line, probability in sorted(candidates, key=lambda row: -row[2]):
            if (side, line) in seen or not (low <= probability <= high):
                continue
            seen.add((side, line))
            if kept >= int(cfg["max_per_player"]):
                break
            kept += 1
            decimal, american = estimated_price(probability, hold)
            pick = (
                f"{projection.player} anytime touchdown"
                if market == "Anytime touchdown"
                else f"{projection.player} {side} {line:g} {market.casefold()}"
            )
            out.append(
                _leg(
                    sport="NFL",
                    event_id=str(projection.start_time or "") + "|" + _norm(projection.matchup),
                    matchup=projection.matchup,
                    start_time=projection.start_time,
                    player=projection.player,
                    team=projection.team,
                    market=market,
                    side=side,
                    line=None if market == "Anytime touchdown" else line,
                    pick=pick,
                    price_american=american,
                    price_decimal=round(decimal, 4),
                    price_source="model",
                    book="Model estimate",
                    model_prob=round(probability, 4),
                    fair_american=decimal_to_american(1 / probability),
                    edge=None,
                    samples=int(projection.samples),
                    projection=round(float(projection.projection), 2),
                    recent=[round(float(value), 1) for value in (projection.recent or [])],
                    confidence=round(float(projection.confidence), 2),
                    reason=_reason(projection, market, side, line, probability),
                )
            )
    return sorted(out, key=lambda row: (-row["model_prob"], row["player"]))


def legs_from_lines(
    lines: list[dict[str, Any]], projections: list[Projection], settings: dict[str, Any]
) -> list[dict[str, Any]]:
    """Score the sportsbook's own line with the model. The number is real; the price is still an estimate."""
    cfg = settings["legs"]
    hold = float(cfg["hold_per_side"])
    low, high = float(cfg["min_model_prob"]), float(cfg["max_model_prob"])
    usable = [
        row for row in projections
        if row.sport == "NFL" and int(row.samples) >= int(cfg["min_samples"])
    ]
    index = {(_norm(row.player), _norm(row.market)): row for row in usable}
    loose = {(_name_key(row.player), _norm(row.market)): row for row in usable}
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, Any]] = set()
    for row in lines:
        market = str(row.get("market") or "")
        projection = index.get((_norm(str(row.get("player"))), _norm(market))) or loose.get(
            (_name_key(str(row.get("player"))), _norm(market))
        )
        if projection is None:
            continue
        line = row.get("line")
        sides: list[tuple[str, float]] = []
        if market == "Anytime touchdown":
            sides.append(("yes", touchdown_probability(projection)))
        elif line is not None:
            over = over_probability(projection, float(line))
            sides.append(("over", over))
            sides.append(("under", 1 - over))
        for side, probability in sides:
            key = (str(row.get("event_id")), _norm(str(row.get("player"))), market + side, line)
            if key in seen or not (low <= probability <= high):
                continue
            seen.add(key)
            decimal, american = estimated_price(probability, hold)
            pick = (
                f"{row['player']} anytime touchdown"
                if market == "Anytime touchdown"
                else f"{row['player']} {side} {float(line):g} {market.casefold()}"
            )
            reason = _reason(projection, market, side, float(line or 0), probability)
            out.append(
                _leg(
                    sport="NFL",
                    event_id=str(row.get("event_id") or ""),
                    matchup=projection.matchup or row.get("matchup") or "",
                    start_time=row.get("start_time") or projection.start_time,
                    player=row["player"],
                    team=row.get("team") or projection.team,
                    market=market,
                    side=side,
                    line=None if market == "Anytime touchdown" else float(line),
                    pick=pick,
                    price_american=american,
                    price_decimal=round(decimal, 4),
                    price_source="model",
                    line_source=row.get("line_source") or "Sportsbook line",
                    book=f"{row.get('book', 'DraftKings')} line · model price",
                    model_prob=round(probability, 4),
                    fair_american=decimal_to_american(1 / probability),
                    edge=None,
                    samples=int(projection.samples),
                    projection=round(float(projection.projection), 2),
                    recent=[round(float(value), 1) for value in (projection.recent or [])],
                    confidence=round(float(projection.confidence), 2),
                    reason=(
                        f"{row.get('book', 'DraftKings')} posts {float(line):g}. " + reason
                        if line is not None
                        else reason
                    ),
                )
            )
    return sorted(out, key=lambda leg: (-leg["model_prob"], leg["player"]))


def legs_from_board(board: list[dict[str, Any]], settings: dict[str, Any]) -> list[dict[str, Any]]:
    """Real sportsbook prices become legs directly, keeping the board's model numbers."""
    cfg = settings["legs"]
    low, high = float(cfg["min_model_prob"]), float(cfg["max_model_prob"])
    out: list[dict[str, Any]] = []
    for row in board:
        if row.get("sport") != "NFL":
            continue
        probability = row.get("model_prob")
        if probability is None or not (low <= float(probability) <= high):
            continue
        out.append(
            _leg(
                sport="NFL",
                event_id=str(row.get("event_id") or ""),
                matchup=row.get("matchup") or "",
                start_time=row.get("start_time") or "",
                player=row.get("player") or "",
                team=row.get("team") or "",
                market=row.get("market") or "",
                side=row.get("side") or "",
                line=row.get("line"),
                pick=row.get("pick") or "",
                price_american=int(row.get("price_american")),
                price_decimal=float(row.get("price_decimal")),
                price_source="book",
                book=row.get("book") or "",
                model_prob=round(float(probability), 4),
                fair_american=decimal_to_american(1 / float(probability)),
                edge=row.get("edge"),
                samples=int(row.get("projection_samples") or 0),
                projection=row.get("projection"),
                recent=[],
                confidence=row.get("confidence"),
                tier=row.get("tier"),
                reason=(
                    f"{row.get('book')} price {row.get('price_american')} versus a model probability of "
                    f"{round(float(probability) * 100)}%."
                ),
            )
        )
    return sorted(out, key=lambda row: (-(row.get("edge") or 0), -row["model_prob"]))


def build_legs(
    board: list[dict[str, Any]],
    projections: list[Projection],
    settings: dict[str, Any],
    lines: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Priced legs first, then the book's own lines, then the model's own lines."""
    priced = legs_from_board(board, settings)
    covered = {("NFL", _norm(row["player"]), _norm(row["market"])) for row in priced}
    booked = [
        leg for leg in legs_from_lines(lines or [], projections, settings)
        if ("NFL", _norm(leg["player"]), _norm(leg["market"])) not in covered
    ]
    covered |= {("NFL", _norm(leg["player"]), _norm(leg["market"])) for leg in booked}
    modelled = legs_from_projections(projections, settings, covered)
    return priced + booked + modelled
