import test from 'node:test';
import assert from 'node:assert/strict';
import { escapeHtml, frequency, sortProducts } from '../../custom_components/pax0r_listkeeper/frontend/view-model.js';
import { dictionaries, translator } from '../../custom_components/pax0r_listkeeper/frontend/translations.js';
import { ShoppingApi } from '../../custom_components/pax0r_listkeeper/frontend/api.js';

test('escapes untrusted product names in markup and attributes', () => {
  assert.equal(escapeHtml('<img onerror="x">&'), '&lt;img onerror=&quot;x&quot;&gt;&amp;');
});
test('frequency handles sparse data and month intervals', () => {
  const t = translator('pl');
  assert.equal(frequency({ history_days: 0 }, t), t('none'));
  assert.equal(frequency({ history_days: 1, average_days: null }, t), t('insufficient'));
  assert.equal(frequency({ history_days: 3, average_days: 30 }, t), t('monthly'));
});
test('frequency sorting keeps missing measurements last', () => {
  const rows = [{label:'a',average_days:null}, {label:'b',average_days:3}, {label:'c',average_days:30}];
  assert.deepEqual(sortProducts(rows, 'long').map(r => r.label), ['c', 'b', 'a']);
  assert.deepEqual(sortProducts(rows, 'short').map(r => r.label), ['b', 'c', 'a']);
});
test('transport sends versioned request through authenticated hass connection', async () => {
  let sent;
  const api = new ShoppingApi({ callWS: async msg => { sent = msg; return { api_version:1, data:[] }; } });
  assert.deepEqual(await api.call('get_dashboard', { days:30 }), []);
  assert.equal(sent.type, 'pax0r_listkeeper/get_dashboard');
  assert.equal(sent.api_version, 1);
  assert.equal(sent.days, 30);
});

test('English is the fallback and explicit Polish localization remains available', () => {
  assert.equal(translator()('catalog'), dictionaries.en.catalog);
  assert.equal(translator('de-DE')('catalog'), dictionaries.en.catalog);
  assert.equal(translator('en-US')('catalog'), dictionaries.en.catalog);
  assert.equal(translator('pl-PL')('catalog'), dictionaries.pl.catalog);
  assert.deepEqual(Object.keys(dictionaries.pl).sort(), Object.keys(dictionaries.en).sort());
});
