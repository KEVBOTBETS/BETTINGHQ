"""WNBA ratings, projections, pricing and portfolio allocation.

Every displayed number is produced here from live season results and live
prices. There is no sample fallback and no forced-play branch.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import NormalDist

import numpy as np


TEAM_COORDS = {
    "ATL": (33.7573, -84.3963), "CHI": (41.8807, -87.6742),
    "CON": (41.4910, -72.0908), "DAL": (32.7473, -97.0945),
    "GS": (37.7680, -122.3877), "IND": (39.7640, -86.1555),
    "LA": (34.0430, -118.2673), "LV": (36.1029, -115.1784),
    "MIN": (44.9795, -93.2760), "NY": (40.6826, -73.9754),
    "PHX": (33.4457, -112.0712), "POR": (45.5316, -122.6668),
    "SEA": (47.6221, -122.3540), "TOR": (43.6435, -79.3791),
    "WSH": (38.8469, -76.9910),
}


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def american_to_decimal(price: float) -> float:
    return 1.0 + (price / 100.0 if price > 0 else 100.0 / -price)


def american_to_prob(price: float) -> float:
    return 100.0 / (price + 100.0) if price > 0 else -price / (-price + 100.0)


def price_ok(price) -> bool:
    """True only for a usable American price from a real market."""
    try:
        value = float(price)
    except (TypeError, ValueError):
        return False
    return math.isfinite(value) and 100.0 <= abs(value) <= 5000.0


def prob_to_american(prob: float) -> int:
    p = min(max(prob, 0.001), 0.999)
    value = -100.0 * p / (1.0 - p) if p >= 0.5 else 100.0 * (1.0 - p) / p
    return int(round(value))


def devig(price_a: float, price_b: float) -> tuple[float | None, float | None]:
    """Remove a two-way hold with the same power method used by MLB Edge."""
    if not price_ok(price_a) or not price_ok(price_b):
        return None, None
    a, b = american_to_prob(float(price_a)), american_to_prob(float(price_b))
    lo, hi = 0.5, 2.0
    for _ in range(60):
        exponent = (lo + hi) / 2.0
        if a ** exponent + b ** exponent > 1.0:
            lo = exponent
        else:
            hi = exponent
    exponent = (lo + hi) / 2.0
    fair_a, fair_b = a ** exponent, b ** exponent
    total = fair_a + fair_b
    return fair_a / total, fair_b / total


def kelly_fraction(prob: float, price: float) -> float:
    b = american_to_decimal(price) - 1.0
    if b <= 0:
        return 0.0
    return max(0.0, (prob * b - (1.0 - prob)) / b)


def solve_ratings(history: list[dict], cfg: dict) -> dict[str, float]:
    """Ridge solve schedule-adjusted team strength from completed margins."""
    teams = sorted({game[side]["abbr"] for game in history for side in ("away", "home")})
    if not teams:
        return {}
    index = {team: i for i, team in enumerate(teams)}
    rows, targets = [], []
    hca = float(cfg["model"]["home_court_points"])
    cap = float(cfg["model"]["rating_mov_cap"])
    for game in history:
        away_score = game["away"].get("score")
        home_score = game["home"].get("score")
        if away_score is None or home_score is None:
            continue
        row = np.zeros(len(teams), dtype=float)
        row[index[game["home"]["abbr"]]] = 1.0
        row[index[game["away"]["abbr"]]] = -1.0
        rows.append(row)
        targets.append(max(-cap, min(cap, float(home_score) - float(away_score))) - hca)
    if not rows:
        return {team: 0.0 for team in teams}
    matrix = np.vstack(rows)
    ridge = float(cfg["model"]["rating_ridge"])
    lhs = matrix.T @ matrix + ridge * np.eye(len(teams))
    values = np.linalg.solve(lhs, matrix.T @ np.asarray(targets))
    values -= values.mean()
    return {team: round(float(values[index[team]]), 3) for team in teams}


def _tip(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _avg(values: list[float], fallback: float) -> float:
    return sum(values) / len(values) if values else fallback


def _weighted(values: list[float], fallback: float, decay: float = 0.88) -> float:
    if not values:
        return fallback
    weights = [decay ** (len(values) - 1 - idx) for idx in range(len(values))]
    return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)


def _shrink(value: float, league: float, games: int, prior_games: float = 8.0) -> float:
    weight = games / (games + prior_games) if games else 0.0
    return league + weight * (value - league)


def _haversine(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float:
    if not a or not b:
        return 0.0
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def _box_line(game: dict, team: str) -> dict | None:
    side = "home" if game["home"]["abbr"] == team else "away"
    stats = game[side].get("stats") or {}
    opp_stats = game["away" if side == "home" else "home"].get("stats") or {}
    mine, theirs = game[side].get("score"), game["away" if side == "home" else "home"].get("score")
    if mine is None or theirs is None:
        return None
    fga, fta = stats.get("fieldGoalsAttempted"), stats.get("freeThrowsAttempted")
    opp_fga, opp_fta = opp_stats.get("fieldGoalsAttempted"), opp_stats.get("freeThrowsAttempted")
    shot_poss = float(fga) + 0.44 * float(fta) if fga is not None and fta is not None else None
    opp_shot_poss = float(opp_fga) + 0.44 * float(opp_fta) if opp_fga is not None and opp_fta is not None else None
    fgm, threes = stats.get("fieldGoalsMade"), stats.get("threePointFieldGoalsMade")
    opp_fgm, opp_threes = opp_stats.get("fieldGoalsMade"), opp_stats.get("threePointFieldGoalsMade")
    return {
        "scored": float(mine), "allowed": float(theirs), "margin": float(mine) - float(theirs),
        "home": side == "home", "shot_poss": shot_poss, "opp_shot_poss": opp_shot_poss,
        "off_eff": float(mine) / shot_poss * 100 if shot_poss else None,
        "def_eff": float(theirs) / opp_shot_poss * 100 if opp_shot_poss else None,
        "pace": (shot_poss + opp_shot_poss) / 2 if shot_poss and opp_shot_poss else None,
        "efg": (float(fgm) + 0.5 * float(threes)) / float(fga) if fga and fgm is not None and threes is not None else None,
        "opp_efg": (float(opp_fgm) + 0.5 * float(opp_threes)) / float(opp_fga) if opp_fga and opp_fgm is not None and opp_threes is not None else None,
        "three_rate": float(stats.get("threePointFieldGoalsAttempted")) / float(fga) if fga and stats.get("threePointFieldGoalsAttempted") is not None else None,
        "ft_rate": float(fta) / float(fga) if fga and fta is not None else None,
        "rebound_share": (float(stats.get("rebounds")) / (float(stats.get("rebounds")) + float(opp_stats.get("rebounds")))) if stats.get("rebounds") is not None and opp_stats.get("rebounds") is not None and float(stats.get("rebounds")) + float(opp_stats.get("rebounds")) else None,
        "assist_rate": float(stats.get("assists")) / float(fgm) if fgm and stats.get("assists") is not None else None,
    }


def _league_baseline(history: list[dict]) -> dict[str, float]:
    lines = [_box_line(game, side) for game in history for side in (game["away"]["abbr"], game["home"]["abbr"])]
    rows = [line for line in lines if line]
    def mean(key: str, fallback: float) -> float:
        return _avg([float(row[key]) for row in rows if row.get(key) is not None], fallback)
    return {
        "points": mean("scored", 82.0), "efficiency": mean("off_eff", 103.0),
        "pace": mean("pace", 79.0), "efg": mean("efg", 0.50),
        "three_rate": mean("three_rate", 0.34), "ft_rate": mean("ft_rate", 0.27),
        "rebound_share": 0.50, "assist_rate": mean("assist_rate", 0.62),
    }


def team_profile(team: str, history: list[dict], next_tipoff: str, ratings: dict[str, float],
                 venue_team: str | None = None) -> dict:
    games = sorted((game for game in history if team in {game["away"]["abbr"], game["home"]["abbr"]}), key=lambda game: game["tipoff"])
    league = _league_baseline(history)
    rows = [row for row in (_box_line(game, team) for game in games) if row]
    scored = [row["scored"] for row in rows]
    allowed = [row["allowed"] for row in rows]
    margins = [row["margin"] for row in rows]
    n = len(rows)
    recent = rows[-8:]
    def metric(key: str, fallback: float, prior: float = 8.0) -> float:
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        return _shrink(_avg(values, fallback), fallback, len(values), prior)
    home_margins = [row["margin"] for row in rows if row["home"]]
    road_margins = [row["margin"] for row in rows if not row["home"]]
    next_time = _tip(next_tipoff)
    last_time = _tip(games[-1]["tipoff"]) if games else None
    rest_days = max(0.0, (next_time - last_time).total_seconds() / 86400.0) if last_time else 2.0
    games_last4 = sum(0 < (next_time - _tip(game["tipoff"])).total_seconds() <= 4 * 86400 for game in games)
    games_last6 = sum(0 < (next_time - _tip(game["tipoff"])).total_seconds() <= 6 * 86400 for game in games)
    destination = TEAM_COORDS.get(venue_team or team)
    previous_venue = TEAM_COORDS.get(games[-1]["home"]["abbr"]) if games else None
    travel_miles = _haversine(previous_venue, destination)
    back_to_back = rest_days < 1.55
    fatigue = (0.70 if back_to_back else 0.0) + (0.35 if games_last4 >= 2 else 0.0) + (0.45 if games_last6 >= 3 else 0.0)
    if rest_days <= 2.25:
        fatigue += min(0.75, travel_miles / 1000.0 * 0.20)
    season_margin = _avg(margins, 0.0)
    recent_margin = _weighted([row["margin"] for row in recent], season_margin)
    classic_recent = rows[-10:]
    return {
        "team": team, "games": n, "boxscore_games": sum(row.get("pace") is not None for row in rows),
        "raw_ppg": round(_avg(scored, league["points"]), 3),
        "raw_papg": round(_avg(allowed, league["points"]), 3),
        "classic_l10_ppg": round(_avg([row["scored"] for row in classic_recent], league["points"]), 3),
        "classic_l10_papg": round(_avg([row["allowed"] for row in classic_recent], league["points"]), 3),
        "classic_l10_pct": round(sum(row["margin"] > 0 for row in classic_recent) / len(classic_recent), 4) if classic_recent else 0.5,
        "classic_home_pct": round(sum(row["margin"] > 0 for row in rows if row["home"]) / len(home_margins), 4) if home_margins else 0.5,
        "classic_road_pct": round(sum(row["margin"] > 0 for row in rows if not row["home"]) / len(road_margins), 4) if road_margins else 0.5,
        "ppg": round(_shrink(_avg(scored, league["points"]), league["points"], n), 2),
        "papg": round(_shrink(_avg(allowed, league["points"]), league["points"], n), 2),
        "l10_ppg": round(_weighted([row["scored"] for row in recent], league["points"]), 2),
        "l10_papg": round(_weighted([row["allowed"] for row in recent], league["points"]), 2),
        "win_pct": round(sum(s > a for s, a in zip(scored, allowed)) / n, 4) if n else 0.5,
        "l10_pct": round(sum(row["margin"] > 0 for row in recent) / len(recent), 4) if recent else 0.5,
        "home_pct": round(sum(row["margin"] > 0 for row in rows if row["home"]) / len(home_margins), 4) if home_margins else 0.5,
        "road_pct": round(sum(row["margin"] > 0 for row in rows if not row["home"]) / len(road_margins), 4) if road_margins else 0.5,
        "home_net": round(_shrink(_avg(home_margins, 0.0), 0.0, len(home_margins), 6.0), 3),
        "road_net": round(_shrink(_avg(road_margins, 0.0), 0.0, len(road_margins), 6.0), 3),
        "recent_net": round(recent_margin - season_margin, 3),
        "off_eff": round(metric("off_eff", league["efficiency"]), 3),
        "def_eff": round(metric("def_eff", league["efficiency"]), 3),
        "pace": round(metric("pace", league["pace"], 10.0), 3),
        "efg": round(metric("efg", league["efg"]), 4),
        "opp_efg": round(metric("opp_efg", league["efg"]), 4),
        "three_rate": round(metric("three_rate", league["three_rate"]), 4),
        "ft_rate": round(metric("ft_rate", league["ft_rate"]), 4),
        "rebound_share": round(metric("rebound_share", 0.5), 4),
        "assist_rate": round(metric("assist_rate", league["assist_rate"]), 4),
        "league_eff": round(league["efficiency"], 3), "league_pace": round(league["pace"], 3),
        "league_efg": round(league["efg"], 4), "league_three_rate": round(league["three_rate"], 4),
        "rest_days": round(rest_days, 2), "back_to_back": back_to_back,
        "games_last4": games_last4, "games_last6": games_last6,
        "travel_miles": round(travel_miles), "fatigue_points": round(fatigue, 3),
        "power_rating": float(ratings.get(team, 0.0)),
    }


def _injury(team: str, injuries: dict[str, dict]) -> dict:
    return injuries.get(team) or {"team": team, "points": 0.0, "uncertain": False, "uncertain_points": 0.0, "players": []}


def project_game(game: dict, away: dict, home: dict, injuries: dict[str, dict], cfg: dict,
                 context: dict | None = None, calibration: dict | None = None) -> dict:
    """Project home-minus-away margin and total with every adjustment visible."""
    m = cfg["model"]
    context, calibration = context or {}, calibration or {}
    away_team, home_team = game["away"]["abbr"], game["home"]["abbr"]
    away_injury, home_injury = _injury(away_team, injuries), _injury(home_team, injuries)
    league_eff = (float(away.get("league_eff", 103.0)) + float(home.get("league_eff", 103.0))) / 2.0
    pace = (float(away.get("pace", 79.0)) + float(home.get("pace", 79.0))) / 2.0
    away_eff = league_eff + 0.56 * (float(away.get("off_eff", league_eff)) - league_eff) + 0.44 * (float(home.get("def_eff", league_eff)) - league_eff)
    home_eff = league_eff + 0.56 * (float(home.get("off_eff", league_eff)) - league_eff) + 0.44 * (float(away.get("def_eff", league_eff)) - league_eff)
    away_eff_score, home_eff_score = pace * away_eff / 100.0, pace * home_eff / 100.0
    away_points_score = (float(away["ppg"]) + float(home["papg"])) / 2.0
    home_points_score = (float(home["ppg"]) + float(away["papg"])) / 2.0
    classic_away_score = (float(away.get("raw_ppg", away["ppg"])) + float(home.get("raw_papg", home["papg"]))) / 2.0
    classic_home_score = (float(home.get("raw_ppg", home["ppg"])) + float(away.get("raw_papg", away["papg"]))) / 2.0
    live_stats = context.get("team_stats") or {}
    def live_score(offense: str, defense: str, fallback: float) -> float:
        off, defend = live_stats.get(offense) or {}, live_stats.get(defense) or {}
        values = [value for value in (off.get("avgPoints"), defend.get("avgPointsAgainst")) if value is not None]
        return _avg([float(value) for value in values], fallback)
    away_base = 0.58 * away_eff_score + 0.27 * away_points_score + 0.15 * live_score(away_team, home_team, away_points_score)
    home_base = 0.58 * home_eff_score + 0.27 * home_points_score + 0.15 * live_score(home_team, away_team, home_points_score)
    raw_base_margin = home_base - away_base
    power_adj = ((float(home["power_rating"]) - float(away["power_rating"]))
                 * float(m["power_rating_weight"]))
    split_raw = (float(home.get("home_net", 0.0)) - float(away.get("road_net", 0.0))) * float(m["split_weight"])
    split_adj = max(-float(m["max_split_adjustment"]), min(float(m["max_split_adjustment"]), split_raw))
    form_raw = (float(home.get("recent_net", 0.0)) - float(away.get("recent_net", 0.0))) * float(m["recent_form_weight"])
    form_adj = max(-float(m["max_form_adjustment"]), min(float(m["max_form_adjustment"]), form_raw))
    schedule_adj = float(away.get("fatigue_points", 0.0)) - float(home.get("fatigue_points", 0.0))
    rebound_adj = (float(home.get("rebound_share", 0.5)) - float(away.get("rebound_share", 0.5))) * float(m["rebound_scale"])
    ft_adj = (float(home.get("ft_rate", 0.27)) - float(away.get("ft_rate", 0.27))) * float(m["free_throw_scale"])
    away_tov = (live_stats.get(away_team) or {}).get("avgTeamTurnovers")
    home_tov = (live_stats.get(home_team) or {}).get("avgTeamTurnovers")
    turnover_adj = ((float(away_tov) - float(home_tov)) * float(m["turnover_weight"])) if away_tov is not None and home_tov is not None else 0.0
    possession_adj = max(-float(m["max_matchup_adjustment"]), min(float(m["max_matchup_adjustment"]), rebound_adj + ft_adj + turnover_adj))
    injury_adj = ((float(away_injury["points"]) - float(home_injury["points"]))
                  * float(m["injury_weight"]))
    home_court = float(m["home_court_points"])
    classic_base_margin = classic_home_score - classic_away_score
    classic_power = (float(home["power_rating"]) - float(away["power_rating"])) * float(m["classic_power_weight"])
    classic_split = ((float(home.get("classic_home_pct", home.get("home_pct", 0.5))) - float(away.get("classic_road_pct", away.get("road_pct", 0.5))))
                     * float(m["classic_split_scale"]) * float(m["classic_split_weight"]))
    classic_form = ((float(home.get("classic_l10_pct", home.get("l10_pct", 0.5))) - float(away.get("classic_l10_pct", away.get("l10_pct", 0.5))))
                    * float(m["classic_form_scale"]) * float(m["classic_form_weight"]))
    classic_rest_raw = (float(home.get("rest_days", 2.0)) - float(away.get("rest_days", 2.0))) * float(m["classic_rest_points_per_day"])
    classic_rest_cap = float(m["classic_max_rest_adjustment"])
    classic_rest = max(-classic_rest_cap, min(classic_rest_cap, classic_rest_raw))
    efficiency_weight = float(m["efficiency_blend"])
    base_component = (1.0 - efficiency_weight) * classic_base_margin + efficiency_weight * raw_base_margin
    power_component = (1.0 - efficiency_weight) * classic_power + efficiency_weight * power_adj
    split_component = (1.0 - efficiency_weight) * classic_split + efficiency_weight * split_adj
    form_component = (1.0 - efficiency_weight) * classic_form + efficiency_weight * form_adj
    schedule_component = (1.0 - efficiency_weight) * classic_rest + efficiency_weight * schedule_adj
    possession_component = efficiency_weight * possession_adj
    pre_prior_margin = base_component + power_component + split_component + form_component + schedule_component + possession_component + injury_adj + home_court
    predictor = context.get("predictor") or {}
    predictor_prob = predictor.get("home_prob")
    predictor_adj = 0.0
    if predictor_prob is not None:
        p = min(0.88, max(0.12, float(predictor_prob)))
        predictor_margin = NormalDist().inv_cdf(p) * float(m.get("spread_sigma", 12.0))
        predictor_adj = max(-float(m["max_predictor_adjustment"]), min(float(m["max_predictor_adjustment"]), (predictor_margin - pre_prior_margin) * float(m["predictor_weight"])))
    calibration_margin = max(-2.0, min(2.0, float(calibration.get("margin_bias") or 0.0)))
    raw_margin = pre_prior_margin + predictor_adj + calibration_margin

    recent_total = (float(away["l10_ppg"]) + float(home["l10_ppg"])
                    + float(away["l10_papg"]) + float(home["l10_papg"])) / 2.0
    season_total = away_base + home_base
    classic_recent_total = (float(away.get("classic_l10_ppg", away["l10_ppg"])) + float(home.get("classic_l10_ppg", home["l10_ppg"]))
                            + float(away.get("classic_l10_papg", away["l10_papg"])) + float(home.get("classic_l10_papg", home["l10_papg"]))) / 2.0
    classic_season_total = classic_away_score + classic_home_score
    injury_total = (float(away_injury["points"]) + float(home_injury["points"])) * float(m["injury_total_weight"])
    efficiency_total = away_eff_score + home_eff_score
    rich_total = 0.58 * efficiency_total + 0.27 * season_total + 0.15 * recent_total
    classic_total = 0.65 * classic_season_total + 0.35 * classic_recent_total
    total_efficiency_weight = float(m.get("total_efficiency_blend", 0.0))
    calibration_total = max(-3.0, min(3.0, float(calibration.get("total_bias") or 0.0)))
    raw_total = (1.0 - total_efficiency_weight) * classic_total + total_efficiency_weight * rich_total - injury_total + calibration_total

    quotes = ((game.get("odds") or {}).get("quotes") or {})
    home_spread = (quotes.get("home_spread") or {}).get("line")
    market_total = (quotes.get("over") or quotes.get("under") or {}).get("line")
    anchored = home_spread is not None
    if anchored:
        market_margin = -float(home_spread)
        raw_gap = raw_margin - market_margin
        max_gap = float(m["max_spread_disagreement"])
        kept_gap = max_gap * math.tanh(raw_gap / max_gap)
        margin = market_margin + float(m["projection_blend"]) * kept_gap
    else:
        market_margin, raw_gap, kept_gap, margin = None, None, None, raw_margin
    if market_total is not None:
        raw_total_gap = raw_total - float(market_total)
        max_total_gap = float(m["max_total_disagreement"])
        kept_total_gap = max_total_gap * math.tanh(raw_total_gap / max_total_gap)
        total = float(market_total) + float(m["total_blend"]) * kept_total_gap
    else:
        raw_total_gap, kept_total_gap, total = None, None, raw_total

    min_games = min(int(away["games"]), int(home["games"]))
    box_coverage = min(float(away.get("boxscore_games", 0)) / max(1, int(away["games"])), float(home.get("boxscore_games", 0)) / max(1, int(home["games"])))
    unresolved = float(away_injury.get("uncertain_points", 0.0)) + float(home_injury.get("uncertain_points", 0.0))
    confidence = 0.58 + 0.19 * min(1.0, min_games / float(m["min_games_for_full_confidence"])) + 0.08 * box_coverage
    confidence += 0.04 if anchored else 0.0
    if raw_gap is not None:
        confidence -= min(0.08, max(0.0, abs(float(raw_gap)) - 2.0) * 0.012)
    confidence -= min(0.12, unresolved * float(cfg["injuries"]["uncertainty_confidence_penalty_per_point"]))
    confidence = min(0.90, max(0.50, confidence))
    three_volatility = max(0.0, (float(away.get("three_rate", 0.34)) + float(home.get("three_rate", 0.34))) / 2.0 - float(away.get("league_three_rate", 0.34)))
    spread_sigma = max(float(m["spread_sigma"]), float(calibration.get("spread_sigma") or 0.0)) + min(0.8, three_volatility * 8.0) + min(0.6, unresolved * 0.15)
    total_sigma = max(float(m["total_sigma"]), float(calibration.get("total_sigma") or 0.0)) + min(1.0, three_volatility * 10.0)

    factors = [
        {"name": "Opponent-adjusted scoring", "points": round(base_component, 2), "note": f'points baseline plus {efficiency_weight*100:.0f}% pace/efficiency check ({pace:.1f} pace)'},
        {"name": "Schedule-adjusted power", "points": round(power_component, 2), "note": "ridge rating from completed margins, regressed"},
        {"name": "Home court", "points": round(home_court, 2), "note": "configured WNBA home-court value"},
        {"name": "Home/road scoring split", "points": round(split_component, 2), "note": "venue results with sample-size shrinkage"},
        {"name": "Recent form", "points": round(form_component, 2), "note": "last-ten results with a small recency-weighted check"},
        {"name": "Rest, travel + schedule load", "points": round(schedule_component, 2), "note": f'{away_team}: {int(away.get("games_last4", 0)) + 1} in 4 / {float(away.get("travel_miles", 0)):.0f} mi; {home_team}: {int(home.get("games_last4", 0)) + 1} in 4'},
        {"name": "Possession matchup", "points": round(possession_component, 2), "note": "rebounding, free-throw pressure and live turnover profile"},
        {"name": "Player availability", "points": round(injury_adj, 2), "note": "role-weighted; administrative absences are excluded"},
        {"name": "ESPN matchup prior", "points": round(predictor_adj, 2), "note": "small capped independent prior when published"},
        {"name": "Walk-forward calibration", "points": round(calibration_margin, 2), "note": f'{int(calibration.get("n") or 0)} prior games; future results excluded'},
    ]
    return {
        "raw_margin": round(raw_margin, 2),
        "margin": round(margin, 2),
        "market_margin": round(market_margin, 2) if market_margin is not None else None,
        "raw_line_gap": round(raw_gap, 2) if raw_gap is not None else None,
        "line_gap": round(margin - market_margin, 2) if market_margin is not None else None,
        "kept_line_gap": round(kept_gap, 2) if kept_gap is not None else None,
        "raw_total": round(raw_total, 2),
        "total": round(total, 2),
        "market_total": round(float(market_total), 2) if market_total is not None else None,
        "raw_total_gap": round(raw_total_gap, 2) if raw_total_gap is not None else None,
        "kept_total_gap": round(kept_total_gap, 2) if kept_total_gap is not None else None,
        "away_score": round((total - margin) / 2.0, 1),
        "home_score": round((total + margin) / 2.0, 1),
        "confidence": round(max(0.0, confidence), 4),
        "spread_sigma": round(spread_sigma, 3), "total_sigma": round(total_sigma, 3),
        "lineup_risk_points": round(unresolved, 3),
        "anchored": anchored,
        "factors": factors,
        "away_profile": away,
        "home_profile": home,
        "away_injuries": away_injury,
        "home_injuries": home_injury,
    }


def rolling_calibration(history: list[dict], cfg: dict, max_games: int = 120) -> dict:
    """Walk-forward residuals only; no future result can train an earlier pick."""
    completed = sorted((game for game in history if game.get("completed") and game.get("season_type") == 2), key=lambda game: game["tipoff"])
    errors_margin: list[float] = []
    errors_total: list[float] = []
    start = max(0, len(completed) - max_games)
    for idx in range(start, len(completed)):
        game = completed[idx]
        prior = completed[:idx]
        if len(prior) < 30:
            continue
        ratings = solve_ratings(prior, cfg)
        away = team_profile(game["away"]["abbr"], prior, game["tipoff"], ratings, game["home"]["abbr"])
        home = team_profile(game["home"]["abbr"], prior, game["tipoff"], ratings, game["home"]["abbr"])
        if min(away["games"], home["games"]) < 5:
            continue
        replay = {**game, "odds": None}
        projection = project_game(replay, away, home, {}, cfg)
        actual_margin = float(game["home"]["score"]) - float(game["away"]["score"])
        actual_total = float(game["home"]["score"]) + float(game["away"]["score"])
        errors_margin.append(actual_margin - float(projection["raw_margin"]))
        errors_total.append(actual_total - float(projection["raw_total"]))
    def metrics(errors: list[float], floor: float, ceiling: float) -> dict:
        if not errors:
            return {"bias": 0.0, "mae": None, "rmse": None, "sigma": floor}
        bias = sum(errors) / len(errors)
        centred = [value - bias for value in errors]
        rmse = math.sqrt(sum(value * value for value in errors) / len(errors))
        sigma = math.sqrt(sum(value * value for value in centred) / len(centred))
        return {"bias": round(bias, 3), "mae": round(sum(abs(value) for value in errors) / len(errors), 3), "rmse": round(rmse, 3), "sigma": round(max(floor, min(ceiling, sigma)), 3)}
    spread = metrics(errors_margin, float(cfg["model"]["spread_sigma"]), float(cfg["model"]["spread_sigma_ceiling"]))
    total = metrics(errors_total, float(cfg["model"]["total_sigma"]), float(cfg["model"]["total_sigma_ceiling"]))
    return {
        "n": len(errors_margin), "method": "walk-forward regular-season residuals",
        "margin_bias": spread["bias"], "spread_mae": spread["mae"], "spread_rmse": spread["rmse"], "spread_sigma": spread["sigma"],
        "total_bias": total["bias"], "total_mae": total["mae"], "total_rmse": total["rmse"], "total_sigma": total["sigma"],
    }


def _compress_edge(raw_edge: float, cfg: dict, market: str) -> float:
    model_cfg = cfg["model"]
    ceiling = float(model_cfg["total_edge_ceiling"] if market == "TOTAL"
                    else model_cfg["side_edge_ceiling"])
    compressed = ceiling * math.tanh(raw_edge / ceiling)
    if compressed > 0:
        compressed = max(0.0, compressed - float(model_cfg.get("selection_haircut", 0.0)))
    return compressed


def _tier(edge: float, confidence: float, line_gap: float | None, price: float, cfg: dict) -> tuple[str, str | None]:
    tiers = cfg["tiers"]
    if edge < float(tiers["lean"]):
        return "AVOID", None
    if edge >= float(tiers["best_bet"]):
        reasons = []
        if confidence < float(tiers["best_bet_min_confidence"]):
            reasons.append("confidence below BEST BET minimum")
        if line_gap is None or abs(line_gap) < float(tiers["best_bet_min_line_gap"]):
            reasons.append("model line is too close to market")
        if line_gap is not None and abs(line_gap) > float(tiers["best_bet_max_line_gap"]):
            reasons.append("model/market disagreement exceeds safety limit")
        if price < float(tiers["best_bet_min_price"]):
            reasons.append("price is too short for BEST BET")
        if price > float(tiers["best_bet_max_price"]):
            reasons.append("price is too long for BEST BET")
        return ("BEST BET", None) if not reasons else ("GOOD", "; ".join(reasons))
    if edge >= float(tiers["good"]):
        return "GOOD", None
    return "LEAN", None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def quote_block_reason(game: dict, cfg: dict, now: datetime | None = None) -> str | None:
    now = now or _utc_now()
    try:
        tipoff = datetime.fromisoformat(str(game.get("tipoff") or "").replace("Z", "+00:00"))
        fetched = datetime.fromisoformat(str((game.get("odds") or {}).get("fetched_at") or "").replace("Z", "+00:00"))
        if tipoff.tzinfo is None or fetched.tzinfo is None:
            raise ValueError("timestamps must include timezone")
    except (TypeError, ValueError):
        return "Verified tipoff and odds timestamp required"
    if tipoff <= now or game.get("completed") or game.get("status") != "pre":
        return "Game has already started"
    age = (now - fetched).total_seconds() / 3600
    if age < -5 / 60:
        return "Odds timestamp is in the future"
    if age >= float(cfg["refresh"]["max_odds_age_hours"]):
        return "Odds are stale; waiting for a live price refresh"
    return None


def _candidate(game: dict, projection: dict, quote_key: str, label: str, market: str,
               side: str, model_prob: float, fair_prob: float | None, cfg: dict) -> dict | None:
    quote = (((game.get("odds") or {}).get("quotes") or {}).get(quote_key))
    if not quote or not price_ok(quote.get("price")):
        return None
    price = float(quote["price"])
    breakeven = american_to_prob(price)
    # Match MLB Edge's separation of handicapping edge and price-shopping edge.
    # Qualification is based on the model versus the complete, no-vig two-way
    # market. The actual offered price is retained for EV and stake sizing.
    raw_edge = (model_prob / fair_prob - 1.0) if fair_prob and fair_prob > 0 else 0.0
    raw_realized_edge = model_prob * american_to_decimal(price) - 1.0
    edge = _compress_edge(raw_edge, cfg, market)
    realized_edge = _compress_edge(raw_realized_edge, cfg, market)
    line_gap = projection["line_gap"] if market in {"ML", "ATS"} else (
        (projection["total"] - projection["market_total"]) if projection["market_total"] is not None else None)
    tier, tier_note = _tier(edge, projection["confidence"], line_gap, price, cfg)
    reasons: list[str] = []
    blocked = quote_block_reason(game, cfg)
    if blocked:
        tier = "AVOID"
        reasons.append(blocked)
    filters = cfg["filters"]
    if fair_prob is None:
        tier = "AVOID"
        reasons.append("Complete two-way market required")
    if realized_edge <= 0:
        tier = "AVOID"
        reasons.append("Offered price has no positive expected value")
    elif realized_edge < float(filters["min_realized_edge"]):
        tier = "AVOID"
        reasons.append("Price edge is below the execution-error buffer")
    if price < float(filters["min_price"]) or price > float(filters["max_price"]):
        tier = "AVOID"
        reasons.append("Price outside allowable range")
    if projection["confidence"] < float(filters["min_confidence"]):
        tier = "AVOID"
        reasons.append("Confidence below minimum")
    if float(projection.get("lineup_risk_points") or 0.0) > float(filters["max_unresolved_injury_points"]):
        tier = "AVOID"
        reasons.append("High-impact player status is unresolved")
    if int(game.get("days_out") or 0) > int(filters["max_days_to_bet"]):
        tier = "AVOID"
        reasons.append("Market is outside the actionable betting window")
    if edge < float(cfg["tiers"]["lean"]):
        reasons.append("Does not clear the Lean model-edge threshold")
    if game["status"] != "pre":
        tier = "AVOID"
        reasons.append("Game has already started")

    bankroll = cfg["bankroll"]
    # Size from the smaller of model and realized compressed edge. This keeps a
    # large raw probability disagreement from producing a large raw-Kelly bet.
    stake_edge = max(0.0, min(edge, realized_edge))
    effective_prob = min(0.999, max(0.001, (1.0 + stake_edge) / american_to_decimal(price)))
    raw_kelly = kelly_fraction(effective_prob, price)
    requested = min(
        float(bankroll["max_stake"]),
        float(bankroll["starting"]) * float(bankroll["max_stake_pct"]),
        float(bankroll["starting"]) * raw_kelly * float(bankroll["kelly_fraction"]),
    )
    if tier != "AVOID" and 0 < requested < float(bankroll["min_stake"]):
        requested = float(bankroll["min_stake"])
    fair_price = prob_to_american(model_prob)
    return {
        "candidate_id": f'{game["game_id"]}:{market}:{side}',
        "game_id": game["game_id"],
        "date": game["date"],
        "tipoff": game["tipoff"],
        "odds_fetched_at": (game.get("odds") or {}).get("fetched_at"),
        "max_odds_age_hours": float(cfg["refresh"]["max_odds_age_hours"]),
        "start_local": game["start_local"],
        "matchup": f'{game["away"]["abbr"]} @ {game["home"]["abbr"]}',
        "away": game["away"]["abbr"],
        "home": game["home"]["abbr"],
        "market": market,
        "side": side,
        "pick": label,
        "line": quote.get("line"),
        "price": int(price),
        "open_line": quote.get("open_line"),
        "open_price": quote.get("open_price"),
        "book": quote.get("book") or (game.get("odds") or {}).get("book"),
        "model_prob": round(model_prob, 4),
        "market_fair_prob": round(fair_prob, 4) if fair_prob is not None else None,
        "breakeven": round(breakeven, 4),
        "fair_price": fair_price,
        "edge_raw": round(raw_edge, 4),
        "edge_probability_points": round(model_prob - fair_prob, 4) if fair_prob is not None else None,
        "edge": round(edge, 4),
        "edge_real_raw": round(raw_realized_edge, 4),
        "edge_real": round(realized_edge, 4),
        "edge_price": round(realized_edge - edge, 4),
        "confidence": projection["confidence"],
        "tier": tier,
        "tier_note": tier_note,
        "reasons": reasons,
        "kelly_raw": round(raw_kelly, 4),
        "stake_before_daily_cap": 0.0 if tier == "AVOID" else round(requested, 2),
        "stake": 0.0,
        "projection": projection,
    }


def price_game(game: dict, projection: dict, cfg: dict) -> list[dict]:
    quotes = ((game.get("odds") or {}).get("quotes") or {})
    if not quotes:
        return []
    ml_fair = devig(quotes["away_ml"]["price"], quotes["home_ml"]["price"]) \
        if quotes.get("away_ml") and quotes.get("home_ml") else (None, None)
    spread_fair = devig(quotes["away_spread"]["price"], quotes["home_spread"]["price"]) \
        if quotes.get("away_spread") and quotes.get("home_spread") else (None, None)
    total_fair = devig(quotes["over"]["price"], quotes["under"]["price"]) \
        if quotes.get("over") and quotes.get("under") else (None, None)

    margin, total = float(projection["margin"]), float(projection["total"])
    spread_sd = float(projection.get("spread_sigma") or cfg["model"]["spread_sigma"])
    total_sd = float(projection.get("total_sigma") or cfg["model"]["total_sigma"])
    home_win = normal_cdf(margin / spread_sd)
    away_win = 1.0 - home_win
    rows = [
        _candidate(game, projection, "away_ml", f'{game["away"]["abbr"]} ML', "ML", "away", away_win, ml_fair[0], cfg),
        _candidate(game, projection, "home_ml", f'{game["home"]["abbr"]} ML', "ML", "home", home_win, ml_fair[1], cfg),
    ]
    if quotes.get("away_spread"):
        line = float(quotes["away_spread"]["line"])
        prob = normal_cdf((line - margin) / spread_sd)
        rows.append(_candidate(game, projection, "away_spread", f'{game["away"]["abbr"]} {line:+g}', "ATS", "away", prob, spread_fair[0], cfg))
    if quotes.get("home_spread"):
        line = float(quotes["home_spread"]["line"])
        prob = 1.0 - normal_cdf((-line - margin) / spread_sd)
        rows.append(_candidate(game, projection, "home_spread", f'{game["home"]["abbr"]} {line:+g}', "ATS", "home", prob, spread_fair[1], cfg))
    if quotes.get("over"):
        line = float(quotes["over"]["line"])
        prob = 1.0 - normal_cdf((line - total) / total_sd)
        rows.append(_candidate(game, projection, "over", f'Over {line:g}', "TOTAL", "over", prob, total_fair[0], cfg))
    if quotes.get("under"):
        line = float(quotes["under"]["line"])
        prob = normal_cdf((line - total) / total_sd)
        rows.append(_candidate(game, projection, "under", f'Under {line:g}', "TOTAL", "under", prob, total_fair[1], cfg))
    return [row for row in rows if row is not None]


def allocate_portfolio(candidates: list[dict], cfg: dict) -> list[dict]:
    """Allocate only the strongest uncorrelated positions inside slate limits."""
    bankroll = cfg["bankroll"]
    cap = float(bankroll["starting"]) * float(bankroll["max_daily_exposure_pct"])
    increment = float(bankroll["round_stake_to"])
    order = {"BEST BET": 0, "GOOD": 1, "LEAN": 2, "AVOID": 3}
    dates = sorted({row["date"] for row in candidates})
    for date in dates:
        remaining, used_games = cap, set()
        selected_count = best_count = 0
        rows = [row for row in candidates if row["date"] == date]
        rows.sort(key=lambda row: (order[row["tier"]], -min(row["edge"], row["edge_real"]), -row["confidence"], row["game_id"], row["market"]))
        for row in rows:
            if row["tier"] == "AVOID":
                continue
            if row["game_id"] in used_games:
                row["tier"] = "AVOID"
                row["reasons"].append("Higher-rated market already selected for this game")
                continue
            if selected_count >= int(cfg["filters"]["max_bets_per_day"]):
                row["tier"] = "AVOID"
                row["reasons"].append("Daily play-count limit reached")
                continue
            if row["tier"] == "BEST BET" and best_count >= int(cfg["filters"]["max_best_bets_per_day"]):
                row["tier"] = "GOOD"
                row["tier_note"] = "Daily BEST BET limit reached"
            requested = float(row["stake_before_daily_cap"])
            granted = min(requested, remaining)
            granted = math.floor((granted + 1e-9) / increment) * increment
            if granted < float(bankroll["min_stake"]):
                row["tier"] = "AVOID"
                row["reasons"].append("Daily exposure cap reached")
                continue
            row["stake"] = round(granted, 2)
            remaining = max(0.0, remaining - granted)
            used_games.add(row["game_id"])
            selected_count += 1
            best_count += row["tier"] == "BEST BET"
            if remaining <= 1e-9 and requested - granted >= increment:
                row["reasons"].append("Stake reduced to fit daily exposure cap")
    candidates.sort(key=lambda row: (row["date"], order[row["tier"]], -row["edge"], row["game_id"]))
    return candidates


def rationale(game: dict, projection: dict, best: dict | None) -> str:
    away, home = game["away"]["abbr"], game["home"]["abbr"]
    pieces = [
        f'Model projects {away} {projection["away_score"]:.1f} – {home} {projection["home_score"]:.1f}.',
        f'Opponent-adjusted scoring, pace/efficiency, venue form, travel, schedule density and role-weighted availability are included.',
    ]
    if projection["anchored"]:
        pieces.append(f'The raw model line is {projection["raw_margin"]:+.1f} home; the market-anchored line is {projection["margin"]:+.1f}.')
    if best and best["tier"] != "AVOID":
        pieces.append(f'{best["pick"]} rates {best["tier"]} at {best["edge"]*100:.1f}% edge and {best["model_prob"]*100:.1f}% model probability.')
    elif game.get("odds"):
        pieces.append("No side clears the current price, confidence and portfolio rules.")
    else:
        pieces.append("No wager is rated until a real market price is available.")
    return " ".join(pieces)
