import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './App.css';
import DisasterMap from './components/DisasterMap';
import RiskCards from './components/RiskCards';
import RiskAnalysis from './components/RiskAnalysis';
import AlertPanel from './components/AlertPanel';
import ResourceCard from './components/ResourceCard';
import ChatAssistant from './components/ChatAssistant';
import { savedDataNote } from './utils/savedData';
import { buildAssistantContext } from './utils/assistantContext';
import { CATEGORIES, formatTime, sortAlerts } from './utils/alerts';
import {
  getIndiaDisasters,
  getOfficialAlerts,
  getWeather,
  getHospitals,
  getShelters,
  getRisk,
} from './services/api';

const INDIA_CENTER = { lat: 20.5937, lon: 78.9629 };
// Presenter-selectable locations (the seven cities with saved hospital/shelter snapshots)
const CITY_PRESETS = [
  { key: 'bengaluru', label: 'Bengaluru', lat: 12.9716, lon: 77.5946 },
  { key: 'chennai', label: 'Chennai', lat: 13.0827, lon: 80.2707 },
  { key: 'delhi', label: 'Delhi', lat: 28.6139, lon: 77.209 },
  { key: 'hyderabad', label: 'Hyderabad', lat: 17.385, lon: 78.4867 },
  { key: 'kolkata', label: 'Kolkata', lat: 22.5726, lon: 88.3639 },
  { key: 'mumbai', label: 'Mumbai', lat: 19.076, lon: 72.8777 },
  { key: 'nagpur', label: 'Nagpur', lat: 21.1458, lon: 79.0882 },
];
const isNamed = (item) => item && !/#\d+$/.test(item.name ?? '');
const NEAREST_ON_MAP = 10;

// Nearest results are always drawn, so they are visible even before zooming in
function withNearest(nearest, viewport) {
  const seen = new Set(viewport.map((i) => i.id));
  return [...viewport, ...nearest.slice(0, NEAREST_ON_MAP).filter((i) => !seen.has(i.id))];
}

function App() {
  const [loading, setLoading] = useState(true);
  const [resourcesLoading, setResourcesLoading] = useState(true);
  const [officialLoading, setOfficialLoading] = useState(true);
  const [disasters, setDisasters] = useState(null);
  const [official, setOfficial] = useState(null);
  const [weather, setWeather] = useState(null);
  const [hospitalResponse, setHospitalResponse] = useState(null);
  const [shelterResponse, setShelterResponse] = useState(null);
  const [mapHospitals, setMapHospitals] = useState([]);
  const [mapShelters, setMapShelters] = useState([]);
  const [mapResourceNote, setMapResourceNote] = useState(null);
  const handleMapResourcesLoaded = useCallback(
    (newHospitals, newShelters, note = null) => {
      setMapHospitals(newHospitals);
      setMapShelters(newShelters);
      setMapResourceNote(note);
    },
    []
  );
  const [aiRisk, setAiRisk] = useState(null);
  const [userLocation, setUserLocation] = useState(null);
  const [locationLabel, setLocationLabel] = useState('India (default)');
  const [error, setError] = useState(null);
  const [mapFocusTarget, setMapFocusTarget] = useState(null);
  const [demoMode, setDemoMode] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const focusSeq = useRef(0);

  const loadData = useCallback(async (refresh = false, lat = null, lon = null) => {
    setLoading(true);
    setError(null);
    try {
      const coords = {
        lat: lat ?? userLocation?.[0] ?? INDIA_CENTER.lat,
        lon: lon ?? userLocation?.[1] ?? INDIA_CENTER.lon,
      };

      // Each source loads independently: one slow/failed call must not blank the dashboard.
      // Hospitals/shelters and official warnings can be slow, so they don't hold up the main loading state.
      const failed = [];
      const track = (label, promise, onSuccess) => promise.then(onSuccess).catch((err) => {
        console.warn(`${label} failed:`, err);
        failed.push(label);
      });

      setResourcesLoading(true);
      Promise.allSettled([
        track('hospitals', getHospitals(coords.lat, coords.lon), setHospitalResponse),
        track('shelters', getShelters(coords.lat, coords.lon), setShelterResponse),
      ]).then(() => setResourcesLoading(false));

      setOfficialLoading(true);
      track('official warnings', getOfficialAlerts(), setOfficial).finally(() => setOfficialLoading(false));

      await Promise.allSettled([
        track('disasters', getIndiaDisasters(refresh), setDisasters),
        track('weather', getWeather(coords.lat, coords.lon), setWeather),
        track('risk', getRisk(refresh, coords.lat, coords.lon), setAiRisk),
      ]);

      if (failed.length > 0) {
        setError(`Could not load: ${failed.join(', ')}`);
      }
      setLastUpdated(new Date().toISOString());
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
          setLocationLabel('India (centre) — location not shared');
          loadData(false, INDIA_CENTER.lat, INDIA_CENTER.lon);
        },
        { enableHighAccuracy: true, timeout: 8000 },
      );
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time initial load on mount
      loadData(false, INDIA_CENTER.lat, INDIA_CENTER.lon);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const [locationChoice, setLocationChoice] = useState('auto');
  const chooseLocation = (key) => {
    setLocationChoice(key);
    if (key === 'gps') {
      navigator.geolocation?.getCurrentPosition(
        (pos) => {
          const loc = [pos.coords.latitude, pos.coords.longitude];
          setUserLocation(loc);
          setLocationLabel(`My location (${loc[0].toFixed(2)}, ${loc[1].toFixed(2)})`);
          loadData(false, loc[0], loc[1]);
          focusMap(loc[0], loc[1], 11);
        },
        () => setLocationLabel('Location permission denied'),
        { enableHighAccuracy: true, timeout: 8000 },
      );
      return;
    }
    const city = key === 'centre'
      ? { label: 'India (centre)', ...INDIA_CENTER }
      : CITY_PRESETS.find((c) => c.key === key);
    if (!city) return;
    setUserLocation([city.lat, city.lon]);
    setLocationLabel(city.label);
    loadData(false, city.lat, city.lon);
    focusMap(city.lat, city.lon, key === 'centre' ? 5 : 11);
  };

  const handleRefresh = () => {
    const lat = userLocation?.[0] ?? INDIA_CENTER.lat;
    const lon = userLocation?.[1] ?? INDIA_CENTER.lon;
    loadData(true, lat, lon);
  };

  const focusMap = useCallback((lat, lon, zoom, highlight = null) => {
    focusSeq.current += 1;
    setMapFocusTarget({ coords: [lat, lon], zoom, highlight, seq: focusSeq.current });
  }, []);

  const hospitals = useMemo(() => hospitalResponse?.hospitals ?? [], [hospitalResponse]);
  const shelters = useMemo(() => shelterResponse?.shelters ?? [], [shelterResponse]);
  // Prefer the nearest place that has a real name; unnamed OSM entries only as a fallback
  const nearestHospital = hospitals.find(isNamed) ?? hospitals[0];
  const nearestShelter = shelters.find(isNamed) ?? shelters[0];

  const mapHospitalsAll = useMemo(() => withNearest(hospitals, mapHospitals), [hospitals, mapHospitals]);
  const mapSheltersAll = useMemo(() => withNearest(shelters, mapShelters), [shelters, mapShelters]);

  const alerts = useMemo(
    () => sortAlerts([...(official?.alerts ?? []), ...(disasters?.alerts ?? [])]),
    [official, disasters]
  );
  const sources = useMemo(() => ({
    ...(disasters?.source_status ?? {}),
    ...(official?.sources ?? {}),
  }), [disasters, official]);
  const risk = aiRisk ?? null;

  const assistantContext = buildAssistantContext({
    locationLabel, weather, risk, disasters, official, alerts,
    nearestHospital, nearestShelter, hospitalResponse, shelterResponse, demoMode,
  });

  const focusResource = (item, label) => focusMap(item.lat, item.lon, 16, {
    title: `${label === 'hospital' ? '🏥' : '🏠'} ${item.name}`,
    lines: [
      `${item.distance_km} km from you`,
      item.data_source === 'snapshot' ? 'Saved OpenStreetMap snapshot' : 'Live OpenStreetMap data',
    ],
  });

  const focusAlert = (a) => focusMap(a.lat, a.lon, a.coord_precision === 'approximate' ? 7 : 8, {
    title: `${CATEGORIES[a.category]?.icon ?? '⚠'} ${a.title}`,
    lines: [
      a.coord_precision === 'approximate' ? a.coord_note : a.location,
      `${a.source} · ${formatTime(a.timestamp) ?? ''}`,
    ].filter(Boolean),
  });

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-logo" aria-hidden="true">
            <svg viewBox="0 0 32 32" width="34" height="34"><path d="M16 2 4 7v8c0 7.2 5 12.9 12 15 7-2.1 12-7.8 12-15V7L16 2Z" fill="currentColor" opacity=".18" /><path d="M16 2 4 7v8c0 7.2 5 12.9 12 15 7-2.1 12-7.8 12-15V7L16 2Z" fill="none" stroke="currentColor" strokeWidth="2" /><path d="M10 17h3l2-5 3 9 2-4h2" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </div>
          <div>
            <h1>CrisisCore</h1>
            <p className="brand-tag">India Disaster Intelligence · real-time multi-hazard monitoring</p>
          </div>
        </div>
        <div className="topbar-meta">
          <label className="location-picker" title="Location used for weather, risk and nearest resources">
            <span aria-hidden="true">📍</span>
            <span className="sr-only">Location</span>
            <select value={locationChoice} onChange={(e) => chooseLocation(e.target.value)}>
              <option value="auto" disabled>{locationLabel}</option>
              <option value="gps">Use my location</option>
              <option value="centre">India (centre)</option>
              <optgroup label="Cities with saved hospital data">
                {CITY_PRESETS.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
              </optgroup>
            </select>
          </label>
          <span className="meta-pill">
            {loading ? <><span className="spinner" aria-hidden="true" /> Updating…</> : `Updated ${formatTime(lastUpdated) ?? '—'}`}
          </span>
          <button type="button" className="btn btn-primary" onClick={handleRefresh} disabled={loading}>↻ Refresh</button>
        </div>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <b>Some data could not be loaded</b> — {error.replace('Could not load: ', '')}. The rest of the dashboard
          still works. Check that the backend is running at http://localhost:8000, then press Refresh.
        </div>
      )}

      <RiskCards
        weather={weather}
        risk={risk}
        alerts={alerts}
        loading={loading}
        sources={sources}
        resourceSaved={hospitalResponse?.data_source === 'snapshot' || shelterResponse?.data_source === 'snapshot'}
        demoMode={demoMode}
      />

      <section className="main-grid">
        <div className="card map-card">
          <header className="card-header">
            <div>
              <h2>India disaster map</h2>
              <p className="card-sub">Toggle layers top-right · click any marker for details</p>
            </div>
          </header>
          <DisasterMap
            disasters={disasters}
            official={official}
            hospitals={mapHospitalsAll}
            shelters={mapSheltersAll}
            userLocation={userLocation}
            onRefresh={handleRefresh}
            loading={loading}
            mapFocusTarget={mapFocusTarget}
            mapFocusZoom={13}
            onMapResourcesLoaded={handleMapResourcesLoaded}
            resourceNote={mapResourceNote}
            demoMode={demoMode}
            onDemoModeChange={setDemoMode}
          />
        </div>

        <AlertPanel
          alerts={alerts}
          loading={loading && alerts.length === 0}
          unavailable={!loading && !disasters && !official}
          officialLoading={officialLoading && !official}
          sources={sources}
          recentEvents={official?.recent_events ?? []}
          onAlertFocus={focusAlert}
        />
      </section>

      <section className="resource-grid">
        <ResourceCard
          title="Nearest hospital"
          icon="🏥"
          item={nearestHospital}
          response={hospitalResponse}
          loading={resourcesLoading}
          onFocusMap={(item) => focusResource(item, 'hospital')}
        />
        <ResourceCard
          title="Nearest shelter"
          icon="🏠"
          item={nearestShelter}
          response={shelterResponse}
          loading={resourcesLoading}
          onFocusMap={(item) => focusResource(item, 'shelter')}
        />
      </section>

      <RiskAnalysis risk={risk} loading={loading} />

      <ChatAssistant context={assistantContext} />

      <footer className="footer">
        <span>CrisisCore 2.0 · India Disaster Intelligence</span>
        <span>
          Sources: NDMA SACHET (IMD / CWC / SDMA) · GDACS · USGS · OpenWeather · © OpenStreetMap contributors
          {savedDataNote(hospitalResponse) ? ' (saved snapshot)' : ''}
        </span>
        <span>Emergency: <b>112</b></span>
      </footer>
    </div>
  );
}

export default App;
