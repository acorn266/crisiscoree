function RiskCards({ weather, risk, alertsCount, loading }) {
  const weatherDisplay = weather?.status === 'ok'
    ? `${Math.round(weather.temperature)}°C`
    : 'Data unavailable';

  const weatherDetails = weather?.status === 'ok'
    ? `Humidity ${weather.humidity}% · Rain ${weather.rainfall_1h_mm ?? 0} mm`
    : weather?.message || 'OpenWeather data unavailable';

  const overallSeverity = risk?.overall?.level ?? 'UNAVAILABLE';
  const overallDisplay = overallSeverity === 'MODEL_NOT_AVAILABLE'
  ? 'Model unavailable'
  : overallSeverity;

  const alertsDisplay = loading ? '...' : (alertsCount ?? 0);

  return (
    <section className="summary-grid">
      <div className="card weather-card">
        <div className="card-title">🌦 WEATHER</div>
        <div className="big-value">{loading ? '...' : weatherDisplay}</div>
        <div className="details">{weatherDetails}</div>
        {weather?.source && <div className="source-tag">Source: {weather.source}</div>}
      </div>

      <div className="card risk-card">
        <div className="card-title">⚠ OVERALL RISK</div>
        <div className={`big-value ${overallSeverity === 'ELEVATED' ? 'danger' : ''}`}>
          {loading ? '...' : overallDisplay}
        </div>
        <div className="details">
          {risk?.overall?.status === 'model_not_available'
            ? 'ML model not trained — no score available'
            : 'Based on detected disaster data'}
        </div>
      </div>

      <div className="card alert-card">
        <div className="card-title">🚨 ALERTS</div>
        <div className="big-value">{alertsDisplay}</div>
        <div className="details">
          {alertsCount === 0 ? 'No active alerts from real data' : 'From detected events'}
        </div>
      </div>
    </section>
  );
}

export default RiskCards;
