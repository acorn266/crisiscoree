"""
Click-on-Map Flood Detection — Web App

A local web page with a map. Click anywhere, and it automatically runs the
flood detection pipeline for that spot (most recent satellite pass vs. a
~30-45 day baseline) and shows you the result right there in the browser.

Run: python app.py
Then open: http://127.0.0.1:5000 in your browser.
"""

import ee
from flask import Flask, jsonify, render_template, request

from monitor_flood import (
    PROJECT_ID, init_earth_engine, get_latest_sentinel1,
    get_baseline_sentinel1, detect_water, get_flood_extent,
    estimate_flood_area_km2,
)

app = Flask(__name__)
_ee_ready = False


def ensure_ee():
    global _ee_ready
    if not _ee_ready:
        init_earth_engine()
        _ee_ready = True


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    lat = float(data["lat"])
    lon = float(data["lon"])
    buffer_deg = 0.15  # ~15km box around the clicked point

    ensure_ee()

    region = ee.Geometry.Rectangle([lon - buffer_deg, lat - buffer_deg,
                                     lon + buffer_deg, lat + buffer_deg])

    try:
        sar_after, after_date = get_latest_sentinel1(region, days_back=14)
        sar_before = get_baseline_sentinel1(region)

        water_before = detect_water(sar_before)
        water_after = detect_water(sar_after)
        flood = get_flood_extent(water_before, water_after, region)

        try:
            area_km2 = estimate_flood_area_km2(flood, region)
        except Exception:
            area_km2 = None

        # Get a map tile URL for the flood layer so the browser can display it
        flood_vis = flood.visualize(palette=["red"])
        flood_map_id = flood_vis.getMapId()
        flood_tile_url = flood_map_id["tile_fetcher"].url_format

        sar_vis = sar_after.visualize(min=-25, max=0)
        sar_map_id = sar_vis.getMapId()
        sar_tile_url = sar_map_id["tile_fetcher"].url_format

        return jsonify({
            "success": True,
            "image_date": after_date,
            "area_km2": area_km2,
            "flood_tile_url": flood_tile_url,
            "sar_tile_url": sar_tile_url,
            "bounds": [[lat - buffer_deg, lon - buffer_deg], [lat + buffer_deg, lon + buffer_deg]],
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    print("Starting flood detection web app...")
    print("Open this in your browser: http://127.0.0.1:5000")
    app.run(debug=False, port=5000)
