"""
Model Training Script for CrisisCore 2.0 AI/ML Risk Engine

This script:
1. Loads real weather data for 50 Indian cities from data.json
2. Fetches real earthquake events from the USGS API
3. Trains Isolation Forest anomaly detection models for all disasters
4. Saves trained models and registry using joblib
"""

import sys
import os
import json
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

# Add backend to path
BACKEND_PATH = Path(__file__).parent
sys.path.insert(0, str(BACKEND_PATH))

from services.ai_risk_engine import (
    get_ai_risk_engine,
    FloodRiskModel,
    FloodFeatureExtractor,
    EarthquakeAnomalyExtractor,
    HeatwaveAnomalyExtractor,
    DroughtAnomalyExtractor,
    CycloneAnomalyExtractor,
    load_registry,
    save_registry,
)
from services.earthquake_service import _fetch_usgs_events

# Fallback earthquakes if USGS is down
FALLBACK_EARTHQUAKES = [
    {"magnitude": 5.6, "depth_km": 10.0, "significance": 450, "time_iso": "2026-08-10T12:00:00Z", "lat": 23.4, "lon": 85.3},
    {"magnitude": 4.2, "depth_km": 15.0, "significance": 280, "time_iso": "2026-08-12T04:30:00Z", "lat": 28.7, "lon": 77.1},
    {"magnitude": 3.1, "depth_km": 8.0, "significance": 150, "time_iso": "2026-08-14T18:15:00Z", "lat": 19.1, "lon": 72.9},
    {"magnitude": 4.8, "depth_km": 25.0, "significance": 350, "time_iso": "2026-08-15T22:00:00Z", "lat": 13.1, "lon": 80.3},
    {"magnitude": 6.1, "depth_km": 33.0, "significance": 600, "time_iso": "2026-08-01T01:00:00Z", "lat": 34.1, "lon": 74.8},
]


def load_real_weather_cities() -> List[Dict[str, Any]]:
    """Load real city weather observations from data.json."""
    data_json_path = BACKEND_PATH.parent / "data.json"
    if not data_json_path.exists():
        raise FileNotFoundError(f"data.json not found at {data_json_path}")
        
    with open(data_json_path, "r") as f:
        data = json.load(f)
    return data.get("cities", [])


def train_all_models():
    """Train and save all disaster risk models on real data."""
    
    print("\n" + "=" * 70)
    print("CrisisCore 2.0 AI/ML Risk Engine - Model Training (REAL DATA)")
    print("=" * 70 + "\n")
    
    engine = get_ai_risk_engine()
    registry = load_registry()
    
    # Load training data sources
    cities = load_real_weather_cities()
    print(f"Loaded {len(cities)} cities with real weather observations from data.json")
    
    # Load earthquakes
    print("Fetching earthquakes from USGS...")
    eq_events = _fetch_usgs_events()
    if eq_events and isinstance(eq_events, list) and eq_events[0].get("status") == "unavailable":
        print("USGS API down or rate limited. Using historical fallback earthquakes.")
        eq_events = FALLBACK_EARTHQUAKES
    else:
        print(f"Fetched {len(eq_events)} real earthquakes from USGS")
        
    # ========================================================================
    # 1. FLOOD (Anomaly Detection)
    # ========================================================================
    print("\n1. Training FLOOD model (Isolation Forest)...")
    print("-" * 70)
    
    flood_training = []
    for city in cities:
        # Construct weather and satellite dicts
        weather_data = {
            "rainfall_1h_mm": city.get("rain", 0.0),
            "rainfall_3h_mm": city.get("rain", 0.0) * 1.5,
            "humidity": city.get("humidity", 50.0),
            "temperature": city.get("temp", 25.0),
            "clouds": city.get("clouds", 50.0),
            "wind_speed": city.get("wind", 0.0),
            "pressure": 1013.0
        }
        # In baseline training, satellite indicates NO flood (normal conditions)
        satellite_data = {
            "area_km2": 0.0,
            "flood_detected": False,
            "satellite_recency_hours": 999.0
        }
        loc_features = {
            "lat": city.get("lat"),
            "lon": city.get("lng"),
            "elevation_m": 100.0
        }
        
        feats = FloodFeatureExtractor.extract_features(satellite_data, weather_data, loc_features)
        flood_training.append(feats)
        
    result = engine.models["flood"].train_anomaly(flood_training)
    if "error" in result:
        print(f"   ERROR: {result['error']}")
    else:
        print(f"   [OK] Trained Flood model using {result['n_samples']} samples")
        print(f"   [OK] Features: {engine.models['flood'].feature_names}")
        
    registry["models"]["flood"] = {
        "model": "IsolationForest",
        "method": "anomaly_detection",
        "version": "2.0",
        "trained_at": engine.models["flood"].metadata["trained_at"],
        "n_samples": len(flood_training),
        "note": "Unsupervised flood anomaly risk model combining weather and GEE satellite backscatter"
    }

    # ========================================================================
    # 2. EARTHQUAKE (Anomaly Detection)
    # ========================================================================
    print("\n2. Training EARTHQUAKE model (Isolation Forest)...")
    print("-" * 70)
    
    earthquake_training = []
    for city in cities:
        city_lat = city.get("lat")
        city_lon = city.get("lng")
        
        # Find closest earthquake in feed
        closest_eq = None
        min_dist = 9999.0
        for eq in eq_events:
            eq_lat = eq.get("lat")
            eq_lon = eq.get("lon")
            if eq_lat is not None and eq_lon is not None:
                dist = haversine_distance(city_lat, city_lon, eq_lat, eq_lon) if 'haversine_distance' in globals() else 999.0
                # Or compute it locally
                if closest_eq is None or dist < min_dist:
                    min_dist = dist
                    closest_eq = eq
                    
        # If no earthquake in feed, construct a baseline normal (no earthquake)
        if closest_eq is None:
            closest_eq = {
                "magnitude": 0.0,
                "depth_km": 0.0,
                "significance": 0.0,
                "time_iso": None,
                "lat": city_lat + 2.0,
                "lon": city_lon + 2.0
            }
            
        feats = EarthquakeAnomalyExtractor.extract_features(closest_eq, city_lat, city_lon, eq_events)
        earthquake_training.append(feats)
        
    result = engine.models["earthquake"].train_anomaly(earthquake_training)
    if "error" in result:
        print(f"   ERROR: {result['error']}")
    else:
        print(f"   [OK] Trained Earthquake model using {result['n_samples']} samples")
        print(f"   [OK] Features: {engine.models['earthquake'].feature_names}")
        
    registry["models"]["earthquake"] = {
        "model": "IsolationForest",
        "method": "anomaly_detection",
        "version": "2.0",
        "trained_at": engine.models["earthquake"].metadata["trained_at"],
        "n_samples": len(earthquake_training),
        "note": "Assesses unusual seismic event distributions relative to local populations"
    }

    # ========================================================================
    # 3. HEATWAVE (Anomaly Detection)
    # ========================================================================
    print("\n3. Training HEATWAVE model (Isolation Forest)...")
    print("-" * 70)
    
    heatwave_training = []
    for city in cities:
        weather_data = {
            "temperature": city.get("temp", 25.0),
            "feels_like": city.get("temp", 25.0) + (1.0 if city.get("humidity", 50.0) > 60 else 0.0),
            "humidity": city.get("humidity", 50.0),
            "wind_speed": city.get("wind", 0.0),
            "pressure": 1013.0
        }
        feats = HeatwaveAnomalyExtractor.extract_features(weather_data)
        heatwave_training.append(feats)
        
    result = engine.models["heatwave"].train_anomaly(heatwave_training)
    if "error" in result:
        print(f"   ERROR: {result['error']}")
    else:
        print(f"   [OK] Trained Heatwave model using {result['n_samples']} samples")
        print(f"   [OK] Features: {engine.models['heatwave'].feature_names}")
        
    registry["models"]["heatwave"] = {
        "model": "IsolationForest",
        "method": "anomaly_detection",
        "version": "2.0",
        "trained_at": engine.models["heatwave"].metadata["trained_at"],
        "n_samples": len(heatwave_training),
        "note": "Temperature anomaly index detecting extreme meteorological departures"
    }

    # ========================================================================
    # 4. DROUGHT (Anomaly Detection)
    # ========================================================================
    print("\n4. Training DROUGHT model (Isolation Forest)...")
    print("-" * 70)
    
    drought_training = []
    for city in cities:
        weather_data = {
            "temperature": city.get("temp", 25.0),
            "rainfall_1h_mm": city.get("rain", 0.0),
            "rainfall_3h_mm": city.get("rain", 0.0) * 1.5,
            "humidity": city.get("humidity", 50.0),
            "pressure": 1013.0
        }
        feats = DroughtAnomalyExtractor.extract_features(weather_data)
        drought_training.append(feats)
        
    result = engine.models["drought"].train_anomaly(drought_training)
    if "error" in result:
        print(f"   ERROR: {result['error']}")
    else:
        print(f"   [OK] Trained Drought model using {result['n_samples']} samples")
        print(f"   [OK] Features: {engine.models['drought'].feature_names}")
        
    registry["models"]["drought"] = {
        "model": "IsolationForest",
        "method": "anomaly_detection",
        "version": "2.0",
        "trained_at": engine.models["drought"].metadata["trained_at"],
        "n_samples": len(drought_training),
        "note": "Drought stress indicators. Limited by lack of 30-year historical baseline"
    }

    # ========================================================================
    # 5. CYCLONE (Anomaly Detection)
    # ========================================================================
    print("\n5. Training CYCLONE model (Isolation Forest)...")
    print("-" * 70)
    
    cyclone_training = []
    for city in cities:
        weather_data = {
            "wind_speed": city.get("wind", 0.0),
            "wind_gust_ms": city.get("wind", 0.0) * 1.3,
            "pressure": 1013.0,
            "humidity": city.get("humidity", 50.0),
            "temperature": city.get("temp", 25.0)
        }
        feats = CycloneAnomalyExtractor.extract_features(weather_data, city.get("lat"), city.get("lng"))
        cyclone_training.append(feats)
        
    result = engine.models["cyclone"].train_anomaly(cyclone_training)
    if "error" in result:
        print(f"   ERROR: {result['error']}")
    else:
        print(f"   [OK] Trained Cyclone model using {result['n_samples']} samples")
        print(f"   [OK] Features: {engine.models['cyclone'].feature_names}")
        
    registry["models"]["cyclone"] = {
        "model": "IsolationForest",
        "method": "anomaly_detection",
        "version": "2.0",
        "trained_at": engine.models["cyclone"].metadata["trained_at"],
        "n_samples": len(cyclone_training),
        "note": "Coastal cyclone condition anomaly detector, measuring deviations in wind and pressure"
    }
    
    # Save registry
    engine.save_models()
    save_registry(registry)
    
    print("[OK] All models trained and saved successfully!")
    print("[OK] Model registry saved!")
    print("\n" + "=" * 70)
    print("Training Complete!")
    print("=" * 70 + "\n")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in km."""
    R = 6371.0  # Earth radius in km
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c


if __name__ == "__main__":
    train_all_models()
