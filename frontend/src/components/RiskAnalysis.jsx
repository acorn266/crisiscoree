import { levelTone } from '../utils/risk';

const HAZARDS = [
  { key: 'flood', label: 'Flood', icon: '🌊' },
  { key: 'earthquake', label: 'Earthquake', icon: '🌍' },
  { key: 'heatwave', label: 'Heatwave', icon: '🔥' },
  { key: 'drought', label: 'Drought', icon: '🌵' },
  { key: 'cyclone', label: 'Cyclone', icon: '🌀' },
];

function HazardTile({ hazard, result }) {
  const available = result && result.available !== false && result.score != null;
  const tone = available ? levelTone(result.level) : 'unavailable';
  return (
    <div className={`hazard-tile tone-${tone}`}>
      <div className="hazard-head">
        <span className="hazard-name">{hazard.icon} {hazard.label}</span>
        <span className={`level-badge tone-${tone}`}>{available ? result.level : 'Unavailable'}</span>
      </div>
      {available ? (
        <>
          <div className="meter" role="meter" aria-valuenow={result.score} aria-valuemin={0} aria-valuemax={100} aria-label={`${hazard.label} estimate`}>
            <div className="meter-fill" style={{ width: `${Math.min(result.score, 100)}%` }} />
          </div>
          <div className="hazard-score">
            <span><b>{result.score}</b>/100</span>
            <span className="data-tag tag-ai">AI estimate</span>
          </div>
          <p className="hazard-basis">{result.basis ?? 'Anomaly score from available data.'}</p>
          {result.guard && <p className="hazard-guard">Capped: {result.guard}</p>}
          <p className="hazard-input">Inputs: {result.input_source ?? 'unknown'}</p>
        </>
      ) : (
        <p className="hazard-basis">{result?.reason ?? 'No data available for this hazard.'}</p>
      )}
    </div>
  );
}

function RiskAnalysis({ risk, loading }) {
  const overall = risk?.overall;
  const risks = risk?.risks ?? {};
  const overallTone = overall?.score != null ? levelTone(overall.level) : 'unavailable';

  return (
    <section className="card risk-panel" aria-label="Risk analysis">
      <header className="card-header">
        <div>
          <h2>Local risk estimates</h2>
          <p className="card-sub">
            AI anomaly scores (Isolation Forest) from live data at your location — indicative only, not official forecasts.
          </p>
        </div>
        {overall?.score != null && (
          <div className={`overall-chip tone-${overallTone}`}>
            <span>Overall</span>
            <b>{overall.level}</b>
            <span>{overall.score}/100</span>
          </div>
        )}
      </header>

      {loading && !risk ? (
        <div className="hazard-grid">
          {HAZARDS.map((h) => <div key={h.key} className="skeleton skeleton-tile" />)}
        </div>
      ) : !risk ? (
        <div className="empty-state compact">
          <p className="empty-title">Risk estimates unavailable.</p>
          <p className="empty-text">The backend could not compute them. Official warnings in the Alerts panel are unaffected.</p>
        </div>
      ) : (
        <div className="hazard-grid">
          {HAZARDS.map((h) => <HazardTile key={h.key} hazard={h} result={risks[h.key]} />)}
        </div>
      )}
      {overall?.basis && <p className="panel-foot">Overall = {overall.basis.charAt(0).toLowerCase() + overall.basis.slice(1)}.</p>}
    </section>
  );
}

export default RiskAnalysis;
