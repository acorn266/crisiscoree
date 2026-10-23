"""
CrisisCore 2.0 AI Context builder for RAG/Assistant preparation.
Combines current weather, earthquakes, GEE flood detection,
AI risk engine scores, emergency alerts, nearest hospitals, and shelters.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from services.weather_service import get_weather
from services.earthquake_service import get_india_earthquakes
from services.drought_service import get_india_droughts
from services.heatwave_service import get_india_heatwaves
from services.cyclone_service import get_india_cyclones
from services.flood_service import get_flood_service
from services.resource_service import get_hospitals, get_shelters
from services.alert_service import generate_alerts
from services.ai_risk_engine import (
    get_ai_risk_engine,
    FloodFeatureExtractor,
    EarthquakeAnomalyExtractor,
    HeatwaveAnomalyExtractor,
    DroughtAnomalyExtractor,
    CycloneAnomalyExtractor,
)


def build_crisis_context(lat: float, lon: float) -> Dict[str, Any]:
    """
    Build a comprehensive structured context JSON for a specific location.
    Combines live data feeds, emergency resources, active alerts, and AI risk scores.
    """
    # 1. Fetch current weather
    weather = get_weather(lat, lon)
    
    # 2. Fetch resources
    hospitals_data = get_hospitals(lat, lon)
    shelters_data = get_shelters(lat, lon)
    hospitals = hospitals_data.get("hospitals", [])
    shelters = shelters_data.get("shelters", [])
    
    # 3. Fetch GEE flood detection
    flood_service = get_flood_service()
    flood_sat_data = None
    if flood_service.check_ready():
        # Perform GEE analysis
        flood_sat_data = flood_service.analyze_flood(lat, lon)
        
    # 4. Fetch national disaster feeds (to compute AI risk and alerts)
    eq_data = get_india_earthquakes()
    drought_data = get_india_droughts()
    heat_data = get_india_heatwaves()
    cyclone_data = get_india_cyclones()
    
    earthquakes = eq_data.get("earthquakes", [])
    droughts = drought_data.get("droughts", [])
    heatwaves = heat_data.get("heatwaves", [])
    cyclones = cyclone_data.get("cyclones", [])
    
    # Filter/find closest earthquake
    closest_eq = None
    min_dist = 9999.0
    from services.ai_risk_engine import haversine_distance
    for eq in earthquakes:
        eq_lat = eq.get("lat")
        eq_lon = eq.get("lon")
        if eq_lat is not None and eq_lon is not None:
            dist = haversine_distance(lat, lon, eq_lat, eq_lon)
            if closest_eq is None or dist < min_dist:
                min_dist = dist
                closest_eq = eq
                
    if closest_eq is None:
        closest_eq = {
            "magnitude": 0.0,
            "depth_km": 0.0,
            "significance": 0.0,
            "time_iso": None,
            "lat": lat + 1.0,
            "lon": lon + 1.0
        }
    
    # 5. Extract features for AI Risk Engine
    flood_feats = FloodFeatureExtractor.extract_features(
        flood_sat_data if flood_sat_data and flood_sat_data.get("success") else None,
        weather if weather.get("status") == "ok" else None,
        {"lat": lat, "lon": lon}
    )
    
    eq_feats = EarthquakeAnomalyExtractor.extract_features(
        closest_eq, lat, lon, earthquakes
    )
    
    heat_feats = HeatwaveAnomalyExtractor.extract_features(
        weather if weather.get("status") == "ok" else {}
    )
    
    drought_feats = DroughtAnomalyExtractor.extract_features(
        weather if weather.get("status") == "ok" else {}
    )
    
    cyclone_feats = CycloneAnomalyExtractor.extract_features(
        weather if weather.get("status") == "ok" else {}, lat, lon
    )
    
    # 6. Predict Risks using AI Engine
    ai_engine = get_ai_risk_engine()
    
    flood_risk = ai_engine.predict_risk("flood", flood_feats)
    eq_risk = ai_engine.predict_risk("earthquake", eq_feats)
    heat_risk = ai_engine.predict_risk("heatwave", heat_feats)
    drought_risk = ai_engine.predict_risk("drought", drought_feats)
    cyclone_risk = ai_engine.predict_risk("cyclone", cyclone_feats)
    
    risks = {
        "flood": flood_risk,
        "earthquake": eq_risk,
        "heatwave": heat_risk,
        "drought": drought_risk,
        "cyclone": cyclone_risk,
    }
    
    # Calculate overall risk
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
    
    # Find contributing categories
    active_risks = sorted(
        [(k, v["score"]) for k, v in risks.items() if v.get("score") is not None],
        key=lambda x: x[1],
        reverse=True
    )
    contributing = [x[0] for x in active_risks[:3]]
    
    overall = {
        "score": overall_score,
        "level": overall_level,
        "confidence": overall_confidence,
        "contributing_categories": contributing
    }
    
    # 7. Generate alerts based on live feeds
    # Create mapped floods lists for alerts generator
    floods = []
    if flood_sat_data and flood_sat_data.get("success"):
        floods.append({
            "disaster_type": "flood",
            "lat": lat,
            "lon": lon,
            "status": "detected" if flood_sat_data.get("flood_detected") else "none_detected",
            "severity": "HIGH" if flood_sat_data.get("area_km2", 0) >= 5 else "LOW",
            "area_km2": flood_sat_data.get("area_km2"),
            "timestamp": flood_sat_data.get("image_date"),
            "source": "Sentinel-1/GEE"
        })
    alerts = generate_alerts(floods, earthquakes, droughts, heatwaves, cyclones)
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {
            "lat": lat,
            "lon": lon
        },
        "weather": {
            "status": weather.get("status"),
            "location_name": weather.get("location", "Unknown"),
            "temperature_c": weather.get("temperature"),
            "feels_like_c": weather.get("feels_like"),
            "humidity_pct": weather.get("humidity"),
            "wind_speed_ms": weather.get("wind_speed_ms"),
            "pressure_hpa": weather.get("pressure"),
            "condition": weather.get("condition"),
            "description": weather.get("description"),
        },
        "earthquake_event": {
            "closest_event": closest_eq,
            "distance_km": min_dist if min_dist != 9999.0 else None,
            "nearby_seismic_density_30d": eq_feats.get("nearby_count", 0.0)
        },
        "flood_info": {
            "satellite_ready": flood_service.check_ready(),
            "flood_detected": flood_sat_data.get("flood_detected") if flood_sat_data else False,
            "flooded_area_km2": flood_sat_data.get("area_km2") if flood_sat_data else None,
            "satellite_image_date": flood_sat_data.get("image_date") if flood_sat_data else None,
        },
        "ai_risk_scores": {
            "risks": risks,
            "overall": overall
        },
        "alerts": alerts,
        "nearest_resources": {
            "hospitals_count": len(hospitals),
            "shelters_count": len(shelters),
            "closest_hospital": hospitals[0] if hospitals else None,
            "closest_shelter": shelters[0] if shelters else None
        }
    }
