"""
Non-interactive version of the flood monitor, for scheduled/automated runs
(e.g. Windows Task Scheduler) where there's no one there to type answers.

EDIT THE SETTINGS BELOW, then this can be run automatically on a schedule.
Every run overwrites flood_map.html with the latest available result and
appends a line to flood_history.csv so you can track flood extent over time.
"""

import csv
import os
from datetime import datetime

# ============================================================
# SETTINGS -- edit this for your location. Your Earth Engine project ID is
# handled automatically via config.py (set once, shared by all scripts).
# ============================================================
PLACE_NAME = "Chennai, India"
# ============================================================

from monitor_flood import (
    init_earth_engine, get_region, get_latest_sentinel1,
    get_baseline_sentinel1, detect_water, get_flood_extent,
    estimate_flood_area_km2, export_results,
)


def log_result(place, date_used, area_km2):
    log_file = "flood_history.csv"
    file_exists = os.path.isfile(log_file)
    with open(log_file, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["run_timestamp", "place", "satellite_image_date", "estimated_flood_km2"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"), place, date_used, area_km2])


def main():
    print(f"=== Automated Flood Check: {PLACE_NAME} ===")
    print(f"Run time: {datetime.now().isoformat(timespec='seconds')}")

    init_earth_engine()
    region = get_region(PLACE_NAME)

    sar_after, after_date = get_latest_sentinel1(region)
    sar_before = get_baseline_sentinel1(region)

    water_before = detect_water(sar_before)
    water_after = detect_water(sar_after)
    flood = get_flood_extent(water_before, water_after, region)

    try:
        area_km2 = estimate_flood_area_km2(flood, region)
    except Exception:
        area_km2 = None

    export_results(flood, region, sar_before, sar_after)
    log_result(PLACE_NAME, after_date, area_km2)

    print(f"Latest image date: {after_date}")
    print(f"Estimated flood extent: {area_km2} km²" if area_km2 is not None else "Area estimate unavailable")
    print("Updated flood_map.html and appended to flood_history.csv")


if __name__ == "__main__":
    main()
