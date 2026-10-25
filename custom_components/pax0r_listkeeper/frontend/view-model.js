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

/** Build product groups before filtering so hidden aliases retain membership. */
export function catalogGroups(names, { query = '', onlySingle = false, sort = 'occurrences', direction = 'asc' } = {}) {
  const groups = new Map();
  for (const name of names) {
    if (!groups.has(name.product_id)) groups.set(name.product_id, {
      id: name.product_id, label: name.canonical_name, names: [], occurrences: 0, purchases: 0, last_seen: '',
    });
    const group = groups.get(name.product_id);
    group.names.push(name);
    group.occurrences += name.occurrences;
    group.purchases += name.purchases;
    if (name.last_seen > group.last_seen) group.last_seen = name.last_seen;
  }
  const search = query.toLocaleLowerCase().trim();
  const rows = [...groups.values()];
  for (const group of rows) {
    group.names.sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
    group.main = group.names.find(n => n.name === group.label) || group.names[0];
    group.names = [group.main, ...group.names.filter(n => n.id !== group.main.id)];
    group.aliasMatch = Boolean(search) && !group.label.toLocaleLowerCase().includes(search)
      && group.names.some(n => n.name.toLocaleLowerCase().includes(search));
  }
  return rows.filter(group => (!onlySingle || group.names.length === 1)
    && (!search || group.label.toLocaleLowerCase().includes(search)
      || group.names.some(n => n.name.toLocaleLowerCase().includes(search))))
    .sort((a, b) => {
      const comparison = sort === 'alpha' ? a.label.localeCompare(b.label)
        : sort === 'seen' ? a.last_seen.localeCompare(b.last_seen)
        : sort === 'purchases' ? a.purchases - b.purchases
        : a.occurrences - b.occurrences || b.last_seen.localeCompare(a.last_seen);
      return comparison * (direction === 'desc' ? -1 : 1) || a.id.localeCompare(b.id);
    });
}
