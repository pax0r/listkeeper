/** Pure presentation helpers, also exercised by Node tests. */
export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]);
}
export function frequency(row, t) {
  if (!row.history_days) return t('none');
  if (row.average_days == null) return t('insufficient');
  if (row.average_days >= 28 && row.average_days <= 31) return t('monthly');
  return t('interval').replace('{days}', Number(row.average_days.toFixed(1)));
}
export function sortProducts(rows, sort) {
  return [...rows].sort((a, b) => {
    if (sort === 'alpha') return a.label.localeCompare(b.label);
    if (sort === 'recent') return (b.last_purchase || '').localeCompare(a.last_purchase || '');
    if (sort === 'short' || sort === 'long') {
      if (a.average_days == null) return b.average_days == null ? 0 : 1;
      if (b.average_days == null) return -1;
      return (a.average_days - b.average_days) * (sort === 'long' ? -1 : 1);
    }
    return (a.purchases - b.purchases) * (sort === 'rare' ? 1 : -1);
  });
}
