import test from 'node:test';
import assert from 'node:assert/strict';
import { catalogGroups } from '../../custom_components/pax0r_listkeeper/frontend/view-model.js';

const names = [
  { id: 'a', product_id: 'p', name: 'Soap', canonical_name: 'Soap', occurrences: 2, purchases: 1, last_seen: '2026-01-01' },
  { id: 'alias', product_id: 'p', name: 'Bar soap', canonical_name: 'Soap', occurrences: 3, purchases: 2, last_seen: '2026-01-03' },
  { id: 'b', product_id: 'q', name: 'Bread', canonical_name: 'Bread', occurrences: 4, purchases: 4, last_seen: '2026-01-02' },
];

test('groups by stable product ID and aggregates name-level activity without changing input', () => {
  const before = structuredClone(names);
  const groups = catalogGroups(names);
  assert.equal(groups.length, 2);
  const soap = groups.find(g => g.id === 'p');
  assert.equal(soap.main.id, 'a');
  assert.deepEqual(soap.names.map(n => n.id), ['a', 'alias']);
  assert.equal(soap.occurrences, 5);
  assert.equal(soap.purchases, 3);
  assert.equal(soap.last_seen, '2026-01-03');
  assert.deepEqual(names, before);
});

test('alias search returns the complete group and requests expansion', () => {
  const groups = catalogGroups(names, { query: 'BAR' });
  assert.deepEqual(groups.map(g => g.id), ['p']);
  assert.equal(groups[0].names.length, 2);
  assert.equal(groups[0].aliasMatch, true);
  assert.equal(catalogGroups(names, { query: 'Soap' })[0].aliasMatch, false);
});

test('single-name filter excludes linked groups even if search matches only one alias', () => {
  assert.deepEqual(catalogGroups(names, { onlySingle: true }).map(g => g.id), ['q']);
  assert.deepEqual(catalogGroups(names, { onlySingle: true, query: 'Bar' }), []);
});

test('each sortable group column supports both directions', () => {
  for (const sort of ['alpha', 'occurrences', 'purchases', 'seen']) {
    const ascending = catalogGroups(names, { sort, direction: 'asc' }).map(g => g.id);
    const descending = catalogGroups(names, { sort, direction: 'desc' }).map(g => g.id);
    assert.deepEqual(descending, ascending.toReversed());
  }
});

test('equal display names never join distinct product identities', () => {
  const groups = catalogGroups(names.map(n => ({ ...n, canonical_name: 'Same label' })));
  assert.equal(groups.length, 2);
  assert.deepEqual(new Set(groups.map(g => g.id)), new Set(['p', 'q']));
});

test('an approved unobserved main name does not invent activity or a last-seen date', () => {
  const groups = catalogGroups([
    { id: 'old', product_id: 'p', name: 'Bred', canonical_name: 'Bread', occurrences: 2, purchases: 1, last_seen: '2026-01-01' },
    { id: 'new', product_id: 'p', name: 'Bread', canonical_name: 'Bread', occurrences: 0, purchases: 0, last_seen: null },
  ]);
  assert.equal(groups[0].main.id, 'new');
  assert.equal(groups[0].last_seen, '2026-01-01');
  assert.equal(groups[0].occurrences, 2);
  assert.equal(groups[0].purchases, 1);
});
