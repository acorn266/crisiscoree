"""Hospital and shelter lookup via OpenStreetMap Overpass API.

Live Overpass is tried first within a short time budget. If it fails, results come
from saved OpenStreetMap snapshots (backend/data/resource_snapshots/*.json, created by
scripts/fetch_resource_snapshots.py) for the nearest demo area, marked
data_source="snapshot" so the UI can say it is saved data.
"""
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import CACHE_TTL_SECONDS, OVERPASS_LIVE_BUDGET_SECONDS
from services.cache_utils import get_cached, set_cached

# Free public Overpass instances, tried in order until one answers
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
# Failed (or snapshot-served) lookups are cached briefly, then live is retried
FAILED_LOOKUP_TTL_SECONDS = 120

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "resource_snapshots"
# Point lookups only use a snapshot whose area centre is this close
SNAPSHOT_MAX_DISTANCE_KM = 100

POINT_RADIUS_M = 10000
POINT_LIMIT = 30
BBOX_LIMIT = 100
SHELTER_AMENITIES = ("social_facility", "community_centre")
SHELTER_NAME_HINTS = ("shelter", "relief", "refuge", "emergency")


# ---------------------------------------------------------------------------
# Live Overpass
# ---------------------------------------------------------------------------

# After a failed live lookup, skip live Overpass for a while so map panning during an
# outage goes straight to saved snapshots instead of waiting the full budget each time.
LIVE_RETRY_AFTER_SECONDS = 60
_live_down_until = 0.0
_live_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="overpass")


def _overpass_post(query: str) -> Dict[str, Any]:
    """POST to the first mirror that answers within the overall live budget; raises if none do."""
    global _live_down_until
    if time.monotonic() < _live_down_until:
        raise RuntimeError("live Overpass recently unavailable; using saved data")
    try:
        # urlopen's timeout applies per socket read, so enforce the overall budget here
        return _live_pool.submit(_overpass_post_live, query).result(timeout=OVERPASS_LIVE_BUDGET_SECONDS + 0.5)
    except FutureTimeout:
        _live_down_until = time.monotonic() + LIVE_RETRY_AFTER_SECONDS
        raise TimeoutError(f"live Overpass exceeded {OVERPASS_LIVE_BUDGET_SECONDS}s budget")
    except Exception:
        _live_down_until = time.monotonic() + LIVE_RETRY_AFTER_SECONDS
        raise


def _overpass_post_live(query: str) -> Dict[str, Any]:
    deadline = time.monotonic() + OVERPASS_LIVE_BUDGET_SECONDS
    last_error: Exception = RuntimeError("no Overpass endpoints configured")
    for url in OVERPASS_URLS:
        remaining = deadline - time.monotonic()
        if remaining < 1:
            break
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
            with urlopen(req, timeout=remaining) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[Overpass] {url} failed: {type(e).__name__}: {e}")
            last_error = e
    raise last_error


def _amenity_filter(amenities) -> str:
    if len(amenities) == 1:
        return f'["amenity"="{amenities[0]}"]'
    return f'["amenity"~"^({"|".join(amenities)})$"]'


def _parse_elements(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    for el in data.get("elements", []):
        el_lat = el.get("lat") or (el.get("center") or {}).get("lat")
        el_lon = el.get("lon") or (el.get("center") or {}).get("lon")
        tags = el.get("tags", {})
        amenity = tags.get("amenity")
        if el_lat is None or el_lon is None or not amenity:
            continue
        items.append({
            "id": str(el.get("id")),
            "name": tags.get("name") or tags.get("operator") or f"{amenity.replace('_', ' ').title()} #{el.get('id')}",
            "lat": el_lat,
            "lon": el_lon,
            "amenity": amenity,
        })
    return items


def _live_around(lat: float, lon: float, amenities) -> Optional[List[Dict[str, Any]]]:
    f = _amenity_filter(amenities)
    query = f"""
    [out:json][timeout:{int(OVERPASS_LIVE_BUDGET_SECONDS) + 5}];
    (
      node{f}(around:{POINT_RADIUS_M},{lat},{lon});
      way{f}(around:{POINT_RADIUS_M},{lat},{lon});
    );
    out center 60;
    """
    try:
        return _parse_elements(_overpass_post(query))
    except Exception as e:
        print(f"[Overpass] {'/'.join(amenities)} near {lat:.2f},{lon:.2f} failed: {type(e).__name__}: {e}")
        return None


def _live_bbox(south: float, west: float, north: float, east: float, amenities) -> Optional[List[Dict[str, Any]]]:
    f = _amenity_filter(amenities)
    query = f"""
    [out:json][timeout:{int(OVERPASS_LIVE_BUDGET_SECONDS) + 5}];
    (
      node{f}({south},{west},{north},{east});
      way{f}({south},{west},{north},{east});
    );
    out center {BBOX_LIMIT * len(amenities)};
    """
    try:
        return _parse_elements(_overpass_post(query))
    except Exception as e:
        print(f"[Overpass BBOX] {'/'.join(amenities)} lookup failed: {type(e).__name__}: {e}")
        return None


# ---------------------------------------------------------------------------
# Saved snapshots (real OpenStreetMap data saved by scripts/fetch_resource_snapshots.py)
# ---------------------------------------------------------------------------

_snapshots: List[Dict[str, Any]] = []
_snapshot_signature: Optional[tuple] = None


def _load_snapshots() -> List[Dict[str, Any]]:
    """Load saved areas, re-reading only when files are added or changed (no restart needed)."""
    global _snapshots, _snapshot_signature
    paths = sorted(SNAPSHOT_DIR.glob("*.json"))
    try:
        signature = tuple((p.name, p.stat().st_mtime_ns) for p in paths)
    except OSError:
        return _snapshots
    if signature != _snapshot_signature:
        loaded = []
        for path in paths:
            try:
                loaded.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError) as e:
                print(f"[Snapshot] could not read {path.name}: {e}")
        _snapshots, _snapshot_signature = loaded, signature
        print(f"[Snapshot] loaded {len(loaded)} saved area(s): {[s.get('area') for s in loaded]}")
    return _snapshots


def _snapshot_meta(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "data_source": "snapshot",
        "snapshot_area": snapshot.get("area"),
        "snapshot_date": snapshot.get("fetched_at"),
        "message": f"Live map data unavailable; showing saved OpenStreetMap data for {snapshot.get('area')}",
    }


def _snapshot_near(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    best, best_dist = None, None
    for snap in _load_snapshots():
        c = snap.get("center") or {}
        if c.get("lat") is None or c.get("lon") is None:
            continue
        d = _haversine_km(lat, lon, c["lat"], c["lon"])
        if d <= SNAPSHOT_MAX_DISTANCE_KM and (best_dist is None or d < best_dist):
            best, best_dist = snap, d
    return best


def _snapshots_in_bbox(south: float, west: float, north: float, east: float) -> List[Dict[str, Any]]:
    hits = []
    for snap in _load_snapshots():
        b = snap.get("bbox") or {}
        if not b:
            continue
        if b["south"] <= north and b["north"] >= south and b["west"] <= east and b["east"] >= west:
            hits.append(snap)
    return hits


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def _cached_lookup(cache_key: str, fetch: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    cached = get_cached(cache_key, CACHE_TTL_SECONDS)
    if cached is not None:
        return cached
    result = fetch()
    live_ok = result.get("status") == "ok" and result.get("data_source") == "live"
    set_cached(cache_key, result, CACHE_TTL_SECONDS if live_ok else FAILED_LOOKUP_TTL_SECONDS)
    return result


def _with_source(item: Dict[str, Any], data_source: str) -> Dict[str, Any]:
    return {**item, "source": "OpenStreetMap", "data_source": data_source}


def _nearest(items: List[Dict[str, Any]], lat: float, lon: float, limit: int) -> List[Dict[str, Any]]:
    out = [
        {**i, "distance_km": round(_haversine_km(lat, lon, i["lat"], i["lon"]), 1)}
        for i in items
    ]
    out.sort(key=lambda x: x["distance_km"])
    return out[:limit]


def _in_bbox(items, south, west, north, east):
    return [i for i in items if south <= i["lat"] <= north and west <= i["lon"] <= east]


def _is_bbox_shelter(item: Dict[str, Any]) -> bool:
    name = item.get("name", "").lower()
    return item["amenity"] == "community_centre" or any(h in name for h in SHELTER_NAME_HINTS)


def _point_shelters(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Prefer facilities actually named as shelters; otherwise community centres
    named = [i for i in items if i["amenity"] == "social_facility" and "shelter" in i.get("name", "").lower()]
    return named or [i for i in items if i["amenity"] == "community_centre"]


def _result(key: str, items: List[Dict[str, Any]], data_source: str, meta: Optional[Dict[str, Any]] = None):
    return {
        "status": "ok" if items else "unavailable",
        "count": len(items),
        key: [_with_source(i, data_source) for i in items],
        "source": "OpenStreetMap",
        "data_source": data_source if items else "none",
        **(meta or {}),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _point_lookup(key: str, lat: float, lon: float, amenities, select) -> Dict[str, Any]:
    live = _live_around(lat, lon, amenities)
    if live is not None:
        items = select(live)
        if items:
            return _result(key, _nearest(items, lat, lon, POINT_LIMIT), "live")
    snap = _snapshot_near(lat, lon)
    if snap is not None:
        items = select([i for i in snap["items"] if i["amenity"] in amenities])
        if items:
            return _result(key, _nearest(items, lat, lon, POINT_LIMIT), "snapshot", _snapshot_meta(snap))
    return _result(key, [], "none")


def _bbox_lookup(key: str, south, west, north, east, amenities, select) -> Dict[str, Any]:
    live = _live_bbox(south, west, north, east, amenities)
    if live is not None:
        items = [i for i in live if select(i)]
        if items:
            return _result(key, items[:BBOX_LIMIT], "live")
    snaps = _snapshots_in_bbox(south, west, north, east)
    items = []
    for snap in snaps:
        items += [
            i for i in _in_bbox(snap["items"], south, west, north, east)
            if i["amenity"] in amenities and select(i)
        ]
    if items:
        unique = list({i["id"]: i for i in items}.values())[:BBOX_LIMIT]
        return _result(key, unique, "snapshot", _snapshot_meta(snaps[0]))
    return _result(key, [], "none")


def get_hospitals(lat: float, lon: float) -> Dict[str, Any]:
    return _cached_lookup(
        f"hospitals_{lat:.2f}_{lon:.2f}",
        lambda: _point_lookup("hospitals", lat, lon, ("hospital",), lambda items: items),
    )


def get_shelters(lat: float, lon: float) -> Dict[str, Any]:
    return _cached_lookup(
        f"shelters_{lat:.2f}_{lon:.2f}",
        lambda: _point_lookup("shelters", lat, lon, SHELTER_AMENITIES, _point_shelters),
    )


def get_hospitals_in_bbox(south: float, west: float, north: float, east: float) -> Dict[str, Any]:
    return _cached_lookup(
        f"hospitals_bbox_{south:.2f}_{west:.2f}_{north:.2f}_{east:.2f}",
        lambda: _bbox_lookup("hospitals", south, west, north, east, ("hospital",), lambda i: True),
    )


def get_shelters_in_bbox(south: float, west: float, north: float, east: float) -> Dict[str, Any]:
    return _cached_lookup(
        f"shelters_bbox_{south:.2f}_{west:.2f}_{north:.2f}_{east:.2f}",
        lambda: _bbox_lookup("shelters", south, west, north, east, SHELTER_AMENITIES, _is_bbox_shelter),
    )
