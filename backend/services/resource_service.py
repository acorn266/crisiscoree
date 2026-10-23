"""Hospital and shelter lookup via OpenStreetMap Overpass API."""
import json
import math
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import CACHE_TTL_SECONDS
from services.cache_utils import get_cached, set_cached

# Free public Overpass instances, tried in order until one answers
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_TIMEOUT_SECONDS = 15
# Failed lookups are cached briefly so a dead mirror doesn't slow every page load
FAILED_LOOKUP_TTL_SECONDS = 120


def _overpass_post(query: str) -> Dict[str, Any]:
    """POST a query to the first Overpass mirror that responds; raises if all fail."""
    last_error: Exception = RuntimeError("no Overpass endpoints configured")
    for url in OVERPASS_URLS:
        try:
            req = Request(
                url,
                data=urlencode({"data": query}).encode("utf-8"),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "CrisisCore-Disaster-Preparedness/2.0",
                },
                method="POST",
            )
            with urlopen(req, timeout=OVERPASS_TIMEOUT_SECONDS) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[Overpass] {url} failed: {type(e).__name__}: {e}")
            last_error = e
    raise last_error


def _cached_lookup(cache_key: str, fetch) -> Dict[str, Any]:
    cached = get_cached(cache_key, CACHE_TTL_SECONDS)
    if cached is not None:
        return cached
    result = fetch()
    ttl = CACHE_TTL_SECONDS if result.get("status") == "ok" else FAILED_LOOKUP_TTL_SECONDS
    set_cached(cache_key, result, ttl)
    return result


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def _overpass_query(lat: float, lon: float, amenity: str, radius_m: int = 10000) -> List[Dict]:
    query = f"""
    [out:json][timeout:15];
    (
      node["amenity"="{amenity}"](around:{radius_m},{lat},{lon});
      way["amenity"="{amenity}"](around:{radius_m},{lat},{lon});
    );
    out center 30;
    """
    try:
        data = _overpass_post(query)
    except Exception as e:
        print(f"[Overpass] {amenity} lookup failed: {type(e).__name__}: {e}")
        return []

    results = []
    for el in data.get("elements", []):
        el_lat = el.get("lat") or (el.get("center") or {}).get("lat")
        el_lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if el_lat is None or el_lon is None:
            continue
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("operator") or f"{amenity.title()} #{el.get('id')}"
        dist = _haversine_km(lat, lon, el_lat, el_lon)
        results.append({
            "id": str(el.get("id")),
            "name": name,
            "lat": el_lat,
            "lon": el_lon,
            "distance_km": round(dist, 1),
            "amenity": amenity,
            "source": "OpenStreetMap",
        })

    results.sort(key=lambda x: x["distance_km"])
    return results

def _overpass_bbox_query(
    south: float,
    west: float,
    north: float,
    east: float,
    amenity: str,
    limit: int = 100,
) -> List[Dict]:

    query = f"""
    [out:json][timeout:15];
    (
      node["amenity"="{amenity}"]({south},{west},{north},{east});
      way["amenity"="{amenity}"]({south},{west},{north},{east});
    );
    out center {limit};
    """

    try:
        data = _overpass_post(query)

        results = []

        for el in data.get("elements", []):
            el_lat = el.get("lat") or (el.get("center") or {}).get("lat")
            el_lon = el.get("lon") or (el.get("center") or {}).get("lon")

            if el_lat is None or el_lon is None:
                continue

            tags = el.get("tags", {})

            name = (
                tags.get("name")
                or tags.get("operator")
                or f"{amenity.title()} #{el.get('id')}"
            )

            results.append({
                "id": str(el.get("id")),
                "name": name,
                "lat": el_lat,
                "lon": el_lon,
                "amenity": amenity,
                "source": "OpenStreetMap",
            })

        return results

    except Exception as e:
        print(
            f"[Overpass BBOX] {amenity} lookup failed: "
            f"{type(e).__name__}: {e}"
        )
        return []

def get_hospitals_in_bbox(
    south: float,
    west: float,
    north: float,
    east: float,
) -> Dict[str, Any]:

    cache_key = (
        f"hospitals_bbox_"
        f"{south:.2f}_{west:.2f}_{north:.2f}_{east:.2f}"
    )

    def fetch():
        items = _overpass_bbox_query(
            south=south,
            west=west,
            north=north,
            east=east,
            amenity="hospital",
            limit=100,
        )

        return {
            "status": "ok" if items else "unavailable",
            "count": len(items),
            "hospitals": items,
            "source": "OpenStreetMap",
        }

    return _cached_lookup(cache_key, fetch)


def get_shelters_in_bbox(
    south: float,
    west: float,
    north: float,
    east: float,
) -> Dict[str, Any]:

    cache_key = (
        f"shelters_bbox_"
        f"{south:.2f}_{west:.2f}_{north:.2f}_{east:.2f}"
    )

    def fetch():

        # Search several OSM amenity types that may represent
        # emergency/community shelter locations.
        shelter_items = []

        for amenity in ["social_facility", "community_centre"]:
            items = _overpass_bbox_query(
                south=south,
                west=west,
                north=north,
                east=east,
                amenity=amenity,
                limit=100,
            )

            for item in items:
                name = item.get("name", "").lower()

                if (
                    "shelter" in name
                    or "relief" in name
                    or "refuge" in name
                    or "emergency" in name
                    or amenity == "community_centre"
                ):
                    shelter_items.append(item)

        # Remove duplicates.
        unique = {}
        for item in shelter_items:
            unique[item["id"]] = item

        shelter_items = list(unique.values())

        return {
            "status": "ok" if shelter_items else "unavailable",
            "count": len(shelter_items),
            "shelters": shelter_items,
            "source": "OpenStreetMap",
        }

    return _cached_lookup(cache_key, fetch)


def get_hospitals(lat: float, lon: float) -> Dict[str, Any]:
    cache_key = f"hospitals_{lat:.2f}_{lon:.2f}"

    def fetch():
        items = _overpass_query(lat, lon, "hospital")
        return {
            "status": "ok" if items else "unavailable",
            "count": len(items),
            "hospitals": items,
            "source": "OpenStreetMap",
        }

    return _cached_lookup(cache_key, fetch)


def get_shelters(lat: float, lon: float) -> Dict[str, Any]:
    cache_key = f"shelters_{lat:.2f}_{lon:.2f}"

    def fetch():
        # OSM uses various tags for emergency shelters
        items = _overpass_query(lat, lon, "social_facility")
        shelter_items = [i for i in items if "shelter" in i.get("name", "").lower()]
        if not shelter_items:
            items = _overpass_query(lat, lon, "community_centre")
            shelter_items = items
        return {
            "status": "ok" if shelter_items else "unavailable",
            "count": len(shelter_items),
            "shelters": shelter_items,
            "source": "OpenStreetMap",
        }

    return _cached_lookup(cache_key, fetch)
