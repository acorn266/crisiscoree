from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import INDIA_BOUNDS, INDIA_FLOOD_MONITOR_REGIONS, CACHE_TTL_SECONDS
from services.flood_service import get_flood_service
from services.earthquake_service import get_india_earthquakes
from services.drought_service import get_india_droughts
from services.heatwave_service import get_india_heatwaves
from services.cyclone_service import get_india_cyclones
from services.risk_engine import get_risk_engine
from services.alert_service import generate_alerts
from services.weather_service import get_weather
from services.resource_service import get_hospitals, get_shelters
from services.cache_utils import cached_fetch, clear_cache
from services.ai_risk_engine import (
    get_ai_risk_engine,
    FloodFeatureExtractor,
    EarthquakeAnomalyExtractor,
    HeatwaveAnomalyExtractor,
    DroughtAnomalyExtractor,
    CycloneAnomalyExtractor,
)
from services.ai_context import build_crisis_context

app = FastAPI(
    title="India Disaster Intelligence Map API",
    description="India-wide disaster intelligence platform powered by real data sources",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Pydantic Models
# ============================================================================

class FloodAnalysisRequest(BaseModel):
    lat: float
    lon: float
    buffer_deg: Optional[float] = 0.15


class FloodAnalysisResponse(BaseModel):
    success: bool
    lat: Optional[float] = None
    lon: Optional[float] = None
    image_date: Optional[str] = None
    area_km2: Optional[float] = None
    flood_detected: Optional[bool] = None
    buffer_deg: Optional[float] = None
    data_note: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# Health & Status
# ============================================================================

@app.get("/")
def root():
    return {
        "message": "India Disaster Intelligence Map API",
        "status": "running",
        "country": "India",
    }


@app.get("/health")
def health():
    flood_service = get_flood_service()
    risk_engine = get_risk_engine()
    return {
        "status": "healthy",
        "flood_service_ready": flood_service.check_ready(),
        "risk_engine_model_available": risk_engine.is_model_available(),
        "data_sources": ["Sentinel-1/GEE", "USGS", "OpenWeather", "OpenStreetMap"],
    }


# ============================================================================
# Flood Detection (preserved POST endpoint)
# ============================================================================

@app.post("/api/flood-risk", response_model=FloodAnalysisResponse)
def analyze_flood_risk(request: FloodAnalysisRequest):
    """Analyze satellite-based flood risk at a geographic location."""
    flood_service = get_flood_service()

    if not flood_service.check_ready():
        return FloodAnalysisResponse(
            success=False,
            error="Flood detection service not initialized. "
                  "Check Google Earth Engine configuration and logs.",
        )

    result = flood_service.analyze_flood(
        lat=request.lat,
        lon=request.lon,
        buffer_deg=request.buffer_deg,
    )
    return FloodAnalysisResponse(**result)


@app.get("/api/flood-status")
def flood_service_status():
    flood_service = get_flood_service()
    return {
        "service_ready": flood_service.check_ready(),
        "message": (
            "Flood detection service ready (Google Earth Engine initialized)"
            if flood_service.check_ready()
            else "Flood detection service not ready (see backend logs)"
        ),
    }


@app.get("/api/disasters/floods")
def get_floods(refresh: bool = Query(False, description="Bypass cache and refresh")):
    """Auto-monitor configurable Indian regions using Sentinel-1/GEE."""
    if refresh:
        clear_cache("floods_india")

    def fetch():
        flood_service = get_flood_service()
        floods = flood_service.monitor_regions(INDIA_FLOOD_MONITOR_REGIONS)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "country": "India",
            "source": "Sentinel-1/GEE",
            "data_note": "Latest available Sentinel-1 satellite data",
            "count": len(floods),
            "floods": floods,
        }

    return cached_fetch("floods_india", CACHE_TTL_SECONDS, fetch)


# ============================================================================
# Earthquake (USGS)
# ============================================================================

@app.get("/api/disasters/earthquakes")
def get_earthquakes(refresh: bool = Query(False)):
    if refresh:
        clear_cache("earthquakes_india")
    return get_india_earthquakes()


# ============================================================================
# Drought, Heatwave, Cyclone
# ============================================================================

@app.get("/api/disasters/droughts")
def get_droughts(refresh: bool = Query(False)):
    if refresh:
        clear_cache("droughts_india")
    return get_india_droughts()


@app.get("/api/disasters/heatwaves")
def get_heatwaves(refresh: bool = Query(False)):
    if refresh:
        clear_cache("heatwaves_india")
    return get_india_heatwaves()


@app.get("/api/disasters/cyclones")
def get_cyclones(refresh: bool = Query(False)):
    if refresh:
        clear_cache("cyclones_india")
    return get_india_cyclones()


# ============================================================================
# Unified India Disaster API
# ============================================================================

@app.get("/api/disasters/india")
def get_india_disasters(refresh: bool = Query(False)):
    """Aggregate all disaster types for India."""
    if refresh:
        clear_cache(None)

    eq_data = get_india_earthquakes()
    drought_data = get_india_droughts()
    heat_data = get_india_heatwaves()
    cyclone_data = get_india_cyclones()

    # Flood monitoring is expensive — use cache unless refresh requested
    if refresh:
        clear_cache("floods_india")
    flood_service = get_flood_service()
    floods = flood_service.monitor_regions(INDIA_FLOOD_MONITOR_REGIONS) if flood_service.check_ready() else [{
        "disaster_type": "flood",
        "status": "unavailable",
        "severity": "UNAVAILABLE",
        "score": None,
        "source": "Sentinel-1/GEE",
        "message": "Earth Engine not initialized",
        "data_note": "Latest available Sentinel-1 satellite data",
    }]

    earthquakes = eq_data.get("earthquakes", [])
    droughts = drought_data.get("droughts", [])
    heatwaves = heat_data.get("heatwaves", [])
    cyclones = cyclone_data.get("cyclones", [])

    alerts = generate_alerts(floods, earthquakes, droughts, heatwaves, cyclones)
    risk_engine = get_risk_engine()
    risk = risk_engine.compute_overall_risk(floods, earthquakes, droughts, heatwaves, cyclones)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country": "India",
        "bounds": INDIA_BOUNDS,
        "floods": floods,
        "earthquakes": earthquakes,
        "droughts": droughts,
        "heatwaves": heatwaves,
        "cyclones": cyclones,
        "alerts": alerts,
        "risk": risk,
        "sources": {
            "floods": "Sentinel-1/GEE",
            "earthquakes": "USGS",
            "droughts": "OpenWeather",
            "heatwaves": "OpenWeather",
            "cyclones": "OpenWeather",
            "hospitals_shelters": "OpenStreetMap",
        },
    }


# ============================================================================
# Weather, Resources, Risk
# ============================================================================

@app.get("/api/weather")
def weather(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
):
    return get_weather(lat, lon)


@app.get("/api/hospitals")
def hospitals(
    lat: float = Query(...),
    lon: float = Query(...),
):
    return get_hospitals(lat, lon)


@app.get("/api/shelters")
def shelters(
    lat: float = Query(...),
    lon: float = Query(...),
):
    return get_shelters(lat, lon)

@app.get("/api/hospitals/map")
def hospitals_map(
    south: float = Query(...),
    west: float = Query(...),
    north: float = Query(...),
    east: float = Query(...),
):
    """Return hospitals inside the current map viewport."""
    from services.resource_service import get_hospitals_in_bbox

    return get_hospitals_in_bbox(
        south=south,
        west=west,
        north=north,
        east=east,
    )


@app.get("/api/shelters/map")
def shelters_map(
    south: float = Query(...),
    west: float = Query(...),
    north: float = Query(...),
    east: float = Query(...),
):
    """Return shelters inside the current map viewport."""
    from services.resource_service import get_shelters_in_bbox

    return get_shelters_in_bbox(
        south=south,
        west=west,
        north=north,
        east=east,
    )

def resolve_lat_lon(lat: Optional[float], lon: Optional[float], city: Optional[str]):
    from config import INDIA_WEATHER_CITIES, INDIA_COASTAL_CITIES
    
    if city:
        for c in INDIA_WEATHER_CITIES + INDIA_COASTAL_CITIES:
            if c["name"].lower() == city.lower():
                return c["lat"], c["lon"], c["name"]
    
    if lat is not None and lon is not None:
        # Try to find city name
        for c in INDIA_WEATHER_CITIES + INDIA_COASTAL_CITIES:
            if abs(c["lat"] - lat) < 0.05 and abs(c["lon"] - lon) < 0.05:
                return lat, lon, c["name"]
        return lat, lon, f"{lat:.2f}, {lon:.2f}"
        
    # Default to Chennai
    return 13.0827, 80.2707, "Chennai"


@app.get("/api/ai-risk")
def get_ai_risk(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    city: Optional[str] = Query(None),
):
    resolved_lat, resolved_lon, city_name = resolve_lat_lon(lat, lon, city)
    
    # 1. Fetch live weather data
    weather = get_weather(resolved_lat, resolved_lon)
    
    # 2. Fetch live earthquake data and get closest event
    eq_data = get_india_earthquakes()
    earthquakes = eq_data.get("earthquakes", [])
    
    closest_eq = None
    min_dist = 9999.0
    from services.ai_risk_engine import haversine_distance
    for eq in earthquakes:
        eq_lat = eq.get("lat")
        eq_lon = eq.get("lon")
        if eq_lat is not None and eq_lon is not None:
            dist = haversine_distance(resolved_lat, resolved_lon, eq_lat, eq_lon)
            if closest_eq is None or dist < min_dist:
                min_dist = dist
                closest_eq = eq
                
    if closest_eq is None:
        closest_eq = {
            "magnitude": 0.0,
            "depth_km": 0.0,
            "significance": 0.0,
            "time_iso": None,
            "lat": resolved_lat + 1.0,
            "lon": resolved_lon + 1.0
        }
        
    # 3. Fetch GEE flood detection
    flood_service = get_flood_service()
    flood_sat_data = None
    if flood_service.check_ready():
        flood_sat_data = flood_service.analyze_flood(resolved_lat, resolved_lon)
        
    # 4. Extract features
    flood_feats = FloodFeatureExtractor.extract_features(
        flood_sat_data if flood_sat_data and flood_sat_data.get("success") else None,
        weather if weather.get("status") == "ok" else None,
        {"lat": resolved_lat, "lon": resolved_lon}
    )
    
    eq_feats = EarthquakeAnomalyExtractor.extract_features(
        closest_eq, resolved_lat, resolved_lon, earthquakes
    )
    
    heat_feats = HeatwaveAnomalyExtractor.extract_features(
        weather if weather.get("status") == "ok" else {}
    )
    
    drought_feats = DroughtAnomalyExtractor.extract_features(
        weather if weather.get("status") == "ok" else {}
    )
    
    cyclone_feats = CycloneAnomalyExtractor.extract_features(
        weather if weather.get("status") == "ok" else {}, resolved_lat, resolved_lon
    )
    
    # 5. Predict risks using the trained engine
    ai_engine = get_ai_risk_engine()
    
    risks = {
        "flood": ai_engine.predict_risk("flood", flood_feats),
        "earthquake": ai_engine.predict_risk("earthquake", eq_feats),
        "heatwave": ai_engine.predict_risk("heatwave", heat_feats),
        "drought": ai_engine.predict_risk("drought", drought_feats),
        "cyclone": ai_engine.predict_risk("cyclone", cyclone_feats),
    }
    
    # 6. Aggregate overall risk score
    scores = [r["score"] for r in risks.values() if r.get("score") is not None]
    overall_score = max(scores) if scores else 0
    
    if overall_score >= 85:
        overall_level = "CRITICAL"
    elif overall_score >= 65:
        overall_level = "HIGH"
    elif overall_score >= 35:
        overall_level = "MEDIUM"
    else:
        overall_level = "LOW"
        
    confidences = [r["confidence"] for r in risks.values() if r.get("score") is not None]
    overall_confidence = float(round(sum(confidences) / len(confidences), 2)) if confidences else 0.0
    
    return {
        "success": True,
        "location": {
            "lat": resolved_lat,
            "lon": resolved_lon,
            "city": city_name
        },
        "risks": risks,
        "overall": {
            "score": overall_score,
            "level": overall_level,
            "confidence": overall_confidence
        },
        "engine": {
            "name": "CrisisCore AI Risk Engine",
            "version": "1.0"
        }
    }


@app.get("/api/ai-context")
def get_ai_context(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    city: Optional[str] = Query(None),
):
    resolved_lat, resolved_lon, _ = resolve_lat_lon(lat, lon, city)
    context = build_crisis_context(resolved_lat, resolved_lon)
    return context


@app.get("/api/risk")
def overall_risk(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    city: Optional[str] = Query(None),
):
    """Expose AI overall risk for general compatibility."""
    res = get_ai_risk(lat, lon, city)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "risk": res["overall"],
        "risks": res["risks"],
        "status": "active",
        "message": "AI risk models loaded and running",
    }


@app.post("/api/cache/clear")
def clear_disaster_cache():
    count = clear_cache(None)
    return {"cleared_entries": count, "status": "ok"}
