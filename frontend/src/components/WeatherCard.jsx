function WeatherCard({ weather }) {
  return (
    <article className="card summary-card">
      <div className="card-title">WEATHER</div>
      <div className="big-value">{weather.temperature}°C</div>
      <div className="details-row">
        <span>Humidity {weather.humidity}%</span>
        <span>Rainfall {weather.rainfall} mm</span>
      </div>
      <div className="micro-copy">{weather.condition} · Wind {weather.windSpeed} km/h</div>
    </article>
  );
}

export default WeatherCard;
