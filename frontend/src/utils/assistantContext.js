// Builds the factual dashboard snapshot sent to the chatbot with each question.
// Everything is pre-counted and labelled so the model never has to infer
// (e.g. which earthquakes are inside India, or whether resource data is live).
import { CATEGORIES, KINDS, formatTime } from './alerts';

function resourceLine(resource, response) {
  if (!resource) {
    return response ? 'unavailable (no live or saved OpenStreetMap data for this location)' : 'still loading';
  }
  const origin = response?.data_source === 'snapshot'
    ? `SAVED OpenStreetMap snapshot for ${response.snapshot_area} (${formatTime(response.snapshot_date)}), not live`
    : 'live OpenStreetMap data';
  return `${resource.name}, ${resource.distance_km} km away (${origin})`;
}

export function buildAssistantContext({
  locationLabel, weather, risk, disasters, official, alerts,
  nearestHospital, nearestShelter, hospitalResponse, shelterResponse, demoMode,
}) {
  const quakes = disasters?.earthquakes ?? [];
  const inIndia = quakes.filter((q) => q.in_india === true);
  const border = quakes.filter((q) => q.in_india === 'border');
  const outside = quakes.filter((q) => q.in_india === false);
  const outsideByCountry = outside.reduce((acc, q) => {
    acc[q.country] = (acc[q.country] || 0) + 1;
    return acc;
  }, {});
  const strongest = (list) => [...list].sort((a, b) => (b.magnitude ?? 0) - (a.magnitude ?? 0))[0];
  const fmtQuake = (q) => `M${q.magnitude} ${q.place} (${formatTime(q.time_iso) ?? 'time unknown'})`;

  const officialAlerts = alerts.filter((a) => KINDS[a.kind]?.group === 'official');
  const indicators = alerts.filter((a) => a.kind === 'risk_indicator');
  const byCategory = alerts.reduce((acc, a) => {
    const c = CATEGORIES[a.category]?.label ?? a.category;
    acc[c] = (acc[c] || 0) + 1;
    return acc;
  }, {});

  const sources = { ...(disasters?.source_status ?? {}), ...(official?.sources ?? {}) };
  const sourceLine = Object.values(sources).map((s) => `${s.name}: ${s.status}`).join('; ');

  const floodWarnings = officialAlerts.filter((a) => a.category === 'flood');
  const lastFlood = (official?.recent_events ?? []).find((e) => e.category === 'flood');

  const riskLines = Object.entries(risk?.risks ?? {}).map(([hazard, r]) => (
    r.score == null
      ? `${hazard}: unavailable (${r.reason ?? 'no data'})`
      : `${hazard}: ${r.level} (${r.score}/100) — AI estimate, not an official forecast; ${r.basis ?? ''}`
      + (r.guard ? ` Capped because ${r.guard}.` : '')
  ));

  return {
    location: locationLabel,
    weather_now: weather?.status === 'ok'
      ? `${weather.temperature}°C, ${weather.description || weather.condition}, humidity ${weather.humidity}%, `
        + `wind ${weather.wind_speed_ms} m/s, rain last hour ${weather.rainfall_1h_mm ?? 0} mm (live OpenWeather)`
      : 'unavailable',
    overall_risk: risk?.overall?.level
      ? `${risk.overall.level} (${risk.overall.score}/100) — CrisisCore AI estimate = highest hazard score below`
      : 'unavailable',
    hazard_estimates: riskLines,
    earthquakes_summary: quakes.length
      ? `${quakes.length} USGS earthquakes (M2.5+) in the India region: ${inIndia.length} INSIDE India, `
        + `${border.length} in India border regions, ${outside.length} OUTSIDE India `
        + `(${Object.entries(outsideByCountry).map(([c, n]) => `${c} ${n}`).join(', ') || 'none'}).`
      : 'USGS earthquake data unavailable',
    earthquakes_inside_india: inIndia.slice(0, 10).map(fmtQuake),
    strongest_inside_india: inIndia.length ? fmtQuake(strongest(inIndia)) : 'none in current USGS data',
    strongest_outside_india: outside.length
      ? `${fmtQuake(strongest(outside))} — in ${strongest(outside).country}, NOT in India`
      : 'none',
    active_alerts_total: `${alerts.length} (${officialAlerts.length} official warnings/events, `
      + `${alerts.filter((a) => a.kind === 'observed_event').length} observed earthquakes, ${indicators.length} automated indicators)`,
    alerts_by_category: Object.entries(byCategory).map(([c, n]) => `${c}: ${n}`).join(', ') || 'none',
    official_warnings: officialAlerts.slice(0, 10).map((a) => (
      `${a.event ?? a.title} — ${a.location} — severity ${a.severity_label ?? a.severity}`
      + `${a.expires ? `, valid until ${formatTime(a.expires)}` : ''} — ${a.source}`
    )),
    flood_status: `${floodWarnings.length} official flood warning(s)`
      + `${floodWarnings.length ? ` (${floodWarnings.map((a) => a.location).join('; ')})` : ''}; `
      + `satellite flood detection is disabled; `
      + `${lastFlood ? `most recent GDACS flood in India: "${lastFlood.title}", ended ${formatTime(lastFlood.ended)}` : 'no recent GDACS flood events'}`,
    data_sources: sourceLine || 'unknown',
    nearest_hospital: resourceLine(nearestHospital, hospitalResponse),
    nearest_shelter: resourceLine(nearestShelter, shelterResponse),
    demo_mode: demoMode ? 'ON — sample flood zones on the map are NOT real' : 'off',
  };
}
