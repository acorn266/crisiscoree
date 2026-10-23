import { KINDS } from '../utils/alerts';
import { levelTone } from '../utils/risk';

const STATUS_LABEL = {
  ok: 'Live', unavailable: 'Unavailable', disabled: 'Off', loading: 'Loading', saved: 'Saved', demo: 'Demo',
};

function StatTile({ icon, label, tag, tagClass, children, tone }) {
  return (
    <article className={`card stat-card ${tone ? `tone-${tone}` : ''}`}>
      <div className="stat-head">
        <span className="stat-label"><span aria-hidden="true">{icon}</span> {label}</span>
        {tag && <span className={`data-tag ${tagClass}`}>{tag}</span>}
      </div>
      {children}
    </article>
  );
}

function RiskCards({ weather, risk, alerts, loading, sources, resourceSaved, demoMode }) {
  const weatherOk = weather?.status === 'ok';
  const overall = risk?.overall;
  const tone = overall?.score != null ? levelTone(overall.level) : 'unavailable';
  const official = alerts.filter((a) => KINDS[a.kind]?.group === 'official').length;
  const observed = alerts.filter((a) => a.kind === 'observed_event').length;
  const indicators = alerts.filter((a) => a.kind === 'risk_indicator').length;

  const sourceRows = [
    ...Object.entries(sources).map(([key, s]) => ({ key, name: s.name, status: s.status })),
    { key: 'osm', name: 'Hospitals & shelters (OSM)', status: resourceSaved ? 'saved' : 'ok' },
    ...(demoMode ? [{ key: 'demo', name: 'Demo flood zones', status: 'demo' }] : []),
  ];

  return (
    <section className="summary-grid" aria-label="Summary">
      <StatTile icon="🌦" label="Weather" tag={weatherOk ? 'Live' : 'Unavailable'} tagClass={weatherOk ? 'tag-live' : 'tag-unavailable'}>
        {loading && !weather ? <div className="skeleton skeleton-value" /> : (
          <>
            <div className="stat-value">{weatherOk ? `${Math.round(weather.temperature)}°C` : '—'}</div>
            <div className="stat-sub">
              {weatherOk
                ? `${weather.description || weather.condition} · ${weather.location}`
                : (weather?.message || 'OpenWeather data unavailable')}
            </div>
            {weatherOk && (
              <div className="stat-foot">
                💧 {weather.humidity}% · 💨 {weather.wind_speed_ms} m/s · 🌧 {weather.rainfall_1h_mm ?? 0} mm/h
              </div>
            )}
          </>
        )}
      </StatTile>

      <StatTile icon="🛡" label="Overall risk" tag="AI estimate" tagClass="tag-ai" tone={tone}>
        {loading && !risk ? <div className="skeleton skeleton-value" /> : (
          <>
            <div className={`stat-value tone-text-${tone}`}>{overall?.score != null ? overall.level : 'Unavailable'}</div>
            {overall?.score != null && (
              <div className="meter meter-sm"><div className="meter-fill" style={{ width: `${Math.min(overall.score, 100)}%` }} /></div>
            )}
            <div className="stat-sub">
              {overall?.score != null ? `${overall.score}/100 · highest local hazard estimate` : 'Risk engine did not return a score'}
            </div>
          </>
        )}
      </StatTile>

      <StatTile icon="🚨" label="Active alerts" tag={official ? 'Official' : undefined} tagClass="tag-official">
        {loading && alerts.length === 0 ? <div className="skeleton skeleton-value" /> : (
          <>
            <div className="stat-value">{alerts.length}</div>
            <div className="stat-breakdown">
              <span><b>{official}</b> official</span>
              <span><b>{observed}</b> observed</span>
              <span><b>{indicators}</b> indicators</span>
            </div>
          </>
        )}
      </StatTile>

      <StatTile icon="🛰" label="Data sources">
        <ul className="source-list">
          {sourceRows.map((s) => (
            <li key={s.key}>
              <span className={`status-dot st-${s.status}`} aria-hidden="true" />
              <span className="source-name">{s.name}</span>
              <span className={`source-status st-${s.status}`}>{STATUS_LABEL[s.status] ?? s.status}</span>
            </li>
          ))}
        </ul>
      </StatTile>
    </section>
  );
}

export default RiskCards;
