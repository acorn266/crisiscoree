"""USGS real-time earthquake feed for India and surrounding region."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import urlopen
import json

from config import INDIA_BOUNDS, CACHE_TTL_SECONDS
from services.cache_utils import cached_fetch

USGS_QUERY_URL = (
    "https://earthquake.usgs.gov/fdsnws/event/1/query"
    "?format=geojson"
    "&minlatitude={min_lat}&maxlatitude={max_lat}"
    "&minlongitude={min_lon}&maxlongitude={max_lon}"
    "&minmagnitude=2.5"
    "&orderby=time"
    "&limit=200"
)


def _fetch_usgs_events() -> List[Dict[str, Any]]:
    bounds = INDIA_BOUNDS
    url = USGS_QUERY_URL.format(
        min_lat=bounds["southwest"]["lat"],
        max_lat=bounds["northeast"]["lat"],
        min_lon=bounds["southwest"]["lon"],
        max_lon=bounds["northeast"]["lon"],
    )
    try:
        with urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        return [{"status": "unavailable", "error": str(e), "source": "USGS"}]

    events = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [None, None, None])
        lon, lat, depth = (coords + [None, None, None])[:3]
        mag = props.get("mag")
        if lat is None or lon is None or mag is None:
            continue

        severity = "LOW"
        if mag >= 6:
            severity = "HIGH"
        elif mag >= 4.5:
            severity = "MEDIUM"

        events.append({
            "disaster_type": "earthquake",
            "id": feature.get("id"),
            "lat": lat,
            "lon": lon,
            "magnitude": mag,
            "depth_km": depth,
            "place": props.get("place", "Unknown location"),
            "time": props.get("time"),
            "time_iso": datetime.fromtimestamp(
                props.get("time", 0) / 1000, tz=timezone.utc
            ).isoformat() if props.get("time") else None,
            "alert": props.get("alert"),
            "significance": props.get("sig"),
            "status": "detected",
            "severity": severity,
            "score": None,
            "timestamp": props.get("time"),
            "source": "USGS",
            "confidence": "high",
        })
    return events


def get_india_earthquakes() -> Dict[str, Any]:
    def fetch():
        events = _fetch_usgs_events()
        if events and events[0].get("status") == "unavailable":
            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": "USGS",
                "count": 0,
                "earthquakes": [],
                "status": "unavailable",
                "message": events[0].get("error"),
            }
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "USGS",
            "count": len(events),
            "earthquakes": events,
            "status": "ok",
        }

    return cached_fetch("earthquakes_india", CACHE_TTL_SECONDS, fetch)
