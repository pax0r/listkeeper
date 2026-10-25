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
  const selections = [{ dataset: { select: 'a' }, checked: true }];
  panel.shadowRoot.getElementById = id => {
    if (!controls.has(id)) controls.set(id, { addEventListener(event, handler) { this[event] = handler; } });
    return controls.get(id);
  };
  panel.shadowRoot.querySelector = selector => selector === 'ha-menu-button' ? {} : null;
  panel.shadowRoot.querySelectorAll = selector => selector === '[data-move]' ? moving : selector === '[data-select]' ? selections : [];
  panel.render = () => {};
  panel.bind();
  return { panel, controls, moving, selections };
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
  assert.deepEqual(request, ['merge_names', { name_ids: ['a', 'b'], target_name_id: 'b' }]);
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
