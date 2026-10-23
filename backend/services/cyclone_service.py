"""Cyclone risk assessment architecture — no fabricated cyclone events."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen
import json

from config import OPENWEATHER_API_KEY, INDIA_COASTAL_CITIES, CACHE_TTL_SECONDS
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


def _assess_cyclone_conditions(weather: Dict[str, Any]) -> Dict[str, Any]:
    """Assess cyclone-relevant conditions from weather — no fake cyclone events."""
    wind = weather.get("wind", {})
    wind_speed = wind.get("speed")  # m/s
    wind_gust = wind.get("gust")
    pressure = weather.get("main", {}).get("pressure")

    features = {
        "wind_speed_ms": wind_speed,
        "wind_gust_ms": wind_gust,
        "pressure_hpa": pressure,
        "description": (weather.get("weather") or [{}])[0].get("description"),
    }

    if wind_speed is None:
        return {
            "cyclone_score": None,
            "severity": "UNAVAILABLE",
            "features": features,
            "confidence": None,
            "status": "unavailable",
            "message": "Wind data unavailable",
        }

    # Tropical cyclone threshold ~33 m/s sustained; we only flag elevated wind conditions
    severity = "NONE"
    if wind_speed >= 33 or (wind_gust and wind_gust >= 40):
        severity = "HIGH"
    elif wind_speed >= 20 or (wind_gust and wind_gust >= 25):
        severity = "ELEVATED"
    elif wind_speed >= 13:
        severity = "MONITOR"

    cyclone_score = None  # No ML model — score stays null
    status = "none_detected" if severity == "NONE" else "conditions_elevated"

    return {
        "cyclone_score": cyclone_score,
        "severity": severity,
        "features": features,
        "confidence": "medium" if severity != "NONE" else "high",
        "status": status,
        "message": (
            "No active cyclone detected; showing wind/pressure conditions only"
            if severity != "HIGH"
            else "Elevated wind conditions detected — monitor IMD advisories"
        ),
    }


def assess_coastal_cyclone(city: Dict[str, Any]) -> Dict[str, Any]:
    weather = _fetch_weather(city["lat"], city["lon"])
    base = {
        "disaster_type": "cyclone",
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
            "cyclone_score": None,
            "score": None,
            "features": {},
            "timestamp": None,
            "confidence": None,
        }

    assessment = _assess_cyclone_conditions(weather)
    ts = weather.get("dt")
    return {
        **base,
        **assessment,
        "score": assessment["cyclone_score"],
        "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None,
    }


def get_india_cyclones() -> Dict[str, Any]:
    def fetch():
        results = [assess_coastal_cyclone(c) for c in INDIA_COASTAL_CITIES]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "OpenWeather",
            "count": len(results),
            "cyclones": results,
            "note": "No fabricated cyclone events; wind/pressure conditions from OpenWeather",
        }

    return cached_fetch("cyclones_india", CACHE_TTL_SECONDS, fetch)
