"""
CrisisCore AI/ML Risk Engine v2.0

Unified architecture for disaster risk assessment using:
- Supervised ML (when labeled data available)
- Anomaly Detection (when labeled data unavailable)
- Real-time feature fusion from all available data sources

No fabricated data. No fake labels. Real models, real predictions.
"""

import os
import json
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

try:
    from sklearn.ensemble import RandomForestClassifier, IsolationForest, GradientBoostingClassifier, ExtraTreesClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import precision_recall_fscore_support
    import joblib
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    print("Warning: scikit-learn not installed. AI Risk Engine will operate in limited mode.")

# ============================================================================
# MODEL REGISTRY & PERSISTENCE
# ============================================================================

MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

REGISTRY_FILE = MODEL_DIR / "model_registry.json"


def load_registry() -> Dict[str, Any]:
    """Load model registry from JSON."""
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"models": {}, "last_updated": None}


def save_registry(registry: Dict[str, Any]) -> None:
    """Save model registry to JSON."""
    registry["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)


# ============================================================================
# DISTANCE HELPER FOR COASTAL PROXIMITY
# ============================================================================

COASTAL_CITIES = [
    {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    {"name": "Mumbai", "lat": 19.076, "lon": 72.8777},
    {"name": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    {"name": "Visakhapatnam", "lat": 17.6868, "lon": 83.2185},
    {"name": "Kochi", "lat": 9.9312, "lon": 76.2673},
    {"name": "Puri", "lat": 19.8135, "lon": 85.8312},
    {"name": "Surat", "lat": 21.1702, "lon": 72.8311},
    {"name": "Mangalore", "lat": 12.9141, "lon": 74.8560},
]

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in km."""
    R = 6371.0  # Earth radius in km
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c

def get_coastal_proximity_km(lat: float, lon: float) -> float:
    """Find distance in km to nearest coastal city."""
    min_dist = 9999.0
    for city in COASTAL_CITIES:
        dist = haversine_distance(lat, lon, city["lat"], city["lon"])
        if dist < min_dist:
            min_dist = dist
    return min_dist


# ============================================================================
# FEATURE ENGINEERING & DATA PREPARATION
# ============================================================================

class FloodFeatureExtractor:
    """Extract and prepare flood features from satellite + weather data."""
    
    @staticmethod
    def extract_features(
        satellite_data: Dict[str, Any],
        weather_data: Dict[str, Any],
        location_features: Dict[str, Any] = None,
    ) -> Dict[str, float]:
        """Combine Sentinel-1 satellite data with weather features."""
        features = {}
        
        # Satellite features
        if satellite_data:
            features["satellite_flood_area_km2"] = float(satellite_data.get("area_km2") or 0.0)
            features["satellite_flood_detected"] = 1.0 if satellite_data.get("flood_detected") else 0.0
            # Recency
            recency = satellite_data.get("satellite_recency_hours")
            if recency is None and satellite_data.get("image_date"):
                try:
                    img_date = datetime.strptime(satellite_data["image_date"], "%Y-%m-%d")
                    now = datetime.utcnow()
                    recency = (now - img_date).total_seconds() / 3600.0
                except Exception:
                    recency = 24.0
            features["satellite_recency_hours"] = float(recency if recency is not None else 24.0)
        else:
            features["satellite_flood_area_km2"] = 0.0
            features["satellite_flood_detected"] = 0.0
            features["satellite_recency_hours"] = 999.0
        
        # Weather features
        if weather_data:
            features["rainfall_1h_mm"] = float(weather_data.get("rainfall_1h_mm") or 0.0)
            features["rainfall_3h_mm"] = float(weather_data.get("rainfall_3h_mm") or 0.0)
            features["humidity_pct"] = float(weather_data.get("humidity") or weather_data.get("humidity_pct") or 50.0)
            features["temperature_c"] = float(weather_data.get("temperature") or weather_data.get("temperature_c") or 25.0)
            features["clouds_pct"] = float(weather_data.get("clouds") or weather_data.get("clouds_pct") or 50.0)
            features["wind_speed_ms"] = float(weather_data.get("wind_speed_ms") or weather_data.get("wind_speed") or 0.0)
            features["pressure_hpa"] = float(weather_data.get("pressure") or weather_data.get("pressure_hpa") or 1013.0)
        else:
            features["rainfall_1h_mm"] = 0.0
            features["rainfall_3h_mm"] = 0.0
            features["humidity_pct"] = 50.0
            features["temperature_c"] = 25.0
            features["clouds_pct"] = 50.0
            features["wind_speed_ms"] = 0.0
            features["pressure_hpa"] = 1013.0
        
        # Location features
        lat = location_features.get("lat", 20.5937) if location_features else 20.5937
        lon = location_features.get("lon", 78.9629) if location_features else 78.9629
        features["is_coastal"] = 1.0 if get_coastal_proximity_km(lat, lon) < 100.0 else 0.0
        features["elevation_m"] = float(location_features.get("elevation_m") or 100.0) if location_features else 100.0
        
        return features


class EarthquakeAnomalyExtractor:
    """Extract features for earthquake anomaly detection near a location."""
    
    @staticmethod
    def extract_features(earthquake_event: Dict[str, Any], target_lat: float, target_lon: float, nearby_events: List[Dict[str, Any]] = None) -> Dict[str, float]:
        """Extract earthquake event characteristics relative to target location."""
        features = {}
        
        features["magnitude"] = float(earthquake_event.get("magnitude") or 0.0)
        features["depth_km"] = float(earthquake_event.get("depth_km") or 10.0)
        features["significance"] = float(earthquake_event.get("significance") or 0.0)
        
        # Recency: hours since event
        time_iso = earthquake_event.get("time_iso")
        if time_iso:
            try:
                event_time = datetime.fromisoformat(time_iso.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                recency_hours = (now - event_time).total_seconds() / 3600.0
                features["recency_hours"] = min(recency_hours, 720.0)  # cap at 30 days
            except Exception:
                features["recency_hours"] = 720.0
        else:
            features["recency_hours"] = 720.0
            
        # Distance from location
        eq_lat = earthquake_event.get("lat")
        eq_lon = earthquake_event.get("lon")
        if eq_lat is not None and eq_lon is not None:
            features["distance_km"] = float(haversine_distance(target_lat, target_lon, eq_lat, eq_lon))
        else:
            features["distance_km"] = 999.0
            
        # Nearby event density (number of events within 300km in the last 30 days)
        if nearby_events:
            count = 0
            for ev in nearby_events:
                ev_lat = ev.get("lat")
                ev_lon = ev.get("lon")
                if ev_lat is not None and ev_lon is not None:
                    dist = haversine_distance(target_lat, target_lon, ev_lat, ev_lon)
                    if dist <= 300.0:
                        count += 1
            features["nearby_count"] = float(count)
        else:
            features["nearby_count"] = 0.0
            
        return features


class HeatwaveAnomalyExtractor:
    """Extract features for heatwave anomaly detection."""
    
    @staticmethod
    def extract_features(weather_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract heat-related features."""
        features = {}
        
        temp = float(weather_data.get("temperature") or weather_data.get("temperature_c") or 25.0)
        feels_like = float(weather_data.get("feels_like") or weather_data.get("feels_like_c") or temp)
        humidity = float(weather_data.get("humidity") or weather_data.get("humidity_pct") or 50.0)
        wind = float(weather_data.get("wind_speed_ms") or weather_data.get("wind_speed") or 0.0)
        pressure = float(weather_data.get("pressure") or weather_data.get("pressure_hpa") or 1013.0)
        
        # Approximate Heat Index
        temp_f = temp * 9 / 5 + 32
        hi_f = (
            -42.379 + 2.04901523 * temp_f + 10.14333127 * humidity
            - 0.22475541 * temp_f * humidity
            - 0.00683783 * temp_f ** 2
            - 0.05481717 * humidity ** 2
            + 0.00122874 * temp_f ** 2 * humidity
            + 0.00085282 * temp_f * humidity ** 2
            - 0.00000199 * temp_f ** 2 * humidity ** 2
        )
        heat_index = round((hi_f - 32) * 5 / 9, 2)
        
        features["temperature_c"] = temp
        features["feels_like_c"] = feels_like
        features["heat_index_c"] = heat_index
        features["humidity_pct"] = humidity
        features["wind_speed_ms"] = wind
        features["pressure_hpa"] = pressure
        
        return features


class DroughtAnomalyExtractor:
    """Extract features for drought anomaly detection."""
    
    @staticmethod
    def extract_features(weather_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract drought-related features."""
        features = {}
        
        features["temperature_c"] = float(weather_data.get("temperature") or weather_data.get("temperature_c") or 25.0)
        features["rainfall_1h_mm"] = float(weather_data.get("rainfall_1h_mm") or 0.0)
        features["rainfall_3h_mm"] = float(weather_data.get("rainfall_3h_mm") or 0.0)
        features["humidity_pct"] = float(weather_data.get("humidity") or weather_data.get("humidity_pct") or 50.0)
        features["pressure_hpa"] = float(weather_data.get("pressure") or weather_data.get("pressure_hpa") or 1013.0)
        
        return features


class CycloneAnomalyExtractor:
    """Extract features for cyclone condition anomaly detection."""
    
    @staticmethod
    def extract_features(weather_data: Dict[str, Any], lat: float, lon: float) -> Dict[str, float]:
        """Extract cyclone-relevant weather features."""
        features = {}
        
        features["wind_speed_ms"] = float(weather_data.get("wind_speed_ms") or weather_data.get("wind_speed") or 0.0)
        features["wind_gust_ms"] = float(weather_data.get("wind_gust_ms") or features["wind_speed_ms"] * 1.2)
        features["pressure_hpa"] = float(weather_data.get("pressure") or weather_data.get("pressure_hpa") or 1013.0)
        features["humidity_pct"] = float(weather_data.get("humidity") or weather_data.get("humidity_pct") or 50.0)
        features["temperature_c"] = float(weather_data.get("temperature") or weather_data.get("temperature_c") or 25.0)
        features["coastal_proximity"] = get_coastal_proximity_km(lat, lon)
        
        return features


# ============================================================================
# BASE MODEL & IMPLEMENTATIONS
# ============================================================================

class DisasterRiskModel:
    """Base class for disaster risk models."""
    
    def __init__(self, disaster_type: str):
        self.disaster_type = disaster_type
        self.model = None
        self.scaler = None
        self.feature_names = []
        self.model_type = None
        self.metadata = {
            "disaster_type": disaster_type,
            "trained_at": None,
            "n_samples": 0,
            "features": [],
            "model_type": None,
            "method": None,  # "supervised_ml" or "anomaly_detection"
        }
        # Calibration bounds for scoring
        self.s_min_ = -0.4
        self.s_max_ = 0.4
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Extract feature importance from trained model."""
        if self.model is None:
            return {}
        
        if hasattr(self.model, 'feature_importances_'):
            # Tree-based models
            importances = self.model.feature_importances_
        elif hasattr(self.model, 'coef_'):
            # Linear models
            importances = np.abs(self.model.coef_[0])
        else:
            return {}
        
        # Normalize to 0-1
        if len(importances) > 0 and np.sum(importances) > 0:
            importances = importances / np.sum(importances)
        
        return {
            name: float(imp) for name, imp in zip(self.feature_names, importances)
        }

    def explain_anomaly(self, raw_features: Dict[str, float]) -> List[str]:
        """Explain anomaly by analyzing Z-score feature deviations."""
        factors = []
        if self.scaler is None or not hasattr(self.scaler, 'mean_') or not self.feature_names:
            return ["unusual environmental features"]
        
        # Calculate Z-scores for current values
        z_scores = {}
        for i, name in enumerate(self.feature_names):
            val = raw_features.get(name, 0.0)
            mean = self.scaler.mean_[i]
            scale = self.scaler.scale_[i] if self.scaler.scale_[i] != 0 else 1.0
            z_scores[name] = (val - mean) / scale
        
        if self.disaster_type == "flood":
            if raw_features.get("satellite_flood_detected", 0.0) > 0.0:
                factors.append("recent satellite flood detection")
            if raw_features.get("satellite_flood_area_km2", 0.0) > 0.1:
                factors.append("elevated flooded area")
            if z_scores.get("rainfall_3h_mm", 0.0) > 0.5 or raw_features.get("rainfall_3h_mm", 0.0) > 2.0:
                factors.append("heavy accumulated rainfall")
            elif z_scores.get("rainfall_1h_mm", 0.0) > 0.5 or raw_features.get("rainfall_1h_mm", 0.0) > 1.0:
                factors.append("recent heavy rainfall")
            if z_scores.get("humidity_pct", 0.0) > 0.2:
                factors.append("high relative humidity")
            if not factors:
                factors.append("saturated weather indicators")
                
        elif self.disaster_type == "earthquake":
            if raw_features.get("magnitude", 0.0) > 3.0:
                factors.append("earthquake magnitude")
            if raw_features.get("recency_hours", 999.0) < 24.0:
                factors.append("recent seismic event")
            if raw_features.get("distance_km", 999.0) < 150.0:
                factors.append("close proximity to epicenter")
            if raw_features.get("nearby_count", 0.0) > 1.0:
                factors.append("elevated nearby seismic activity density")
            if not factors:
                factors.append("unusual seismic activity")
                
        elif self.disaster_type == "heatwave":
            if z_scores.get("temperature_c", 0.0) > 0.5 or raw_features.get("temperature_c", 0.0) > 35.0:
                factors.append("extreme temperature")
            if z_scores.get("feels_like_c", 0.0) > 0.5 or raw_features.get("feels_like_c", 0.0) > 37.0:
                factors.append("high apparent temperature")
            if z_scores.get("heat_index_c", 0.0) > 0.5 or raw_features.get("heat_index_c", 0.0) > 37.0:
                factors.append("elevated heat index")
            if z_scores.get("humidity_pct", 0.0) > 0.5:
                factors.append("high relative humidity")
            if not factors:
                factors.append("extreme temperature markers")
                
        elif self.disaster_type == "drought":
            if raw_features.get("rainfall_1h_mm", 0.0) == 0.0 and raw_features.get("rainfall_3h_mm", 0.0) == 0.0:
                factors.append("lack of recent rainfall")
            if z_scores.get("humidity_pct", 0.0) < -0.5 or raw_features.get("humidity_pct", 50.0) < 30.0:
                factors.append("low relative humidity")
            if z_scores.get("temperature_c", 0.0) > 0.5 or raw_features.get("temperature_c", 0.0) > 35.0:
                factors.append("high temperature")
            if not factors:
                factors.append("dry meteorological indicators")
                
        elif self.disaster_type == "cyclone":
            if z_scores.get("wind_speed_ms", 0.0) > 0.5 or raw_features.get("wind_speed_ms", 0.0) > 10.0:
                factors.append("elevated wind speed")
            if z_scores.get("wind_gust_ms", 0.0) > 0.5 or raw_features.get("wind_gust_ms", 0.0) > 12.0:
                factors.append("strong wind gusts")
            if z_scores.get("pressure_hpa", 0.0) < -0.5 or raw_features.get("pressure_hpa", 1013.0) < 1008.0:
                factors.append("low atmospheric pressure")
            if raw_features.get("coastal_proximity", 999.0) < 100.0:
                factors.append("coastal proximity")
            if not factors:
                factors.append("cyclone-like weather markers")
                
        return factors[:4]


class AnomalyDetectionModel(DisasterRiskModel):
    """Anomaly detection model using Isolation Forest."""
    
    def __init__(self, disaster_type: str):
        super().__init__(disaster_type)
        self.contamination = 0.1
        
    def train_anomaly(self, training_data: List[Dict[str, float]]) -> Dict[str, Any]:
        """Train Isolation Forest on real feature vectors."""
        if not HAS_SKLEARN:
            return {"error": "scikit-learn not installed"}
        
        if len(training_data) < 5:
            return {"error": f"Insufficient data ({len(training_data)} samples)"}
        
        self.feature_names = list(training_data[0].keys())
        
        # Build training matrix
        X = np.array([[sample[name] for name in self.feature_names] for sample in training_data])
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Fit Isolation Forest
        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=42,
            n_jobs=-1
        )
        self.model.fit(X_scaled)
        
        # Calibrate decision scores
        decision_scores = self.model.decision_function(X_scaled)
        self.s_min_ = float(np.min(decision_scores))
        self.s_max_ = float(np.max(decision_scores))
        
        self.model_type = "IsolationForest"
        self.metadata["model_type"] = "IsolationForest"
        self.metadata["method"] = "anomaly_detection"
        self.metadata["trained_at"] = datetime.now(timezone.utc).isoformat()
        self.metadata["n_samples"] = len(training_data)
        self.metadata["features"] = self.feature_names
        
        return {
            "model": "IsolationForest",
            "method": "anomaly_detection",
            "n_samples": len(training_data),
            "s_min": self.s_min_,
            "s_max": self.s_max_
        }
        
    def predict(self, features: Dict[str, float]) -> Dict[str, Any]:
        if self.model is None:
            return {
                "score": None,
                "level": "DATA_LIMITED",
                "confidence": 0,
                "model": "IsolationForest",
                "method": "anomaly_detection",
                "factors": [],
                "available": False,
                "reason": "Model not trained"
            }
        
        try:
            X = np.array([[features.get(name, 0.0) for name in self.feature_names]])
            X_scaled = self.scaler.transform(X)
            
            # decision_function score: lower = more anomalous
            s = self.model.decision_function(X_scaled)[0]
            
            # Map score to 0-100 index
            s_min = getattr(self, "s_min_", -0.4)
            s_max = getattr(self, "s_max_", 0.4)
            
            if s < 0:
                # Anomalous
                div = s_min if s_min < 0 else -0.4
                ratio = s / div
                risk_score = 50 + 50 * min(1.0, max(0.0, ratio))
            else:
                # Normal
                div = s_max if s_max > 0 else 0.4
                ratio = s / div
                risk_score = 50 - 50 * min(1.0, max(0.0, ratio))
                
            risk_score = int(min(100, max(0, risk_score)))
            
            # Set levels
            if risk_score >= 85:
                level = "CRITICAL"
            elif risk_score >= 65:
                level = "HIGH"
            elif risk_score >= 35:
                level = "MEDIUM"
            else:
                level = "LOW"
                
            # Confidence based on anomaly score severity
            confidence = float(round(0.70 + 0.25 * min(1.0, abs(s) / 0.3), 2))
            
            # Get explainable factors
            factors = self.explain_anomaly(features)
            
            # Explicitly mark drought as limited
            reason = f"{self.disaster_type.capitalize()} risk assessed via Isolation Forest anomaly detection"
            if self.disaster_type == "drought":
                reason += ". Note: Limited by absence of long-term drought baseline."
                
            return {
                "score": risk_score,
                "level": level,
                "confidence": confidence,
                "model": "IsolationForest",
                "method": "anomaly_detection",
                "factors": factors,
                "available": True,
                "reason": reason
            }
        except Exception as e:
            return {
                "score": None,
                "level": "DATA_LIMITED",
                "confidence": 0,
                "model": "IsolationForest",
                "method": "anomaly_detection",
                "factors": [],
                "available": False,
                "reason": f"Prediction error: {str(e)}"
            }


class FloodRiskModel(DisasterRiskModel):
    """ML model for flood risk assessment, combining satellite and weather anomalies."""
    
    def __init__(self):
        super().__init__("flood")
        self.anomaly_model = AnomalyDetectionModel("flood")
        
    def train_supervised(self, training_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Trained supervised models for flood (if ground-truth data available)."""
        if not HAS_SKLEARN:
            return {"error": "scikit-learn not installed"}
        
        if len(training_data) < 10:
            return {"error": f"Insufficient data ({len(training_data)} samples)"}
            
        X = np.array([[d["features"][name] for name in d["features"].keys()] for d in training_data])
        y = np.array([d["label"] for d in training_data])
        self.feature_names = list(training_data[0]["features"].keys())
        
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
        
        models = {
            "RandomForest": RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1),
            "ExtraTrees": ExtraTreesClassifier(n_estimators=100, random_state=42, n_jobs=-1),
            "GradientBoosting": GradientBoostingClassifier(n_estimators=100, random_state=42),
            "LogisticRegression": LogisticRegression(random_state=42, max_iter=1000),
        }
        
        best_model_name = None
        best_score = -1
        results = {}
        
        for name, model in models.items():
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="binary", zero_division=0)
            score = f1 * 0.4 + recall * 0.6  # prioritize recall
            
            results[name] = {
                "precision": float(precision),
                "recall": float(recall),
                "f1": float(f1),
                "score": float(score)
            }
            if score > best_score:
                best_score = score
                best_model_name = name
                self.model = model
                
        self.model_type = best_model_name
        self.metadata["model_type"] = best_model_name
        self.metadata["method"] = "supervised_ml"
        self.metadata["trained_at"] = datetime.now(timezone.utc).isoformat()
        self.metadata["n_samples"] = len(training_data)
        self.metadata["features"] = self.feature_names
        
        return {
            "selected_model": best_model_name,
            "all_models": results,
            "best_score": best_score
        }
        
    def train_anomaly(self, training_data: List[Dict[str, float]]) -> Dict[str, Any]:
        """Fallback training method using unsupervised Isolation Forest."""
        res = self.anomaly_model.train_anomaly(training_data)
        self.model = self.anomaly_model.model
        self.scaler = self.anomaly_model.scaler
        self.feature_names = self.anomaly_model.feature_names
        self.model_type = "IsolationForest"
        self.metadata["model_type"] = "IsolationForest"
        self.metadata["method"] = "anomaly_detection"
        self.metadata["trained_at"] = self.anomaly_model.metadata["trained_at"]
        self.metadata["n_samples"] = self.anomaly_model.metadata["n_samples"]
        self.metadata["features"] = self.anomaly_model.feature_names
        self.s_min_ = getattr(self.anomaly_model, "s_min_", -0.4)
        self.s_max_ = getattr(self.anomaly_model, "s_max_", 0.4)
        return res

    def predict(self, features: Dict[str, float]) -> Dict[str, Any]:
        if self.model is None:
            return {
                "score": None,
                "level": "DATA_LIMITED",
                "confidence": 0,
                "model": "IsolationForest",
                "method": "anomaly_detection",
                "factors": [],
                "available": False,
                "reason": "Model not trained"
            }
            
        if self.metadata.get("method") == "supervised_ml":
            try:
                X = np.array([[features.get(name, 0.0) for name in self.feature_names]])
                X_scaled = self.scaler.transform(X)
                prob = self.model.predict_proba(X_scaled)[0]
                flood_prob = prob[1]
                score = int(flood_prob * 100)
                
                if score >= 85:
                    level = "CRITICAL"
                elif score >= 65:
                    level = "HIGH"
                elif score >= 35:
                    level = "MEDIUM"
                else:
                    level = "LOW"
                    
                importances = self.get_feature_importance()
                top_importances = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:3]
                factors = [f[0] for f in top_importances]
                
                return {
                    "score": score,
                    "level": level,
                    "confidence": float(max(prob)),
                    "model": self.model_type,
                    "method": "supervised_ml",
                    "factors": factors,
                    "available": True,
                    "reason": f"Flood risk predicted by {self.model_type} model"
                }
            except Exception as e:
                return {
                    "score": None,
                    "level": "DATA_LIMITED",
                    "confidence": 0,
                    "model": self.model_type,
                    "method": "supervised_ml",
                    "factors": [],
                    "available": False,
                    "reason": f"Prediction error: {str(e)}"
                }
        else:
            # Predict using IsolationForest anomaly detection
            res = self.anomaly_model.predict(features)
            
            # Combine satellite evidence with model output
            area_km2 = features.get("satellite_flood_area_km2", 0.0)
            detected = features.get("satellite_flood_detected", 0.0)
            
            if detected > 0.0 or area_km2 > 0.01:
                base_score = res["score"] if res["score"] is not None else 0
                # Direct satellite detection guarantees at least 80% risk, scaling up to 100%
                sat_score = 80 + min(20, int(area_km2 * 10))
                combined_score = max(base_score, sat_score)
                res["score"] = int(min(100, combined_score))
                
                # Re-calculate level
                if res["score"] >= 85:
                    res["level"] = "CRITICAL"
                elif res["score"] >= 65:
                    res["level"] = "HIGH"
                elif res["score"] >= 35:
                    res["level"] = "MEDIUM"
                else:
                    res["level"] = "LOW"
                
                # Satellite evidence boosts confidence
                res["confidence"] = min(0.95, res["confidence"] + 0.15)
                
                # Prioritize satellite factors
                if "recent satellite flood detection" not in res["factors"]:
                    res["factors"].insert(0, "recent satellite flood detection")
                if "elevated flooded area" not in res["factors"] and area_km2 > 0.1:
                    res["factors"].insert(1, "elevated flooded area")
                res["factors"] = res["factors"][:4]
                res["reason"] = "Flood risk assessed via Isolation Forest anomaly detection combined with active Sentinel-1 satellite evidence"
                
            return res


# ============================================================================
# UNIFIED AI RISK ENGINE
# ============================================================================

class AIRiskEngine:
    """CrisisCore Unified AI/ML Risk Engine."""
    
    def __init__(self):
        self.models = {
            "flood": FloodRiskModel(),
            "earthquake": AnomalyDetectionModel("earthquake"),
            "heatwave": AnomalyDetectionModel("heatwave"),
            "drought": AnomalyDetectionModel("drought"),
            "cyclone": AnomalyDetectionModel("cyclone"),
        }
        self.registry = load_registry()
        self._load_trained_models()
    
    def _load_trained_models(self) -> None:
        """Load trained models from disk using joblib."""
        for disaster_type in self.models.keys():
            model_path = MODEL_DIR / f"{disaster_type}_model.joblib"
            if model_path.exists():
                try:
                    saved_model = joblib.load(model_path)
                    self.models[disaster_type] = saved_model
                    print(f"Loaded trained model: {disaster_type} ({saved_model.model_type})")
                except Exception as e:
                    print(f"Error loading {disaster_type} model: {e}")
    
    def save_models(self) -> None:
        """Save all trained models to disk using joblib."""
        for disaster_type, model in self.models.items():
            if model.model is not None:
                model_path = MODEL_DIR / f"{disaster_type}_model.joblib"
                joblib.dump(model, model_path)
                print(f"Saved model: {disaster_type} to {model_path}")
        
        save_registry(self.registry)
    
    def predict_risk(
        self,
        disaster_type: str,
        features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Predict risk for a disaster type."""
        if disaster_type not in self.models:
            return {
                "score": None,
                "level": "DATA_LIMITED",
                "confidence": 0,
                "model": "None",
                "method": "None",
                "factors": [],
                "available": False,
                "reason": f"Unknown disaster type: {disaster_type}"
            }
        
        model = self.models[disaster_type]
        return model.predict(features)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_engine: Optional[AIRiskEngine] = None


def get_ai_risk_engine() -> AIRiskEngine:
    """Get or create the singleton AI Risk Engine."""
    global _engine
    if _engine is None:
        _engine = AIRiskEngine()
    return _engine
