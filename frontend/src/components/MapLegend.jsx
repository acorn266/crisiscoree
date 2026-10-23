const SYMBOLS = [
  { key: 'flood', label: 'Flood', marker: 'flood', glyph: '🌊' },
  { key: 'warning', label: 'Official warning', marker: 'warning', glyph: '⚠' },
  { key: 'cyclone', label: 'Cyclone', marker: 'cyclone', glyph: '🌀' },
  { key: 'heat', label: 'Heat', marker: 'heat', glyph: '🔥' },
  { key: 'drought', label: 'Drought', marker: 'drought', glyph: '🌵' },
  { key: 'hospital', label: 'Hospital', marker: 'hospital', glyph: '✚' },
  { key: 'shelter', label: 'Shelter', marker: 'shelter', glyph: '⌂' },
];

const QUAKES = [
  { key: 'eq-high', label: 'M5+', color: '#ff5252' },
  { key: 'eq-mid', label: 'M3–4.9', color: '#ffb340' },
  { key: 'eq-low', label: '<M3', color: '#35d07f' },
];

function MapLegend() {
  return (
    <div className="map-legend" aria-label="Map legend">
      <div className="legend-row">
        {SYMBOLS.map((s) => (
          <span key={s.key} className="legend-item">
            <span className={`cc-marker cc-marker--${s.marker} legend-marker`}><span>{s.glyph}</span></span>
            {s.label}
          </span>
        ))}
        <span className="legend-item">
          <span className="legend-quakes">
            {QUAKES.map((q) => <i key={q.key} style={{ background: q.color }} title={q.label} />)}
          </span>
          Earthquake (M5+ / 3–4.9 / &lt;3)
        </span>
      </div>
      <div className="legend-row legend-row--notes">
        <span className="legend-item"><i className="legend-dashed" /> Dashed area = approximate location</span>
        <span className="legend-item"><span className="cc-marker cc-marker--ended legend-marker"><span>🌊</span></span> Grey = ended event</span>
        <span className="legend-item"><span className="cc-marker cc-marker--demo legend-marker"><span>D</span></span> DEMO = sample data</span>
      </div>
    </div>
  );
}

export default MapLegend;
