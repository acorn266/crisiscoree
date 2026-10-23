"""Alert service — generates alerts only from actual detected events/data.

Every alert has the same shape so the UI can filter and label it:
  category  earthquake | flood | cyclone | heatwave | drought | severe_weather
  kind      official_warning  issued by an authority (NDMA SACHET / IMD / CWC)
            official_event    verified by a disaster agency (GDACS)
            observed_event    measured by a monitoring network (USGS)
            risk_indicator    automatically derived by CrisisCore from weather thresholds
Official warnings/events come from services/official_alerts_service.py.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _make_alert(
    alert_id: str,
    title: str,
    detail: str,
    severity: str,
    disaster_type: str,
    lat: float = None,
    lon: float = None,
    source: str = None,
    kind: str = "risk_indicator",
    location: Optional[str] = None,
    timestamp: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    return {
        "id": alert_id,
        "title": title,
        "detail": detail,
        "severity": severity.lower(),
        "category": disaster_type,
        "disaster_type": disaster_type,
        "kind": kind,
        "location": location,
        "lat": lat,
        "lon": lon,
        "coord_precision": "exact" if lat is not None and lon is not None else None,
        "source": source,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }


def generate_alerts(
    floods: List[Dict],
    earthquakes: List[Dict],
    droughts: List[Dict],
    heatwaves: List[Dict],
    cyclones: List[Dict],
) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []

    for eq in earthquakes:
        if eq.get("status") != "detected":
            continue
        mag = eq.get("magnitude", 0)
        if mag >= 4.0:
            sev = "high" if mag >= 5.5 else "medium"
            in_india = eq.get("in_india")
            where = "in India" if in_india is True else (
                "India border region" if in_india == "border" else f"outside India ({eq.get('country', 'unknown')})"
            )
            alerts.append(_make_alert(
                alert_id=f"eq-{eq.get('id', 'unknown')}",
                title=f"M{mag} Earthquake — {eq.get('place', 'Unknown')}",
                detail=f"Magnitude {mag}, depth {eq.get('depth_km', '?')} km — {where}. "
                       f"USGS significance {eq.get('significance', '?')}.",
                severity=sev,
                disaster_type="earthquake",
                lat=eq.get("lat"),
                lon=eq.get("lon"),
                source="USGS",
                kind="observed_event",
                location=eq.get("place"),
                timestamp=eq.get("time_iso"),
                country=eq.get("country"),
                in_india=in_india,
                magnitude=mag,
                source_url=f"https://earthquake.usgs.gov/earthquakes/eventpage/{eq.get('id')}",
            ))

    for flood in floods:
        if flood.get("status") == "detected" and flood.get("flood_detected"):
            area = flood.get("area_km2", "?")
            sev = "high" if flood.get("severity") == "HIGH" else "medium"
            alerts.append(_make_alert(
                alert_id=f"flood-{flood.get('region_id', 'unknown')}",
                title=f"Flood detected — {flood.get('region', 'Unknown region')}",
                detail=f"Estimated area: {area} km² | Data: Latest available Sentinel-1 satellite data",
                severity=sev,
                disaster_type="flood",
                lat=flood.get("lat"),
                lon=flood.get("lon"),
                source="Sentinel-1/GEE",
                kind="observed_event",
                location=flood.get("region"),
                timestamp=flood.get("image_date"),
            ))

    for hw in heatwaves:
        if hw.get("severity") in ("HIGH", "EXTREME", "MODERATE"):
            sev = "high" if hw.get("severity") == "EXTREME" else "medium" if hw.get("severity") == "HIGH" else "low"
            alerts.append(_make_alert(
                alert_id=f"heat-{hw.get('location', 'unknown')}",
                title=f"Heat stress indicator — {hw.get('location', 'Unknown')}",
                detail=f"Observed {hw.get('temperature', '?')}°C (heat index "
                       f"{(hw.get('features') or {}).get('heat_index_c', '?')}°C) — CrisisCore threshold "
                       f"{hw.get('severity')}. Not an official IMD heatwave warning.",
                severity=sev,
                disaster_type="heatwave",
                lat=hw.get("lat"),
                lon=hw.get("lon"),
                source="CrisisCore indicator · OpenWeather",
                kind="risk_indicator",
                location=hw.get("location"),
                timestamp=hw.get("timestamp"),
            ))

    for cy in cyclones:
        if cy.get("severity") in ("HIGH", "ELEVATED"):
            alerts.append(_make_alert(
                alert_id=f"cyclone-{cy.get('location', 'unknown')}",
                title=f"High wind indicator — {cy.get('location', 'Unknown')}",
                detail=(cy.get("message") or "Elevated wind/pressure conditions")
                       + " — CrisisCore threshold, not an official IMD cyclone warning.",
                severity="high" if cy.get("severity") == "HIGH" else "medium",
                disaster_type="cyclone",
                lat=cy.get("lat"),
                lon=cy.get("lon"),
                source="CrisisCore indicator · OpenWeather",
                kind="risk_indicator",
                location=cy.get("location"),
                timestamp=cy.get("timestamp"),
            ))

    for dr in droughts:
        if dr.get("severity") == "ELEVATED_STRESS":
            alerts.append(_make_alert(
                alert_id=f"drought-{dr.get('region', 'unknown')}",
                title=f"Dry-conditions indicator — {dr.get('region', 'Unknown')}",
                detail=(dr.get("message") or "Environmental stress indicators elevated")
                       + " — from a single weather reading; not an official drought declaration.",
                severity="medium",
                disaster_type="drought",
                lat=dr.get("lat"),
                lon=dr.get("lon"),
                source="CrisisCore indicator · OpenWeather",
                kind="risk_indicator",
                location=dr.get("region"),
                timestamp=dr.get("timestamp"),
            ))

    return alerts
