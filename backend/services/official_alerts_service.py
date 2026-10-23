"""Official disaster warnings and verified events from free public sources.

- NDMA SACHET (sachet.ndma.gov.in): India's national Common Alerting Protocol (CAP)
  feed. Carries official warnings issued by IMD regional centres, CWC and state
  disaster management authorities.
- GDACS (gdacs.org): UN/European Commission Global Disaster Alert and Coordination
  System. Verified floods, tropical cyclones, droughts and earthquakes.

Nothing here is generated: every alert/event is copied from the source, with its
link. CAP alerts carry district names but no coordinates, so map positions for them
are the approximate centre of the state named in the alert (marked "approximate").
"""
import json
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.request import Request, urlopen

SACHET_RSS_URL = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"
GDACS_URL = (
    "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
    "?eventlist=FL;TC;DR;EQ;WF&country=IND"
)
CAP_NS = {"c": "urn:oasis:names:tc:emergency:cap:1.2"}
USER_AGENT = "CrisisCore-Disaster-Preparedness/2.0"
REFRESH_SECONDS = 600
RECENT_EVENT_DAYS = 120

# Approximate geographic centres of Indian states / UTs (used only to place
# area-based official warnings on the map; always labelled "approximate").
STATE_CENTRES: Dict[str, Tuple[float, float]] = {
    "Andhra Pradesh": (15.91, 79.74), "Arunachal Pradesh": (28.22, 94.73),
    "Assam": (26.20, 92.94), "Bihar": (25.10, 85.31), "Chhattisgarh": (21.28, 81.87),
    "Goa": (15.30, 74.12), "Gujarat": (22.26, 71.19), "Haryana": (29.06, 76.09),
    "Himachal Pradesh": (31.10, 77.17), "Jharkhand": (23.61, 85.28),
    "Karnataka": (15.32, 75.71), "Kerala": (10.85, 76.27), "Madhya Pradesh": (22.97, 78.66),
    "Maharashtra": (19.75, 75.71), "Manipur": (24.66, 93.91), "Meghalaya": (25.47, 91.37),
    "Mizoram": (23.16, 92.94), "Nagaland": (26.16, 94.56), "Odisha": (20.95, 85.10),
    "Punjab": (31.15, 75.34), "Rajasthan": (27.02, 74.22), "Sikkim": (27.53, 88.51),
    "Tamil Nadu": (11.13, 78.66), "Telangana": (18.11, 79.02), "Tripura": (23.94, 91.99),
    "Uttar Pradesh": (26.85, 80.95), "Uttarakhand": (30.07, 79.02),
    "West Bengal": (22.99, 87.85), "Andaman and Nicobar Islands": (11.74, 92.66),
    "Chandigarh": (30.73, 76.78), "Delhi": (28.70, 77.10), "Jammu and Kashmir": (33.78, 76.58),
    "Ladakh": (34.15, 77.58), "Lakshadweep": (10.57, 72.64), "Puducherry": (11.94, 79.81),
    "Dadra and Nagar Haveli and Daman and Diu": (20.40, 72.83),
}
STATE_ALIASES = {
    "Orissa": "Odisha", "J&K": "Jammu and Kashmir", "Jammu & Kashmir": "Jammu and Kashmir",
    "Andaman & Nicobar": "Andaman and Nicobar Islands", "Andaman": "Andaman and Nicobar Islands",
    "Nicobar": "Andaman and Nicobar Islands", "Pondicherry": "Puducherry", "NCT of Delhi": "Delhi",
}
# IMD regional / state meteorological centres -> state they cover
IMD_CENTRE_STATE = {
    "Chennai": "Tamil Nadu", "Mumbai": "Maharashtra", "Kolkata": "West Bengal",
    "Bengaluru": "Karnataka", "Bangalore": "Karnataka", "Jaipur": "Rajasthan", "Goa": "Goa",
    "Thiruvananthapuram": "Kerala", "Hyderabad": "Telangana", "Amaravati": "Andhra Pradesh",
    "Bhubaneswar": "Odisha", "Guwahati": "Assam", "Patna": "Bihar", "Lucknow": "Uttar Pradesh",
    "Bhopal": "Madhya Pradesh", "Ahmedabad": "Gujarat", "Chandigarh": "Punjab",
    "Srinagar": "Jammu and Kashmir", "Shimla": "Himachal Pradesh", "Dehradun": "Uttarakhand",
    "Raipur": "Chhattisgarh", "Ranchi": "Jharkhand", "Gangtok": "Sikkim", "Agartala": "Tripura",
    "Imphal": "Manipur", "Shillong": "Meghalaya", "Itanagar": "Arunachal Pradesh",
    "Aizawl": "Mizoram", "Kohima": "Nagaland", "Port Blair": "Andaman and Nicobar Islands",
    "New Delhi": "Delhi", "Delhi": "Delhi", "Leh": "Ladakh",
}

CAP_SEVERITY = {"Extreme": "critical", "Severe": "high", "Moderate": "medium", "Minor": "low"}
GDACS_SEVERITY = {"Red": "critical", "Orange": "high", "Green": "low"}
GDACS_CATEGORY = {"FL": "flood", "TC": "cyclone", "DR": "drought", "EQ": "earthquake", "WF": "wildfire"}


def _get(url: str, timeout: float) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as resp:
        return resp.read()


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def category_for_event(event: str) -> str:
    e = (event or "").lower()
    if any(k in e for k in ("flood", "inundation", "dam ")):
        return "flood"
    if any(k in e for k in ("cyclone", "depression", "storm surge", "deep depression")):
        return "cyclone"
    if "heat" in e:
        return "heatwave"
    if "drought" in e:
        return "drought"
    if "earthquake" in e or "tsunami" in e:
        return "earthquake"
    return "severe_weather"


def _find_state(*texts: str) -> Optional[str]:
    for text in texts:
        if not text:
            continue
        for alias, state in STATE_ALIASES.items():
            if alias.lower() in text.lower():
                return state
        for state in sorted(STATE_CENTRES, key=len, reverse=True):
            if state.lower() in text.lower():
                return state
    return None


def _state_from_sender(sender: str) -> Optional[str]:
    # e.g. "controlroom@ndma.gov.in (IMD Chennai)" / "(Andhra Pradesh SDMA)"
    inner = sender[sender.find("(") + 1: sender.rfind(")")] if "(" in sender else sender
    state = _find_state(inner)
    if state:
        return state
    if inner.startswith("IMD "):
        return IMD_CENTRE_STATE.get(inner[4:].strip())
    return None


# ---------------------------------------------------------------------------
# NDMA SACHET (CAP)
# ---------------------------------------------------------------------------

def _fetch_sachet() -> Dict[str, Any]:
    root = ET.fromstring(_get(SACHET_RSS_URL, 20))
    items = root.findall("./channel/item")

    def fetch_cap(item):
        try:
            return item, ET.fromstring(_get(item.findtext("link"), 15))
        except Exception as e:  # one bad CAP file must not drop the rest
            print(f"[SACHET] CAP fetch failed: {type(e).__name__}: {e}")
            return item, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        docs = list(pool.map(fetch_cap, items))

    now = datetime.now(timezone.utc)
    cancelled = set()
    for _, doc in docs:
        if doc is not None and doc.findtext("c:msgType", namespaces=CAP_NS) == "Cancel":
            for ref in (doc.findtext("c:references", namespaces=CAP_NS) or "").split():
                parts = ref.split(",")
                if len(parts) >= 2:
                    cancelled.add(parts[1])

    latest: Dict[tuple, Dict[str, Any]] = {}
    for item, doc in docs:
        if doc is None:
            continue
        identifier = doc.findtext("c:identifier", namespaces=CAP_NS) or item.findtext("guid")
        if doc.findtext("c:msgType", namespaces=CAP_NS) == "Cancel" or identifier in cancelled:
            continue
        infos = doc.findall("c:info", CAP_NS)
        info = next(
            (i for i in infos if (i.findtext("c:language", namespaces=CAP_NS) or "").lower().startswith("en")),
            infos[0] if infos else None,
        )
        if info is None:
            continue
        g = lambda tag: (info.findtext(f"c:{tag}", namespaces=CAP_NS) or "").strip()
        expires = _parse_time(g("expires"))
        if expires and expires < now:
            continue
        areas = [(a.findtext("c:areaDesc", namespaces=CAP_NS) or "").strip() for a in info.findall("c:area", CAP_NS)]
        area_text = "; ".join(a for a in areas if a) or "Area not specified"
        sender = item.findtext("author") or ""
        issuer = sender[sender.find("(") + 1: sender.rfind(")")] if "(" in sender else sender
        state = _find_state(area_text, g("headline")) or _state_from_sender(sender)
        lat, lon = STATE_CENTRES.get(state, (None, None)) if state else (None, None)
        event = g("event") or "Weather warning"
        sent = _parse_time(doc.findtext("c:sent", namespaces=CAP_NS))
        alert = {
            "id": f"sachet-{identifier}",
            "category": category_for_event(event),
            "kind": "official_warning",
            "title": f"{event} — {state or area_text[:60]}",
            "event": event,
            "detail": g("headline") or g("description") or event,
            "location": area_text,
            "state": state,
            "severity": CAP_SEVERITY.get(g("severity"), "medium"),
            "severity_label": g("severity") or "Unknown",
            "urgency": g("urgency"),
            "certainty": g("certainty"),
            "lat": lat,
            "lon": lon,
            "coord_precision": "approximate" if lat is not None else None,
            "coord_note": f"Approximate: centre of {state}" if state else "No coordinates in official alert",
            "source": f"NDMA SACHET · {issuer}",
            "source_url": item.findtext("link"),
            "timestamp": (sent or now).isoformat(),
            "effective": g("effective") or None,
            "expires": expires.isoformat() if expires else None,
        }
        key = (issuer, event, area_text)
        if key not in latest or alert["timestamp"] > latest[key]["timestamp"]:
            latest[key] = alert

    alerts = sorted(latest.values(), key=lambda a: a["timestamp"], reverse=True)
    return {"alerts": alerts, "feed_items": len(items), "fetched": sum(d is not None for _, d in docs)}


# ---------------------------------------------------------------------------
# GDACS
# ---------------------------------------------------------------------------

def _fetch_gdacs() -> Dict[str, Any]:
    data = json.loads(_get(GDACS_URL, 20).decode("utf-8"))
    now = datetime.now(timezone.utc)
    current, recent = [], []
    for feat in data.get("features", []):
        p = feat.get("properties", {})
        # The country search also returns events elsewhere (e.g. Indonesian earthquakes);
        # keep only events that list India among affected countries.
        countries = " ".join(
            [str(p.get("country") or "")] + [str(c.get("countryname", "")) for c in p.get("affectedcountries") or []]
        )
        if "india" not in countries.lower():
            continue
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") if geom.get("type") == "Point" else None
        category = GDACS_CATEGORY.get(p.get("eventtype"), "other")
        start, end = _parse_time(p.get("fromdate")), _parse_time(p.get("todate"))
        report = (p.get("url") or {}).get("report")
        event = {
            "id": f"gdacs-{p.get('eventtype')}-{p.get('eventid')}",
            "category": category,
            "kind": "official_event",
            "title": p.get("name") or p.get("eventname") or f"{category.title()} event",
            "detail": (p.get("description") or p.get("htmldescription") or "").strip()
                      or f"GDACS {p.get('alertlevel', '')} alert",
            "location": p.get("country") or "India",
            "severity": GDACS_SEVERITY.get(p.get("alertlevel"), "medium"),
            "severity_label": f"GDACS {p.get('alertlevel', 'unknown')} alert",
            "lat": coords[1] if coords else None,
            "lon": coords[0] if coords else None,
            "coord_precision": "exact" if coords else None,
            "source": "GDACS (UN / European Commission)",
            "source_url": report,
            "timestamp": (end or start or now).isoformat(),
            "started": start.isoformat() if start else None,
            "ended": end.isoformat() if end else None,
            "is_current": bool(p.get("iscurrent")) and str(p.get("iscurrent")).lower() != "false",
        }
        if event["is_current"]:
            current.append(event)
        elif end and end >= now - timedelta(days=RECENT_EVENT_DAYS):
            event["status"] = "ended"
            recent.append(event)
    return {"current": current, "recent": sorted(recent, key=lambda e: e["timestamp"], reverse=True)}


# ---------------------------------------------------------------------------
# Cached, background-refreshed snapshot
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_state: Dict[str, Any] = {"data": None, "fetched_at": 0.0, "refreshing": False}


def _source_status(name: str, ok: bool, count: int, error: Optional[str] = None) -> Dict[str, Any]:
    return {
        "name": name,
        "status": "ok" if ok else "unavailable",
        "count": count,
        "error": error,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _refresh() -> Dict[str, Any]:
    started = time.time()
    result: Dict[str, Any] = {"alerts": [], "recent_events": [], "sources": {}}
    previous = _state["data"] or {}

    try:
        sachet = _fetch_sachet()
        result["alerts"] += sachet["alerts"]
        result["sources"]["sachet"] = _source_status("NDMA SACHET (IMD / CWC / SDMA warnings)", True, len(sachet["alerts"]))
    except Exception as e:
        print(f"[SACHET] feed failed: {type(e).__name__}: {e}")
        result["sources"]["sachet"] = _source_status("NDMA SACHET (IMD / CWC / SDMA warnings)", False, 0, str(e))
        # keep the last good official warnings rather than showing none
        kept = [a for a in previous.get("alerts", []) if a["id"].startswith("sachet-")]
        if kept:
            result["alerts"] += kept
            result["sources"]["sachet"]["note"] = "Showing last successfully fetched warnings"

    try:
        gdacs = _fetch_gdacs()
        result["alerts"] += gdacs["current"]
        result["recent_events"] = gdacs["recent"]
        result["sources"]["gdacs"] = _source_status("GDACS (UN / EC)", True, len(gdacs["current"]))
    except Exception as e:
        print(f"[GDACS] feed failed: {type(e).__name__}: {e}")
        result["sources"]["gdacs"] = _source_status("GDACS (UN / EC)", False, 0, str(e))
        result["recent_events"] = previous.get("recent_events", [])

    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    print(f"[Official] refreshed in {time.time() - started:.1f}s: {len(result['alerts'])} alerts")
    return result


def _refresh_in_background() -> None:
    def run():
        try:
            data = _refresh()
            with _lock:
                _state.update(data=data, fetched_at=time.time())
        finally:
            _state["refreshing"] = False

    with _lock:
        if _state["refreshing"]:
            return
        _state["refreshing"] = True
    threading.Thread(target=run, daemon=True).start()


def warm_up() -> None:
    """Start fetching at backend startup so the first page load is instant."""
    _refresh_in_background()


def get_official_alerts(wait_seconds: float = 25.0) -> Dict[str, Any]:
    """Return cached official data; refresh in the background when stale."""
    if _state["data"] is None or time.time() - _state["fetched_at"] > REFRESH_SECONDS:
        _refresh_in_background()
    deadline = time.time() + wait_seconds
    while _state["data"] is None and time.time() < deadline:
        time.sleep(0.25)
    if _state["data"] is None:
        return {
            "alerts": [], "recent_events": [], "loading": True,
            "sources": {
                "sachet": {"name": "NDMA SACHET (IMD / CWC / SDMA warnings)", "status": "loading", "count": 0},
                "gdacs": {"name": "GDACS (UN / EC)", "status": "loading", "count": 0},
            },
        }
    return _state["data"]
