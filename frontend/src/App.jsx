import { useCallback, useEffect, useState } from 'react';
import './App.css';
import DisasterMap from './components/DisasterMap';
import RiskCards from './components/RiskCards';
import RiskAnalysis from './components/RiskAnalysis';
import AlertPanel from './components/AlertPanel';
import ResourceCard from './components/ResourceCard';
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

      const [disasterData, weatherData, hospitalData, shelterData, riskData] = await Promise.all([
        getIndiaDisasters(refresh),
        getWeather(coords.lat, coords.lon),
        getHospitals(coords.lat, coords.lon),
        getShelters(coords.lat, coords.lon),
        getRisk(refresh, coords.lat, coords.lon),
      ]);

      setDisasters(disasterData);
      setWeather(weatherData);
      setHospitals(hospitalData.hospitals ?? []);
      setShelters(shelterData.shelters ?? []);
      setAiRisk(riskData);
    } catch (err) {
      setError(err.message || 'Failed to load disaster data');
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
      loadData(false, INDIA_CENTER.lat, INDIA_CENTER.lon);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRefresh = () => {
    const lat = userLocation?.[0] ?? INDIA_CENTER.lat;
    const lon = userLocation?.[1] ?? INDIA_CENTER.lon;
    loadData(true, lat, lon);
  };

  const alerts = (disasters?.alerts ?? []).filter(
    (alert) => alert.severity === 'high' || alert.severity === 'critical'
  );
  const risk = aiRisk ?? disasters?.risk ?? null;
  const nearestHospital = hospitals[0];
  const nearestShelter = shelters[0];

  const assistantContext = {
    location: locationLabel,
    disasters: disasters ? {
      floods: disasters.floods?.length ?? 0,
      earthquakes: disasters.earthquakes?.length ?? 0,
      alerts: alerts.length,
    } : null,
    risk,
    weather,
    userLocation,
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
              : loading ? 'Searching...' : 'Data unavailable',
            distance: nearestHospital ? `${nearestHospital.distance_km} km` : '--',
            icon: '🏥',
            lat: nearestHospital?.lat,
            lon: nearestHospital?.lon,
          }}
          onFocusMap={(coords, zoom) => setMapFocusTarget(coords)}
        />
        <ResourceCard
          resource={{
            id: 'shelter',
            title: '🏠 Nearest Shelter',
            summary: nearestShelter
              ? nearestShelter.name
              : loading ? 'Searching...' : 'Data unavailable',
            distance: nearestShelter ? `${nearestShelter.distance_km} km` : '--',
            icon: '🏠',
            lat: nearestShelter?.lat,
            lon: nearestShelter?.lon,
          }}
          onFocusMap={(coords, zoom) => setMapFocusTarget(coords)}
        />
        <ResourceCard
          resource={{
            id: 'alert',
            title: '🚨 Emergency Alerts',
            summary: loading
              ? 'Loading alerts...'
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
          onAlertFocus={(lat, lon) => setMapFocusTarget([lat, lon])}
        />
      </section>

      <section className="card assistant">
        <div className="assistant-icon">🤖</div>
        <div className="assistant-content">
          <h2>CrisisCore AI Assistant</h2>
          <p>
            Ask about current disaster conditions, safety, emergency resources, or preparedness.
            LLM integration coming soon — context is prepared from live disaster data.
          </p>
          <div className="assistant-context-preview">
            <small>
              Context ready: location={assistantContext.location},
              alerts={assistantContext.disasters?.alerts ?? 0},
              earthquakes={assistantContext.disasters?.earthquakes ?? 0},
              weather={weather?.status === 'ok' ? `${weather.temperature}°C` : 'unavailable'}
            </small>
          </div>
          <div className="chat-input">
            <input type="text" placeholder="Ask: Is my area safe right now?" disabled />
            <button disabled title="LLM not connected yet">Ask AI</button>
          </div>
        </div>
      </section>

      <footer>
        CrisisCore 2.0 · India Disaster Intelligence Map ·
        Sources: Sentinel-1/GEE · USGS · OpenWeather · OpenStreetMap
      </footer>
    </div>
  );
}

export default App;
