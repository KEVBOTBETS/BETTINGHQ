"""
Fifteen-season walk-forward backtest on free historical data.

    python -m pipeline.history_backtest            # uses the cached CSV, fetches if missing
    python -m pipeline.history_backtest --fetch    # re-download nflverse games.csv first
    python -m pipeline.history_backtest --tune     # also sweep the market-blend settings

Why this exists. The live accuracy record has a few dozen graded NFL games, and
calibration needs 400 observations from 100 games before it will switch on --
most of a season. nflverse publishes every NFL game since 1999 with final
scores and CLOSING spreads, totals, moneylines and prices (full prices from
2010), free and keyless on GitHub. That is ~4,000 priced games to ask the only
question that matters: does the model's disagreement with the market carry
information, and how much of it should be kept?

What is replayed, week by week, 2011-2025:
  * ratings solved only from games that had finished before that week, around
    a preseason prior built from the previous season (regressed) and the
    market-spread ratings posted up to that week -- the same functions,
    settings and anchoring the live board uses;
  * every game priced against its CLOSING line with build.price_game, then
    filtered, correlation-guarded and weekly-capped exactly like the board.

What is NOT replayed (so read the result as a floor, not a forecast):
  * ESPN FPI, market win totals, injuries, depth charts and weather -- no free
    historical archive of what they said before each game;
  * opening or mid-week prices -- only closes exist. Closing lines are the
    sharpest number of the week, so this is the hardest possible test. A
    model that merely ties the close here can still beat a Tuesday number.

Output: site/data/backtest.json (shown on the Accuracy tab) and a printed
report. Nothing in config/settings.json is changed automatically; --tune
prints what the data supports and the tested settings are adopted by hand.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import sys
import time
from collections import defaultdict

from . import build as B, market as MKT, model as M, ratings as R, weather as WX

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "state", "nflverse_games.csv")
OUT_PATH = os.path.join(ROOT, "site", "data", "backtest.json")
URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

# nflverse -> ESPN codes. Relocated franchises keep one identity so the
# preseason prior carries across the move.
ALIASES = {"LA": "LAR", "STL": "LAR", "WAS": "WSH", "OAK": "LV", "SD": "LAC"}
FIRST_PRICED_SEASON = 2010


def fetch(path: str = CSV_PATH) -> None:
    import requests
    r = requests.get(URL, timeout=120)
    r.raise_for_status()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(r.text)
    print(f"   fetched {len(r.text) / 1e6:.1f} MB of nflverse games")


def _num(v):
    try:
        return None if v in (None, "", "NA") else float(v)
    except ValueError:
        return None


def _utc(day: str, clock: str) -> str:
    """nflverse times are US Eastern. Close enough: EDT through October."""
    try:
        d = dt.datetime.fromisoformat(f"{day}T{clock or '13:00'}")
    except ValueError:
        d = dt.datetime.fromisoformat(f"{day}T13:00")
    d += dt.timedelta(hours=4 if d.month in (8, 9, 10) else 5)
    return d.strftime("%Y-%m-%dT%H:%MZ")


def to_game(row: dict) -> dict | None:
    if row.get("game_type") not in ("REG", "WC", "DIV", "CON", "SB"):
        return None
    home = ALIASES.get(row["home_team"], row["home_team"])
    away = ALIASES.get(row["away_team"], row["away_team"])
    hs, as_ = _num(row.get("home_score")), _num(row.get("away_score"))
    spread = _num(row.get("spread_line"))
    return {
        "game_id": row["game_id"],
        "season": int(row["season"]),
        "season_type": 2 if row["game_type"] == "REG" else 3,
        "week": int(row["week"]),
        "date_utc": _utc(row["gameday"], row.get("gametime")),
        "home": {"abbr": home, "id": home, "name": home},
        "away": {"abbr": away, "id": away, "name": away},
        "neutral": row.get("location") == "Neutral",
        "completed": hs is not None and as_ is not None,
        "home_score": None if hs is None else int(hs),
        "away_score": None if as_ is None else int(as_),
        "odds": {
            "book": "close (nflverse)",
            # nflverse spread_line is the expected HOME margin; ESPN's
            # spread_home is the home handicap, so the sign flips.
            "spread_home": None if spread is None else -spread,
            "spread_price_home": _num(row.get("home_spread_odds")),
            "spread_price_away": _num(row.get("away_spread_odds")),
            "total": _num(row.get("total_line")),
            "over_price": _num(row.get("over_odds")),
            "under_price": _num(row.get("under_odds")),
            "ml_home": _num(row.get("home_moneyline")),
            "ml_away": _num(row.get("away_moneyline")),
        },
    }


def load(path: str = CSV_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        rows = [to_game(r) for r in csv.DictReader(fh)]
    return [g for g in rows if g and g["season"] >= FIRST_PRICED_SEASON - 1]


def backtest_cfg(cfg: dict) -> dict:
    """The live settings, minus inputs that have no historical archive."""
    c = json.loads(json.dumps(cfg))
    c["ratings"]["use_market_win_totals"] = False     # win_totals.json is 2026's
    c["model"]["calibration"] = {**c["model"].get("calibration", {}), "enabled": False}
    return c


# --------------------------------------------------------------------------- #
# Stage 1: everything that does not depend on the blend settings, per game.
# --------------------------------------------------------------------------- #

def contexts(games: list[dict], cfg: dict, seasons: list[int]) -> list[dict]:
    venues = WX.load_venues()
    divisions = B.load_divisions()
    out: list[dict] = []
    for season in seasons:
        prior_games = [g for g in games if g["season"] == season - 1 and g["season_type"] == 2]
        this = [g for g in games if g["season"] == season and g["season_type"] == 2]
        if not prior_games or not this:
            continue
        preseason, _ = R.preseason_prior(prior_games, cfg)
        rests = B.rest_days(this)
        for week in sorted({g["week"] for g in this}):
            history = [g for g in this if g["week"] < week]
            posted = [g for g in this if g["week"] <= week]
            played = R.games_played(history)
            prior = preseason
            if cfg["ratings"].get("use_market_spread_ratings", True):
                mrat, _ = MKT.solve(posted, cfg)
                if mrat:
                    prior, _ = MKT.blend_prior(preseason, mrat, played, cfg)
            if history:
                rat, hfa = R.solve_margin_ratings(history, cfg, prior=prior)
            else:
                rat, hfa = prior, float(cfg["model"]["home_field_fallback"])
            team_hfa = R.per_team_home_field(history, hfa, cfg) if history else {}
            score_rat, league, bump = R.solve_scoring_ratings(history, cfg, prior_games=prior_games)
            for g in (x for x in this if x["week"] == week and x["completed"]):
                out.append({"g": g, "season": season, "week": week, "rat": rat, "hfa": hfa,
                            "team_hfa": team_hfa, "score_rat": score_rat, "league": league,
                            "bump": bump, "rests": rests, "venues": venues, "divisions": divisions,
                            "n_home": played.get(g["home"]["abbr"], 0),
                            "n_away": played.get(g["away"]["abbr"], 0)})
        print(f"   {season}: {sum(1 for c in out if c['season'] == season)} games prepared")
    return out


# --------------------------------------------------------------------------- #
# Stage 2: price and grade under a given set of settings.
# --------------------------------------------------------------------------- #

def _settle(c: dict, g: dict) -> str | None:
    hs, as_ = g["home_score"], g["away_score"]
    margin, total = hs - as_, hs + as_
    if c["market"] == "ML":
        return "Push" if margin == 0 else ("Win" if (margin > 0) == (c["side"] == "home") else "Loss")
    if c["market"] == "ATS":
        adj = margin + float(c["line"])
        return "Push" if abs(adj) < 1e-9 else ("Win" if (adj > 0) == (c["side"] == "home") else "Loss")
    if abs(total - float(c["line"])) < 1e-9:
        return "Push"
    return "Win" if (total > float(c["line"])) == (c["side"] == "over") else "Loss"


def price_all(ctx: list[dict], cfg: dict) -> list[dict]:
    rows: list[dict] = []
    for x in ctx:
        g = x["g"]
        conf = M.confidence_score(x["n_home"], x["n_away"], True, cfg, 2)
        proj = B.project(g, x["rat"], x["hfa"], x["score_rat"], x["league"], x["bump"],
                         x["rests"], {}, cfg, {}, {}, x["venues"], x["team_hfa"], x["divisions"])
        today = dt.date.fromisoformat(g["date_utc"][:10])
        cands = B.apply_filters(B.price_game(g, proj, cfg, conf, stale=False), cfg, g, today)
        for c in cands:
            c["result"] = _settle(c, g)
            c["season"] = x["season"]
            c["gap"] = proj.get("gap")
            c["total_gap"] = proj.get("total_gap")
        rows.extend(cands)
    # Same guards as the live board, per real week.
    by_week: dict = defaultdict(list)
    for r in rows:
        by_week[(r["season"], r["week"])].append(r)
    for wk in by_week.values():
        B.weekly_cap(B.correlation_guard(wk, cfg), cfg)
    return rows


def _logloss(p: float, y: int) -> float:
    p = min(0.999, max(0.001, p))
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def scores(rows: list[dict]) -> dict:
    """Model vs market on one canonical side per game and market."""
    out = {}
    for market, side in (("ML", "home"), ("ATS", "home"), ("TOTAL", "over")):
        sel = [r for r in rows if r["market"] == market and r["side"] == side
               and r["result"] in ("Win", "Loss") and r.get("market_fair_prob")]
        if not sel:
            continue
        y = [1 if r["result"] == "Win" else 0 for r in sel]
        pm = [float(r["model_prob"]) for r in sel]
        pk = [float(r["market_fair_prob"]) for r in sel]
        n = len(sel)
        out[market] = {
            "n": n,
            "model_logloss": round(sum(map(_logloss, pm, y)) / n, 5),
            "market_logloss": round(sum(map(_logloss, pk, y)) / n, 5),
            "model_brier": round(sum((p - t) ** 2 for p, t in zip(pm, y)) / n, 5),
            "market_brier": round(sum((p - t) ** 2 for p, t in zip(pk, y)) / n, 5),
        }
        o = out[market]
        o["logloss_edge"] = round(o["market_logloss"] - o["model_logloss"], 5)
    return out


def _block(rows: list[dict]) -> dict:
    settled = [r for r in rows if r["result"] in ("Win", "Loss", "Push")]
    w = sum(r["result"] == "Win" for r in settled)
    lo = sum(r["result"] == "Loss" for r in settled)
    units = sum((M.american_to_decimal(r["price"]) - 1) if r["result"] == "Win"
                else (-1.0 if r["result"] == "Loss" else 0.0) for r in settled)
    return {"n": len(settled), "wins": w, "losses": lo, "record": f"{w}-{lo}",
            "win_pct": round(w / (w + lo), 4) if w + lo else None,
            "units": round(units, 2), "roi": round(units / len(settled), 4) if settled else None,
            "avg_prob": round(sum(float(r["model_prob"]) for r in settled) / len(settled), 4) if settled else None}


def calibration(rows: list[dict], bins: int = 10) -> list[dict]:
    b: dict = defaultdict(list)
    for r in rows:
        if r["result"] not in ("Win", "Loss"):
            continue
        p = float(r["model_prob"])
        b[min(bins - 1, int(p * bins))].append((p, 1 if r["result"] == "Win" else 0))
    return [{"bucket": f"{k / bins:.0%}-{(k + 1) / bins:.0%}", "n": len(v),
             "predicted": round(sum(p for p, _ in v) / len(v), 4),
             "actual": round(sum(y for _, y in v) / len(v), 4)}
            for k, v in sorted(b.items()) if len(v) >= 25]


def summarise(rows: list[dict]) -> dict:
    sel = [r for r in rows if r["tier"] != "PASS"]
    seasons = sorted({r["season"] for r in rows})
    return {
        "scores": scores(rows),
        "selected": _block(sel),
        "by_tier": {t: _block([r for r in sel if r["tier"] == t]) for t in ("BEST BET", "GOOD", "LEAN")},
        "by_market": {m: _block([r for r in sel if r["market"] == m]) for m in ("ML", "ATS", "TOTAL")},
        "by_season": [{"season": s, **_block([r for r in sel if r["season"] == s]),
                       "scores": scores([r for r in rows if r["season"] == s])} for s in seasons],
        "calibration_selected": calibration(sel),
        "calibration_all_home_sides": calibration([r for r in rows if r["side"] in ("home", "over")]),
    }


def tune(ctx: list[dict], cfg: dict, train: set[int], test: set[int]) -> dict:
    """Sweep how much of the model's disagreement to keep; judge on log loss."""
    grid = []
    for pb in (0.0, 0.15, 0.3, 0.45, 0.55, 0.7):
        for mb in (0.35, 0.5, 0.65, 0.8):
            c = json.loads(json.dumps(cfg))
            c["model"]["projection_blend"] = pb
            c["model"]["market_blend"] = mb
            rows = price_all(ctx, c)
            def ll(seasons):
                sc = scores([r for r in rows if r["season"] in seasons])
                return {m: v["logloss_edge"] for m, v in sc.items()}
            grid.append({"projection_blend": pb, "market_blend": mb,
                         "train": ll(train), "test": ll(test),
                         "test_selected": _block([r for r in rows if r["season"] in test and r["tier"] != "PASS"])})
            print(f"   pb={pb:.2f} mb={mb:.2f}  train {grid[-1]['train']}  test {grid[-1]['test']}")
    best = max(grid, key=lambda g: sum(g["train"].values()))
    return {"grid": grid, "best_on_train": best}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--first", type=int, default=2011)
    ap.add_argument("--last", type=int, default=2025)
    args = ap.parse_args()
    if args.fetch or not os.path.exists(CSV_PATH):
        fetch()
    t0 = time.time()
    cfg = backtest_cfg(B.load_cfg())
    games = load()
    seasons = list(range(args.first, args.last + 1))
    print(f"== nflverse walk-forward backtest {seasons[0]}-{seasons[-1]} ==")
    ctx = contexts(games, cfg, seasons)
    rows = price_all(ctx, cfg)
    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "source": "nflverse games.csv (closing lines)",
        "seasons": [seasons[0], seasons[-1]],
        "games": len(ctx),
        "settings": {k: cfg["model"].get(k) for k in ("projection_blend", "market_blend", "margin_sd",
                                                       "total_sd", "selection_haircut")},
        "tiers": {k: cfg["tiers"].get(k) for k in ("best_bet", "good", "lean")},
        "limits": ("Priced against CLOSING lines with no FPI, win totals, injuries or weather. "
                   "Read it as a floor: the hardest number of the week, with fewer inputs than the live board."),
        **summarise(rows),
    }
    if args.tune:
        train = set(range(seasons[0], 2021))
        test = set(range(2021, seasons[-1] + 1))
        result["tuning"] = tune(ctx, cfg, train, test)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(result, fh, separators=(",", ":"))
    print_report(result)
    print(f"   {time.time() - t0:.0f}s · wrote {OUT_PATH}")
    return 0


def print_report(res: dict) -> None:
    print()
    print(f"  {res['games']} games, {res['seasons'][0]}-{res['seasons'][1]}, priced at the close")
    for m, s in res["scores"].items():
        verdict = "model better" if s["logloss_edge"] > 0 else "market better"
        print(f"  {m:6s} log loss model {s['model_logloss']:.4f} vs market {s['market_logloss']:.4f} "
              f"({verdict}, n={s['n']})")
    print("  selected plays:", res["selected"]["record"], "ROI", res["selected"]["roi"])
    for t, b in res["by_tier"].items():
        if b["n"]:
            print(f"    {t:9s} {b['record']:>9s}  win {b['win_pct']}  ROI {b['roi']}")
    for m, b in res["by_market"].items():
        if b["n"]:
            print(f"    {m:9s} {b['record']:>9s}  win {b['win_pct']}  ROI {b['roi']}")


if __name__ == "__main__":
    sys.exit(main())
