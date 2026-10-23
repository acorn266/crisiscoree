import { isValidLatLng } from '../utils/geo';

const AMENITY_LABEL = {
  hospital: 'Hospital',
  community_centre: 'Community centre',
  social_facility: 'Social facility',
};

function ResourceCard({ title, icon, item, response, loading, onFocusMap }) {
  const canFocus = Boolean(onFocusMap) && isValidLatLng(item?.lat, item?.lon);
  const saved = response?.data_source === 'snapshot';
  const savedDate = saved && response.snapshot_date
    ? new Date(response.snapshot_date).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
    : null;

  return (
    <article className="card resource-card">
      <div className="resource-icon" aria-hidden="true">{icon}</div>
      <div className="resource-body">
        <div className="resource-head">
          <h3>{title}</h3>
          {item && (
            <span className={`data-tag ${saved ? 'tag-saved' : 'tag-live'}`}>
              {saved ? `Saved · ${response.snapshot_area}` : 'Live'}
            </span>
          )}
        </div>
        {loading && !item ? (
          <div className="skeleton skeleton-line" />
        ) : item ? (
          <>
            <p className="resource-name">{item.name}</p>
            <p className="resource-meta">
              {AMENITY_LABEL[item.amenity] ?? item.amenity} · <b>{item.distance_km} km</b> away
            </p>
            {saved && (
              <p className="resource-note">
                Live OpenStreetMap lookup unavailable — saved snapshot from {savedDate}. Nearest within the saved {response.snapshot_area} area.
              </p>
            )}
          </>
        ) : (
          <p className="resource-empty">
            No live or saved data for this location. Saved data covers Bengaluru, Chennai, Delhi, Hyderabad,
            Kolkata, Mumbai and Nagpur.
          </p>
        )}
        {canFocus && (
          <button type="button" className="btn btn-small" onClick={() => onFocusMap(item)}>
            Show on map →
          </button>
        )}
      </div>
    </article>
  );
}

export default ResourceCard;
