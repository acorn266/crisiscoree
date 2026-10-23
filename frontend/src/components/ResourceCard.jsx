function ResourceCard({ resource, onFocusMap }) {
  const handleClick = () => {
    if (onFocusMap && resource.lat != null && resource.lon != null) {
      onFocusMap([resource.lat, resource.lon], 13);
    }
  };

  return (
    <article 
      className="card resource-card"
      onClick={handleClick}
      style={{ cursor: onFocusMap && resource.lat != null ? 'pointer' : 'default' }}
    >
      <div className="resource-icon" aria-hidden="true">{resource.icon}</div>

      <div className="resource-copy">
        <h3>{resource.title}</h3>
        <p>{resource.summary}</p>
        <span className="resource-distance">{resource.distance}</span>
        {resource.lat != null && (
          <small style={{ display: 'block', marginTop: '4px', opacity: 0.7, cursor: 'pointer' }}>
            Click to focus on map →
          </small>
        )}
      </div>
    </article>
  );
}

export default ResourceCard;
