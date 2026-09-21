from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .http import ProviderError
from .legs import build_legs
from .parlays import build_parlays
from .model import evaluate_quotes, evaluate_quotes_against_projections, merge_boards
from .providers.espn import EspnProjectionProvider
from .providers.espn_props import EspnPropLines
from .providers.espn_injuries import EspnInjuries
from .grade import Grader
from .providers.odds_api_io import OddsApiIoProvider
from .providers.the_odds_api import TheOddsApiProvider


ROOT = Path(__file__).resolve().parents[1]


def load_settings() -> dict[str, Any]:
    return json.loads((ROOT / "config" / "settings.json").read_text())


def _write_json(name: str, value: Any) -> None:
    destination = ROOT / "site" / "data" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, indent=2, sort_keys=False) + "\n")


def build() -> dict[str, Any]:
    settings = load_settings()
    primary_key = os.getenv("ODDS_API_IO_KEY", "").strip()
    secondary_key = os.getenv("THE_ODDS_API_KEY", "").strip()
    primary = OddsApiIoProvider(primary_key, settings) if primary_key else None
    secondary = TheOddsApiProvider(secondary_key, settings) if secondary_key else None
    espn = EspnProjectionProvider(settings)
    espn_prefetch: dict[str, tuple[list[Any], str | None]] = {}
    if True:
        def fetch_keyless(sport_name: str) -> tuple[str, list[Any], str | None]:
            try:
                return sport_name, espn.fetch(sport_name), None
            except ProviderError as exc:
                return sport_name, [], str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            for sport_name, rows, error in pool.map(fetch_keyless, settings["sports"]):
                espn_prefetch[sport_name] = (rows, error)

    quotes = []
    projections = []
    source_by_sport: dict[str, dict[str, Any]] = {}
    feed = settings.get("odds_feed", {})
    window_hours = float(feed.get("window_hours") or 0)
    now = dt.datetime.now(dt.timezone.utc)
    odds_windows: dict[str, Any] = {}
    for sport in settings["sports"]:
        errors: list[str] = []
        sport_quotes = []
        sport_projections = []
        source = None
        # ESPN first: it is keyless, it is needed for the model anyway, and its
        # kickoff times decide whether spending paid odds credits is worth it.
        if sport in espn_prefetch:
            sport_projections, prefetch_error = espn_prefetch[sport]
            if prefetch_error:
                errors.append(prefetch_error)
        else:
            try:
                sport_projections = espn.fetch(sport)
            except ProviderError as exc:
                errors.append(str(exc))
        source = espn.name if sport_projections else "No source available"

        # Only games that have not kicked off yet decide the odds window.
        stamp_now = now.isoformat()
        kickoffs = sorted(
            stamp
            for stamp in (str(row.start_time or "") for row in sport_projections)
            if stamp and stamp > stamp_now
        )
        next_kickoff = kickoffs[0] if kickoffs else None
        hours_away = None
        if next_kickoff:
            try:
                hours_away = (dt.datetime.fromisoformat(next_kickoff) - now).total_seconds() / 3600
            except ValueError:
                hours_away = None
        # A paid key is only spent close to kickoff, when the prices are the ones
        # that will actually be available to bet.
        inside_window = window_hours <= 0 or hours_away is None or hours_away <= window_hours
        odds_windows[sport] = {
            "next_kickoff": next_kickoff,
            "hours_to_kickoff": None if hours_away is None else round(hours_away, 1),
            "window_hours": window_hours,
            "inside_window": bool(inside_window),
        }
        if inside_window:
            for provider in (primary, secondary):
                if not provider or sport_quotes:
                    continue
                try:
                    sport_quotes = provider.fetch(sport)
                    if sport_quotes:
                        source = provider.name
                except ProviderError as exc:
                    errors.append(str(exc))
        quotes.extend(sport_quotes)
        projections.extend(sport_projections)
        source_by_sport[sport] = {
            "source": source,
            "priced_quotes": len(sport_quotes),
            "projections": len(sport_projections),
            "errors": errors,
        }

    # Keyless sportsbook lines: real numbers to score, even with no odds key.
    book_lines: list[dict[str, Any]] = []
    if settings.get("line_feed", {}).get("enabled", True):
        try:
            book_lines = EspnPropLines(settings).fetch(espn.upcoming_events("NFL"))
        except ProviderError as exc:
            for info in source_by_sport.values():
                info["errors"].append(str(exc))
    injuries = EspnInjuries(settings).fetch()
    grader = Grader(ROOT, settings)
    accuracy = grader.run()
    legs = build_legs(
        merge_boards(
            evaluate_quotes(quotes, settings),
            evaluate_quotes_against_projections(quotes, projections, settings),
        ),
        projections,
        settings,
        book_lines,
        injuries,
        grader.calibration(),
    )
    parlays = build_parlays(legs, settings)
    # Snapshot exactly what is published, so the record is of real shown legs.
    shown = {leg["id"]: leg for ticket in parlays["tickets"] for leg in ticket["legs"]}
    for leg in sorted(legs, key=lambda row: -float(row["model_prob"]))[:400]:
        shown.setdefault(leg["id"], leg)
    grader.snapshot(list(shown.values()), dt.datetime.now(dt.timezone.utc).date().isoformat())
    board = merge_boards(
        evaluate_quotes(quotes, settings),
        evaluate_quotes_against_projections(quotes, projections, settings),
    )
    projection_rows = [row.to_dict() for row in projections]
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    meta = {
        "generated_at": now,
        "provider_priority": ["Odds-API.io", "The Odds API", "ESPN public statistics"],
        "target_book": settings["bookmakers"]["target"],
        "keyless_fallback": True,
        "configured": {
            "odds_api_io": bool(primary_key),
            "the_odds_api": bool(secondary_key),
            "espn_keyless": True
        },
        "counts": {
            "priced_quotes": len(quotes),
            "board": len(board),
            "actionable": sum(row["tier"] != "PASS" for row in board),
            "best": sum(row["tier"] == "BEST" for row in board),
            "good": sum(row["tier"] == "GOOD" for row in board),
            "leans": sum(row["tier"] == "LEAN" for row in board),
            "projections": len(projection_rows),
        },
        "source_by_sport": source_by_sport,
        "workflow_url": (
            f"https://github.com/{repository}/actions/workflows/release.yml" if repository else ""
        ),
        "notes": [
            "API credentials are optional and are read only from GitHub Actions secrets.",
            "If both odds providers are unavailable, ESPN schedules and box-score statistics produce projection-only rows.",
            "Action Network and OddsShark are not scraped because automated extraction is blocked or prohibited.",
        ],
    }
    meta["odds_feed"] = {
        "window": odds_windows,
        "markets": list(feed.get("markets") or []),
        "quota": (getattr(secondary, "quota", None) or {}) if secondary else {},
        "line_source": "DraftKings lines via ESPN" if book_lines else None,
    }
    meta["accuracy"] = accuracy
    meta["counts"]["injury_report"] = len(injuries)
    meta["counts"]["ruled_out"] = sum(row.get("blocking") == "yes" for row in injuries.values())
    meta["counts"]["book_lines"] = len(book_lines)
    meta["counts"]["legs_on_book_lines"] = sum(bool(leg.get("line_source")) for leg in legs)
    meta["counts"]["legs"] = len(legs)
    meta["counts"]["book_priced_legs"] = sum(leg["price_source"] == "book" for leg in legs)
    meta["counts"]["parlays"] = len(parlays["tickets"])
    meta["estimated_prices"] = not meta["counts"]["book_priced_legs"]
    _write_json("legs.json", legs)
    _write_json("parlays.json", parlays)
    _write_json("board.json", board)
    _write_json("projections.json", projection_rows)
    _write_json("meta.json", meta)
    return meta


def main() -> None:
    argparse.ArgumentParser(description="Build the Props Edge data files").parse_args()
    meta = build()
    counts = meta["counts"]
    print(
        f"Props Edge refreshed: {counts['actionable']} priced plays, "
        f"{counts.get('legs', 0)} legs, {counts.get('parlays', 0)} parlays, "
        f"{counts['projections']} ESPN projections"
    )


if __name__ == "__main__":
    main()
