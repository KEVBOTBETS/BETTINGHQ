"""Coloured terminal output. Degrades to plain text when piped or NO_COLOR."""
from __future__ import annotations

import os
import sys

_ON = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _ON else s


def dim(s):    return _c("2", s)
def bold(s):   return _c("1", s)
def gold(s):   return _c("38;5;214", s)
def green(s):  return _c("38;5;41", s)
def red(s):    return _c("38;5;203", s)
def blue(s):   return _c("38;5;75", s)


def rule(title: str = "", width: int = 58) -> str:
    if not title:
        return dim("─" * width)
    pad = max(0, width - len(title) - 3)
    return dim("── ") + bold(title) + " " + dim("─" * pad)


def ladder_bars(rung: int, max_rung: int, base: float, decimal: float,
                current_stake: float | None = None,
                past: list[float] | None = None) -> str:
    """Staircase of rungs, widths proportional to stake.

    Rungs already climbed use the stakes actually bet (`past`); rungs ahead
    compound forward from `current_stake`, not from base at a made-up price.
    """
    past = list(past or [])
    stakes = []
    for i in range(max_rung):
        if i < rung and i < len(past):
            stakes.append(past[i])
        elif i < rung:
            stakes.append(base)
        else:
            break
    s = current_stake if current_stake is not None else base
    for _ in range(rung, max_rung):
        stakes.append(round(s, 2))
        s = round(s * decimal, 2)
    top = stakes[-1] or 1.0
    out = []
    for i in range(max_rung - 1, -1, -1):
        w = max(1, round(stakes[i] / top * 26))
        # A climbed rung's return IS the next rung's stake — that is what you
        # actually collected, at the price you actually got.
        ret = stakes[i + 1] if (i < rung and i + 1 < len(stakes)) else stakes[i] * decimal
        label = f"${stakes[i]:>9,.2f} -> ${ret:>10,.2f}"
        if i < rung:
            out.append(f"  {green('R%d' % i)} {green('█' * w)}{dim('·' * (26-w))}  {label}")
        elif i == rung:
            out.append(f"  {gold('R%d' % i)} {gold('▓' * w)}{dim('·' * (26-w))}  "
                       f"{bold(label)}  {gold('<- next')}")
        else:
            out.append(f"  {dim('R%d' % i)} {dim('░' * w)}{dim('·' * (26-w))}  {dim(label)}")
    return "\n".join(out)


def probbar(p: float, width: int = 22, breakeven: float | None = None) -> str:
    filled = max(0, min(width, round(p * width)))
    bar = ("█" * filled) + ("·" * (width - filled))
    col = green if (breakeven is None or p >= breakeven) else gold
    return col(bar)
