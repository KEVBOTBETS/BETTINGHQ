"""Grade published prop legs against the real box score, then measure the model.

Every refresh writes a snapshot of the legs the site actually showed (the parlay
legs and the top of each cheat sheet). Once those games are final this module
reads ESPN's box score, marks each leg win/loss/push, and turns the record into a
calibration number: if legs the model calls 60% only land 48%, the model is told
to stop claiming 60%.
"""
from __future__ import annotations

import datetime as dt
import json
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
                if not player:
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
        return ("Win" if actual >= 1 else "Loss"), actual
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


class Grader:
    def __init__(self, root: Path, settings: dict[str, Any]) -> None:
        self.root = Path(root)
        self.settings = settings
        self.client = JsonClient("ESPN box score", SITE_URL, timeout=20)
        self.history = self.root / "site" / "data" / "history"
        self.graded_path = self.root / "site" / "data" / "graded.json"
        self.accuracy_path = self.root / "site" / "data" / "accuracy.json"

    def snapshot(self, legs: list[dict[str, Any]], day: str) -> Path:
        """Record what the site is showing, so it can be graded later."""
        self.history.mkdir(parents=True, exist_ok=True)
        keep = [
            {
                "id": leg.get("id"), "event_id": leg.get("event_id"), "player": leg.get("player"),
                "market": leg.get("market"), "side": leg.get("side"), "line": leg.get("line"),
                "model_prob": leg.get("model_prob"), "price_american": leg.get("price_american"),
                "line_source": leg.get("line_source"), "start_time": leg.get("start_time"),
                "matchup": leg.get("matchup"),
            }
            for leg in legs
        ]
        path = self.history / f"{day}.json"
        path.write_text(json.dumps({"day": day, "legs": keep}, indent=1) + "\n")
        return path

    def _read(self, path: Path, fallback: Any) -> Any:
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return fallback

    def run(self, max_days: int = 21) -> dict[str, Any]:
        """Grade any snapshot leg whose game has finished, then refresh the accuracy file."""
        graded: list[dict[str, Any]] = self._read(self.graded_path, [])
        done = {(row.get("day"), row.get("id")) for row in graded}
        summaries: dict[str, dict[tuple[str, str], float] | None] = {}
        days = sorted(path for path in self.history.glob("*.json"))[-max_days:]
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        for path in days:
            snapshot = self._read(path, {})
            day = str(snapshot.get("day") or path.stem)
            for leg in snapshot.get("legs") or []:
                if (day, leg.get("id")) in done:
                    continue
                if str(leg.get("start_time") or "") > now:
                    continue
                event_id = str(leg.get("event_id") or "")
                if not event_id.isdigit():
                    continue
                if event_id not in summaries:
                    try:
                        summary = self.client.get("/summary", {"event": event_id}, retries=1)
                    except ProviderError:
                        summary = None
                    status = (((summary or {}).get("header") or {}).get("competitions") or [{}])[0]
                    completed = bool(((status.get("status") or {}).get("type") or {}).get("completed"))
                    summaries[event_id] = market_values(summary) if (summary and completed) else None
                values = summaries[event_id]
                if not values:
                    continue
                outcome = grade_leg(leg, values)
                if not outcome:
                    continue
                result, actual = outcome
                graded.append({**leg, "day": day, "result": result, "actual": actual, "graded_at": now})
                done.add((day, leg.get("id")))
        accuracy = accuracy_from(graded)
        self.graded_path.write_text(json.dumps(graded[-5000:], indent=1) + "\n")
        self.accuracy_path.write_text(json.dumps(accuracy, indent=1) + "\n")
        return accuracy

    def calibration(self) -> float:
        accuracy = self._read(self.accuracy_path, {})
        if not accuracy.get("calibration_active"):
            return 1.0
        return float(accuracy.get("calibration_shrink") or 1.0)
