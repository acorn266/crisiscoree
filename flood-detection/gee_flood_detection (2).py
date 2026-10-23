"""
Satellite Flood Detection using Google Earth Engine + Sentinel-1 SAR

What this does:
1. Takes a place name (or bounding box) and two date ranges: "before" and "after"
2. Pulls Sentinel-1 radar imagery for both periods
3. Detects water via backscatter thresholding
4. Subtracts permanent water bodies to isolate NEW flooding
5. Cleans up noise using a digital elevation model
6. Exports a GeoTIFF flood map + an interactive HTML map

Run: python gee_flood_detection.py
"""

import ee
import geemap
import sys
from config import get_project_id

# ---------------------------------------------------------------------------
# STEP 0: Authenticate & initialize Earth Engine
# ---------------------------------------------------------------------------

def init_earth_engine():
    project_id = get_project_id()
    try:
        ee.Initialize(project=project_id)
    except Exception:
        print("First-time setup: authenticating with Google Earth Engine...")
        ee.Authenticate()
        try:
            ee.Initialize(project=project_id)
        except Exception as e:
            print("\nEarth Engine needs a Google Cloud project to be linked.")
            print("If you see a 'project not registered' error, run:")
            print("  earthengine authenticate --project=YOUR_PROJECT_ID")
            print(f"\nOriginal error: {e}")
            sys.exit(1)


# ---------------------------------------------------------------------------
# STEP 1: Get area of interest from a place name
# ---------------------------------------------------------------------------

def get_region(place_name=None, bbox=None):
    """
    Returns an ee.Geometry for the area of interest.
    Provide EITHER a place_name (uses geemap's geocoder) OR a bbox
    (list of [min_lon, min_lat, max_lon, max_lat]).
    """
    if bbox:
        return ee.Geometry.Rectangle(bbox)

    if place_name:
        coords = geemap.geocode(place_name)
        if not coords:
            raise ValueError(f"Could not find location: {place_name}")
        lat, lon = coords[0].lat, coords[0].lng
        # ~0.5 degree buffer box around the point (~50km) — adjust as needed
        buffer = 0.5
        return ee.Geometry.Rectangle([lon - buffer, lat - buffer, lon + buffer, lat + buffer])

    raise ValueError("Provide either place_name or bbox")


# ---------------------------------------------------------------------------
# STEP 2: Pull & prep Sentinel-1 SAR imagery
# ---------------------------------------------------------------------------

def get_sentinel1_image(region, start_date, end_date):
    """Fetches a median-composite Sentinel-1 VH-band image for a date range."""
    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .select("VH")
    )

    count = collection.size().getInfo()
    if count == 0:
        raise ValueError(
            f"No Sentinel-1 images found for {start_date} to {end_date} in this region. "
            "Try widening the date range."
        )
    print(f"  Found {count} Sentinel-1 image(s) for {start_date} to {end_date}")

    return collection.median().clip(region)


# ---------------------------------------------------------------------------
# STEP 3: Detect water via thresholding
# ---------------------------------------------------------------------------

def detect_water(sar_image, threshold_db=-16):
    """
    SAR backscatter below this threshold (in dB) is classified as water.
    -16 dB is a commonly used default for VH polarization; adjust if
    results look too aggressive/conservative for your area.
    """
    return sar_image.lt(threshold_db).selfMask()


# ---------------------------------------------------------------------------
# STEP 4: Isolate NEW flooding (after-water minus permanent water)
# ---------------------------------------------------------------------------

def get_flood_extent(before_water, after_water, region):
    # JRC Global Surface Water — permanent water bodies reference layer
    permanent_water = (
        ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
        .select("seasonality")
        .gte(10)  # water present >= 10 months/year = permanent
    )

    new_flood = after_water.And(before_water.unmask(0).Not()).And(permanent_water.unmask(0).Not())

    # Clean up isolated noise pixels (connectivity < 8 pixels removed)
    connections = new_flood.connectedPixelCount(25)
    cleaned = new_flood.updateMask(connections.gte(8))

    return cleaned.clip(region)


# ---------------------------------------------------------------------------
# STEP 5: Remove terrain/radar-shadow false positives using a DEM
# ---------------------------------------------------------------------------

def mask_steep_slopes(flood_image, region, max_slope_degrees=5):
    dem = ee.Image("USGS/SRTMGL1_003").clip(region)
    slope = ee.Terrain.slope(dem)
    return flood_image.updateMask(slope.lt(max_slope_degrees))


# ---------------------------------------------------------------------------
# STEP 6: Export results
# ---------------------------------------------------------------------------

def export_results(flood_image, region, sar_after, out_tif="flood_extent.tif", out_html="flood_map.html"):
    print(f"  Exporting GeoTIFF to {out_tif} ...")
    geemap.ee_export_image(
        flood_image,
        filename=out_tif,
        scale=20,
        region=region,
        file_per_band=False,
    )

    print(f"  Building interactive map: {out_html} ...")
    m = geemap.Map()
    m.centerObject(region, 10)
    m.addLayer(sar_after, {"min": -25, "max": 0}, "SAR (after)")
    m.addLayer(flood_image, {"palette": ["blue"]}, "Detected Flood")
    m.addLayer(region, {}, "Area of Interest", opacity=0.1)
    m.to_html(out_html)
    print("  Done.")


# ---------------------------------------------------------------------------
# MAIN — interactive prompts
# ---------------------------------------------------------------------------

def main():
    print("=== Satellite Flood Detection (Sentinel-1 SAR) ===\n")
    init_earth_engine()

    place = input("Enter a place name (e.g. 'Jakarta, Indonesia'): ").strip()
    region = get_region(place_name=place)

    print("\nDate ranges use YYYY-MM-DD format.")
    before_start = input("BEFORE period start date: ").strip()
    before_end = input("BEFORE period end date: ").strip()
    after_start = input("AFTER (flood) period start date: ").strip()
    after_end = input("AFTER (flood) period end date: ").strip()

    print("\nFetching imagery...")
    sar_before = get_sentinel1_image(region, before_start, before_end)
    sar_after = get_sentinel1_image(region, after_start, after_end)

    print("Detecting water...")
    water_before = detect_water(sar_before)
    water_after = detect_water(sar_after)

    print("Isolating new flood extent...")
    flood = get_flood_extent(water_before, water_after, region)
    flood = mask_steep_slopes(flood, region)

    export_results(flood, region, sar_after)

    print("\nAll done! Open flood_map.html in your browser to view results,")
    print("or open flood_extent.tif in QGIS/ArcGIS/geemap for further analysis.")


if __name__ == "__main__":
    main()
