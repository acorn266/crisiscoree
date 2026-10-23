"""
ML-ready risk engine architecture.

Supports sklearn, TensorFlow, and PyTorch model loading.
When no trained model is available, returns model_not_available status
instead of pretending rule-based logic is AI.
"""
import os
from typing import Any, Dict, List, Optional

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")


class RiskEngine:
    """Unified disaster risk scoring engine with ML model support."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or os.path.join(MODEL_DIR, "risk_model.pkl")
        self.model = None
        self.model_type: Optional[str] = None
        self._try_load_model()

    def _try_load_model(self) -> None:
        if not os.path.exists(self.model_path):
            return
        try:
            import joblib
            self.model = joblib.load(self.model_path)
            self.model_type = "sklearn"
        except ImportError:
            pass
        except Exception:
            pass

        if self.model is None:
            tf_path = self.model_path.replace(".pkl", ".keras")
            if os.path.exists(tf_path):
                try:
                    import tensorflow as tf
                    self.model = tf.keras.models.load_model(tf_path)
                    self.model_type = "tensorflow"
                except ImportError:
                    pass
                except Exception:
                    pass

        if self.model is None:
            pt_path = self.model_path.replace(".pkl", ".pt")
            if os.path.exists(pt_path):
                try:
                    import torch
                    self.model = torch.load(pt_path, map_location="cpu")
                    self.model_type = "pytorch"
                except ImportError:
                    pass
                except Exception:
                    pass

    def is_model_available(self) -> bool:
        return self.model is not None

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_model_available():
            return {
                "status": "model_not_available",
                "score": None,
                "severity": "MODEL_NOT_AVAILABLE",
                "message": "No trained ML model loaded. Place model at backend/models/risk_model.pkl",
            }
        # Placeholder for future ML inference
        return {
            "status": "model_not_available",
            "score": None,
            "severity": "MODEL_NOT_AVAILABLE",
            "message": "Model loaded but inference pipeline not yet configured",
        }

    def compute_overall_risk(
        self,
        floods: List[Dict],
        earthquakes: List[Dict],
        droughts: List[Dict],
        heatwaves: List[Dict],
        cyclones: List[Dict],
    ) -> Dict[str, Any]:
        categories = {
            "flood": self._category_summary(floods, "flood"),
            "earthquake": self._category_summary(earthquakes, "earthquake"),
            "drought": self._category_summary(droughts, "drought"),
            "heatwave": self._category_summary(heatwaves, "heatwave"),
            "cyclone": self._category_summary(cyclones, "cyclone"),
        }

        return {
            **categories,
            "overall": {
                "score": None,
                "severity": "MODEL_NOT_AVAILABLE",
                "status": "model_not_available",
            },
        }

    def _category_summary(self, items: List[Dict], disaster_type: str) -> Dict[str, Any]:
        if not items:
            return {"score": None, "severity": "UNAVAILABLE", "status": "unavailable"}

        severities = [i.get("severity") for i in items if i.get("severity")]
        high_sev = {"HIGH", "EXTREME", "ELEVATED_STRESS", "ELEVATED"}
        medium_sev = {"MEDIUM", "MODERATE", "MONITOR", "conditions_elevated", "partial"}

        if any(s in high_sev for s in severities):
            sev = "ELEVATED"
        elif any(s in medium_sev for s in severities):
            sev = "MONITOR"
        elif all(s in ("UNAVAILABLE", "NONE", None) for s in severities):
            sev = "UNAVAILABLE" if all(s == "UNAVAILABLE" for s in severities) else "NONE"
        else:
            sev = "NONE"

        detected = any(i.get("status") in ("detected", "conditions_elevated", "partial", "ok") for i in items)

        return {
            "score": None,
            "severity": sev,
            "status": "data_available" if detected else "none_detected",
            "disaster_type": disaster_type,
        }


_engine: Optional[RiskEngine] = None


def get_risk_engine() -> RiskEngine:
    global _engine
    if _engine is None:
        _engine = RiskEngine()
    return _engine
