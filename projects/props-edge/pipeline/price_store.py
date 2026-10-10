"""Keep quote provenance through outages without turning retained prices into bets."""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import replace
from typing import Any

from .qualified import eligible_book_key
from .schema import Projection, PropQuote, american_to_decimal


def stamp(value):
    try:
        result = dt.datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return result if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def identity(q):
    return (q.event_id, q.player.casefold(), q.market.casefold(), q.side, q.line, q.book.casefold())


def recover(current: list[PropQuote], previous: dict[str, Any], projections: list[Projection], settings: dict,
            failed_sources: set[str], now: dt.datetime) -> tuple[list[PropQuote], dict, dict]:
    inventory = {}
    for data in previous.get("quotes", []) if isinstance(previous, dict) else []:
        try:
            q = PropQuote(**data)
            if q.provider in failed_sources:
                inventory[identity(q)] = replace(q, quote_status="retained")
        except (TypeError, ValueError, AttributeError):
            continue
    for q in current:
        old = inventory.get(identity(q))
        if not old or (stamp(q.updated_at) and (not stamp(old.updated_at) or stamp(q.updated_at) >= stamp(old.updated_at))):
            inventory[identity(q)] = q
    contracts = {(p.event_id, p.player.casefold(), p.market.casefold(), stamp(p.start_time)) for p in projections if p.roster_verified}
    kept, usable = [], []
    diagnostics = {"observed": 0, "retained": 0, "reference": 0, "expired": 0, "rejected": 0, "max_age_hours": 4}
    for q in inventory.values():
        try:
            start, updated = stamp(q.start_time), stamp(q.updated_at)
            valid = (start is not None and updated is not None and start > now and updated <= now
                     and eligible_book_key(q.book, settings) is not None and q.event_id
                     and q.side in {"over", "under", "yes", "no"} and isinstance(q.price_american, (int, float))
                     and math.isfinite(q.price_american) and abs(q.price_american) >= 100
                     and math.isfinite(q.price_decimal) and abs(q.price_decimal-american_to_decimal(q.price_american)) < .0001
                     and (q.line is None if q.side in {"yes", "no"} else isinstance(q.line, (int, float)) and math.isfinite(q.line))
                     and (q.event_id, q.player.casefold(), q.market.casefold(), start) in contracts)
            if not valid:
                diagnostics["rejected"] += 1
                continue
            age = (now-updated).total_seconds()/3600
            if age > 72:
                continue
            if age >= 4:
                diagnostics["expired"] += 1
                kept.append(replace(q, quote_status="expired"))
                continue
            status = "retained" if q.quote_status == "retained" else "reference" if q.reference_only else "observed"
            diagnostics[status] += 1
            kept.append(q)
            usable.append(q)
        except (ValueError, TypeError, AttributeError, OverflowError):
            diagnostics["rejected"] += 1
    state = {"schema": 1, "checked_at": now.isoformat(), "quotes": [q.to_dict() for q in kept]}
    return usable, state, diagnostics
