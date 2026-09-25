"""Screen ESPN moneylines into a selectable ladder option board.

An honest note about what can and cannot be computed here. ESPN's scoreboard
usually returns ONE provider. De-vigging a single two-way market gives you that
book's fair probability, which is a good estimate — it is the market's opinion,
and the market is hard to beat. But "edge" measured against that same book is
circular: it always works out to -hold/(1+hold) for both sides. So this module
reports `vig_cost` (what the hold costs you) instead of pretending to have
found value. Real cross-book edge is only reported when two or more providers
appear, which on ESPN is uncommon.

Ranking is therefore on de-vigged win probability, which is exactly the
"highest chance of winning" criterion, with the hold as a tiebreak.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
import math
from statistics import mean

from . import espn
from .oddsmath import american_to_decimal, decimal_to_american, implied


@dataclass
class Candidate:
    league: str
    event_id: str
    start_utc: str
    starts_in_h: float
    matchup: str
    pick: str
    side: str                 # home | away | draw
    provider: str
    american: float
    decimal: float
    raw_prob: float           # implied by the price, vig included
    fair_prob: float          # de-vigged
    vig_cost: float           # what the hold costs you per unit staked
    hold: float
    n_providers: int
    open_american: float | None = None
    drift: float | None = None      # close prob - open prob; + means it shortened
    steam: str = ""
    cross_book_edge: float | None = None
    note: str = field(default="")

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        lines = [
            f"{self.pick}  {self.american:+.0f}  ({self.decimal:.3f})  [{self.provider}]",
            f"  {self.league.upper()} — {self.matchup}",
            f"  starts in {self.starts_in_h:.1f}h ({self.start_utc})",
            f"  de-vigged win prob {self.fair_prob:.1%}  |  "
            f"price implies {self.raw_prob:.1%}  |  hold {self.hold:.2%}",
            f"  vig cost {self.vig_cost:+.2%} per unit staked",
        ]
        if self.drift is not None and self.open_american is not None:
            lines.append(f"  opened {self.open_american:+.0f} -> now {self.american:+.0f}"
                         f"  ({self.drift:+.2%} implied)  {self.steam}")
        if self.cross_book_edge is not None:
            lines.append(f"  cross-book edge {self.cross_book_edge:+.2%} "
                         f"({self.n_providers} providers)")
        if self.note:
            lines.append(f"  ! {self.note}")
        return "\n".join(lines)


def _devig(prices: dict[str, float]) -> tuple[dict[str, float], float]:
    """prices: side -> american odds. Returns (side -> fair prob, hold)."""
    raw = {s: implied(american_to_decimal(a)) for s, a in prices.items()}
    total = sum(raw.values())
    if total <= 0:
        raise ValueError("degenerate market")
    return {s: r / total for s, r in raw.items()}, total - 1.0


def screen_event(
    event: dict,
    league: str,
    min_decimal: float,
    max_decimal: float,
    max_hold: float = 0.10,
    require_pre: bool = True,
    use_open: bool = False,
) -> list[Candidate]:
    """require_pre=False lets the backtester screen finished games.
    use_open prices off the opening line instead of the close."""
    comps = event.get("competitions") or []
    if not comps:
        return []
    comp = comps[0]

    st = espn.status(comp)
    if not st.get("state"):
        st = espn.status(event)
    if require_pre and st.get("state") != "pre":
        return []

    hrs = espn.starts_in_hours(event)
    if hrs is None:
        hrs = 0.0 if not require_pre else None
    if hrs is None:
        return []

    tm = espn.teams(comp)
    if "home" not in tm or "away" not in tm:
        return []
    matchup = f"{tm['away']['name']} @ {tm['home']['name']}"

    books = espn.moneylines(comp)
    if not books:
        return []

    three_way = league in espn.THREE_WAY
    per_side_fair: dict[str, list[float]] = {}
    per_side_best: dict[str, tuple[float, str]] = {}
    per_side_open: dict[str, float] = {}
    holds: list[float] = []

    for b in books:
        sfx = "_open" if use_open else ""
        get = lambda k: b.get(k + sfx) if b.get(k + sfx) is not None else (
            None if use_open else b.get(k))
        prices = {}
        for k in ("home", "away"):
            v = get(k)
            if v is not None:
                prices[k] = v
        if three_way:
            v = get("draw")
            if v is not None:
                prices["draw"] = v
        # De-vigging needs the complete market or the result is meaningless.
        if len(prices) < 2 or (three_way and "draw" not in prices):
            continue
        try:
            fair, h = _devig(prices)
        except (ValueError, ZeroDivisionError):
            continue
        # A negative hold from one book means arbitrage, which does not
        # really happen — it means the market is incomplete or misparsed.
        if h < 0 or h > max_hold:
            continue
        holds.append(h)
        for side, amer in prices.items():
            per_side_fair.setdefault(side, []).append(fair[side])
            dec = american_to_decimal(amer)
            cur = per_side_best.get(side)
            if cur is None or dec > cur[0]:
                per_side_best[side] = (dec, b["provider"])
            op = b.get("%s_open" % side)
            if op is not None and side not in per_side_open:
                per_side_open[side] = op

    if not per_side_fair or not holds:
        return []

    avg_hold = mean(holds)
    n = len(holds)
    out: list[Candidate] = []

    for side, probs in per_side_fair.items():
        dec, provider = per_side_best[side]
        if not (min_decimal <= dec <= max_decimal):
            continue
        fair = mean(probs)
        note = "" if n > 1 else "single provider — vig cost is the hold, not a signal"
        vig_cost = fair * dec - 1.0

        open_amer = per_side_open.get(side)
        drift = steam = None
        if open_amer is not None:
            open_dec = american_to_decimal(open_amer)
            drift = implied(dec) - implied(open_dec)
            if drift > 0.015:
                steam = "shortened — money came in on this side"
            elif drift < -0.015:
                steam = "drifted — money went the other way"
            else:
                steam = "line barely moved"
        out.append(Candidate(
            league=league,
            event_id=str(event.get("id", "")),
            start_utc=event.get("date", ""),
            starts_in_h=round(hrs, 2),
            matchup=matchup,
            pick="Draw" if side == "draw" else tm[side]["name"],
            side=side,
            provider=provider,
            american=decimal_to_american(dec),
            decimal=round(dec, 4),
            raw_prob=round(implied(dec), 4),
            fair_prob=round(fair, 4),
            vig_cost=round(vig_cost, 4),
            hold=round(avg_hold, 4),
            n_providers=n,
            open_american=open_amer,
            drift=round(drift, 4) if drift is not None else None,
            steam=steam or "",
            cross_book_edge=round(vig_cost, 4) if n > 1 else None,
            note=note,
        ))
    return out


def collect(
    leagues: list[str],
    min_decimal: float,
    max_decimal: float,
    horizon_hours: float,
    max_hold: float = 0.10,
    date: str | None = None,
    fetch=None,
) -> tuple[list[Candidate], list[str]]:
    """Returns (candidates, warnings). `fetch` is injectable for tests."""
    live_fetch = fetch is None
    fetch = fetch or espn.events
    cands: list[Candidate] = []
    warnings: list[str] = []

    # ESPN's undated endpoint often stays on the US calendar day that just
    # ended. Explicitly fetch every date touched by the horizon so evening
    # refreshes include tonight and tomorrow instead of yesterday's finals.
    if date or not live_fetch:
        dates: list[str | None] = [date]
    else:
        anchor = datetime.now(timezone.utc).date()
        days = max(1, math.ceil(horizon_hours / 24) + 1)
        dates = [(anchor + timedelta(days=i)).strftime("%Y%m%d")
                 for i in range(days)]

    for lg in leagues:
        evs, seen = [], set()
        errors = []
        for d in dates:
            try:
                batch = fetch(lg, d)
            except espn.ESPNError as e:
                errors.append(str(e))
                continue
            for ev in batch:
                key = str(ev.get("id") or "")
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                evs.append(ev)
        if not evs:
            detail = f" ({errors[0]})" if errors else ""
            warnings.append(f"{lg}: no events returned{detail}")
            continue
        found = 0
        for ev in evs:
            for c in screen_event(ev, lg, min_decimal, max_decimal, max_hold):
                if 0 <= c.starts_in_h <= horizon_hours:
                    cands.append(c)
                    found += 1
        if found == 0:
            warnings.append(f"{lg}: {len(evs)} events, none qualified")
    return cands, warnings


def rank(cands: list[Candidate]) -> list[Candidate]:
    """Highest de-vigged win probability, then cheapest hold, then most books."""
    return sorted(cands, key=lambda c: (c.fair_prob, -c.hold, c.n_providers), reverse=True)
