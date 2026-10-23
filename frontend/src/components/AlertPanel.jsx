import { useMemo, useState } from 'react';
import { isValidLatLng } from '../utils/geo';
import {
  CATEGORIES, CATEGORY_SOURCES, KINDS, SEVERITY_RANK, categoryOf, formatTime, sortAlerts, timeAgo,
} from '../utils/alerts';

const FILTER_CATEGORIES = ['earthquake', 'flood', 'cyclone', 'heatwave', 'drought', 'severe_weather'];
const KIND_FILTERS = [
  { key: 'all', label: 'All sources' },
  { key: 'official', label: 'Official' },
  { key: 'observed', label: 'Observed' },
  { key: 'indicator', label: 'Indicators' },
];
const SOURCE_NAMES = {
  usgs: 'USGS', gdacs: 'GDACS', sachet: 'NDMA SACHET', openweather: 'OpenWeather', satellite_floods: 'Satellite detection',
};

function EmptyState({ category, sources, recentEvents }) {
  const relevant = category === 'all'
    ? Object.keys(SOURCE_NAMES)
    : CATEGORY_SOURCES[category] ?? [];
  const down = relevant.filter((k) => sources[k] && sources[k].status !== 'ok');
  const label = category === 'all' ? '' : `${CATEGORIES[category].label.toLowerCase()} `;
  const recent = category === 'all' ? null : recentEvents.find((e) => e.category === category);
  return (
    <div className="empty-state">
      <div className="empty-icon">{category === 'all' ? '✅' : CATEGORIES[category].icon}</div>
      <p className="empty-title">No active {label}alerts reported.</p>
      <p className="empty-text">
        Checked: {relevant.filter((k) => sources[k]).map((k) => SOURCE_NAMES[k]).join(', ') || 'no sources'}.
      </p>
      {recent && (
        <p className="empty-text">Most recent: {recent.title} (ended {formatTime(recent.ended)}, {recent.source}).</p>
      )}
      {down.length > 0 && (
        <p className="empty-warn">
          ⚠ {down.map((k) => `${SOURCE_NAMES[k]} (${sources[k].status})`).join(', ')} — missing data is not proof
          that there is no danger. Follow IMD and local authority advisories.
        </p>
      )}
    </div>
  );
}

function AlertCard({ alert, onFocus }) {
  const cat = CATEGORIES[categoryOf(alert)] ?? CATEGORIES.severe_weather;
  const kind = KINDS[alert.kind] ?? KINDS.risk_indicator;
  const hasLocation = isValidLatLng(alert.lat, alert.lon);
  const handle = () => hasLocation && onFocus?.(alert);
  return (
    <article
      className={`alert-card sev-${alert.severity} ${hasLocation ? 'is-clickable' : ''}`}
      style={{ '--cat': cat.color }}
      onClick={handle}
      onKeyDown={(e) => { if (e.key === 'Enter') handle(); }}
      role={hasLocation ? 'button' : undefined}
      tabIndex={hasLocation ? 0 : undefined}
      title={hasLocation ? 'Show on map' : undefined}
    >
      <div className="alert-card-head">
        <span className="alert-cat">{cat.icon} {cat.label}</span>
        <span className={`sev-badge sev-${alert.severity}`}>{alert.severity}</span>
        <span className={`kind-badge kind-${kind.group}`}>{kind.label}</span>
      </div>
      <h3 className="alert-title">{alert.title}</h3>
      {alert.location && alert.location !== alert.title && <div className="alert-loc">📍 {alert.location}</div>}
      {alert.detail && <p className="alert-detail">{alert.detail}</p>}
      <div className="alert-meta">
        <span>{alert.source}</span>
        {alert.timestamp && <span title={formatTime(alert.timestamp)}>· {timeAgo(alert.timestamp)}</span>}
        {alert.expires && <span>· valid until {formatTime(alert.expires)}</span>}
      </div>
      {(hasLocation || alert.source_url) && (
        <div className="alert-actions">
          {hasLocation && (
            <span className="alert-focus">
              {alert.coord_precision === 'approximate' ? 'Show approximate area →' : 'Show on map →'}
            </span>
          )}
          {alert.source_url && (
            <a href={alert.source_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
              Source record ↗
            </a>
          )}
        </div>
      )}
    </article>
  );
}

function AlertPanel({
  alerts, loading, unavailable = false, officialLoading = false,
  sources = {}, recentEvents = [], onAlertFocus,
}) {
  const [category, setCategory] = useState('all');
  const [severity, setSeverity] = useState('all');
  const [kind, setKind] = useState('all');

  const counts = useMemo(() => {
    const c = { all: alerts.length };
    for (const a of alerts) c[categoryOf(a)] = (c[categoryOf(a)] || 0) + 1;
    return c;
  }, [alerts]);

  const visible = useMemo(() => sortAlerts(alerts.filter((a) => (
    (category === 'all' || categoryOf(a) === category)
    && (severity === 'all' || (SEVERITY_RANK[a.severity] ?? 9) <= SEVERITY_RANK[severity])
    && (kind === 'all' || KINDS[a.kind]?.group === kind)
  ))), [alerts, category, severity, kind]);

  return (
    <section className="card alerts-panel" aria-label="Alerts">
      <header className="card-header">
        <div>
          <h2>Alerts</h2>
          <p className="card-sub">Official warnings, observed events and automated indicators</p>
        </div>
        <span className="count-pill">{loading ? '…' : `${alerts.length} active`}</span>
      </header>

      <div className="filter-chips" role="tablist" aria-label="Filter by disaster type">
        <button type="button" className={`chip ${category === 'all' ? 'is-active' : ''}`} onClick={() => setCategory('all')}>
          All <b>{counts.all ?? 0}</b>
        </button>
        {FILTER_CATEGORIES.map((c) => (
          <button
            key={c}
            type="button"
            className={`chip ${category === c ? 'is-active' : ''}`}
            style={{ '--cat': CATEGORIES[c].color }}
            onClick={() => setCategory(c)}
          >
            {CATEGORIES[c].icon} {CATEGORIES[c].label} <b>{counts[c] ?? 0}</b>
          </button>
        ))}
      </div>

      <div className="filter-row">
        <div className="segmented" role="group" aria-label="Filter by source type">
          {KIND_FILTERS.map((k) => (
            <button key={k.key} type="button" className={kind === k.key ? 'is-active' : ''} onClick={() => setKind(k.key)}>
              {k.label}
            </button>
          ))}
        </div>
        <label className="select-wrap">
          <span className="sr-only">Minimum severity</span>
          <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="all">All severities</option>
            <option value="critical">Critical only</option>
            <option value="high">High and above</option>
            <option value="medium">Medium and above</option>
            <option value="low">Low and above</option>
          </select>
        </label>
      </div>

      {officialLoading && (
        <div className="inline-note"><span className="spinner" aria-hidden="true" /> Loading official warnings (NDMA SACHET, GDACS)…</div>
      )}

      <div className="alert-list">
        {loading ? (
          <>
            <div className="skeleton skeleton-card" />
            <div className="skeleton skeleton-card" />
            <div className="skeleton skeleton-card" />
          </>
        ) : unavailable && alerts.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">⚠️</div>
            <p className="empty-title">Alert data could not be loaded.</p>
            <p className="empty-warn">This is not confirmation that there is no danger. Use Refresh to try again.</p>
          </div>
        ) : visible.length === 0 ? (
          <EmptyState category={category} sources={sources} recentEvents={recentEvents} />
        ) : (
          visible.map((a) => <AlertCard key={a.id} alert={a} onFocus={onAlertFocus} />)
        )}
      </div>
    </section>
  );
}

export default AlertPanel;
