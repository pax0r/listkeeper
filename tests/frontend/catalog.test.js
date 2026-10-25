import test from 'node:test';
import assert from 'node:assert/strict';
import { translator } from '../../custom_components/pax0r_listkeeper/frontend/translations.js';

let Panel;
globalThis.HTMLElement = class { attachShadow() { this.shadowRoot = {}; } };
globalThis.customElements = { define(_name, component) { Panel = component; } };
await import('../../custom_components/pax0r_listkeeper/frontend/panel.js');

function fixture() {
  const panel = new Panel();
  panel.t = translator('en');
  panel.state.data = [
    { id: 'a', name: 'Soap', product_id: 'p', canonical_name: 'Soap', occurrences: 1, purchases: 0, last_seen: '2026-01-01' },
    { id: 'b', name: 'Hand soap', product_id: 'q', canonical_name: 'Hand soap', occurrences: 2, purchases: 1, last_seen: '2026-01-02' },
  ];
  const controls = new Map();
  const moving = [{ dataset: { move: 'b' } }];
  const selections = [{ dataset: { selectProduct: 'p' }, checked: true }];
  const sorting = [{ dataset: { catalogSort: 'alpha' } }];
  const expanding = [{ dataset: { expandProduct: 'p' } }];
  const renaming = [{ dataset: { renameProduct: 'p' } }];
  panel.shadowRoot.getElementById = id => {
    if (!controls.has(id)) controls.set(id, { addEventListener(event, handler) { this[event] = handler; } });
    return controls.get(id);
  };
  panel.shadowRoot.querySelector = selector => selector === 'ha-menu-button' ? {} : null;
  panel.shadowRoot.querySelectorAll = selector => selector === '[data-move]' ? moving
    : selector === '[data-select-product]' ? selections : selector === '[data-catalog-sort]' ? sorting
    : selector === '[data-expand-product]' ? expanding : selector === '[data-rename-product]' ? renaming : [];
  panel.render = () => {};
  panel.bind();
  return { panel, controls, moving, selections, sorting, expanding, renaming };
}

test('merge requires an explicit main name and submits selected names across search filters', () => {
  const { panel, controls } = fixture();
  panel.state.selected = new Set(['a', 'b']);
  panel.state.query = 'Soap';
  controls.get('merge').click();
  let request;
  panel.mutate = (...args) => { request = args; };
  controls.get('confirm-dialog').click();
  assert.equal(request, undefined);
  controls.get('dialog-target').change({ target: { value: 'b' } });
  controls.get('confirm-dialog').click();
  assert.deepEqual(request, ['merge_names', { name_ids: ['a', 'b'], target_name_id: 'b', whole_products: true }]);
});

test('move binds the row identity to its own destination dialog and can be cancelled', () => {
  const { panel, controls, moving } = fixture();
  moving[0].onclick();
  assert.equal(panel.state.dialog.nameId, 'b');
  let request;
  panel.mutate = (...args) => { request = args; };
  controls.get('dialog-target').change({ target: { value: 'p' } });
  controls.get('confirm-dialog').click();
  assert.deepEqual(request, ['move_name', { name_id: 'b', product_id: 'p' }]);
  controls.get('cancel-dialog').click();
  assert.equal(panel.state.dialog, null);
});

test('selection survives searching and is cleared only on explicit action', () => {
  const { panel, controls, selections } = fixture();
  selections[0].onchange();
  panel.state.query = 'Hand';
  panel.catalog(panel.state.data);
  assert.deepEqual([...panel.state.selected], ['a']);
  controls.get('clear-selection').click();
  assert.equal(panel.state.selected.size, 0);
});

test('switching list clears pending selections, dialogs and history filters', () => {
  const { panel, controls } = fixture();
  panel.state.selected.add('a'); panel.state.dialog = { kind: 'merge', target: 'a' };
  panel.state.nameId = 'a'; panel.state.offset = 100; panel.state.query = 'Soap';
  let loaded = false;
  panel.load = () => { loaded = true; };
  controls.get('list-context').change({ target: { value: 'todo.testing' } });
  assert.equal(panel.state.entityId, 'todo.testing');
  assert.equal(panel.state.selected.size, 0);
  assert.equal(panel.state.dialog, null);
  assert.equal(panel.state.data, null);
  assert.equal(panel.state.nameId, '');
  assert.equal(panel.state.offset, 0);
  assert.equal(loaded, true);
});

test('every panel operation carries its selected list context', async () => {
  const { panel } = fixture();
  panel.state.entityId = 'todo.testing';
  let request;
  panel.api = { call: async (...args) => { request = args; } };
  await panel.call('export_data');
  assert.deepEqual(request, ['export_data', { entity_id: 'todo.testing' }]);
});

test('late responses from the previous list cannot replace the current context data', async () => {
  const { panel } = fixture();
  const waiting = new Map();
  panel.state.entityId = 'todo.home';
  panel.api = { call: async (action, fields) => action === 'get_lists'
    ? [{ entity_id: 'todo.home', name: 'Home' }, { entity_id: 'todo.test', name: 'Test' }]
    : new Promise(resolve => waiting.set(fields.entity_id, resolve)) };
  const first = panel.load();
  await Promise.resolve();
  panel.state.entityId = 'todo.test';
  const second = panel.load();
  await Promise.resolve();
  waiting.get('todo.test')({ marker: 'current' });
  await second;
  waiting.get('todo.home')({ marker: 'stale' });
  await first;
  assert.deepEqual(panel.state.data, { marker: 'current' });
  assert.equal(panel.state.entityId, 'todo.test');
});

test('selecting a collapsed product includes every alias in the merge request', () => {
  const { panel, selections, controls } = fixture();
  panel.state.data.push({ id: 'alias', name: 'Bar soap', product_id: 'p', canonical_name: 'Soap', occurrences: 3, purchases: 2, last_seen: '2026-01-03' });
  panel.state.query = 'Bar';
  selections[0].onchange();
  assert.deepEqual([...panel.state.selected], ['a', 'alias']);
  panel.state.selected.add('b');
  controls.get('merge').click();
  let request;
  panel.mutate = (...args) => { request = args; };
  controls.get('dialog-target').change({ target: { value: 'b' } });
  controls.get('confirm-dialog').click();
  assert.deepEqual(new Set(request[1].name_ids), new Set(['a', 'alias', 'b']));
  assert.equal(request[1].whole_products, true);
  selections[0].checked = false;
  selections[0].onchange();
  assert.deepEqual([...panel.state.selected], ['b']);
});

test('column buttons reverse direction and expansion/filtering preserve selection', () => {
  const { panel, sorting, expanding, controls } = fixture();
  sorting[0].onclick();
  assert.equal(panel.state.catalogSort, 'alpha');
  assert.equal(panel.state.catalogDirection, 'asc');
  sorting[0].onclick();
  assert.equal(panel.state.catalogDirection, 'desc');
  sorting[0].dataset.catalogSort = 'purchases';
  sorting[0].onclick();
  assert.equal(panel.state.catalogDirection, 'desc');
  panel.state.selected.add('a');
  expanding[0].onclick();
  assert.equal(panel.state.expandedProducts.has('p'), true);
  expanding[0].onclick();
  assert.equal(panel.state.expandedProducts.has('p'), false);
  controls.get('single-products').click();
  assert.equal(panel.state.onlySingle, true);
  assert.deepEqual([...panel.state.selected], ['a']);
});

test('collapsed groups render one product selector and hide individual name actions', () => {
  const { panel } = fixture();
  panel.state.data.push({ id: 'alias', name: 'Bar soap', product_id: 'p', canonical_name: 'Soap', occurrences: 3, purchases: 2, last_seen: '2026-01-03' });
  let markup = panel.catalog(panel.state.data);
  assert.equal((markup.match(/data-select-product="p"/g) || []).length, 1);
  assert.equal(markup.includes('data-move="alias"'), false);
  assert.match(markup, /aria-sort="ascending"/);
  panel.state.query = 'Bar';
  markup = panel.catalog(panel.state.data);
  assert.match(markup, /data-move="alias"/);
  assert.equal(markup.includes('data-select-product="q"'), false);
  panel.state.collapsedProducts.add('p');
  assert.equal(panel.catalog(panel.state.data).includes('data-move="alias"'), false);
});

test('renaming uses product identity and keeps a failed edit available for correction', async () => {
  const { panel, controls, renaming } = fixture();
  renaming[0].onclick();
  assert.equal(panel.state.dialog.label, 'Soap');
  assert.equal(panel.state.dialog.productId, 'p');
  controls.get('rename-label').input({ target: { value: 'Liquid soap' } });
  const requests = [];
  panel.api = { call: async (...args) => { requests.push(args); throw { code: 'name_conflict' }; } };
  await panel.mutate('rename_product', { product_id: 'p', label: panel.state.dialog.label });
  assert.equal(panel.state.dialog.label, 'Liquid soap');
  assert.equal(panel.state.error, panel.t('nameConflict'));
  assert.equal(requests[0][0], 'rename_product');
  controls.get('cancel-dialog').click();
  assert.equal(panel.state.dialog, null);
});

test('rename confirmation rejects a blank value and submits the edited label', () => {
  const { panel, controls, renaming } = fixture();
  renaming[0].onclick();
  let request;
  panel.mutate = (...args) => { request = args; };
  controls.get('rename-label').input({ target: { value: '   ' } });
  controls.get('confirm-dialog').click();
  assert.equal(request, undefined);
  controls.get('rename-label').input({ target: { value: 'Liquid soap' } });
  controls.get('confirm-dialog').click();
  assert.deepEqual(request, ['rename_product', { product_id: 'p', label: 'Liquid soap' }]);
});
