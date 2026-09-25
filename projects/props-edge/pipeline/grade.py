"""Freeze every published pregame prop leg and grade final box-score outcomes.

Exact-line audits and one preferred side per event/player/market stay separate.
Calibration is diagnostic; research prices never produce wager returns.
"""
from __future__ import annotations

import datetime as dt
import json
import hashlib
import re
from pathlib import Path
from typing import Any

from .http import JsonClient, ProviderError
from .providers.espn import _canonical_market
from .schema import as_float

SITE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
TOUCHDOWN_PARTS = ("Rushing touchdowns", "Receiving touchdowns")
BUCKETS = [(0.0, 0.35), (0.35, 0.45), (0.45, 0.55), (0.55, 0.65), (0.65, 0.75), (0.75, 1.01)]


def name_key(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z]+", str(value or "")) if part]
    parts = [part for part in parts if part.casefold() not in {"jr", "sr", "ii", "iii", "iv", "v"}]
    return (parts[0][:1] + parts[-1]).casefold() if parts else ""


def market_values(summary: dict[str, Any]) -> dict[tuple[str, str], float]:
    """Every stat in one box score, keyed by player and the market it settles."""
    values: dict[tuple[str, str], float] = {}
    for team_block in ((summary.get("boxscore") or {}).get("players") or []):
        for stat_group in team_block.get("statistics") or []:
            group = str(stat_group.get("type") or stat_group.get("name") or "")
            names = stat_group.get("keys") or stat_group.get("names") or stat_group.get("labels") or []
            for athlete_row in stat_group.get("athletes") or []:
                player = str((athlete_row.get("athlete") or {}).get("displayName") or "")
                if not player or athlete_row.get("didNotPlay") or athlete_row.get("inactive"):
                    continue
                key = name_key(player)
                for name, raw in zip(names, athlete_row.get("stats") or []):
                    combined = re.match(r"^\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*$", str(raw))
                    if "passing" in group.casefold() and combined and "c" in str(name).casefold():
                        values[(key, "Pass completions")] = float(combined.group(1))
                        values[(key, "Pass attempts")] = float(combined.group(2))
                        continue
                    market = _canonical_market("NFL", group, str(name))
                    value = as_float(raw)
                    if market is None or value is None:
                        continue
                    values[(key, market)] = float(value)
    for (player, market) in list(values):
        if market in TOUCHDOWN_PARTS:
            total = sum(values.get((player, part), 0.0) for part in TOUCHDOWN_PARTS)
            values[(player, "Anytime touchdown")] = total
    return values


def grade_leg(leg: dict[str, Any], values: dict[tuple[str, str], float]) -> tuple[str, float] | None:
    """Win, Loss or Push for one leg, with the number the player actually posted."""
    key = (name_key(str(leg.get("player"))), str(leg.get("market")))
    if key not in values:
        return None
    actual = float(values[key])
    side = str(leg.get("side"))
    if str(leg.get("market")) == "Anytime touchdown":
        return ("Win" if (actual >= 1) == (side != "no") else "Loss"), actual
    line = leg.get("line")
    if line is None:
        return None
    line = float(line)
    if actual == line:
        return "Push", actual
    if side == "over":
        return ("Win" if actual > line else "Loss"), actual
    if side == "under":
        return ("Win" if actual < line else "Loss"), actual
    return None


def accuracy_from(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Record, hit rate by confidence bucket, Brier score and the calibration shrink."""
    settled = [row for row in rows if row.get("result") in ("Win", "Loss")]
    wins = sum(row["result"] == "Win" for row in settled)
    pushes = sum(row.get("result") == "Push" for row in rows)
    brier = (
        sum((float(row["model_prob"]) - (1.0 if row["result"] == "Win" else 0.0)) ** 2 for row in settled)
        / len(settled)
        if settled
        else None
    )
    buckets = []
    for low, high in BUCKETS:
        inside = [row for row in settled if low <= float(row["model_prob"]) < high]
        if not inside:
            continue
        predicted = sum(float(row["model_prob"]) for row in inside) / len(inside)
        actual = sum(row["result"] == "Win" for row in inside) / len(inside)
        buckets.append({
            "from": low, "to": high, "legs": len(inside),
            "predicted": round(predicted, 4), "actual": round(actual, 4),
        })
    by_market: dict[str, dict[str, Any]] = {}
    for row in settled:
        entry = by_market.setdefault(str(row.get("market")), {"legs": 0, "wins": 0, "predicted": 0.0})
        entry["legs"] += 1
        entry["wins"] += row["result"] == "Win"
        entry["predicted"] += float(row["model_prob"])
    for entry in by_market.values():
        entry["hit_rate"] = round(entry["wins"] / entry["legs"], 4)
        entry["predicted"] = round(entry["predicted"] / entry["legs"], 4)

    # One number that pulls every probability back toward a coin flip by as much as
    # the record says the model is overconfident. 1.0 means no correction.
    shrink = 1.0
    if len(settled) >= 200:
        predicted_edge = sum(abs(float(row["model_prob"]) - 0.5) for row in settled) / len(settled)
        actual_edge = 0.0
        for row in settled:
            hit = row["result"] == "Win"
            leaned_over = float(row["model_prob"]) >= 0.5
            actual_edge += (1.0 if hit == leaned_over else 0.0)
        actual_edge = abs(actual_edge / len(settled) - 0.5)
        if predicted_edge > 0.01:
            shrink = max(0.4, min(1.0, actual_edge / predicted_edge))
    return {
        "legs": len(rows),
        "settled": len(settled),
        "record": f"{wins}-{len(settled) - wins}" + (f"-{pushes}" if pushes else ""),
        "hit_rate": round(wins / len(settled), 4) if settled else None,
        "average_predicted": round(sum(float(row["model_prob"]) for row in settled) / len(settled), 4) if settled else None,
        "brier": None if brier is None else round(brier, 4),
        "buckets": buckets,
        "by_market": by_market,
        "calibration_shrink": round(shrink, 3),
        "calibration_active": len(settled) >= 200,
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def instant(value):
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(dt.timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def identity(leg):
    """One immutable outcome per event/player/market/side/exact line."""
    fields = [str(leg.get(k) or "") for k in ("event_id", "player", "market", "side")]
    line = leg.get("line")
    fields.append(format(float(line), ".12g") if isinstance(line, (int, float)) else str(line))
    return hashlib.sha256("|".join(fields).encode()).hexdigest()[:24]


class Grader:
    def __init__(self, root: Path, settings: dict[str, Any]) -> None:
        self.root, self.settings = Path(root), settings
        self.client = JsonClient("ESPN box score", SITE_URL, timeout=20)
        self.history = self.root / "site/data/history"
        self.graded_path = self.root / "site/data/graded.json"
        self.accuracy_path = self.root / "site/data/leg-accuracy.json"
        self.state_path = self.root / "state/leg_history.json"

    def _read(self, path, fallback):
        # Corrupt history must stop a refresh, not silently reset its accuracy.
        return json.loads(path.read_text()) if path.exists() else fallback

    def _save(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, indent=1, allow_nan=False) + "\n")
        temporary.replace(path)

    def _state(self):
        state = self._read(self.state_path, {"schema": 2, "records": {}, "legacy_excluded": 0})
        if not state.get("legacy_checked"):
            # Daily legacy files lack a trustworthy capture time. Keep original
            # files untouched and disclose exclusion instead of inventing one.
            old = self._read(self.graded_path, [])
            state["legacy_excluded"] = len(old)
            if old:
                archive = self.root / "state/legacy_leg_results.json"
                if not archive.exists(): self._save(archive, old)
            state["legacy_checked"] = True
        return state

    def snapshot(self, legs, day=None, now=None):
        now = instant(now) if now is not None else dt.datetime.now(dt.timezone.utc)
        if now is None: raise ValueError("Snapshot time must include a timezone")
        state = self._state()
        chosen = {(r["event_id"], r["player"], r["market"]) for r in state["records"].values() if r.get("selected")}
        valid = [r for r in legs if isinstance(r.get("model_prob"), (int, float)) and 0 <= r["model_prob"] <= 1]
        for leg in sorted(valid, key=lambda r: -r["model_prob"]):
            start, captured = instant(leg.get("start_time")), now
            probability = leg.get("model_prob")
            event = str(leg.get("result_event_id") or leg.get("event_id") or "")
            if not start or start <= captured or not event.isdigit(): continue
            if not isinstance(probability, (int, float)) or not 0 <= probability <= 1: continue
            row = {k: leg.get(k) for k in ("player", "team", "market", "side", "line", "model_prob", "price_american", "price_source", "line_source", "book", "start_time", "matchup", "tier", "projection", "samples", "confidence", "updated_at")}
            row.update(event_id=event)
            key = identity(row)
            if key in state["records"]: continue
            group = (event, row["player"], row["market"])
            row.update(id=key, captured_at=captured.isoformat(), version="2026-09-23-frozen-v1", result="Pending", selected=group not in chosen)
            chosen.add(group)
            state["records"][key] = row
        self._save(self.state_path, state)
        return self.state_path

    def run(self, max_days=None, now=None):
        now = instant(now) if now is not None else dt.datetime.now(dt.timezone.utc)
        state = self._state()
        summaries = {}
        for leg in state["records"].values():
            if leg.get("result") != "Pending": continue
            start, captured = instant(leg.get("start_time")), instant(leg.get("captured_at"))
            if not start or not captured or captured >= start or captured > now or start > now: continue
            event = leg["event_id"]
            if event not in summaries:
                try:
                    summary = self.client.get("/summary", {"event": event}, retries=1)
                    comp = ((summary.get("header") or {}).get("competitions") or [{}])[0]
                    status = (comp.get("status") or {}).get("type") or {}
                    summaries[event] = "VOID" if "CANCEL" in str(status.get("name", "")).upper() else market_values(summary) if status.get("completed") else None
                except ProviderError:
                    summaries[event] = None
            values = summaries[event]
            if values == "VOID":
                leg.update(result="Void", graded_at=now.isoformat())
            elif values:
                outcome = grade_leg(leg, values)
                if outcome: leg.update(result=outcome[0], actual=outcome[1], graded_at=now.isoformat())
        rows = list(state["records"].values())
        preferred = [r for r in rows if r.get("selected")]
        accuracy = accuracy_from(preferred)
        # No online feedback fitted on repeatedly corrected outputs. Keep
        # calibration diagnostic until a held-out, versioned fit is validated.
        accuracy.update(calibration_active=False, calibration_shrink=1.0,
                        calibration_note="Calibration is diagnostic only; no automatic refit.",
                        total_logged=len(rows), pending=sum(r["result"] == "Pending" for r in preferred),
                        independent_events=len({r["event_id"] for r in preferred}),
                        legacy_excluded=state.get("legacy_excluded", 0),
                        method="One first pregame preferred leg per event/player/market. Full side/line audit retained separately. No wager ROI at estimated prices.")
        self._save(self.state_path, state)
        self._save(self.graded_path, [r for r in rows if r["result"] != "Pending"])
        self._save(self.root / "site/data/leg-history.json", {"schema": 2, "records": rows})
        self._save(self.accuracy_path, accuracy)
        return accuracy

    def calibration(self):
        return 1.0
