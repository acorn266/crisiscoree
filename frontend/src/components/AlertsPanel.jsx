function AlertsPanel({ alerts }) {
  return (
    <div className="card alerts-panel">
      <div className="section-header compact">
        <h2>ALERTS</h2>
        <span className="status-pill">{alerts.length} Active</span>
      </div>

      <div className="alert-list">
        {alerts.map((alert) => (
          <div key={alert.id} className={`alert-row ${alert.severity}`}>
            <span className="alert-dot" />
            <div>
              <strong>{alert.title}</strong>
              <p>{alert.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default AlertsPanel;
