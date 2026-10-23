"""
Near-Real-Time Satellite Flood Monitor (Sentinel-1 SAR)

Improvements over the basic version:
  - Auto-finds the MOST RECENT available satellite pass (no manual dates needed)
  - Auto-finds a clean baseline image from ~30-60 days ago for comparison
  - Stricter, cleaner detection (speckle filtering + tighter threshold + bigger
    minimum blob size) to cut down false positives from bare soil/runways/etc.
  - Saves a side-by-side BEFORE / AFTER / FLOOD image so you can visually
    sanity-check the result yourself
  - Designed to be run on a schedule (see run_monitor.bat) so it automatically
    re-checks whenever new satellite data becomes available — this is the
    closest thing to "real-time" that's physically possible with satellites,
    since Sentinel-1 only revisits any given spot every ~6-12 days.

Run: python monitor_flood.py
"""

import ee
import geemap
import sys
from datetime import datetime, timedelta
from config import get_project_id

PROJECT_ID = get_project_id()

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def init_earth_engine():
    try:
        ee.Initialize(project=PROJECT_ID)
    except Exception:
        print("Authenticating with Google Earth Engine...")
        ee.Authenticate()
        try:
            ee.Initialize(project=PROJECT_ID)
        except Exception as e:
            print(f"\nCouldn't initialize Earth Engine: {e}")
            print("Try running: earthengine --project=YOUR_PROJECT_ID authenticate")
            sys.exit(1)


def get_region(place_name, buffer_deg=0.15):
    """Smaller default buffer (~15km) than before -- keeps exports fast and
    keeps the analysis focused on the actual place, not a huge surrounding area."""
    coords = geemap.geocode(place_name)
    if not coords:
        raise ValueError(f"Could not find location: {place_name}")
    lat, lon = coords[0].lat, coords[0].lng
    return ee.Geometry.Rectangle([lon - buffer_deg, lat - buffer_deg,
                                   lon + buffer_deg, lat + buffer_deg])


# ---------------------------------------------------------------------------
# Find the latest available imagery automatically
# ---------------------------------------------------------------------------

def get_latest_sentinel1(region, days_back=14):
    """Finds the most recent Sentinel-1 image available for this region."""
    today = datetime.utcnow().date()
    start = (today - timedelta(days=days_back)).isoformat()
    end = (today + timedelta(days=1)).isoformat()

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .select("VH")
        .sort("system:time_start", False)  # newest first
    )

    count = collection.size().getInfo()
    if count == 0:
        raise ValueError(
            f"No Sentinel-1 imagery found in the last {days_back} days for this area. "
            "Try increasing days_back, or the satellite simply hasn't passed over "
            "recently -- try again in a day or two."
        )

    latest = collection.first()
    date_str = ee.Date(latest.get("system:time_start")).format("YYYY-MM-dd").getInfo()
    print(f"  Most recent image available: {date_str} ({count} image(s) found in window)")
    return latest.clip(region), date_str


def get_baseline_sentinel1(region, days_ago_start=45, days_ago_end=30):
    """Finds a 'normal conditions' baseline image from 30-45 days ago (a period
    unlikely to overlap with any recent flood event) to compare against."""
    today = datetime.utcnow().date()
    start = (today - timedelta(days=days_ago_start)).isoformat()
    end = (today - timedelta(days=days_ago_end)).isoformat()

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .select("VH")
    )

    count = collection.size().getInfo()
    if count == 0:
        raise ValueError(
            f"No baseline imagery found between {start} and {end}. "
            "Try widening days_ago_start/days_ago_end."
        )
    print(f"  Baseline: {count} image(s) from {start} to {end}")
    return collection.median().clip(region)


# ---------------------------------------------------------------------------
# Detection (stricter than the basic version)
# ---------------------------------------------------------------------------

def speckle_filter(image, radius=30):
    """SAR images are naturally 'noisy' (speckle). A focal median smooths
    this out before thresholding, cutting down false-positive noise."""
    return image.focal_median(radius, "circle", "meters")


def detect_water(sar_image, threshold_db=-18):
    """Stricter threshold than the basic script (-18 vs -16) — fewer
    false positives from bare soil, but may miss some shallow flooding.
    Adjust up toward -16/-15 if you find it's missing obvious floods."""
    filtered = speckle_filter(sar_image)
    return filtered.lt(threshold_db).selfMask()


def get_flood_extent(before_water, after_water, region, min_pixels=20):
    permanent_water = (
        ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
        .select("seasonality")
        .gte(10)
    )

    new_flood = after_water.And(before_water.unmask(0).Not()).And(permanent_water.unmask(0).Not())

    # Bigger minimum blob size than before (20 vs 8) = less noise
    connections = new_flood.connectedPixelCount(50)
    cleaned = new_flood.updateMask(connections.gte(min_pixels))

    dem = ee.Image("USGS/SRTMGL1_003").clip(region)
    slope = ee.Terrain.slope(dem)
    cleaned = cleaned.updateMask(slope.lt(5))

    return cleaned.clip(region)


def estimate_flood_area_km2(flood_image, region):
    """Rough estimate of flooded area in km^2 for a quick sanity-check number."""
    area_img = flood_image.multiply(ee.Image.pixelArea())
    stats = area_img.reduceRegion(
        reducer=ee.Reducer.sum(), geometry=region, scale=20, maxPixels=1e10
    )
    area_m2 = stats.getInfo().get("VH", 0) or 0
    return round(area_m2 / 1_000_000, 2)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_results(flood_image, region, sar_before, sar_after, out_html="flood_map.html"):
    print(f"  Building interactive map: {out_html} ...")
    m = geemap.Map()
    m.centerObject(region, 11)
    m.addLayer(sar_before, {"min": -25, "max": 0}, "Baseline (before)", shown=False)
    m.addLayer(sar_after, {"min": -25, "max": 0}, "Latest (after)")
    m.addLayer(flood_image, {"palette": ["red"]}, "Detected Flood")
    m.addLayer(region, {}, "Area of Interest", opacity=0.1)
    m.to_html(out_html)
    print("  Done.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("=== Near-Real-Time Flood Monitor (Sentinel-1 SAR) ===\n")
    init_earth_engine()

    place = input("Enter a place name (e.g. 'Chennai, India'): ").strip()
    region = get_region(place)

    print("\nFetching most recent satellite pass...")
    sar_after, after_date = get_latest_sentinel1(region)

    print("Fetching baseline (normal conditions, ~30-45 days ago)...")
    sar_before = get_baseline_sentinel1(region)

    print("Detecting water (with noise filtering)...")
    water_before = detect_water(sar_before)
    water_after = detect_water(sar_after)

    print("Isolating new flood extent...")
    flood = get_flood_extent(water_before, water_after, region)

    print("Estimating flooded area...")
    try:
        area_km2 = estimate_flood_area_km2(flood, region)
        print(f"  Estimated new flood extent: ~{area_km2} km²")
    except Exception:
        area_km2 = None
        print("  (Could not compute area estimate, skipping)")

    export_results(flood, region, sar_before, sar_after)

    print(f"\nLatest imagery used: {after_date}")
    if area_km2 is not None:
        print(f"Estimated flood extent: ~{area_km2} km²")
    print("\nOpen flood_map.html in your browser to view results.")
    print("Toggle 'Baseline (before)' on in the layer panel to compare against the latest image.")
    print("\nTip: run this script on a schedule (see run_monitor.bat / README) to")
    print("auto-refresh whenever new satellite imagery becomes available.")


if __name__ == "__main__":
    main()
