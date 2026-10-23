"""Physical-threshold guards for the AI risk scores.

The Isolation Forest models score how *unusual* conditions look, not how
*dangerous* they are, so a mild day can come out as an extreme anomaly. These
guards cap a model score when live observations clearly rule out the hazard,
using criteria modelled on IMD definitions. They only ever lower a score.

  Heatwave  IMD: max temp >= 40 C (plains), >= 37 C (coast); severe >= 45 C.
  Cyclone   IMD: depression winds >= 31 km/h (8.6 m/s), cyclonic storm >= 62 km/h (17.2 m/s).
  Flood     IMD: heavy rain 64.5-115.5 mm/24h (~2.7 mm/h); very heavy > 115.5 mm/24h.
  Drought   IMD declares drought from rainfall deficits over weeks; one weather
            reading can never confirm it, so it is capped at MEDIUM.
"""
from typing import Any, Dict, Optional, Tuple

LOW_CAP = 34      # highest LOW score
MEDIUM_CAP = 64   # highest MEDIUM score


def _level(score: int) -> str:
    if score >= 85:
        return "CRITICAL"
    if score >= 65:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def _num(weather: Dict[str, Any], key: str) -> Optional[float]:
    value = weather.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _heatwave_cap(w: Dict[str, Any]) -> Optional[Tuple[int, str]]:
    temp = _num(w, "temperature")
    feels = _num(w, "feels_like")
    if temp is None:
        return None
    effective = max(temp, feels if feels is not None else temp)
    if effective < 35:
        return LOW_CAP, f"{effective:.0f}°C is below heatwave levels (IMD: 40°C plains, 37°C coast)"
    if effective < 40:
        return MEDIUM_CAP, f"{effective:.0f}°C is warm but below the IMD heatwave threshold of 40°C"
    return None


def _cyclone_cap(w: Dict[str, Any]) -> Optional[Tuple[int, str]]:
    wind = _num(w, "wind_speed_ms")
    pressure = _num(w, "pressure")
    if wind is None:
        return None
    pressure_ok = pressure is None or pressure >= 1000
    if wind < 8.6 and pressure_ok:
        return LOW_CAP, f"wind {wind:.1f} m/s is below IMD depression strength (8.6 m/s) and pressure is normal"
    if wind < 17.2 and (pressure is None or pressure >= 990):
        return MEDIUM_CAP, f"wind {wind:.1f} m/s is below IMD cyclonic-storm strength (17.2 m/s)"
    return None


def _flood_cap(w: Dict[str, Any], satellite: Optional[Dict[str, Any]]) -> Optional[Tuple[int, str]]:
    if satellite and satellite.get("success") and satellite.get("flood_detected"):
        return None  # satellite evidence of flooding is never capped
    rain_1h = _num(w, "rainfall_1h_mm") or 0.0
    rain_3h = _num(w, "rainfall_3h_mm") or 0.0
    if rain_1h < 2.5 and rain_3h < 7.5:
        return LOW_CAP, f"no heavy rain observed ({rain_1h:.1f} mm in the last hour)"
    if rain_1h < 7.5:
        return MEDIUM_CAP, f"rain {rain_1h:.1f} mm/h is below very-heavy-rain levels"
    return None


def _drought_cap(w: Dict[str, Any]) -> Optional[Tuple[int, str]]:
    rain = (_num(w, "rainfall_1h_mm") or 0.0) + (_num(w, "rainfall_3h_mm") or 0.0)
    humidity = _num(w, "humidity")
    if rain > 0 or (humidity is not None and humidity >= 60):
        return LOW_CAP, "recent rain or humid air — no drought signal in current weather"
    return MEDIUM_CAP, "drought needs weeks of rainfall deficit; a single reading can't confirm it"


def apply_guard(
    disaster_type: str,
    result: Dict[str, Any],
    weather: Optional[Dict[str, Any]],
    satellite: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return result with its score capped when observed conditions rule the hazard out."""
    score = result.get("score")
    if score is None or not weather or weather.get("status") != "ok":
        return result

    if disaster_type == "heatwave":
        cap = _heatwave_cap(weather)
    elif disaster_type == "cyclone":
        cap = _cyclone_cap(weather)
    elif disaster_type == "flood":
        cap = _flood_cap(weather, satellite)
    elif disaster_type == "drought":
        cap = _drought_cap(weather)
    else:
        cap = None

    if cap is None or score <= cap[0]:
        return result

    limit, reason = cap
    return {
        **result,
        "score": limit,
        "level": _level(limit),
        "model_score": score,
        "guard": reason,
        "factors": [f"capped: {reason}"] + list(result.get("factors") or []),
    }
