"""Fetch saved hospital/shelter snapshots from OpenStreetMap (Overpass) for demo areas.

The backend serves these files only when live Overpass lookups fail. Every entry is
copied from OpenStreetMap as-is; nothing is generated. Re-run any time to refresh:

    cd backend
    .\\venv\\Scripts\\python.exe scripts\\fetch_resource_snapshots.py            # all areas
    .\\venv\\Scripts\\python.exe scripts\\fetch_resource_snapshots.py mumbai     # one area

Data © OpenStreetMap contributors, available under the Open Database License (ODbL).
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "resource_snapshots"

# Area centres; each snapshot covers centre ± HALF_SIZE_DEG (~28 km) in each direction
AREAS = {
    "bengaluru": {"name": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    "mumbai": {"name": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    "delhi": {"name": "Delhi", "lat": 28.7041, "lon": 77.1025},
    "chennai": {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    "kolkata": {"name": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    "hyderabad": {"name": "Hyderabad", "lat": 17.3850, "lon": 78.4867},
    "nagpur": {"name": "Nagpur", "lat": 21.1458, "lon": 79.0882},
}
HALF_SIZE_DEG = 0.25
AMENITIES = ("hospital", "social_facility", "community_centre")

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
REQUEST_TIMEOUT = 120
ROUNDS = 3
BACKOFF_SECONDS = 20


def _query(bbox: str) -> str:
    parts = "".join(
        f'node["amenity"="{a}"]({bbox});way["amenity"="{a}"]({bbox});' for a in AMENITIES
    )
    return f"[out:json][timeout:100];({parts});out center tags;"


def _post(url: str, query: str) -> dict:
    req = Request(
        url,
        data=urlencode({"data": query}).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "CrisisCore-Disaster-Preparedness/2.0 (snapshot fetch)",
        },
        method="POST",
    )
    with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_area(key: str) -> bool:
    area = AREAS[key]
    south, north = area["lat"] - HALF_SIZE_DEG, area["lat"] + HALF_SIZE_DEG
    west, east = area["lon"] - HALF_SIZE_DEG, area["lon"] + HALF_SIZE_DEG
    query = _query(f"{south},{west},{north},{east}")

    for round_no in range(1, ROUNDS + 1):
        for url in MIRRORS:
            started = time.time()
            try:
                data = _post(url, query)
            except Exception as e:
                print(f"  [{key}] round {round_no} {url} failed after {time.time() - started:.0f}s: {type(e).__name__}: {e}")
                continue
            if data.get("remark") and "runtime error" in data["remark"].lower():
                print(f"  [{key}] {url} returned a partial result ({data['remark'][:80]}); trying next mirror")
                continue

            items = []
            for el in data.get("elements", []):
                lat = el.get("lat") or (el.get("center") or {}).get("lat")
                lon = el.get("lon") or (el.get("center") or {}).get("lon")
                tags = el.get("tags") or {}
                amenity = tags.get("amenity")
                if lat is None or lon is None or amenity not in AMENITIES:
                    continue
                items.append({
                    "id": str(el.get("id")),
                    "osm_type": el.get("type"),
                    "name": tags.get("name") or tags.get("operator") or f"{amenity.replace('_', ' ').title()} #{el.get('id')}",
                    "lat": lat,
                    "lon": lon,
                    "amenity": amenity,
                })

            if not items:
                print(f"  [{key}] {url} returned no elements; trying next mirror")
                continue

            snapshot = {
                "area": area["name"],
                "center": {"lat": area["lat"], "lon": area["lon"]},
                "bbox": {"south": south, "west": west, "north": north, "east": east},
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "OpenStreetMap via Overpass API",
                "source_url": url,
                "license": "© OpenStreetMap contributors, ODbL 1.0",
                "counts": {a: sum(1 for i in items if i["amenity"] == a) for a in AMENITIES},
                "items": sorted(items, key=lambda i: (i["amenity"], i["id"])),
            }
            SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
            out = SNAPSHOT_DIR / f"{key}.json"
            out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  [{key}] OK from {url} in {time.time() - started:.0f}s: {snapshot['counts']} -> {out.name}")
            return True
        if round_no < ROUNDS:
            print(f"  [{key}] all mirrors failed in round {round_no}; waiting {BACKOFF_SECONDS}s")
            time.sleep(BACKOFF_SECONDS)
    return False


def main() -> int:
    keys = [k.lower() for k in sys.argv[1:]] or list(AREAS)
    unknown = [k for k in keys if k not in AREAS]
    if unknown:
        print(f"Unknown area(s): {unknown}. Choose from: {list(AREAS)}")
        return 2
    failed = [k for k in keys if not fetch_area(k)]
    print(f"\nDone: {len(keys) - len(failed)}/{len(keys)} areas saved." + (f" Failed: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
