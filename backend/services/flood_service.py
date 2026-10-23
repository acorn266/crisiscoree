"""
FastAPI service wrapper for Google Earth Engine Flood Detection.

Provides REST endpoints to analyze satellite-based flooding for any geographic
location using Sentinel-1 SAR imagery via Google Earth Engine.
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

FLOOD_DETECTION_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "flood-detection")
if os.path.exists(FLOOD_DETECTION_PATH):
    sys.path.insert(0, FLOOD_DETECTION_PATH)

try:
    import ee
    import geemap
    HAS_EE = True
except ImportError:
    HAS_EE = False
    print("Warning: earthengine-api/geemap not installed.")


def _bbox_geometry(lat: float, lon: float, buffer_deg: float) -> dict:
    """Return GeoJSON polygon for analysis region bounding box."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon - buffer_deg, lat - buffer_deg],
            [lon + buffer_deg, lat - buffer_deg],
            [lon + buffer_deg, lat + buffer_deg],
            [lon - buffer_deg, lat + buffer_deg],
            [lon - buffer_deg, lat - buffer_deg],
        ]],
    }


def _flood_severity(area_km2: Optional[float]) -> str:
    if area_km2 is None:
        return "UNKNOWN"
    if area_km2 >= 50:
        return "HIGH"
    if area_km2 >= 5:
        return "MEDIUM"
    if area_km2 > 0.01:
        return "LOW"
    return "NONE"


class FloodDetectionService:
    """Satellite-based flood detection using Google Earth Engine + Sentinel-1 SAR."""

    def __init__(self, project_id: Optional[str] = None):
        self.ee_initialized = False
        self.project_id = project_id
        self._init_earth_engine()

    def _init_earth_engine(self):
        if not HAS_EE:
            return
        try:
            if not self.project_id:
                config_path = os.path.join(FLOOD_DETECTION_PATH, "config.txt")
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        self.project_id = f.read().strip()
            if self.project_id:
                ee.Initialize(project=self.project_id)
            else:
                ee.Initialize()
            self.ee_initialized = True
            print("Google Earth Engine initialized successfully")
        except Exception as e:
            print(f"Could not initialize Earth Engine: {e}")
            self.ee_initialized = False

    def check_ready(self) -> bool:
        return self.ee_initialized

    def get_region(self, lat: float, lon: float, buffer_deg: float = 0.15) -> Optional[Any]:
        if not self.ee_initialized:
            return None
        try:
            return ee.Geometry.Rectangle([
                lon - buffer_deg, lat - buffer_deg,
                lon + buffer_deg, lat + buffer_deg
            ])
        except Exception as e:
            print(f"Error creating region: {e}")
            return None

    def get_latest_sentinel1(self, region: Any, days_back: int = 14) -> tuple[Optional[Any], Optional[str]]:
        if not self.ee_initialized or region is None:
            return None, None
        try:
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
                .sort("system:time_start", False)
            )
            count = collection.size().getInfo()
            if count == 0:
                return None, None
            latest = collection.first()
            date_str = ee.Date(latest.get("system:time_start")).format("YYYY-MM-dd").getInfo()
            return latest.clip(region), date_str
        except Exception as e:
            print(f"Error fetching Sentinel-1: {e}")
            return None, None

    def get_baseline_sentinel1(self, region: Any, days_ago_start: int = 45, days_ago_end: int = 30) -> Optional[Any]:
        if not self.ee_initialized or region is None:
            return None
        try:
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
                return None
            return collection.median().clip(region)
        except Exception as e:
            print(f"Error fetching baseline: {e}")
            return None

    def speckle_filter(self, image: Any, radius: int = 30) -> Any:
        try:
            return image.focal_median(radius, "circle", "meters")
        except Exception as e:
            return image

    def detect_water(self, sar_image: Any, threshold_db: float = -18) -> Optional[Any]:
        if sar_image is None:
            return None
        try:
            filtered = self.speckle_filter(sar_image)
            return filtered.lt(threshold_db).selfMask()
        except Exception as e:
            return None

    def get_flood_extent(self, water_before: Any, water_after: Any, region: Any, min_pixels: int = 20) -> Optional[Any]:
        if water_before is None or water_after is None or region is None:
            return None
        try:
            permanent_water = (
                ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
                .select("seasonality")
                .gte(10)
            )
            new_flood = (
                water_after
                .And(water_before.unmask(0).Not())
                .And(permanent_water.unmask(0).Not())
            )
            connections = new_flood.connectedPixelCount(50)
            cleaned = new_flood.updateMask(connections.gte(min_pixels))
            dem = ee.Image("USGS/SRTMGL1_003").clip(region)
            slope = ee.Terrain.slope(dem)
            cleaned = cleaned.updateMask(slope.lt(5))
            return cleaned.clip(region)
        except Exception as e:
            print(f"Error computing flood extent: {e}")
            return None

    def estimate_flood_area_km2(self, flood_image: Any, region: Any) -> Optional[float]:
        if flood_image is None or region is None:
            return None
        try:
            area_img = flood_image.multiply(ee.Image.pixelArea())
            stats = area_img.reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=region,
                scale=20,
                maxPixels=1e10
            )
            area_m2 = stats.getInfo().get("VH", 0) or 0
            return round(area_m2 / 1_000_000, 2)
        except Exception as e:
            print(f"Error estimating area: {e}")
            return None

    def analyze_flood(self, lat: float, lon: float, buffer_deg: float = 0.15) -> Dict[str, Any]:
        if not self.ee_initialized:
            return {
                "success": False,
                "error": "Earth Engine not initialized. Check configuration."
            }
        try:
            region = self.get_region(lat, lon, buffer_deg)
            if region is None:
                return {"success": False, "error": "Could not create region geometry"}

            sar_after, after_date = self.get_latest_sentinel1(region)
            if sar_after is None:
                return {
                    "success": False,
                    "error": "No recent Sentinel-1 imagery available for this location."
                }

            sar_before = self.get_baseline_sentinel1(region)
            if sar_before is None:
                return {"success": False, "error": "No baseline imagery available for comparison."}

            water_before = self.detect_water(sar_before)
            water_after = self.detect_water(sar_after)
            if water_before is None or water_after is None:
                return {"success": False, "error": "Water detection failed"}

            flood = self.get_flood_extent(water_before, water_after, region)
            if flood is None:
                return {"success": False, "error": "Could not compute flood extent"}

            area_km2 = self.estimate_flood_area_km2(flood, region)
            return {
                "success": True,
                "lat": lat,
                "lon": lon,
                "image_date": after_date,
                "area_km2": area_km2,
                "flood_detected": area_km2 is not None and area_km2 > 0.01,
                "buffer_deg": buffer_deg,
                "data_note": "Latest available Sentinel-1 satellite data",
            }
        except Exception as e:
            return {"success": False, "error": f"Analysis failed: {str(e)}"}

    def monitor_region(self, region_id: str, name: str, lat: float, lon: float, buffer_deg: float = 0.25) -> Dict[str, Any]:
        """Monitor a configured region and return standardized disaster item."""
        result = self.analyze_flood(lat, lon, buffer_deg)
        base = {
            "disaster_type": "flood",
            "region": name,
            "region_id": region_id,
            "lat": lat,
            "lon": lon,
            "geometry": _bbox_geometry(lat, lon, buffer_deg),
            "geometry_type": "analysis_region",
            "source": "Sentinel-1/GEE",
            "data_note": "Latest available Sentinel-1 satellite data",
        }

        if not result.get("success"):
            return {
                **base,
                "status": "unavailable",
                "severity": "UNAVAILABLE",
                "score": None,
                "timestamp": None,
                "confidence": None,
                "area_km2": None,
                "flood_detected": None,
                "message": result.get("error", "Analysis unavailable"),
            }

        area = result.get("area_km2")
        detected = result.get("flood_detected", False)
        severity = _flood_severity(area) if detected else "NONE"

        return {
            **base,
            "status": "detected" if detected else "none_detected",
            "severity": severity,
            "score": None,
            "timestamp": result.get("image_date"),
            "confidence": "medium" if detected else "high",
            "area_km2": area,
            "flood_detected": detected,
            "image_date": result.get("image_date"),
        }

    def monitor_regions(self, regions: List[Dict[str, Any]], buffer_deg: float = 0.25) -> List[Dict[str, Any]]:
        if not self.ee_initialized:
            return [{
                "disaster_type": "flood",
                "status": "unavailable",
                "severity": "UNAVAILABLE",
                "score": None,
                "source": "Sentinel-1/GEE",
                "message": "Earth Engine not initialized",
                "data_note": "Latest available Sentinel-1 satellite data",
            }]
        return [
            self.monitor_region(r["id"], r["name"], r["lat"], r["lon"], buffer_deg)
            for r in regions
        ]


_flood_service = None


def get_flood_service() -> FloodDetectionService:
    global _flood_service
    if _flood_service is None:
        _flood_service = FloodDetectionService()
    return _flood_service
