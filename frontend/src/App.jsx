import { useCallback, useEffect, useState } from 'react';
import './App.css';
import DisasterMap from './components/DisasterMap';
import RiskCards from './components/RiskCards';
import RiskAnalysis from './components/RiskAnalysis';
import AlertPanel from './components/AlertPanel';
import ResourceCard from './components/ResourceCard';
import ChatAssistant from './components/ChatAssistant';
import {
  getIndiaDisasters,
  getWeather,
  getHospitals,
  getShelters,
  getRisk,
} from './services/api';

const INDIA_CENTER = { lat: 20.5937, lon: 78.9629 };

function App() {
  const [loading, setLoading] = useState(true);
  const [resourcesLoading, setResourcesLoading] = useState(true);
  const [disasters, setDisasters] = useState(null);
  const [weather, setWeather] = useState(null);
  const [hospitals, setHospitals] = useState([]);
  const [shelters, setShelters] = useState([]);
  const [mapHospitals, setMapHospitals] = useState([]);
  const [mapShelters, setMapShelters] = useState([]);
  const handleMapResourcesLoaded = useCallback(
  (newHospitals, newShelters) => {
    setMapHospitals(newHospitals);
    setMapShelters(newShelters);
  },
  []
);
  const [aiRisk, setAiRisk] = useState(null);
  const [userLocation, setUserLocation] = useState(null);
  const [locationLabel, setLocationLabel] = useState('India (default)');
  const [error, setError] = useState(null);
  const [mapFocusTarget, setMapFocusTarget] = useState(null);

  const loadData = useCallback(async (refresh = false, lat = null, lon = null) => {
    setLoading(true);
    setError(null);
    try {
      const coords = {
        lat: lat ?? userLocation?.[0] ?? INDIA_CENTER.lat,
        lon: lon ?? userLocation?.[1] ?? INDIA_CENTER.lon,
      };

      // Each source loads independently: one slow/failed call must not blank the dashboard.
      // Hospitals/shelters (Overpass) can be slow, so they don't hold up the main loading state.
      const failed = [];
      const track = (label, promise, onSuccess) => promise.then(onSuccess).catch((err) => {
        console.warn(`${label} failed:`, err);
        failed.push(label);
      });

      setResourcesLoading(true);
      Promise.allSettled([
        track('hospitals', getHospitals(coords.lat, coords.lon), (d) => setHospitals(d?.hospitals ?? [])),
        track('shelters', getShelters(coords.lat, coords.lon), (d) => setShelters(d?.shelters ?? [])),
      ]).then(() => setResourcesLoading(false));

      await Promise.allSettled([
        track('disasters', getIndiaDisasters(refresh), setDisasters),
        track('weather', getWeather(coords.lat, coords.lon), setWeather),
        track('risk', getRisk(refresh, coords.lat, coords.lon), setAiRisk),
      ]);

      if (failed.length > 0) {
        setError(`Could not load: ${failed.join(', ')}`);
      }
    } finally {
      setLoading(false);
    }
  }, [userLocation]);

  useEffect(() => {
    if (typeof navigator !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const loc = [pos.coords.latitude, pos.coords.longitude];
          setUserLocation(loc);
          setLocationLabel(`${loc[0].toFixed(2)}, ${loc[1].toFixed(2)}`);
          loadData(false, loc[0], loc[1]);
        },
        () => {
          setLocationLabel('India (center)');
          loadData(false, INDIA_CENTER.lat, INDIA_CENTER.lon);
        },
        { enableHighAccuracy: true, timeout: 8000 },
      );
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time initial load on mount
      loadData(false, INDIA_CENTER.lat, INDIA_CENTER.lon);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRefresh = () => {
    const lat = userLocation?.[0] ?? INDIA_CENTER.lat;
    const lon = userLocation?.[1] ?? INDIA_CENTER.lon;
    loadData(true, lat, lon);
  };

  // Backend severities: critical > high > medium (e.g. M4+ earthquakes) > low
  const SEVERITY_RANK = { critical: 0, high: 1, medium: 2 };
  const alerts = (disasters?.alerts ?? [])
    .filter((alert) => alert.severity in SEVERITY_RANK)
    .sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);
  const risk = aiRisk ?? disasters?.risk ?? null;
  const nearestHospital = hospitals[0];
  const nearestShelter = shelters[0];

  // Compact, human-readable snapshot of the dashboard sent with each chat question
  const assistantContext = {
    location: locationLabel,
    weather: weather?.status === 'ok'
      ? `${weather.temperature}°C, ${weather.description || weather.condition}, humidity ${weather.humidity}%`
      : 'unavailable',
    overall_risk: risk?.overall?.level ?? 'unavailable',
    active_alerts: alerts.length,
    top_alerts: alerts.slice(0, 5).map((a) => a.title),
    earthquakes_tracked: disasters?.earthquakes?.length ?? 0,
    satellite_flood_detection: disasters?.floods?.[0]?.status === 'unavailable' ? 'not enabled' : 'enabled',
    nearest_hospital: nearestHospital ? `${nearestHospital.name} (${nearestHospital.distance_km} km)` : 'unknown',
    nearest_shelter: nearestShelter ? `${nearestShelter.name} (${nearestShelter.distance_km} km)` : 'unknown',
  };

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>India Disaster Intelligence Map</h1>
          <p>CrisisCore 2.0 — Real-time disaster monitoring across India</p>
        </div>
        <div className="location">
          📍 <span>{locationLabel}</span>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          ⚠ {error} — Ensure backend is running at http://localhost:8000
        </div>
      )}

      <RiskCards
        weather={weather}
        risk={risk}
        alertsCount={alerts.length}
        loading={loading}
      />

      <section className="main-grid">
        <div className="card map-card">
          <div className="section-header">
            <h2>🗺 India Disaster Map</h2>
            <span className="live">● Real Data</span>
          </div>
          <DisasterMap
            disasters={disasters}
            hospitals={mapHospitals}
            shelters={mapShelters}
            userLocation={userLocation}
            onRefresh={handleRefresh}
            loading={loading}
            mapFocusTarget={mapFocusTarget}
            mapFocusZoom={13}
            onMapResourcesLoaded={handleMapResourcesLoaded}
          />
        </div>

        <RiskAnalysis risk={risk} loading={loading} />
      </section>

      <section className="resource-grid">
        <ResourceCard
          resource={{
            id: 'hospital',
            title: '🏥 Nearest Hospital',
            summary: nearestHospital
              ? nearestHospital.name
              : resourcesLoading ? 'Searching...' : 'Data unavailable',
            distance: nearestHospital ? `${nearestHospital.distance_km} km` : '--',
            icon: '🏥',
            lat: nearestHospital?.lat,
            lon: nearestHospital?.lon,
          }}
          onFocusMap={(coords, zoom) => setMapFocusTarget({ coords, zoom })}
        />
        <ResourceCard
          resource={{
            id: 'shelter',
            title: '🏠 Nearest Shelter',
            summary: nearestShelter
              ? nearestShelter.name
              : resourcesLoading ? 'Searching...' : 'Data unavailable',
            distance: nearestShelter ? `${nearestShelter.distance_km} km` : '--',
            icon: '🏠',
            lat: nearestShelter?.lat,
            lon: nearestShelter?.lon,
          }}
          onFocusMap={(coords, zoom) => setMapFocusTarget({ coords, zoom })}
        />
        <ResourceCard
          resource={{
            id: 'alert',
            title: '🚨 Emergency Alerts',
            summary: loading
              ? 'Loading alerts...'
              : !disasters
                ? 'Alert data unavailable'
                : alerts.length === 0
                  ? 'No active alerts'
                  : `${alerts.length} active alert${alerts.length > 1 ? 's' : ''}`,
            distance: 'From real events →',
            icon: '🚨',
          }}
        />
      </section>

      <section className="alerts-section">
        <AlertPanel
          alerts={alerts}
          loading={loading}
          unavailable={!loading && !disasters}
          onAlertFocus={(lat, lon) => setMapFocusTarget({ coords: [lat, lon], zoom: 8 })}
        />
      </section>

      <ChatAssistant context={assistantContext} />

      <footer>
        CrisisCore 2.0 · India Disaster Intelligence Map ·
        Sources: Sentinel-1/GEE · USGS · OpenWeather · OpenStreetMap
      </footer>
    </div>
  );
}

export default App;
