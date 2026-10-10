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
from .parlay_history import update as update_parlay_history
from .qualified import evaluate_quotes, evaluate_quotes_against_projections, merge_boards, select_portfolio, eligible_book_key
from .providers.covers import CoversProvider
from .providers.draftkings_network import DraftKingsNetworkProvider
from .price_store import recover
from .providers.espn_recovered import EspnProjectionProvider as RecoveredProjectionProvider
from . import accuracy as projection_accuracy
from .providers.espn import EspnProjectionProvider
from .providers.espn_props import EspnPropLines
from .providers.espn_injuries import EspnInjuries
from .grade import Grader
from .providers.odds_api_io import OddsApiIoProvider
from .providers.the_odds_api import TheOddsApiProvider


ROOT = Path(__file__).resolve().parents[1]


def load_settings() -> dict[str, Any]:
    return json.loads((ROOT / "config" / "settings.json").read_text())


def load_qualification_settings():
    config = json.loads((ROOT / "config/qualification.json").read_text())
    config["fetch"]["lookahead_days"] = load_settings()["fetch"]["lookahead_days"]
    return config


def _write_json(name: str, value: Any) -> None:
    destination = ROOT / "site" / "data" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=False, allow_nan=False) + "\n")
    temporary.replace(destination)


def build() -> dict[str, Any]:
    settings = load_settings()
    qualification = load_qualification_settings()
    primary_key = os.getenv("ODDS_API_IO_KEY", "").strip()
    secondary_key = os.getenv("THE_ODDS_API_KEY", "").strip()
    primary = OddsApiIoProvider(primary_key, settings) if primary_key else None
    secondary = TheOddsApiProvider(secondary_key, settings) if secondary_key else None
    espn = EspnProjectionProvider(settings)
    projections_provider = RecoveredProjectionProvider(qualification)
    espn_prefetch: dict[str, tuple[list[Any], str | None]] = {}
    def fetch_keyless(sport_name: str) -> tuple[str, list[Any], str | None]:
        try:
            return sport_name, projections_provider.fetch(sport_name), None
        except ProviderError as exc:
            return sport_name, [], str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for sport_name, rows, error in pool.map(fetch_keyless, settings["sports"]):
            espn_prefetch[sport_name] = (rows, error)

    quotes = []
    projections = []
    source_by_sport: dict[str, dict[str, Any]] = {}
    price_sources = {}
    failed_sources = set()
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
                sport_projections = projections_provider.fetch(sport)
            except ProviderError as exc:
                errors.append(str(exc))
        source = projections_provider.name if sport_projections else "No source available"
        if sport_projections:
            covers = CoversProvider(qualification)
            try:
                sport_quotes = covers.fetch(sport, sport_projections)
                if sport_quotes: source = "Covers public comparison + ESPN regular-season projections"
                price_sources[covers.name] = {"status": "available" if sport_quotes else "empty", "quotes": len(sport_quotes), **covers.diagnostics}
            except ProviderError as exc:
                errors.append(str(exc))
                failed_sources.add(covers.name)
                price_sources[covers.name] = {"status": "unavailable", "error": str(exc), **covers.diagnostics}
            fallback = DraftKingsNetworkProvider(qualification)
            if not sport_quotes:
                try:
                    sport_quotes = fallback.fetch(sport, sport_projections)
                    if sport_quotes: source = fallback.name + " + ESPN regular-season projections"
                    price_sources[fallback.name] = {"status": "reference" if sport_quotes else "empty", "quotes": len(sport_quotes), **fallback.diagnostics}
                except ProviderError as exc:
                    errors.append(str(exc))
                    failed_sources.add(fallback.name)
                    price_sources[fallback.name] = {"status": "unavailable", "error": str(exc), **fallback.diagnostics}
            else:
                price_sources[fallback.name] = {"status": "standby", "quotes": 0}

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

    if not projections and any(info["errors"] for info in source_by_sport.values()):
        raise ProviderError("Projection refresh failed; previous published data retained")
    quotes = [q for q in quotes if eligible_book_key(q.book, qualification)]
    cache_path = ROOT / "state/price_quotes.json"
    try:
        previous_quotes = json.loads(cache_path.read_text())
    except (OSError, ValueError):
        # The last published feed is a safe bootstrap; its timestamps are retained.
        try:
            previous_quotes = {"quotes": json.loads((ROOT / "site/data/quotes.json").read_text())}
        except (OSError, ValueError):
            previous_quotes = {}
    quotes, quote_state, quote_health = recover(quotes, previous_quotes, projections, qualification, failed_sources, dt.datetime.now(dt.timezone.utc))
    board = select_portfolio(merge_boards(
        evaluate_quotes(quotes, qualification),
        evaluate_quotes_against_projections(quotes, projections, qualification),
    ), qualification)
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
    legs = build_legs(
        board,
        projections,
        settings,
        book_lines,
        injuries,
        grader.calibration(),
    )
    parlays = build_parlays(legs, settings)
    # Every published leg is frozen, including unpriced research. Projections
    # and actual priced calls retain separate error/return metrics.
    grader.snapshot(legs)
    accuracy = grader.run()
    parlay_record = update_parlay_history(ROOT, parlays['tickets'])
    history_errors = []
    projection_accuracy.update(ROOT, board, projections, history_errors,
                               max_odds_age_hours=qualification["projection_model"]["max_odds_age_hours"])
    if history_errors:
        source_by_sport.setdefault("NFL", {}).setdefault("errors", []).extend(history_errors)
    projection_rows = [row.to_dict() for row in projections]
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    meta = {
        "generated_at": now,
        "provider_priority": ["Covers public comparison (no key)", "DraftKings Network public reference (no key)", "Optional odds providers", "ESPN regular-season statistics"],
        "target_book": settings["bookmakers"]["target"],
        "keyless_fallback": True,
        "configured": {
            "odds_api_io": bool(primary_key),
            "the_odds_api": bool(secondary_key),
            "espn_keyless": True,
            "covers_keyless": True,
            "draftkings_network_keyless": True
        },
        "counts": {
            "priced_quotes": len(quotes),
            "eligible_priced_quotes": len(quotes),
            "qualified_options": sum(row["tier"] != "PASS" for row in board),
            "held_options": sum(bool(row.get("held")) for row in board),
            "board": len(board),
            "actionable": sum(row["tier"] != "PASS" and not row.get("held") for row in board),
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
            "If verified keyless prices are unavailable, keep model-price scenarios labeled research. Optional API keys are never required.",
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
    meta["parlay_record"] = parlay_record
    meta["max_odds_age_hours"] = qualification["projection_model"]["max_odds_age_hours"]
    meta["price_source_status"] = "available" if quote_health["observed"] else "retained" if quote_health["retained"] else "reference" if quote_health["reference"] else "unavailable"
    meta["quote_health"] = {**quote_health, "sources": price_sources}
    reasons = {}
    for row in board:
        reason = row.get("reason") or "No reason supplied"
        category = "retained / confirmation" if row.get("quote_status", "observed") != "observed" else "reference / confirmation" if row.get("reference_only") else "qualified" if row.get("tier") != "PASS" and not row.get("held") else "portfolio hold" if row.get("held") else "insufficient sample" if "sample" in reason.lower() else "insufficient edge / model filters"
        reasons[category] = reasons.get(category, 0) + 1
    meta["quote_health"]["board_reasons"] = reasons
    market_coverage = {}
    for projection in projections:
        group = market_coverage.setdefault(projection.market, {"projections": 0, "observed": 0, "retained": 0, "reference": 0, "expired": 0, "qualified": 0})
        group["projections"] += 1
    for data in quote_state["quotes"]:
        group = market_coverage.setdefault(data["market"], {"projections": 0, "observed": 0, "retained": 0, "reference": 0, "expired": 0, "qualified": 0})
        status = "expired" if data["quote_status"] == "expired" else "retained" if data["quote_status"] == "retained" else "reference" if data["reference_only"] else "observed"
        group[status] += 1
    for row in board:
        if row.get("tier") != "PASS" and not row.get("held"):
            market_coverage[row["market"]]["qualified"] += 1
    meta["quote_health"]["markets"] = market_coverage
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
    # Preserve every eligible observed offer for exact-line comparison. Portfolio
    # selection deliberately chooses one contract; comparison must not invent books.
    _write_json("quotes.json", [quote.to_dict() for quote in quotes])
    _write_json("projections.json", projection_rows)
    _write_json("meta.json", meta)
    _write_json("quote-history.json", quote_state)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_temp = cache_path.with_suffix(".json.tmp")
    cache_temp.write_text(json.dumps(quote_state, indent=2, allow_nan=False) + "\n")
    cache_temp.replace(cache_path)
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
