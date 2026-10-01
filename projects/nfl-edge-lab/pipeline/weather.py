"""
Kickoff weather, fetched automatically for every venue on the board.

Source is Open-Meteo: keyless, free, no account, no quota worth worrying about,
and it will happily answer for sixteen stadiums in a single request. That last
part matters -- the whole slate costs one HTTP call, so this can run on every
scheduled refresh instead of once a week.

What the model does with it is deliberately narrow.

WIND is the only weather variable with a large, repeatable effect on NFL scoring.
It shortens the passing game and it wrecks the kicking game at the same time,
which is why totals in a 20 mph crosswind land several points under their
still-air equivalent. Rain and cold get small adjustments; the television
narrative around them is far bigger than the effect in the data. Snow gets a
real one, mostly because it comes with wind and a slow field.

Roof handling is explicit rather than trusting ESPN's `indoor` flag alone: a
fixed dome ignores weather entirely, a retractable roof gets half the
adjustment (the roof is usually closed exactly when the weather would have
mattered), and a canopy stadium is treated as outdoors with the wind damped.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from typing import Any

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.open-meteo.com/v1/forecast"
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"

HOURLY = ("temperature_2m,apparent_temperature,precipitation_probability,precipitation,"
          "rain,snowfall,wind_speed_10m,wind_gusts_10m,cloud_cover,weather_code")

WMO = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Freezing fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain",
    67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Rain showers", 81: "Rain showers", 82: "Violent showers",
    85: "Snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
    96: "Thunderstorm, hail", 99: "Thunderstorm, hail",
}

ROOF_FACTOR = {"dome": 0.0, "retractable": 0.5, "canopy": 0.85, "open": 1.0}


def load_venues() -> dict:
    with open(os.path.join(ROOT, "config", "venues.json"), encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Locating a venue
# --------------------------------------------------------------------------- #

def venue_key(game: dict, venues: dict) -> dict | None:
    """
    Coordinates and roof type for a game's venue.

    Three chances to find it: the venue name we shipped, the home team's usual
    stadium, and finally a one-time geocode of the venue city. The third exists
    for the games this file cannot anticipate -- an international fixture in a
    stadium the NFL has never used before, a hurricane relocation, a neutral-site
    playoff game.
    """
    vs = venues.get("venues") or {}
    name = (game.get("venue") or "").strip().lower()
    if name and name in vs:
        return {**vs[name], "matched": "venue"}
    # Fuzzy: ESPN occasionally decorates a name ("Wembley Stadium (London)").
    for key, val in vs.items():
        if name and (key in name or name in key):
            return {**val, "matched": "venue~"}
    abbr = (game.get("home") or {}).get("abbr")
    home_key = (venues.get("by_team") or {}).get(abbr)
    if home_key and home_key in vs and not game.get("neutral"):
        return {**vs[home_key], "matched": "team"}
    return None


def geocode(city: str, region: str | None, cache: dict) -> dict | None:
    """Look a city up once, then remember it forever in state/geo.json."""
    key = f"{city}|{region or ''}".lower()
    if key in cache:
        return cache[key]
    try:
        r = requests.get(GEOCODE, params={"name": city, "count": 1, "language": "en"}, timeout=20)
        results = (r.json() or {}).get("results") or []
    except Exception:  # noqa: BLE001
        results = []
    hit = None
    if results:
        hit = {"lat": results[0]["latitude"], "lon": results[0]["longitude"],
               "roof": "open", "matched": "geocode"}
    cache[key] = hit
    return hit


# --------------------------------------------------------------------------- #
# Forecast
# --------------------------------------------------------------------------- #

def _round_key(lat: float, lon: float) -> str:
    return f"{round(float(lat), 3)},{round(float(lon), 3)}"


def fetch_forecasts(points: list[tuple[float, float]], days: int = 16) -> dict[str, dict]:
    """
    One request for every stadium on the board.

    Open-Meteo accepts comma-separated coordinate lists and answers with one
    block per point in the same order, so sixteen venues cost one call. If the
    batch form ever changes shape the single-point fallback still works.
    """
    if not points:
        return {}
    uniq: list[tuple[float, float]] = []
    for p in points:
        if p not in uniq:
            uniq.append(p)
    params = {
        "latitude": ",".join(str(p[0]) for p in uniq),
        "longitude": ",".join(str(p[1]) for p in uniq),
        "hourly": HOURLY,
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "UTC",
        "forecast_days": max(1, min(int(days), 16)),
    }
    try:
        r = requests.get(API, params=params, timeout=45)
        r.raise_for_status()
        payload: Any = r.json()
    except Exception as exc:  # noqa: BLE001
        print(f"  ! weather fetch: {type(exc).__name__}: {exc}")
        return {}
    blocks = payload if isinstance(payload, list) else [payload]
    out: dict[str, dict] = {}
    for point, block in zip(uniq, blocks):
        if isinstance(block, dict) and block.get("hourly"):
            out[_round_key(*point)] = {**block["hourly"], "_source": "Open-Meteo"}
    return out


def nws_hourly(properties: dict, now=None) -> dict | None:
    """Convert official hourly periods; unknown gust/rain amounts remain unknown."""
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        generated = dt.datetime.fromisoformat(properties['generatedAt'].replace('Z', '+00:00'))
        if not 0 <= (now-generated).total_seconds() <= 6*3600: return None
    except (KeyError, ValueError, TypeError): return None
    result = {'time': [], 'temperature_2m': [], 'wind_speed_10m': [],
              'precipitation_probability': [], '_source': 'National Weather Service',
              '_generated_at': generated.isoformat(), '_conditions': []}
    for period in properties.get('periods', []):
        try:
            start = dt.datetime.fromisoformat(period['startTime']).astimezone(dt.timezone.utc)
            end = dt.datetime.fromisoformat(period['endTime']).astimezone(dt.timezone.utc)
            if (end-start).total_seconds() != 3600: continue
            temp = period.get('temperature')
            unit = period.get('temperatureUnit')
            if not isinstance(temp,(int,float)) or unit not in ('F','C'): continue
            temp = temp if unit == 'F' else temp*9/5+32
            speed = str(period.get('windSpeed', ''))
            numbers = re.findall(r'\d+(?:\.\d+)?',speed)
            wind = max(map(float,numbers)) if numbers and speed.endswith(' mph') else 0.0 if speed.lower()=='calm' else None
            probability = (period.get('probabilityOfPrecipitation') or {}).get('value')
            probability = probability if isinstance(probability,(int,float)) and 0<=probability<=100 else None
            result['time'].append(start.replace(tzinfo=None).isoformat())
            result['temperature_2m'].append(round(temp,1))
            result['wind_speed_10m'].append(wind)
            result['precipitation_probability'].append(probability)
            result['_conditions'].append(period.get('shortForecast') or '—')
        except (KeyError, ValueError, TypeError): continue
    return result if result['time'] else None


def fetch_nws(point: tuple) -> dict | None:
    lat, lon = point
    if not (24<=lat<=50 and -130<=lon<=-60): return None
    headers = {'User-Agent': 'KEVBOTBETS-weather (https://kevbotbets.github.io/BETTINGHQ/)',
               'Accept': 'application/geo+json'}
    try:
        response = requests.get(f'https://api.weather.gov/points/{lat},{lon}', headers=headers, timeout=12)
        response.raise_for_status()
        url = response.json().get('properties',{}).get('forecastHourly','')
        parsed = urlparse(url)
        if parsed.scheme!='https' or parsed.netloc!='api.weather.gov': return None
        response = requests.get(url,headers=headers,timeout=12)
        response.raise_for_status()
        return nws_hourly(response.json().get('properties',{}))
    except (requests.RequestException, ValueError, TypeError): return None


def at_kickoff(hourly: dict, kickoff_utc: str) -> dict | None:
    """Pull the forecast hour closest to kickoff out of the hourly series."""
    times = (hourly or {}).get("time") or []
    if not times:
        return None
    try:
        ko = dt.datetime.fromisoformat(kickoff_utc.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    ko = ko.astimezone(dt.timezone.utc).replace(tzinfo=None)
    best_i, best_gap = None, None
    for i, t in enumerate(times):
        try:
            ts = dt.datetime.fromisoformat(t.replace("Z", ""))
        except ValueError:
            continue
        gap = abs((ts - ko).total_seconds())
        if best_gap is None or gap < best_gap:
            best_i, best_gap = i, gap
    if best_i is None or best_gap is None or best_gap > (3600 if hourly.get("_source") == "National Weather Service" else 6 * 3600):
        return None

    if hourly.get("_source") == "National Weather Service":
        hour = dt.datetime.fromisoformat(times[best_i])
        if not hour <= ko < hour + dt.timedelta(hours=1): return None

    def val(field: str):
        arr = hourly.get(field) or []
        return arr[best_i] if best_i < len(arr) else None

    code = val("weather_code")
    return {
        "time_utc": times[best_i],
        "temp_f": val("temperature_2m"),
        "feels_f": val("apparent_temperature"),
        "wind_mph": val("wind_speed_10m"),
        "gust_mph": val("wind_gusts_10m"),
        "precip_prob": val("precipitation_probability"),
        "precip_in": val("precipitation"),
        "snow_in": val("snowfall"),
        "cloud_pct": val("cloud_cover"),
        "code": code,
        "condition": val("_conditions") or (WMO.get(int(code), "—") if code is not None else "—"),
        "source": hourly.get("_source", "Open-Meteo"),
        "source_generated_at": hourly.get("_generated_at"),
    }


# --------------------------------------------------------------------------- #
# Model adjustment
# --------------------------------------------------------------------------- #

def adjustment(fc: dict | None, roof: str, cfg: dict) -> dict:
    """
    Turn a forecast into a points adjustment on the projected total.

    Returns the adjustment and the human-readable reasons behind it, because a
    number that moves a line without saying why is worse than no number at all.
    """
    w = cfg.get("weather") or {}
    result = {"total_adj": 0.0, "margin_adj": 0.0, "reasons": [], "roof": roof,
              "applied": False}
    if not w.get("enabled", True) or not fc:
        return result
    factor = ROOF_FACTOR.get(roof, 1.0)
    if factor <= 0:
        result["reasons"].append("Indoors — weather ignored")
        return result

    total = 0.0
    wind = fc.get("gust_mph") or fc.get("wind_mph") or 0.0
    steady = fc.get("wind_mph") or 0.0
    for threshold, points in sorted(w.get("wind_thresholds") or [], key=lambda x: x[0]):
        if steady >= float(threshold) or wind >= float(threshold) + 6:
            total = float(points)
    if total:
        gust_note = f" (gusts {fc['gust_mph']:.0f})" if fc.get("gust_mph") is not None else " (gust forecast unavailable)"
        result["reasons"].append(f"Wind {steady:.0f} mph{gust_note}")

    snow = fc.get("snow_in") or 0.0
    if snow and snow > 0.05:
        total += float(w.get("snow_total_adj", -2.0))
        result["reasons"].append("Snow at kickoff")
    elif (fc.get("precip_prob") or 0) >= float(w.get("precip_prob_threshold", 55)):
        total += float(w.get("precip_total_adj", -1.0))
        result["reasons"].append(f"{fc.get('precip_prob'):.0f}% chance of rain")

    temp = fc.get("temp_f")
    if temp is not None:
        if temp <= float(w.get("cold_temp_f", 20)):
            total += float(w.get("cold_total_adj", -1.2))
            result["reasons"].append(f"{temp:.0f}°F")
        elif temp >= float(w.get("heat_temp_f", 92)):
            total += float(w.get("heat_total_adj", -0.5))
            result["reasons"].append(f"{temp:.0f}°F")

    result["total_adj"] = round(total * factor, 2)
    result["applied"] = result["total_adj"] != 0.0
    if factor < 1.0 and result["applied"]:
        result["reasons"].append(f"{roof} roof — effect halved" if roof == "retractable"
                                 else f"{roof} — wind damped")
    return result


# --------------------------------------------------------------------------- #

def build_for_games(games: list[dict], cfg: dict, geo_cache: dict) -> dict[str, dict]:
    """Forecast + adjustment for every game we can locate. Keyed by game_id."""
    if not (cfg.get("weather") or {}).get("enabled", True):
        return {}
    venues = load_venues()
    located: dict[str, dict] = {}
    points: list[tuple[float, float]] = []
    for g in games:
        loc = venue_key(g, venues)
        if not loc and g.get("venue_city"):
            loc = geocode(g["venue_city"], g.get("venue_state"), geo_cache)
        if not loc:
            continue
        roof = "dome" if (g.get("indoor") and loc.get("roof") == "open") else loc.get("roof", "open")
        located[g["game_id"]] = {**loc, "roof": roof}
        points.append((round(float(loc["lat"]), 3), round(float(loc["lon"]), 3)))

    series = fetch_forecasts(points, days=int((cfg.get("weather") or {}).get("forecast_days", 16)))

    # Request NWS only for near-term outdoor kickoffs without primary coverage.
    now = dt.datetime.now(dt.timezone.utc)
    missing = set()
    for g in games:
        loc = located.get(g['game_id'])
        try: kickoff = dt.datetime.fromisoformat(g.get('date_utc','').replace('Z','+00:00'))
        except (ValueError, TypeError): continue
        if not loc or loc['roof']=='dome' or not 0 <= (kickoff-now).total_seconds() <= 7*86400: continue
        point = (round(float(loc['lat']),3),round(float(loc['lon']),3))
        hourly = series.get(_round_key(*point))
        if not hourly or not at_kickoff(hourly,g['date_utc']): missing.add(point)
    with ThreadPoolExecutor(max_workers=4) as pool:
        fallback_series = dict(zip(sorted(missing),pool.map(fetch_nws,sorted(missing))))

    out: dict[str, dict] = {}
    for g in games:
        loc = located.get(g["game_id"])
        if not loc:
            continue
        hourly = series.get(_round_key(loc["lat"], loc["lon"]))
        fc = at_kickoff(hourly, g.get("date_utc") or "") if hourly else None
        if not fc:
            fallback = fallback_series.get((round(float(loc["lat"]),3),round(float(loc["lon"]),3)))
            fc = at_kickoff(fallback,g.get("date_utc") or "") if fallback else None
        adj = adjustment(fc, loc["roof"], cfg)
        out[g["game_id"]] = {
            "venue": g.get("venue"),
            "city": g.get("venue_city"),
            "roof": loc["roof"],
            "forecast": fc,
            **adj,
        }
    return out
