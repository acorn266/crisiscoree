// Shared labels for alert categories, kinds and severities.

export const CATEGORIES = {
  earthquake: { label: 'Earthquake', icon: '🌍', color: 'var(--cat-earthquake)' },
  flood: { label: 'Flood', icon: '🌊', color: 'var(--cat-flood)' },
  cyclone: { label: 'Cyclone', icon: '🌀', color: 'var(--cat-cyclone)' },
  heatwave: { label: 'Heatwave', icon: '🔥', color: 'var(--cat-heatwave)' },
  drought: { label: 'Drought', icon: '🌵', color: 'var(--cat-drought)' },
  severe_weather: { label: 'Severe weather', icon: '⛈️', color: 'var(--cat-weather)' },
  wildfire: { label: 'Wildfire', icon: '🔥', color: 'var(--cat-heatwave)' },
};

export const KINDS = {
  official_warning: { label: 'Official warning', short: 'Official', group: 'official' },
  official_event: { label: 'Verified event', short: 'Official', group: 'official' },
  observed_event: { label: 'Observed event', short: 'Observed', group: 'observed' },
  risk_indicator: { label: 'Automated indicator', short: 'Indicator', group: 'indicator' },
};

export const SEVERITY_RANK = { critical: 0, high: 1, medium: 2, low: 3 };

// Which sources can report each category (used for honest empty states)
export const CATEGORY_SOURCES = {
  earthquake: ['usgs', 'gdacs'],
  flood: ['sachet', 'gdacs', 'satellite_floods'],
  cyclone: ['sachet', 'gdacs', 'openweather'],
  heatwave: ['sachet', 'openweather'],
  drought: ['gdacs', 'openweather'],
  severe_weather: ['sachet'],
};

export function categoryOf(alert) {
  return alert.category || alert.disaster_type || 'severe_weather';
}

export function sortAlerts(alerts) {
  return [...alerts].sort((a, b) => {
    const s = (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9);
    if (s !== 0) return s;
    return String(b.timestamp || '').localeCompare(String(a.timestamp || ''));
  });
}

export function formatTime(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function timeAgo(iso) {
  if (!iso) return null;
  const ms = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(ms)) return null;
  const min = Math.round(ms / 60000);
  if (min < 1) return 'just now';
  if (min < 60) return `${min} min ago`;
  const h = Math.round(min / 60);
  if (h < 48) return `${h} h ago`;
  return `${Math.round(h / 24)} days ago`;
}
