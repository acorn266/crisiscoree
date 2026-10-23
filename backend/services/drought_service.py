"""Drought risk assessment using OpenWeather and available environmental data."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
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
            if data.get("cod") != 200:
                return None
            return data
    except (URLError, TimeoutError, json.JSONDecodeError):
        return None


def _compute_drought_indicators(weather: Dict[str, Any]) -> Dict[str, Any]:
    """Compute drought indicators from available weather — no rain==0 shortcut."""
    main = weather.get("main", {})
    rain_1h = weather.get("rain", {}).get("1h", 0)
    rain_3h = weather.get("rain", {}).get("3h", 0)
    temp = main.get("temp")
    humidity = main.get("humidity")
    features = {
        "temperature_c": temp,
        "humidity_pct": humidity,
        "rainfall_1h_mm": rain_1h,
        "rainfall_3h_mm": rain_3h,
        "pressure_hpa": main.get("pressure"),
    }

    # Without historical rainfall baselines, full drought scoring is unavailable
    if temp is None or humidity is None:
        return {
            "drought_score": None,
            "severity": "UNAVAILABLE",
            "contributing_features": features,
            "confidence": None,
            "status": "unavailable",
            "message": "Insufficient weather data for drought assessment",
        }

    # Indicator-based advisory only (not a final ML score)
    stress_indicators = []
    if humidity < 30:
        stress_indicators.append("low_humidity")
    if temp > 38:
        stress_indicators.append("high_temperature")
    if rain_1h == 0 and rain_3h == 0:
        stress_indicators.append("no_recent_rainfall")

    if not stress_indicators:
        advisory = "NONE"
    elif len(stress_indicators) >= 2:
        advisory = "ELEVATED_STRESS"
    else:
        advisory = "MONITOR"

    return {
        "drought_score": None,
        "severity": advisory,
        "contributing_features": {**features, "stress_indicators": stress_indicators},
        "confidence": "low",
        "status": "partial",
        "message": "Drought score requires historical baselines; showing environmental stress indicators only",
    }


def assess_city_drought(city: Dict[str, Any]) -> Dict[str, Any]:
    weather = _fetch_weather(city["lat"], city["lon"])
    base = {
        "disaster_type": "drought",
        "region": city["name"],
        "lat": city["lat"],
        "lon": city["lon"],
        "source": "OpenWeather",
    }
    if weather is None:
        return {
            **base,
            "status": "unavailable",
            "severity": "UNAVAILABLE",
            "drought_score": None,
            "score": None,
            "contributing_features": {},
            "data_timestamp": None,
            "confidence": None,
            "message": "Weather data unavailable",
        }

    indicators = _compute_drought_indicators(weather)
    ts = weather.get("dt")
    return {
        **base,
        "status": indicators["status"],
        "severity": indicators["severity"],
        "drought_score": indicators["drought_score"],
        "score": indicators["drought_score"],
        "contributing_features": indicators["contributing_features"],
        "data_timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None,
        "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None,
        "confidence": indicators["confidence"],
        "message": indicators.get("message"),
    }


def get_india_droughts() -> Dict[str, Any]:
    def fetch():
        results = [assess_city_drought(c) for c in INDIA_WEATHER_CITIES]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "OpenWeather",
            "count": len(results),
            "droughts": results,
        }

    return cached_fetch("droughts_india", CACHE_TTL_SECONDS, fetch)
