import { isValidLatLng } from '../utils/geo';

function ResourceCard({ resource, onFocusMap }) {
  const canFocus = Boolean(onFocusMap) && isValidLatLng(resource.lat, resource.lon);
  const handleClick = () => {
    if (canFocus) {
      onFocusMap([resource.lat, resource.lon], 15);
    }
  };

  return (
    <article
      className="card resource-card"
      onClick={handleClick}
      style={{ cursor: canFocus ? 'pointer' : 'default' }}
    >
      <div className="resource-icon" aria-hidden="true">{resource.icon}</div>

      <div className="resource-copy">
        <h3>{resource.title}</h3>
        <p>{resource.summary}</p>
        <span className="resource-distance">{resource.distance}</span>
        {resource.note && <small className="saved-data-note">ⓘ {resource.note}</small>}
        {canFocus && (
          <small style={{ display: 'block', marginTop: '4px', opacity: 0.7, cursor: 'pointer' }}>
            Click to focus on map →
          </small>
        )}
      </div>
    </article>
  );
}

export default ResourceCard;
