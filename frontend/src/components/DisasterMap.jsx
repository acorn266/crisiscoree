import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Circle,
  CircleMarker,
  Rectangle,
  Polygon,
  LayerGroup,
  LayersControl,
  useMap,
  useMapEvents,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import MapLegend from './MapLegend';
import {
  analyzeFloodRisk,
  getHospitalsInMap,
  getSheltersInMap,
} from '../services/api';
import { isValidLatLng } from '../utils/geo';
import { savedDataNote } from '../utils/savedData';
import { CATEGORIES, KINDS, formatTime } from '../utils/alerts';
import { DEMO_FLOODS } from '../demo/demoFloods';

const INDIA_CENTER = [20.5937, 78.9629];
const INDIA_BOUNDS = L.latLngBounds([6.5, 68.1], [35.5, 97.4]);
const DEFAULT_ZOOM = 5;
// Area-based official warnings are drawn as a circle of this radius around the state centre
const APPROX_RADIUS_M = 60000;

const located = (item) => isValidLatLng(item.lat, item.lon);

function badgeIcon(variant, glyph, size = 28) {
  return L.divIcon({
    className: `cc-marker cc-marker--${variant}`,
    html: `<span>${glyph}</span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });
}

const ICONS = {
  user: badgeIcon('user', '●', 22),
  hospital: badgeIcon('hospital', '✚', 26),
  shelter: badgeIcon('shelter', '⌂', 26),
  flood: badgeIcon('flood', '🌊', 30),
  floodEnded: badgeIcon('ended', '🌊', 26),
  floodDemo: badgeIcon('demo', 'DEMO', 40),
  cyclone: badgeIcon('cyclone', '🌀', 28),
  cycloneEnded: badgeIcon('ended', '🌀', 26),
  heat: badgeIcon('heat', '🔥', 26),
  drought: badgeIcon('drought', '🌵', 26),
  highlight: badgeIcon('highlight', '', 44),
};

function warningIcon(count) {
  return badgeIcon('warning', count > 1 ? `⚠<b>${count}</b>` : '⚠', count > 1 ? 36 : 28);
}

function IndiaFitBounds() {
  const map = useMap();
  useEffect(() => {
    // fitBounds on a zero-size container (hidden tab, layout not settled) yields NaN coordinates
    const fit = () => {
      map.invalidateSize();
      const size = map.getSize();
      if (size.x > 0 && size.y > 0) {
        map.fitBounds(INDIA_BOUNDS, { padding: [20, 20] });
        return true;
      }
      return false;
    };
    if (fit()) return undefined;
    const id = setInterval(() => { if (fit()) clearInterval(id); }, 300);
    return () => clearInterval(id);
  }, [map]);
  return null;
}

// target: { coords: [lat, lon], zoom, highlight? } — a new object each click, so re-clicking refocuses
function MapFocusTarget({ target, defaultZoom }) {
  const map = useMap();
  useEffect(() => {
    if (!target) return;
    const [lat, lon] = target.coords ?? [];
    if (!isValidLatLng(lat, lon)) return;
    map.setView([lat, lon], target.zoom ?? defaultZoom);
    // Instant scroll: smooth scrolling is a no-op in some embedded browsers
    const rect = map.getContainer().getBoundingClientRect();
    if (rect.top < 0 || rect.bottom > window.innerHeight) {
      map.getContainer().scrollIntoView?.({ block: 'center' });
    }
  }, [map, target, defaultZoom]);
  return null;
}

function MapResizeHandler() {
  const map = useMap();
  useEffect(() => {
    const handler = () => map.invalidateSize();
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, [map]);
  return null;
}

function MapClickHandler({ onMapClick }) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function MapResourceLoader({ onResourcesLoaded }) {
  const map = useMap();

  useEffect(() => {
    let cancelled = false;
    let requestId = 0;

    const loadResources = async () => {
      const thisRequest = ++requestId;
      // Don't query Overpass while viewing the entire country.
      // Wait until the user zooms into a useful region.
      if (map.getZoom() < 7) {
        onResourcesLoaded([], []);
        return;
      }

      const bounds = map.getBounds();
      try {
        const [hospitalData, shelterData] = await Promise.all([
          getHospitalsInMap(bounds.getSouth(), bounds.getWest(), bounds.getNorth(), bounds.getEast()),
          getSheltersInMap(bounds.getSouth(), bounds.getWest(), bounds.getNorth(), bounds.getEast()),
        ]);
        if (!cancelled && thisRequest === requestId) {
          onResourcesLoaded(
            hospitalData.hospitals ?? [],
            shelterData.shelters ?? [],
            savedDataNote(hospitalData) ?? savedDataNote(shelterData)
          );
        }
      } catch (err) {
        console.warn('Map resource loading failed:', err);
        if (!cancelled && thisRequest === requestId) {
          onResourcesLoaded([], []);
        }
      }
    };

    loadResources();
    map.on('moveend', loadResources);
    return () => {
      cancelled = true;
      map.off('moveend', loadResources);
    };
  }, [map, onResourcesLoaded]);

  return null;
}

function HighlightMarker({ target }) {
  const markerRef = useRef(null);
  useEffect(() => {
    // Open the popup once the marker is on the map
    const id = setTimeout(() => markerRef.current?.openPopup(), 50);
    return () => clearTimeout(id);
  }, [target]);
  const [lat, lon] = target.coords;
  return (
    <Marker position={[lat, lon]} icon={ICONS.highlight} ref={markerRef} zIndexOffset={1000}>
      <Popup>
        <div className="popup">
          <div className="popup-title">{target.highlight.title}</div>
          {target.highlight.lines?.map((line) => <div key={line}>{line}</div>)}
          <div className="popup-meta">{lat.toFixed(4)}, {lon.toFixed(4)}</div>
        </div>
      </Popup>
    </Marker>
  );
}

function geoJsonToLeafletPositions(geometry) {
  if (!geometry || geometry.type !== 'Polygon') return null;
  return geometry.coordinates[0].map(([lon, lat]) => [lat, lon]);
}

function eqColor(mag) {
  if (mag >= 5) return '#ff5252';
  if (mag >= 3) return '#ffb340';
  return '#35d07f';
}

const AMENITY_LABEL = {
  hospital: 'Hospital',
  community_centre: 'Community centre',
  social_facility: 'Social facility',
};

function ResourcePopup({ item, label }) {
  const saved = item.data_source === 'snapshot';
  return (
    <div className="popup">
      <div className="popup-title">{label === 'hospital' ? '🏥' : '🏠'} {item.name}</div>
      <div>{AMENITY_LABEL[item.amenity] ?? item.amenity}{item.distance_km != null ? ` · ${item.distance_km} km away` : ''}</div>
      <div className="popup-meta">{item.lat.toFixed(5)}, {item.lon.toFixed(5)}</div>
      <div className={`popup-badge ${saved ? 'is-saved' : 'is-live'}`}>
        {saved ? 'Saved OpenStreetMap snapshot' : 'Live OpenStreetMap data'}
      </div>
      <a href={`https://www.openstreetmap.org/?mlat=${item.lat}&mlon=${item.lon}#map=18/${item.lat}/${item.lon}`} target="_blank" rel="noreferrer">
        View on OpenStreetMap ↗
      </a>
    </div>
  );
}

function AlertPopup({ alert, ended = false }) {
  const kind = KINDS[alert.kind];
  return (
    <div className="popup">
      <div className="popup-title">{CATEGORIES[alert.category]?.icon} {alert.title}</div>
      <div className={`popup-badge ${ended ? 'is-ended' : 'is-official'}`}>
        {ended ? 'Ended event' : (kind?.label ?? 'Alert')} · {alert.severity_label ?? alert.severity}
      </div>
      {alert.location && <div><b>Area:</b> {alert.location}</div>}
      {alert.detail && <div className="popup-detail">{alert.detail}</div>}
      {ended && alert.started && <div><b>Period:</b> {formatTime(alert.started)} – {formatTime(alert.ended)}</div>}
      {!ended && alert.expires && <div><b>Valid until:</b> {formatTime(alert.expires)}</div>}
      {alert.coord_precision === 'approximate' && <div className="popup-warn">📍 {alert.coord_note}</div>}
      <div className="popup-meta">Source: {alert.source} · {formatTime(alert.timestamp)}</div>
      {alert.source_url && <a href={alert.source_url} target="_blank" rel="noreferrer">Official record ↗</a>}
    </div>
  );
}

function DisasterMap({
  disasters,
  official = null,
  hospitals = [],
  shelters = [],
  onMapResourcesLoaded,
  userLocation,
  onRefresh,
  loading,
  mapFocusTarget = null,
  mapFocusZoom = 13,
  resourceNote = null,
  demoMode = false,
  onDemoModeChange,
}) {
  const mapShellRef = useRef(null);
  const leafletMapRef = useRef(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [floodClickData, setFloodClickData] = useState(null);
  const [floodClickBounds, setFloodClickBounds] = useState(null);
  const [floodAnalyzing, setFloodAnalyzing] = useState(false);
  const [floodError, setFloodError] = useState(null);
  const [locateError, setLocateError] = useState(null);

  const { floods, earthquakes, droughts, heatwaves, cyclones } = useMemo(() => ({
    floods: disasters?.floods ?? [],
    earthquakes: disasters?.earthquakes ?? [],
    droughts: disasters?.droughts ?? [],
    heatwaves: disasters?.heatwaves ?? [],
    cyclones: disasters?.cyclones ?? [],
  }), [disasters]);

  const officialAlerts = useMemo(() => official?.alerts ?? [], [official]);
  const recentEvents = useMemo(() => official?.recent_events ?? [], [official]);

  const officialByCategory = useMemo(() => {
    const out = {};
    for (const a of officialAlerts.filter(located)) {
      (out[a.category] ||= []).push(a);
    }
    return out;
  }, [officialAlerts]);

  // Area-based weather warnings share a state centre: group them into one marker per state
  const weatherWarningGroups = useMemo(() => {
    const groups = new Map();
    for (const a of officialByCategory.severe_weather ?? []) {
      const key = `${a.lat},${a.lon}`;
      if (!groups.has(key)) groups.set(key, { lat: a.lat, lon: a.lon, state: a.state, items: [] });
      groups.get(key).items.push(a);
    }
    return [...groups.values()];
  }, [officialByCategory]);

  const officialFloods = officialByCategory.flood ?? [];
  const endedFloods = recentEvents.filter((e) => e.category === 'flood' && located(e));
  const endedCyclones = recentEvents.filter((e) => e.category === 'cyclone' && located(e));
  const satelliteFloods = floods.filter((f) => f.status !== 'unavailable');
  // The backend reports a single "unavailable" flood entry when satellite detection is off
  const satelliteFloodEnabled = !(floods.length === 1 && floods[0]?.status === 'unavailable');
  const elevatedHeat = heatwaves.filter((h) => !['NONE', 'UNAVAILABLE'].includes(h.severity) && located(h));
  const elevatedDrought = droughts.filter((d) => !['NONE', 'UNAVAILABLE'].includes(d.severity) && located(d));
  const elevatedWind = cyclones.filter((c) => !['NONE', 'UNAVAILABLE'].includes(c.severity) && located(c));

  // Never leave the flood layer silently empty: say what is (and isn't) known
  const floodStatus = useMemo(() => {
    const parts = [];
    if (!official || official.loading) parts.push('Checking NDMA SACHET & GDACS for flood alerts…');
    else {
      const sachetOk = official.sources?.sachet?.status === 'ok';
      const gdacsOk = official.sources?.gdacs?.status === 'ok';
      parts.push(officialFloods.length
        ? `${officialFloods.length} official flood warning${officialFloods.length > 1 ? 's' : ''} (location approximate)`
        : 'No active official flood warnings reported');
      if (!sachetOk || !gdacsOk) parts.push(`⚠ ${[!sachetOk && 'NDMA SACHET', !gdacsOk && 'GDACS'].filter(Boolean).join(' & ')} unavailable — no data is not proof of safety`);
      const lastEnded = endedFloods[0];
      if (lastEnded) parts.push(`Last GDACS flood in India ended ${formatTime(lastEnded.ended)}`);
    }
    parts.push(satelliteFloodEnabled ? 'Satellite detection on' : 'Satellite detection off');
    return parts;
  }, [official, officialFloods.length, endedFloods, satelliteFloodEnabled]);

  // Toasts clear themselves so they don't cover the map during a demo
  useEffect(() => {
    if (!floodError && !locateError) return undefined;
    const id = setTimeout(() => {
      setFloodError(null);
      setLocateError(null);
    }, 6000);
    return () => clearTimeout(id);
  }, [floodError, locateError]);

  const handleFloodAnalysis = useCallback(async (lat, lon) => {
    if (!isValidLatLng(lat, lon)) return;
    setFloodAnalyzing(true);
    setFloodError(null);
    setFloodClickData(null);
    setFloodClickBounds(null);

    try {
      const result = await analyzeFloodRisk(lat, lon);
      if (result.success) {
        setFloodClickData(result);
        const buffer = result.buffer_deg || 0.15;
        setFloodClickBounds([
          [lat - buffer, lon - buffer],
          [lat + buffer, lon + buffer],
        ]);
      } else {
        setFloodError(result.error || 'Flood analysis unavailable');
      }
    } catch (err) {
      setFloodError(err.message || 'Network error');
    } finally {
      setFloodAnalyzing(false);
    }
  }, []);

  const toggleFullscreen = useCallback(() => {
    const el = mapShellRef.current;
    if (!el) return;
    const after = () => setTimeout(() => window.dispatchEvent(new Event('resize')), 200);
    if (!document.fullscreenElement) {
      el.requestFullscreen?.().then(() => { setIsFullscreen(true); after(); }).catch(() => {});
    } else {
      document.exitFullscreen?.().then(() => { setIsFullscreen(false); after(); }).catch(() => {});
    }
  }, []);

  useEffect(() => {
    const onFsChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
      setTimeout(() => window.dispatchEvent(new Event('resize')), 200);
    };
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, []);

  const handleLocateMe = useCallback(() => {
    const map = leafletMapRef.current;
    if (!map) return;
    setLocateError(null);
    map.locate({ setView: true, maxZoom: 14 });
    map.once('locationerror', (e) => {
      setLocateError(e.message || 'Could not determine your location');
    });
  }, []);

  const handleFitToDisasters = useCallback(() => {
    const map = leafletMapRef.current;
    if (!map) return;
    const points = [
      ...earthquakes, ...officialAlerts, ...satelliteFloods, ...elevatedHeat, ...elevatedDrought, ...elevatedWind,
      ...(demoMode ? DEMO_FLOODS : []),
    ].filter(located).map((p) => [p.lat, p.lon]);
    if (points.length > 0) {
      map.fitBounds(points, { padding: [30, 30], maxZoom: 7 });
    }
  }, [earthquakes, officialAlerts, satelliteFloods, elevatedHeat, elevatedDrought, elevatedWind, demoMode]);

  const highlightTarget = mapFocusTarget?.highlight && isValidLatLng(...(mapFocusTarget.coords ?? []))
    ? mapFocusTarget : null;

  return (
    <div className={`map-shell ${isFullscreen ? 'map-fullscreen' : ''}`} ref={mapShellRef}>
      <div className="map-toolbar">
        <div className="map-toolbar-group">
          {onRefresh && (
            <button type="button" className="btn btn-ghost" onClick={onRefresh} disabled={loading}>
              {loading ? <span className="spinner" aria-hidden="true" /> : '↻'} {loading ? 'Refreshing' : 'Refresh'}
            </button>
          )}
          <button type="button" className="btn btn-ghost" onClick={handleLocateMe} title="Go to my location">📍 My location</button>
          <button type="button" className="btn btn-ghost" onClick={handleFitToDisasters} title="Fit map to active events">🎯 Fit to events</button>
          <button type="button" className="btn btn-ghost" onClick={toggleFullscreen} title="Toggle fullscreen">
            ⛶ {isFullscreen ? 'Exit' : 'Fullscreen'}
          </button>
        </div>
        {onDemoModeChange && (
          <label className={`demo-switch ${demoMode ? 'is-on' : ''}`} title="Show clearly labelled SAMPLE flood zones for presentations. Not real data.">
            <input type="checkbox" checked={demoMode} onChange={(e) => onDemoModeChange(e.target.checked)} />
            <span className="demo-switch-track" aria-hidden="true"><span /></span>
            Demo flood data
          </label>
        )}
      </div>

      {demoMode && (
        <div className="demo-banner" role="status">
          DEMO MODE — the striped “DEMO” flood zones are sample data, not real events.
        </div>
      )}

      <div className="map-frame">
        <MapContainer
          center={INDIA_CENTER}
          zoom={DEFAULT_ZOOM}
          scrollWheelZoom
          className="map-container"
          maxBounds={INDIA_BOUNDS.pad(0.5)}
          minZoom={4}
          ref={leafletMapRef}
        >
          <IndiaFitBounds />
          <MapFocusTarget target={mapFocusTarget} defaultZoom={mapFocusZoom} />
          <MapResizeHandler />
          {satelliteFloodEnabled && <MapClickHandler onMapClick={handleFloodAnalysis} />}
          <MapResourceLoader onResourcesLoaded={onMapResourcesLoaded} />
          <TileLayer
            attribution="&copy; OpenStreetMap contributors"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <LayersControl position="topright" collapsed={window.innerWidth < 900}>
            <LayersControl.Overlay checked name="🌊 Floods">
              <LayerGroup>
                {officialFloods.map((a) => (
                  <React.Fragment key={a.id}>
                    {a.coord_precision === 'approximate' && (
                      <Circle
                        center={[a.lat, a.lon]}
                        radius={APPROX_RADIUS_M}
                        pathOptions={{ color: '#3b82f6', weight: 1.5, dashArray: '6 6', fillOpacity: 0.08 }}
                      />
                    )}
                    <Marker position={[a.lat, a.lon]} icon={ICONS.flood}>
                      <Popup><AlertPopup alert={a} /></Popup>
                    </Marker>
                  </React.Fragment>
                ))}
                {endedFloods.map((e) => (
                  <Marker key={e.id} position={[e.lat, e.lon]} icon={ICONS.floodEnded}>
                    <Popup><AlertPopup alert={e} ended /></Popup>
                  </Marker>
                ))}
                {satelliteFloods.map((f) => {
                  const positions = geoJsonToLeafletPositions(f.geometry);
                  const key = f.region_id || f.region || `${f.lat}-${f.lon}`;
                  return (
                    <React.Fragment key={key}>
                      {positions && (
                        <Polygon
                          positions={positions}
                          pathOptions={{
                            color: f.flood_detected ? '#0066cc' : '#4fc3f7',
                            weight: 2,
                            fillOpacity: f.flood_detected ? 0.2 : 0.05,
                            dashArray: f.flood_detected ? undefined : '5,5',
                          }}
                        >
                          <Popup>
                            <div className="popup">
                              <div className="popup-title">🛰 {f.region}</div>
                              <div>Status: {f.status} · Severity: {f.severity}</div>
                              <div>{f.flood_detected ? `Area: ${f.area_km2} km²` : 'No new flood detected in analysis region'}</div>
                              <div className="popup-meta">Sentinel-1 / GEE · image {f.image_date || f.timestamp || 'N/A'}</div>
                            </div>
                          </Popup>
                        </Polygon>
                      )}
                      {f.flood_detected && located(f) && (
                        <Marker position={[f.lat, f.lon]} icon={ICONS.flood}>
                          <Popup>FLOOD DETECTED — {f.region}<br />Area: {f.area_km2} km²</Popup>
                        </Marker>
                      )}
                    </React.Fragment>
                  );
                })}
                {demoMode && DEMO_FLOODS.map((d) => (
                  <React.Fragment key={d.id}>
                    <Circle
                      center={[d.lat, d.lon]}
                      radius={d.radius_km * 1000}
                      pathOptions={{ color: '#f59e0b', weight: 2, dashArray: '2 8', fillColor: '#f59e0b', fillOpacity: 0.15 }}
                    />
                    <Marker position={[d.lat, d.lon]} icon={ICONS.floodDemo}>
                      <Popup>
                        <div className="popup">
                          <div className="popup-badge is-demo">SAMPLE DATA — NOT A REAL EVENT</div>
                          <div className="popup-title">{d.title}</div>
                          <div>{d.region}</div>
                          <div className="popup-detail">{d.detail}</div>
                          <div className="popup-meta">Demo mode · switch off in the map toolbar</div>
                        </div>
                      </Popup>
                    </Marker>
                  </React.Fragment>
                ))}
              </LayerGroup>
            </LayersControl.Overlay>

            <LayersControl.Overlay checked name="🌍 Earthquakes">
              <LayerGroup>
                {earthquakes.filter(located).map((eq) => (
                  <CircleMarker
                    key={eq.id}
                    center={[eq.lat, eq.lon]}
                    radius={Math.max(5, (eq.magnitude || 2) * 3.2)}
                    pathOptions={{
                      color: eqColor(eq.magnitude),
                      fillColor: eqColor(eq.magnitude),
                      fillOpacity: 0.45,
                      weight: 1.5,
                    }}
                  >
                    <Popup>
                      <div className="popup">
                        <div className="popup-title">🌍 M{eq.magnitude?.toFixed(1)} earthquake</div>
                        <div>{eq.place}</div>
                        <div className={`popup-badge ${eq.in_india === true ? 'is-india' : 'is-outside'}`}>
                          {eq.in_india === true ? 'Inside India' : eq.in_india === 'border' ? 'India border region' : `Outside India · ${eq.country}`}
                        </div>
                        <div>Depth {eq.depth_km ?? '?'} km · Significance {eq.significance ?? 'N/A'}</div>
                        <div className="popup-meta">Observed by USGS · {formatTime(eq.time_iso) ?? 'time unknown'}</div>
                        <a href={`https://earthquake.usgs.gov/earthquakes/eventpage/${eq.id}`} target="_blank" rel="noreferrer">USGS event page ↗</a>
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}
              </LayerGroup>
            </LayersControl.Overlay>

            <LayersControl.Overlay checked name="⚠️ Official warnings">
              <LayerGroup>
                {weatherWarningGroups.map((g) => (
                  <React.Fragment key={`${g.lat},${g.lon}`}>
                    <Circle
                      center={[g.lat, g.lon]}
                      radius={APPROX_RADIUS_M}
                      pathOptions={{ color: '#06b6d4', weight: 1.5, dashArray: '6 6', fillOpacity: 0.06 }}
                    />
                    <Marker position={[g.lat, g.lon]} icon={warningIcon(g.items.length)}>
                      <Popup maxWidth={320}>
                        <div className="popup">
                          <div className="popup-title">⚠️ {g.items.length} official warning{g.items.length > 1 ? 's' : ''} — {g.state}</div>
                          {g.items.map((a) => (
                            <div key={a.id} className="popup-item">
                              <b>{a.event}</b> · {a.severity_label}<br />
                              <span>{a.location}</span><br />
                              <span className="popup-meta">{a.source}{a.expires ? ` · until ${formatTime(a.expires)}` : ''}</span>
                            </div>
                          ))}
                          <div className="popup-warn">📍 Approximate: centre of {g.state} (alerts name districts, not coordinates)</div>
                        </div>
                      </Popup>
                    </Marker>
                  </React.Fragment>
                ))}
              </LayerGroup>
            </LayersControl.Overlay>

            <LayersControl.Overlay name="🌀 Cyclones">
              <LayerGroup>
                {(officialByCategory.cyclone ?? []).map((a) => (
                  <Marker key={a.id} position={[a.lat, a.lon]} icon={ICONS.cyclone}>
                    <Popup><AlertPopup alert={a} /></Popup>
                  </Marker>
                ))}
                {endedCyclones.map((e) => (
                  <Marker key={e.id} position={[e.lat, e.lon]} icon={ICONS.cycloneEnded}>
                    <Popup><AlertPopup alert={e} ended /></Popup>
                  </Marker>
                ))}
                {elevatedWind.map((c) => (
                  <Marker key={c.location} position={[c.lat, c.lon]} icon={ICONS.cyclone}>
                    <Popup>
                      <div className="popup">
                        <div className="popup-title">🌀 Wind indicator — {c.location}</div>
                        <div className="popup-badge is-indicator">Automated indicator · {c.severity}</div>
                        <div>Wind {c.features?.wind_speed_ms ?? '?'} m/s</div>
                        <div className="popup-meta">CrisisCore threshold on OpenWeather data — not an IMD warning</div>
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </LayerGroup>
            </LayersControl.Overlay>

            <LayersControl.Overlay name="🔥 Heatwave">
              <LayerGroup>
                {(officialByCategory.heatwave ?? []).map((a) => (
                  <Marker key={a.id} position={[a.lat, a.lon]} icon={ICONS.heat}>
                    <Popup><AlertPopup alert={a} /></Popup>
                  </Marker>
                ))}
                {elevatedHeat.map((h) => (
                  <Marker key={h.location} position={[h.lat, h.lon]} icon={ICONS.heat}>
                    <Popup>
                      <div className="popup">
                        <div className="popup-title">🔥 Heat indicator — {h.location}</div>
                        <div className="popup-badge is-indicator">Automated indicator · {h.severity}</div>
                        <div>{h.temperature ?? '?'}°C · heat index {h.features?.heat_index_c ?? '?'}°C</div>
                        <div className="popup-meta">CrisisCore threshold on OpenWeather data — not an IMD warning</div>
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </LayerGroup>
            </LayersControl.Overlay>

            <LayersControl.Overlay name="🌵 Drought">
              <LayerGroup>
                {(officialByCategory.drought ?? []).map((a) => (
                  <Marker key={a.id} position={[a.lat, a.lon]} icon={ICONS.drought}>
                    <Popup><AlertPopup alert={a} /></Popup>
                  </Marker>
                ))}
                {elevatedDrought.map((d) => (
                  <Marker key={d.region} position={[d.lat, d.lon]} icon={ICONS.drought}>
                    <Popup>
                      <div className="popup">
                        <div className="popup-title">🌵 Dry-conditions indicator — {d.region}</div>
                        <div className="popup-badge is-indicator">Automated indicator · {d.severity}</div>
                        <div>{d.contributing_features?.temperature_c ?? '?'}°C · humidity {d.contributing_features?.humidity_pct ?? '?'}%</div>
                        <div className="popup-meta">Single OpenWeather reading — not an official drought declaration</div>
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </LayerGroup>
            </LayersControl.Overlay>

            <LayersControl.Overlay checked name="🏥 Hospitals">
              <LayerGroup>
                {hospitals.filter(located).map((h) => (
                  <Marker key={`h-${h.id}`} position={[h.lat, h.lon]} icon={ICONS.hospital}>
                    <Popup><ResourcePopup item={h} label="hospital" /></Popup>
                  </Marker>
                ))}
              </LayerGroup>
            </LayersControl.Overlay>

            <LayersControl.Overlay checked name="🏠 Shelters">
              <LayerGroup>
                {shelters.filter(located).map((s) => (
                  <Marker key={`s-${s.id}`} position={[s.lat, s.lon]} icon={ICONS.shelter}>
                    <Popup><ResourcePopup item={s} label="shelter" /></Popup>
                  </Marker>
                ))}
              </LayerGroup>
            </LayersControl.Overlay>
          </LayersControl>

          {isValidLatLng(userLocation?.[0], userLocation?.[1]) && (
            <Marker position={userLocation} icon={ICONS.user}>
              <Popup>Your location (browser)</Popup>
            </Marker>
          )}

          {highlightTarget && <HighlightMarker key={highlightTarget.seq} target={highlightTarget} />}

          {floodClickBounds && floodClickData?.success && isValidLatLng(floodClickData.lat, floodClickData.lon) && (
            <Rectangle
              bounds={floodClickBounds}
              pathOptions={{
                color: '#0066cc',
                weight: 2,
                fillOpacity: floodClickData.flood_detected ? 0.15 : 0.05,
                dashArray: '5, 5',
              }}
            >
              <Popup>
                <div className="popup">
                  <div className="popup-title">🛰 Satellite flood analysis</div>
                  <div>{floodClickData.flood_detected ? `Flood detected · ${floodClickData.area_km2} km²` : 'No flood in analysis region'}</div>
                  <div className="popup-meta">Sentinel-1 SAR · image {floodClickData.image_date || 'N/A'}</div>
                </div>
              </Popup>
            </Rectangle>
          )}
        </MapContainer>

        {floodAnalyzing && <div className="map-toast map-toast-info">Analyzing flood risk via Sentinel-1/GEE (20–40 s)…</div>}
        {floodError && <div className="map-toast map-toast-error">Flood data unavailable: {floodError}</div>}
        {locateError && <div className="map-toast map-toast-error">Location error: {locateError}</div>}
      </div>

      <div className="map-status">
        <span className="map-status-label">🌊 Floods</span>
        {floodStatus.map((s) => <span key={s} className="map-status-item">{s}</span>)}
      </div>
      {resourceNote && <div className="map-status map-status--saved">🏥🏠 {resourceNote}</div>}

      <MapLegend />
    </div>
  );
}

export default DisasterMap;
