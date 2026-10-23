const LEGEND_ITEMS = [
  { key: 'flood', label: 'Flood', color: '#0066cc', icon: '🌊' },
  { key: 'earthquake', label: 'Earthquake', color: '#ff5252', icon: '🌍' },
  { key: 'drought', label: 'Drought', color: '#c68642', icon: '🌵' },
  { key: 'heatwave', label: 'Heatwave', color: '#ff7043', icon: '🔥' },
  { key: 'cyclone', label: 'Cyclone', color: '#7e57c2', icon: '🌀' },
  { key: 'hospital', label: 'Hospital', color: '#ef5350', icon: '🏥' },
  { key: 'shelter', label: 'Shelter', color: '#66bb6a', icon: '🏠' },
  { key: 'unavailable', label: 'Data Unavailable', color: '#78909c', icon: '⬜' },
];

const EARTHQUAKE_SEVERITY = [
  { key: 'eq-high', label: 'M5.0+', color: '#ff5252' },
  { key: 'eq-mid', label: 'M3.0–4.9', color: '#ffb340' },
  { key: 'eq-low', label: 'Below M3.0', color: '#35d07f' },
];

function MapLegend() {
  return (
    <div className="map-legend-panel">
      <strong className="legend-title">Map Legend</strong>
      <div className="legend-grid">
        {LEGEND_ITEMS.map((item) => (
          <span key={item.key} className="legend-item">
            <i className="legend-dot" style={{ background: item.color }} />
            {item.icon} {item.label}
          </span>
        ))}
      </div>

      <strong className="legend-title legend-subtitle">Earthquake Severity</strong>
      <div className="legend-grid">
        {EARTHQUAKE_SEVERITY.map((item) => (
          <span key={item.key} className="legend-item">
            <i className="legend-dot" style={{ background: item.color }} />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export default MapLegend;
