"""OpenWeather service for current weather at a location."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen
import json

from config import OPENWEATHER_API_KEY, INDIA_BOUNDS, CACHE_TTL_SECONDS
from services.cache_utils import cached_fetch


def fetch_weather(lat: float, lon: float) -> Optional[Dict[str, Any]]:
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


def get_weather(lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
    center = INDIA_BOUNDS["center"]
    lat = lat if lat is not None else center["lat"]
    lon = lon if lon is not None else center["lon"]
    cache_key = f"weather_{lat:.2f}_{lon:.2f}"

    def fetch():
        data = fetch_weather(lat, lon)
        if data is None:
            return {
                "status": "unavailable",
                "lat": lat,
                "lon": lon,
                "source": "OpenWeather",
                "message": "Weather data unavailable",
            }

        rain = data.get("rain", {})
        main = data.get("main", {})
        wind = data.get("wind", {})
        weather_desc = (data.get("weather") or [{}])[0]

        return {
            "status": "ok",
            "lat": lat,
            "lon": lon,
            "location": data.get("name", "Unknown"),
            "temperature": main.get("temp"),
            "feels_like": main.get("feels_like"),
            "humidity": main.get("humidity"),
            "pressure": main.get("pressure"),
            "rainfall_1h_mm": rain.get("1h", 0),
            "rainfall_3h_mm": rain.get("3h", 0),
            "wind_speed_ms": wind.get("speed"),
            "condition": weather_desc.get("main", "Unknown"),
            "description": weather_desc.get("description", ""),
            "timestamp": datetime.fromtimestamp(
                data.get("dt", 0), tz=timezone.utc
            ).isoformat() if data.get("dt") else None,
            "source": "OpenWeather",
        }

    return cached_fetch(cache_key, min(CACHE_TTL_SECONDS, 600), fetch)
