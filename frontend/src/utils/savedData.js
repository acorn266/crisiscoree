// Backend marks hospital/shelter results served from saved OpenStreetMap snapshots
// with data_source: 'snapshot'. Returns a short UI note, or null for live data.
export function savedDataNote(response) {
  if (response?.data_source !== 'snapshot') return null;
  const date = response.snapshot_date
    ? new Date(response.snapshot_date).toLocaleDateString(undefined, {
      day: 'numeric', month: 'short', year: 'numeric',
    })
    : null;
  const area = response.snapshot_area ? ` for ${response.snapshot_area}` : '';
  return `Saved data${area}${date ? ` (${date})` : ''} — live map data unavailable`;
}
