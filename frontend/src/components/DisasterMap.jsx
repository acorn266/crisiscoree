import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
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

const INDIA_CENTER = [20.5937, 78.9629];
const INDIA_BOUNDS = L.latLngBounds([6.5, 68.1], [35.5, 97.4]);
const DEFAULT_ZOOM = 5;

const userIcon = L.icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const hospitalIcon = L.divIcon({
  className: 'custom-div-icon hospital-icon',
  html: '<span>🏥</span>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const shelterIcon = L.divIcon({
  className: 'custom-div-icon shelter-icon',
  html: '<span>🏠</span>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const floodIcon = L.divIcon({
  className: 'custom-div-icon flood-icon',
  html: '<span>🌊</span>',
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

const droughtIcon = L.divIcon({
  className: 'custom-div-icon drought-icon',
  html: '<span>🌵</span>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const heatIcon = L.divIcon({
  className: 'custom-div-icon heat-icon',
  html: '<span>🔥</span>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const cycloneIcon = L.divIcon({
  className: 'custom-div-icon cyclone-icon',
  html: '<span>🌀</span>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

function IndiaFitBounds() {
  const map = useMap();
  useEffect(() => {
    map.fitBounds(INDIA_BOUNDS, { padding: [20, 20] });
  }, [map]);
  return null;
}

function MapFocusTarget({ target, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (target) {
      map.setView(target, zoom || 13);
    }
  }, [map, target, zoom]);
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

    const loadResources = async () => {
      // Don't query Overpass while viewing the entire country.
      // Wait until the user zooms into a useful region.
      if (map.getZoom() < 7) {
        onResourcesLoaded([], []);
        return;
      }

      const bounds = map.getBounds();

      const south = bounds.getSouth();
      const west = bounds.getWest();
      const north = bounds.getNorth();
      const east = bounds.getEast();

      try {
        const [hospitalData, shelterData] = await Promise.all([
          getHospitalsInMap(south, west, north, east),
          getSheltersInMap(south, west, north, east),
        ]);

        if (!cancelled) {
          onResourcesLoaded(
            hospitalData.hospitals ?? [],
            shelterData.shelters ?? []
          );
        }
      } catch (err) {
        console.error('Map resource loading failed:', err);

        if (!cancelled) {
          onResourcesLoaded([], []);
        }
      }
    };

    loadResources();

    const handleMoveEnd = () => {
      loadResources();
    };

    map.on('moveend', handleMoveEnd);

    return () => {
      cancelled = true;
      map.off('moveend', handleMoveEnd);
    };
  }, [map, onResourcesLoaded]);

  return null;
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

function isValidLatLng(lat, lon) {
  return (
    typeof lat === 'number' &&
    typeof lon === 'number' &&
    !Number.isNaN(lat) &&
    !Number.isNaN(lon) &&
    lat >= -90 && lat <= 90 &&
    lon >= -180 && lon <= 180
  );
}

function DisasterMap({
  disasters,
  hospitals = [],
  shelters = [],
  onMapResourcesLoaded,
  userLocation,
  onRefresh,
  loading,
  mapFocusTarget = null,
  mapFocusZoom = 13,
}) {
  const mapShellRef = useRef(null);
  const leafletMapRef = useRef(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [floodClickData, setFloodClickData] = useState(null);
  const [floodClickBounds, setFloodClickBounds] = useState(null);
  const [floodAnalyzing, setFloodAnalyzing] = useState(false);
  const [floodError, setFloodError] = useState(null);
  const [locateError, setLocateError] = useState(null);

  const floods = disasters?.floods ?? [];
  const earthquakes = disasters?.earthquakes ?? [];
  const droughts = disasters?.droughts ?? [];
  const heatwaves = disasters?.heatwaves ?? [];
  const cyclones = disasters?.cyclones ?? [];

  const handleFloodAnalysis = useCallback(async (lat, lon) => {
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

    if (!document.fullscreenElement) {
      el.requestFullscreen?.().then(() => {
        setIsFullscreen(true);
        setTimeout(() => {
          window.dispatchEvent(new Event('resize'));
        }, 200);
      }).catch(() => {});
    } else {
      document.exitFullscreen?.().then(() => {
        setIsFullscreen(false);
        setTimeout(() => {
          window.dispatchEvent(new Event('resize'));
        }, 200);
      }).catch(() => {});
    }
  }, []);

  useEffect(() => {
    const onFsChange = () => {
      const fs = !!document.fullscreenElement;
      setIsFullscreen(fs);
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
      ...floods.filter((f) => isValidLatLng(f.lat, f.lon)).map((f) => [f.lat, f.lon]),
      ...earthquakes.filter((eq) => isValidLatLng(eq.lat, eq.lon)).map((eq) => [eq.lat, eq.lon]),
      ...droughts.filter((d) => isValidLatLng(d.lat, d.lon)).map((d) => [d.lat, d.lon]),
      ...heatwaves.filter((h) => isValidLatLng(h.lat, h.lon)).map((h) => [h.lat, h.lon]),
      ...cyclones.filter((c) => isValidLatLng(c.lat, c.lon)).map((c) => [c.lat, c.lon]),
    ];

    if (points.length > 0) {
      map.fitBounds(points, { padding: [30, 30] });
    }
  }, [floods, earthquakes, droughts, heatwaves, cyclones]);

  function MapResizeHandler() {
    const map = useMap();
    useEffect(() => {
      const handler = () => map.invalidateSize();
      window.addEventListener('resize', handler);
      return () => window.removeEventListener('resize', handler);
    }, [map]);
    return null;
  }

  return (
    <div className={`map-shell ${isFullscreen ? 'map-fullscreen' : ''}`} ref={mapShellRef}>
      <div className="map-toolbar">
        <button type="button" className="map-btn" onClick={toggleFullscreen} title="Toggle fullscreen">
          {isFullscreen ? '⛶ Exit Fullscreen' : '⛶ Fullscreen'}
        </button>
        {onRefresh && (
          <button type="button" className="map-btn" onClick={onRefresh} disabled={loading}>
            {loading ? 'Refreshing...' : '↻ Refresh Data'}
          </button>
        )}
        <button type="button" className="map-btn" onClick={handleLocateMe} title="Go to my location">
          📍 My Location
        </button>
        <button type="button" className="map-btn" onClick={handleFitToDisasters} title="Fit map to active events">
          🎯 Fit to Events
        </button>
        <span className="source-tag">Sources: Sentinel-1/GEE · USGS · OpenWeather · OSM</span>
      </div>

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
        <MapFocusTarget target={mapFocusTarget} zoom={mapFocusZoom} />
        <MapResizeHandler />
        <MapClickHandler onMapClick={handleFloodAnalysis} />
        <MapResourceLoader
          onResourcesLoaded={onMapResourcesLoaded}
        />
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <LayersControl position="topright" collapsed={false}>
          <LayersControl.Overlay checked name="🌊 Flood">
            <LayerGroup>
              {floods.map((f) => {
                const positions = geoJsonToLeafletPositions(f.geometry);
                const key = f.region_id || f.region || `${f.lat}-${f.lon}`;
                if (f.status === 'unavailable') {
                  return positions ? (
                    <Polygon
                      key={key}
                      positions={positions}
                      pathOptions={{ color: '#78909c', weight: 1, dashArray: '4', fillOpacity: 0.05 }}
                    >
                      <Popup>
                        <strong>🌊 {f.region}</strong><br />
                        Status: Data unavailable<br />
                        {f.message}<br />
                        <small>Source: Sentinel-1/GEE — Latest available Sentinel-1 satellite data</small>
                      </Popup>
                    </Polygon>
                  ) : (
                    f.lat != null && f.lon != null ? (
                      <Marker
                      key={key}
                      position={[f.lat, f.lon]}
                      icon={floodIcon}
                      >
                      <Popup>
                      <strong>🌊 {f.region}</strong><br />
                      Status: Data unavailable<br />
                      {f.message}
                      </Popup>
                      </Marker>
                    ) : null
                  );
                }
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
                          <strong>🌊 {f.region}</strong><br />
                          Status: {f.status}<br />
                          Severity: {f.severity}<br />
                          {f.flood_detected ? `Area: ${f.area_km2} km²` : 'No new flood detected in analysis region'}<br />
                          Image date: {f.image_date || f.timestamp || 'N/A'}<br />
                          <small>Source: Sentinel-1/GEE — Latest available Sentinel-1 satellite data</small>
                        </Popup>
                      </Polygon>
                    )}
                    {f.flood_detected && (
                      <Marker position={[f.lat, f.lon]} icon={floodIcon}>
                        <Popup>
                          <strong>FLOOD DETECTED — {f.region}</strong><br />
                          Area: {f.area_km2} km²<br />
                          Severity: {f.severity}
                        </Popup>
                      </Marker>
                    )}
                  </React.Fragment>
                );
              })}
            </LayerGroup>
          </LayersControl.Overlay>

          <LayersControl.Overlay checked name="🌍 Earthquake">
            <LayerGroup>
              {earthquakes.filter((eq) => isValidLatLng(eq.lat, eq.lon)).map((eq) => (
                <CircleMarker
                  key={eq.id}
                  center={[eq.lat, eq.lon]}
                  radius={Math.max(6, (eq.magnitude || 2) * 5)}
                  pathOptions={{
                    color: eqColor(eq.magnitude),
                    fillColor: eqColor(eq.magnitude),
                    fillOpacity: 0.75,
                    weight: 1.5,
                  }}
                >
                  <Popup>
                    <strong>🌍 M{eq.magnitude?.toFixed(1)}</strong><br />
                    {eq.place}<br />
                    Depth: {eq.depth_km ?? '?'} km<br />
                    Time: {eq.time_iso || 'Unknown'}<br />
                    Alert: {eq.alert || 'None'}<br />
                    Significance: {eq.significance ?? 'N/A'}<br />
                    <small>Source: USGS</small>
                  </Popup>
                </CircleMarker>
              ))}
            </LayerGroup>
          </LayersControl.Overlay>

          <LayersControl.Overlay name="🌵 Drought">
            <LayerGroup>
              {droughts.filter((d) => d.severity !== 'NONE' && d.severity !== 'UNAVAILABLE' && isValidLatLng(d.lat, d.lon)).map((d) => (
                <Marker key={d.region} position={[d.lat, d.lon]} icon={droughtIcon}>
                  <Popup>
                    <strong>🌵 {d.region}</strong><br />
                    Severity: {d.severity}<br />
                    Status: {d.status}<br />
                    {d.message && <>{d.message}<br /></>}
                    Temp: {d.contributing_features?.temperature_c ?? '?'}°C<br />
                    Humidity: {d.contributing_features?.humidity_pct ?? '?'}%<br />
                    <small>Source: OpenWeather</small>
                  </Popup>
                </Marker>
              ))}
            </LayerGroup>
          </LayersControl.Overlay>

          <LayersControl.Overlay name="🔥 Heatwave">
            <LayerGroup>
              {heatwaves.filter((h) => h.severity !== 'NONE' && h.severity !== 'UNAVAILABLE' && isValidLatLng(h.lat, h.lon)).map((h) => (
                <CircleMarker
                  key={h.location}
                  center={[h.lat, h.lon]}
                  radius={8}
                  pathOptions={{ color: '#ff7043', fillColor: '#ff7043', fillOpacity: 0.6 }}
                >
                  <Popup>
                    <strong>🔥 {h.location}</strong><br />
                    Severity: {h.severity}<br />
                    Temperature: {h.temperature ?? '?'}°C<br />
                    Heat index: {h.features?.heat_index_c ?? '?'}°C<br />
                    <small>Source: OpenWeather</small>
                  </Popup>
                </CircleMarker>
              ))}
            </LayerGroup>
          </LayersControl.Overlay>

          <LayersControl.Overlay name="🌀 Cyclone">
            <LayerGroup>
              {cyclones.filter((c) => c.severity !== 'NONE' && c.severity !== 'UNAVAILABLE' && isValidLatLng(c.lat, c.lon)).map((c) => (
                <Marker key={c.location} position={[c.lat, c.lon]} icon={cycloneIcon}>
                  <Popup>
                    <strong>🌀 {c.location}</strong><br />
                    Severity: {c.severity}<br />
                    Wind: {c.features?.wind_speed_ms ?? '?'} m/s<br />
                    {c.message}<br />
                    <small>Source: OpenWeather — No fabricated cyclone events</small>
                  </Popup>
                </Marker>
              ))}
            </LayerGroup>
          </LayersControl.Overlay>

          <LayersControl.Overlay name="🏥 Hospitals">
            <LayerGroup>
              {hospitals.filter((h) => isValidLatLng(h.lat, h.lon)).map((h) => (
                <Marker key={h.id} position={[h.lat, h.lon]} icon={hospitalIcon}>
                  <Popup>
                    <strong>🏥 {h.name}</strong><br />
                    Distance: {h.distance_km} km<br />
                    <small>Source: OpenStreetMap</small>
                  </Popup>
                </Marker>
              ))}
            </LayerGroup>
          </LayersControl.Overlay>

          <LayersControl.Overlay name="🏠 Shelters">
            <LayerGroup>
              {shelters.filter((s) => isValidLatLng(s.lat, s.lon)).map((s) => (
                <Marker key={s.id} position={[s.lat, s.lon]} icon={shelterIcon}>
                  <Popup>
                    <strong>🏠 {s.name}</strong><br />
                    Distance: {s.distance_km} km<br />
                    <small>Source: OpenStreetMap</small>
                  </Popup>
                </Marker>
              ))}
            </LayerGroup>
          </LayersControl.Overlay>
        </LayersControl>

        {userLocation && (
          <Marker position={userLocation} icon={userIcon}>
            <Popup>
              <strong>Your Location</strong><br />
              Browser geolocation
            </Popup>
          </Marker>
        )}

        {floodClickBounds && floodClickData?.success && (
          <Rectangle
            bounds={floodClickBounds}
            pathOptions={{
              color: '#0066cc',
              weight: 2,
              opacity: 0.8,
              fillColor: '#0066cc',
              fillOpacity: floodClickData.flood_detected ? 0.15 : 0.05,
              dashArray: '5, 5',
            }}
          >
            <Popup>
              <strong>🛰 Satellite Flood Analysis Region</strong><br />
              <strong>Location:</strong> {floodClickData.lat.toFixed(4)}, {floodClickData.lon.toFixed(4)}<br />
              {floodClickData.flood_detected ? (
                <>
                  <strong style={{ color: '#0066cc' }}>✓ FLOOD DETECTED</strong><br />
                  <strong>Flooded Area:</strong> {floodClickData.area_km2} km²<br />
                </>
              ) : (
                <>
                  <strong style={{ color: '#4fc3f7' }}>○ No flood in analysis region</strong><br />
                </>
              )}
              <strong>Image Date:</strong> {floodClickData.image_date || 'N/A'}<br />
              <strong>Satellite:</strong> Sentinel-1 SAR (VH polarization)<br />
              <strong>Resolution:</strong> 10 meters/pixel<br />
              <strong>Data Source:</strong> Google Earth Engine<br />
              <small style={{ display: 'block', marginTop: '8px', opacity: 0.8 }}>
                Detection based on radar backscatter values. No permanent water included.
              </small>
            </Popup>
          </Rectangle>
        )}

        {floodClickData?.flood_detected && (
          <Marker position={[floodClickData.lat, floodClickData.lon]} icon={floodIcon}>
            <Popup>
              <strong>FLOOD DETECTED (click analysis)</strong><br />
              Area: {floodClickData.area_km2} km²
            </Popup>
          </Marker>
        )}
      </MapContainer>

      {floodAnalyzing && (
        <div className="map-toast map-toast-info">
          Analyzing flood risk via Sentinel-1/GEE (20–40s)...
        </div>
      )}

      {floodError && (
        <div className="map-toast map-toast-error">
          Flood data unavailable: {floodError}
        </div>
      )}

      {locateError && (
        <div className="map-toast map-toast-error">
          Location error: {locateError}
        </div>
      )}

      <MapLegend />
    </div>
  );
}

export default DisasterMap;
