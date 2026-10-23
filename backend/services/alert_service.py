"""Alert service — generates alerts only from actual detected events/data."""
from datetime import datetime, timezone
from typing import Any, Dict, List


def _make_alert(
    alert_id: str,
    title: str,
    detail: str,
    severity: str,
    disaster_type: str,
    lat: float = None,
    lon: float = None,
    source: str = None,
) -> Dict[str, Any]:
    return {
        "id": alert_id,
        "title": title,
        "detail": detail,
        "severity": severity.lower(),
        "disaster_type": disaster_type,
        "lat": lat,
        "lon": lon,
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
            alerts.append(_make_alert(
                alert_id=f"eq-{eq.get('id', 'unknown')}",
                title=f"M{mag} Earthquake — {eq.get('place', 'Unknown')}",
                detail=f"Depth: {eq.get('depth_km', '?')} km | Significance: {eq.get('significance', '?')}",
                severity=sev,
                disaster_type="earthquake",
                lat=eq.get("lat"),
                lon=eq.get("lon"),
                source="USGS",
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
            ))

    for hw in heatwaves:
        if hw.get("severity") in ("HIGH", "EXTREME", "MODERATE"):
            sev = "high" if hw.get("severity") == "EXTREME" else "medium" if hw.get("severity") == "HIGH" else "low"
            alerts.append(_make_alert(
                alert_id=f"heat-{hw.get('location', 'unknown')}",
                title=f"Heat stress — {hw.get('location', 'Unknown')}",
                detail=f"Temperature: {hw.get('temperature', '?')}°C | Severity: {hw.get('severity')}",
                severity=sev,
                disaster_type="heatwave",
                lat=hw.get("lat"),
                lon=hw.get("lon"),
                source="OpenWeather",
            ))

    for cy in cyclones:
        if cy.get("severity") in ("HIGH", "ELEVATED"):
            alerts.append(_make_alert(
                alert_id=f"cyclone-{cy.get('location', 'unknown')}",
                title=f"Elevated wind conditions — {cy.get('location', 'Unknown')}",
                detail=cy.get("message", "Monitor IMD cyclone advisories"),
                severity="high" if cy.get("severity") == "HIGH" else "medium",
                disaster_type="cyclone",
                lat=cy.get("lat"),
                lon=cy.get("lon"),
                source="OpenWeather",
            ))

    for dr in droughts:
        if dr.get("severity") == "ELEVATED_STRESS":
            alerts.append(_make_alert(
                alert_id=f"drought-{dr.get('region', 'unknown')}",
                title=f"Drought stress indicators — {dr.get('region', 'Unknown')}",
                detail=dr.get("message", "Environmental stress indicators elevated"),
                severity="medium",
                disaster_type="drought",
                lat=dr.get("lat"),
                lon=dr.get("lon"),
                source="OpenWeather",
            ))

    return alerts
