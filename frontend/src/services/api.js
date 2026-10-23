const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

async function fetchJson(path, options = {}) {
  const response = await fetch(`${BACKEND_URL}${path}`, options);
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${path}`);
  }
  return response.json();
}

export async function getHealth() {
  return fetchJson('/health');
}

export async function getIndiaDisasters(refresh = false) {
  return fetchJson(`/api/disasters/india${refresh ? '?refresh=true' : ''}`);
}

export async function getEarthquakes(refresh = false) {
  return fetchJson(`/api/disasters/earthquakes${refresh ? '?refresh=true' : ''}`);
}

export async function getFloods(refresh = false) {
  return fetchJson(`/api/disasters/floods${refresh ? '?refresh=true' : ''}`);
}

export async function getWeather(lat, lon) {
  const params = new URLSearchParams();
  if (lat != null) params.set('lat', lat);
  if (lon != null) params.set('lon', lon);
  const qs = params.toString();
  return fetchJson(`/api/weather${qs ? `?${qs}` : ''}`);
}

export async function getRisk(refresh = false, lat = null, lon = null) {
  const params = new URLSearchParams();
  if (refresh) params.set('refresh', 'true');
  if (lat != null) params.set('lat', lat);
  if (lon != null) params.set('lon', lon);
  const qs = params.toString();
  return fetchJson(`/api/ai-risk${qs ? `?${qs}` : ''}`);
}

export async function getHospitals(lat, lon) {
  return fetchJson(`/api/hospitals?lat=${lat}&lon=${lon}`);
}

export async function getShelters(lat, lon) {
  return fetchJson(`/api/shelters?lat=${lat}&lon=${lon}`);
}

export async function getHospitalsInMap(south, west, north, east) {
  return fetchJson(
    `/api/hospitals/map?south=${south}&west=${west}&north=${north}&east=${east}`
  );
}

export async function getSheltersInMap(south, west, north, east) {
  return fetchJson(
    `/api/shelters/map?south=${south}&west=${west}&north=${north}&east=${east}`
  );
}

export async function analyzeFloodRisk(lat, lon, bufferDeg = 0.15) {
  return fetchJson('/api/flood-risk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lat, lon, buffer_deg: bufferDeg }),
  });
}

export { BACKEND_URL };
