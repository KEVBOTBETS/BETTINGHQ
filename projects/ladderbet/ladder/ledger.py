"""Ledger — every bet, what you actually got, and where the money went.

Three numbers here that the pick screen cannot tell you, and that only
accumulate over time:

  slippage  screened price minus the price you actually took. Measures the cost
            of the gap between seeing a bet and placing it.
  CLV       your price minus the closing price. The single best long-run
            indicator of whether you are picking well, because it is measured
            against the market's final opinion rather than one game's outcome.
  net       actual wager profit/loss, realized when a run busts or cashes out.
            Stake overrides and amendments use the recorded amounts.
"""
from __future__ import annotations

import csv
from io import StringIO

FIELDS = [
    "placed_at", "settled_at", "league", "matchup", "pick", "rung",
    "screened_decimal", "decimal", "slippage", "closing_decimal", "clv",
    "american", "stake", "result", "returned", "cashed_out", "running_net",
    "profit_loss", "running_profit_loss",
]


def rows(state: dict) -> list[dict]:
    """Flatten history into ledger rows with a running net."""
    out, net, running_pl, run_pl = [], 0.0, 0.0, 0.0
    for h in state.get("history", []):
        if h.get("event") == "cash_out":
            net += run_pl
            run_pl = 0.0
            out.append({
                "placed_at": "", "settled_at": h.get("settled_at", ""),
                "league": "", "matchup": "", "pick": "— cashed out —",
                "rung": h.get("rung", ""), "screened_decimal": "", "decimal": "",
                "slippage": "", "closing_decimal": "", "clv": "", "american": "",
                "stake": "", "result": "cashout", "returned": "",
                "cashed_out": round(h.get("banked", 0.0), 2),
                "running_net": round(net, 2),
                "profit_loss": "", "running_profit_loss": round(running_pl, 2),
            })
            continue

        res = h.get("result")
        if not res:
            continue
        stake = float(h.get("stake") or 0.0)
        returned = float(h.get("returned") or 0.0)
        profit_loss = (returned - stake) if res in ("win", "loss") else 0.0
        running_pl += profit_loss
        run_pl += profit_loss
        if res == "loss" or h.get("cashed_out"):
            net += run_pl
            run_pl = 0.0

        out.append({
            "placed_at": h.get("placed_at", ""),
            "settled_at": h.get("settled_at", ""),
            "league": (h.get("league") or "").upper(),
            "matchup": h.get("matchup", ""),
            "pick": h.get("pick", ""),
            "rung": h.get("rung", ""),
            "screened_decimal": h.get("screened_decimal", ""),
            "decimal": h.get("decimal", ""),
            "slippage": h.get("slippage", ""),
            "closing_decimal": h.get("closing_decimal", ""),
            "clv": h.get("clv", ""),
            "american": h.get("american", ""),
            "stake": h.get("stake", ""),
            "result": res,
            "returned": h.get("returned", ""),
            "cashed_out": h.get("cashed_out", ""),
            "running_net": round(net, 2),
            "profit_loss": round(profit_loss, 2),
            "running_profit_loss": round(running_pl, 2),
        })
    return out


def summary(state: dict) -> dict:
    r = rows(state)
    bets = [x for x in r if x["result"] in ("win", "loss")]
    wins = [x for x in bets if x["result"] == "win"]
    slips = [float(x["slippage"]) for x in bets
             if x["slippage"] not in ("", None)]
    clvs = [float(x["clv"]) for x in bets if x["clv"] not in ("", None)]
    staked = sum(float(x["stake"]) for x in bets if x["stake"] not in ("", None))

    return {
        "bets": len(bets),
        "wins": len(wins),
        "losses": len(bets) - len(wins),
        "win_rate": (len(wins) / len(bets)) if bets else 0.0,
        "total_staked": round(staked, 2),
        "net": r[-1]["running_net"] if r else 0.0,
        "profit_loss": round(sum(float(x.get("profit_loss") or 0) for x in bets), 2),
        "runs_cashed": state.get("runs_completed", 0),
        "runs_busted": state.get("runs_busted", 0),
        "avg_slippage": round(sum(slips) / len(slips), 4) if slips else None,
        "slippage_n": len(slips),
        "avg_clv": round(sum(clvs) / len(clvs), 4) if clvs else None,
        "clv_beat_rate": (sum(1 for c in clvs if c > 0) / len(clvs)) if clvs else None,
        "clv_n": len(clvs),
    }


def to_csv(state: dict) -> str:
    buf = StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore")
    w.writeheader()
    for row in rows(state):
        w.writerow(row)
    return buf.getvalue()
