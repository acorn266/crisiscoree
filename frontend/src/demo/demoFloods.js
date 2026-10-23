// DEMO MODE ONLY — illustrative sample flood zones for presentations.
// These are NOT real events. They are only shown when the user switches on
// "Demo flood data" in the map toolbar (off by default) and are always labelled.

export const DEMO_FLOODS = [
  {
    id: 'demo-flood-a',
    title: 'DEMO flood zone A (sample)',
    region: 'Brahmaputra plains, Assam — illustrative position',
    lat: 26.45,
    lon: 91.6,
    radius_km: 35,
    severity: 'high',
    detail: 'Sample river-flood zone used to demonstrate how flood alerts look on the map.',
  },
  {
    id: 'demo-flood-b',
    title: 'DEMO flood zone B (sample)',
    region: 'Kosi basin, Bihar — illustrative position',
    lat: 25.95,
    lon: 86.75,
    radius_km: 28,
    severity: 'medium',
    detail: 'Sample flood extent for demonstration purposes only.',
  },
  {
    id: 'demo-flood-c',
    title: 'DEMO flood zone C (sample)',
    region: 'Coastal Kerala — illustrative position',
    lat: 9.6,
    lon: 76.4,
    radius_km: 22,
    severity: 'medium',
    detail: 'Sample urban-flooding zone for demonstration purposes only.',
  },
];
