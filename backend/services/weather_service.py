"""OpenWeather service for current weather at a location."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen
import json

from config import (
    OPENWEATHER_API_KEY,
    INDIA_BOUNDS,
    WEATHER_CACHE_TTL_SECONDS,
    WEATHER_MAX_WORKERS,
)
from services.cache_utils import cached_fetch


def _fetch_weather_uncached(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    params = urlencode({
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    })
    url = f"https://api.openweathermap.org/data/2.5/weather?{params}"
    try:
        with urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if data.get("cod") == 200 else None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        print(f"[OpenWeather] {lat:.2f},{lon:.2f} failed: {type(e).__name__}: {e}")
        return None


def fetch_weather(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Raw OpenWeather response, cached per location (shared by all services)."""
    if not OPENWEATHER_API_KEY:
        return None
    return cached_fetch(
        f"owm_raw_{lat:.2f}_{lon:.2f}",
        WEATHER_CACHE_TTL_SECONDS,
        lambda: _fetch_weather_uncached(lat, lon),
    )


def map_parallel(fn: Callable[[Any], Any], items: Iterable[Any]) -> List[Any]:
    """Run fn over items concurrently (bounded), preserving order."""
    items = list(items)
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(WEATHER_MAX_WORKERS, len(items))) as pool:
        return list(pool.map(fn, items))


def get_weather(lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
    center = INDIA_BOUNDS["center"]
    lat = lat if lat is not None else center["lat"]
    lon = lon if lon is not None else center["lon"]
    cache_key = f"weather_{lat:.2f}_{lon:.2f}"

    def fetch():
        data = fetch_weather(lat, lon)
        if data is None:
            return None  # not cached, so the next request retries

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

    result = cached_fetch(cache_key, WEATHER_CACHE_TTL_SECONDS, fetch)
    if result is None:
        return {
            "status": "unavailable",
            "lat": lat,
            "lon": lon,
            "source": "OpenWeather",
            "message": (
                "Weather data unavailable"
                if OPENWEATHER_API_KEY
                else "OPENWEATHER_API_KEY not set in backend/.env"
            ),
        }
    return result
