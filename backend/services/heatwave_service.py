"""Heatwave risk assessment using OpenWeather data."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen
import json

from config import OPENWEATHER_API_KEY, INDIA_WEATHER_CITIES, CACHE_TTL_SECONDS
from services.cache_utils import cached_fetch


def _fetch_weather(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    if not OPENWEATHER_API_KEY:
        return None
    params = urlencode({
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    })
    url = f"https://api.openweathermap.org/data/2.5/weather?{params}"
    try:
        with urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if data.get("cod") == 200 else None
    except (URLError, TimeoutError, json.JSONDecodeError):
        return None


def _heat_index_c(temp_c: float, humidity: float) -> float:
    """Approximate heat index from temperature (C) and relative humidity."""
    temp_f = temp_c * 9 / 5 + 32
    hi = (
        -42.379 + 2.04901523 * temp_f + 10.14333127 * humidity
        - 0.22475541 * temp_f * humidity
        - 0.00683783 * temp_f ** 2
        - 0.05481717 * humidity ** 2
        + 0.00122874 * temp_f ** 2 * humidity
        + 0.00085282 * temp_f * humidity ** 2
        - 0.00000199 * temp_f ** 2 * humidity ** 2
    )
    return round((hi - 32) * 5 / 9, 1)


def _assess_heat(weather: Dict[str, Any]) -> Dict[str, Any]:
    main = weather.get("main", {})
    temp = main.get("temp")
    feels_like = main.get("feels_like")
    humidity = main.get("humidity")

    if temp is None or humidity is None:
        return {
            "heat_score": None,
            "severity": "UNAVAILABLE",
            "temperature_c": None,
            "features": {},
            "status": "unavailable",
        }

    heat_index = _heat_index_c(temp, humidity)
    effective_temp = feels_like if feels_like is not None else temp

    severity = "NONE"
    if effective_temp >= 45 or heat_index >= 45:
        severity = "EXTREME"
    elif effective_temp >= 40 or heat_index >= 40:
        severity = "HIGH"
    elif effective_temp >= 35 or heat_index >= 37:
        severity = "MODERATE"

    # heat_score as normalized indicator (0-100) derived from real temperature data
    heat_score = min(100, max(0, round((effective_temp - 25) * 4, 1)))

    return {
        "heat_score": heat_score if severity != "NONE" else round(heat_score * 0.5, 1),
        "severity": severity,
        "temperature_c": temp,
        "features": {
            "feels_like_c": feels_like,
            "humidity_pct": humidity,
            "heat_index_c": heat_index,
            "description": (weather.get("weather") or [{}])[0].get("description"),
        },
        "status": "ok" if severity != "NONE" else "none_detected",
    }


def assess_city_heatwave(city: Dict[str, Any]) -> Dict[str, Any]:
    weather = _fetch_weather(city["lat"], city["lon"])
    base = {
        "disaster_type": "heatwave",
        "location": city["name"],
        "lat": city["lat"],
        "lon": city["lon"],
        "source": "OpenWeather",
    }
    if weather is None:
        return {
            **base,
            "status": "unavailable",
            "severity": "UNAVAILABLE",
            "heat_score": None,
            "score": None,
            "temperature": None,
            "features": {},
            "timestamp": None,
        }

    assessment = _assess_heat(weather)
    ts = weather.get("dt")
    return {
        **base,
        **assessment,
        "score": assessment["heat_score"],
        "temperature": assessment["temperature_c"],
        "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None,
    }


def get_india_heatwaves() -> Dict[str, Any]:
    def fetch():
        results = [assess_city_heatwave(c) for c in INDIA_WEATHER_CITIES]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "OpenWeather",
            "count": len(results),
            "heatwaves": results,
        }

    return cached_fetch("heatwaves_india", CACHE_TTL_SECONDS, fetch)
