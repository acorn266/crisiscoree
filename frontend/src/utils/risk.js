export function levelTone(level) {
  const s = (level || '').toUpperCase();
  if (s === 'CRITICAL') return 'critical';
  if (['HIGH', 'EXTREME', 'ELEVATED', 'ELEVATED_STRESS'].includes(s)) return 'high';
  if (['MEDIUM', 'MODERATE', 'MONITOR', 'PARTIAL'].includes(s)) return 'medium';
  if (['LOW', 'NONE'].includes(s)) return 'low';
  return 'unavailable';
}
