import { ShoppingApi } from './api.js';
import { translator } from './translations.js';
import { escapeHtml as e, frequency, sortProducts } from './view-model.js';

class Pax0rListkeeperPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.state = { view: 'dashboard', days: '', sort: 'frequent', query: '', catalogSort: 'occurrences',
      selected: new Set(), offset: 0, nameId: '', data: null, loading: false, error: '', dialog: null, notice: '', entityId: '', lists: [] };
    this.request = 0;
  }
  set hass(value) {
    this._hass = value;
    this.api = new ShoppingApi(value);
    this.t = translator(value.language);
    if (!this.started && this.isConnected) { this.started = true; this.load(); }
  }
  connectedCallback() {
    if (this._hass && !this.started) { this.started = true; this.load(); }
  }
  call(action, fields = {}) {
    return this.api.call(action, { ...fields, entity_id: this.state.entityId });
  }
  async load() {
    const token = ++this.request;
    this.state.loading = true; this.state.error = ''; this.render();
    try {
      const lists = await this.api.call('get_lists');
      if (token !== this.request) return;
      this.state.lists = lists;
      if (!lists.some(l => l.entity_id === this.state.entityId)) {
        this.state.entityId = lists[0]?.entity_id || '';
        this.state.selected.clear(); this.state.dialog = null; this.state.nameId = ''; this.state.offset = 0;
        this.state.data = null;
      }
      if (!this.state.entityId) throw new Error(this.t('noLists'));
      const { view, days, nameId, offset } = this.state;
      const action = { dashboard: 'get_dashboard', catalog: 'get_product_names',
        history: 'get_purchase_history', settings: 'get_diagnostics' }[view];
      const fields = view === 'dashboard' ? { days: days ? Number(days) : null }
        : view === 'history' ? { offset, limit: 100, ...(nameId ? { name_id: nameId } : {}) } : {};
      const data = await this.call(action, fields);
      if (token === this.request) this.state.data = data;
    } catch (err) { if (token === this.request) this.state.error = err.message || this.t('error'); }
    finally { if (token === this.request) { this.state.loading = false; this.render(); } }
  }
  async mutate(action, data) {
    this.state.loading = true; this.state.error = ''; this.render();
    try { await this.call(action, data); this.state.selected.clear(); this.state.dialog = null;
      this.state.notice = this.t('saved'); await this.load(); }
    catch (err) { this.state.error = err.message || this.t('error'); }
    finally { this.state.loading = false; this.render(); }
  }
  options(values, selected) {
    return values.map(([key, label]) => `<option value="${e(key)}" ${key === selected ? 'selected' : ''}>${e(label)}</option>`).join('');
  }
  table(headings, rows) {
    return `<div class="scroll"><table><thead><tr>${headings.map(h => `<th>${e(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('') || `<tr><td colspan="${headings.length}">${e(this.t('empty'))}</td></tr>`}</tbody></table></div>`;
  }
  dashboard(data) {
    const t = this.t;
    const sorts = ['frequent', 'rare', 'short', 'long', 'recent', 'alpha'];
    return `<div class="controls"><label>${t('all')}<select id="period">${this.options([
      ['', t('all')], ['90', t('d90')], ['30', t('d30')]], this.state.days)}</select></label>
      <label>${t('sort')}<select id="sort">${this.options(sorts.map(k => [k, t(k)]), this.state.sort)}</select></label></div>
      <div class="cards">${Object.entries(data.summary).map(([k, v]) => `<ha-card><strong>${e(v)}</strong><span>${e(t(k === 'shopping_days' ? 'days' : k))}</span></ha-card>`).join('')}</div>
      <p>${t('frequencyHint')}</p>${this.table([t('product'), t('count'), t('frequency'), t('first'), t('last')],
        sortProducts(data.products, this.state.sort).map(p => `<tr><td>${e(p.label)}</td><td>${p.purchases}</td><td>${e(frequency(p, t))}</td><td>${e(p.first_purchase || '—')}</td><td>${e(p.last_purchase || '—')}</td></tr>`))}`;
  }
  catalog(data) {
    const t = this.t, s = this.state;
    const rows = data.filter(n => `${n.name} ${n.canonical_name}`.toLocaleLowerCase().includes(s.query.toLocaleLowerCase()));
    rows.sort((a, b) => s.catalogSort === 'alpha' ? a.name.localeCompare(b.name)
      : s.catalogSort === 'purchases' ? b.purchases - a.purchases
      : s.catalogSort === 'seen' ? b.last_seen.localeCompare(a.last_seen)
      : a.occurrences - b.occurrences || b.last_seen.localeCompare(a.last_seen));
    const selected = data.filter(n => s.selected.has(n.id));
    const products = [...new Map(data.map(n => [n.product_id, n.canonical_name])).entries()];
    return `<details><summary>${t('catalogHelp')}</summary><p>${t('catalogInstructions')}</p><p>${t('dedupInstructions')}</p></details>
      <div class="controls"><label>${t('search')}<input id="search" value="${e(s.query)}"></label>
      <label>${t('sort')}<select id="catalog-sort">${this.options([['occurrences', t('occurrenceSort')], ['purchases', t('purchaseSort')], ['seen', t('seenSort')], ['alpha', t('alpha')]], s.catalogSort)}</select></label>
      </div>${selected.length ? `<div class="controls selection" role="region" aria-label="${t('selection')}">
      <span>${t('selection')}: ${selected.length}</span><button id="merge" ${selected.length < 2 ? 'disabled' : ''}>${t('merge')}…</button>
      <button id="clear-selection">${t('clearSelection')}</button></div>` : ''}
      ${this.table(['', t('name'), t('occurrences'), t('count'), t('seen'), t('canonical'), ''], rows.map(n => `<tr>
      <td><input type="checkbox" aria-label="${e(n.name)}" data-select="${e(n.id)}" ${s.selected.has(n.id) ? 'checked' : ''}></td>
      <td>${e(n.name)}</td><td>${n.occurrences}</td><td>${n.purchases}</td><td>${e(n.last_seen.slice(0, 10))}</td><td>${e(n.canonical_name)}</td>
      <td><details><summary>${t('actions')}</summary><button data-history="${e(n.id)}">${t('history')}</button><button data-split="${e(n.id)}">${t('split')}</button><button data-move="${e(n.id)}">${t('move')}…</button></details></td></tr>`))}
      ${this.catalogDialog(selected, products)}`;
  }
  catalogDialog(selected, products) {
    const d = this.state.dialog, t = this.t;
    if (!d) return '';
    const moving = d.kind === 'move';
    return `<dialog aria-labelledby="dialog-title"><h2 id="dialog-title">${t(moving ? 'move' : 'merge')}</h2>
      ${this.state.error ? `<p role="alert">${e(this.state.error)}</p>` : ''}
      ${moving ? `<p>${e(d.name)}</p><p>${t('moveHelp')}</p>` : `<ul>${selected.map(n => `<li>${e(n.name)}</li>`).join('')}</ul><p>${t('mergeConfirm')}</p>`}
      <label>${t(moving ? 'destinationProduct' : 'mainName')}<select id="dialog-target">
      <option value="">${t('choose')}</option>${this.options(moving ? products.filter(([id]) => id !== d.productId) : selected.map(n => [n.id, n.name]), d.target)}</select></label>
      <p>${t('historyPreserved')}</p><div class="controls"><button id="cancel-dialog">${t('cancel')}</button>
      <button id="confirm-dialog" ${!d.target ? 'disabled' : ''}>${t(moving ? 'move' : 'merge')}</button></div></dialog>`;
  }
  history(data) {
    const t = this.t;
    return `<button id="all-names">${t('allNames')}</button>${this.table(
      [t('date'), t('original'), t('canonical'), t('status'), t('correction')],
      data.events.map(p => `<tr><td>${e(p.occurred_at)}</td><td>${e(p.original_name)}</td><td>${e(p.canonical_name)}</td><td>${e(t(p.status))}</td><td>${e(p.correction_reason || '—')}</td></tr>`))}
      <div class="controls"><button id="previous" ${!this.state.offset ? 'disabled' : ''}>${t('previous')}</button>
      <span>${this.state.offset} / ${data.total}</span><button id="next" ${this.state.offset + 100 >= data.total ? 'disabled' : ''}>${t('next')}</button></div>`;
  }
  settings(data) {
    const t = this.t;
    return `<p>${t('configure')}</p><pre>${e(JSON.stringify(data, null, 2))}</pre>
      <button id="export">${t('export')}</button><button id="delete" class="danger">${t('remove')}</button>`;
  }
  render() {
    if (!this.t) return;
    const t = this.t, s = this.state;
    const body = s.loading ? `<p role="status">${t('loading')}</p>`
      : `${s.error ? `<p role="alert">${e(s.error)}</p>` : ''}${s.data ? this[s.view](s.data) : ''}`;
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;color:var(--primary-text-color);background:var(--primary-background-color);min-height:100%;font:14px var(--paper-font-body1_-_font-family,Roboto,sans-serif)}
      header{display:flex;align-items:center;gap:12px;background:var(--app-header-background-color,var(--primary-color));color:var(--app-header-text-color,#fff);padding:12px 20px}
      header h1{font-size:20px;flex:1}main{padding:20px;max-width:1250px;margin:auto}nav{display:flex;gap:8px;flex-wrap:wrap;padding:12px 0}
      button,input,select{font:inherit;padding:10px;border-radius:var(--ha-card-border-radius,8px);border:1px solid var(--divider-color);color:var(--primary-text-color);background:var(--card-background-color);box-sizing:border-box}
      button{cursor:pointer}button:disabled{opacity:.45;cursor:default}button[aria-current=true]{border-color:var(--primary-color);color:var(--primary-color)}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--primary-color)}
      .controls{display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin:16px 0}label{display:flex;flex-direction:column;gap:6px}input[type=checkbox]{width:20px;height:20px}
      summary{cursor:pointer;padding:8px 0}.selection{position:sticky;top:0;background:var(--card-background-color);padding:12px;z-index:1;border:1px solid var(--primary-color);border-radius:8px}
      dialog{box-sizing:border-box;max-width:min(520px,94vw);max-height:90vh;overflow:auto;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:12px;padding:24px}dialog::backdrop{background:rgba(0,0,0,.45)}dialog select{max-width:100%}
      .cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}ha-card{padding:22px;display:flex;flex-direction:column;gap:10px;background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:var(--ha-card-border-radius,12px)}strong{font-size:30px;color:var(--primary-color)}
      .scroll{overflow:auto;border:1px solid var(--divider-color);border-radius:12px;background:var(--card-background-color)}table{border-collapse:collapse;width:100%;text-align:left}th,td{padding:12px;border-bottom:1px solid var(--divider-color)}td button{margin:2px}th{color:var(--secondary-text-color)}p{line-height:1.6}pre{white-space:pre-wrap;overflow-wrap:anywhere}.danger,[role=alert]{color:var(--error-color,#db4437)}
      @media(max-width:700px){main{padding:12px}.cards{grid-template-columns:repeat(2,1fr)}header{padding:8px}header h1{font-size:18px}th,td{padding:9px}}
    </style><header><ha-menu-button></ha-menu-button><h1>pax0r's Listkeeper</h1><button id="refresh" ${s.loading ? 'disabled' : ''}>${t('refresh')}</button></header>
      <main><div class="list-context"><label>${t('currentList')}<select id="list-context" ${s.loading ? 'disabled' : ''}>${this.options(s.lists.map(l => [l.entity_id, `${l.name} (${l.entity_id})`]), s.entityId)}</select></label><p>${t('listIsolation')}</p></div>
      <nav>${['dashboard','catalog','history','settings'].map(v => `<button data-view="${v}" aria-current="${v === s.view}">${t(v)}</button>`).join('')}</nav>${s.notice ? `<p role="status">${e(s.notice)}</p>` : ''}${body}</main>`;
    this.bind();
  }
  bind() {
    const root = this.shadowRoot, s = this.state;
    const on = (id, event, handler) => root.getElementById(id)?.addEventListener(event, handler);
    on('list-context', 'change', ev => {
      s.entityId = ev.target.value; s.data = null; s.dialog = null; s.selected.clear();
      s.nameId = ''; s.offset = 0; s.query = ''; s.notice = ''; this.load();
    });
    root.querySelector('ha-menu-button').hass = this._hass;
    root.querySelectorAll('[data-view]').forEach(b => b.onclick = () => { s.view = b.dataset.view; s.data = null; this.load(); });
    on('refresh', 'click', async () => { try { await this.call('refresh'); } catch { /* load displays status */ } this.load(); });
    on('period', 'change', ev => { s.days = ev.target.value; this.load(); });
    on('sort', 'change', ev => { s.sort = ev.target.value; this.render(); });
    on('catalog-sort', 'change', ev => { s.catalogSort = ev.target.value; this.render(); });
    on('search', 'input', ev => {
      const start = ev.target.selectionStart; s.query = ev.target.value; this.render();
      const input = root.getElementById('search'); input.focus(); input.setSelectionRange(start, start);
    });
    root.querySelectorAll('[data-select]').forEach(b => b.onchange = () => {
      if (b.checked) s.selected.add(b.dataset.select); else s.selected.delete(b.dataset.select); this.render();
    });
    on('clear-selection', 'click', () => { s.selected.clear(); this.render(); });
    on('merge', 'click', () => { s.dialog = { kind: 'merge', target: '' }; this.render(); });
    on('cancel-dialog', 'click', () => { s.dialog = null; this.render(); });
    on('dialog-target', 'change', ev => { s.dialog.target = ev.target.value;
      root.getElementById('confirm-dialog').disabled = !s.dialog.target; });
    on('confirm-dialog', 'click', () => {
      const d = s.dialog;
      if (!d?.target) return;
      if (d.kind === 'merge') this.mutate('merge_names', { name_ids: [...s.selected], target_name_id: d.target });
      else this.mutate('move_name', { name_id: d.nameId, product_id: d.target });
    });
    const dialog = root.querySelector('dialog');
    if (dialog) { dialog.addEventListener('cancel', () => { s.dialog = null; }); dialog.showModal(); }
    root.querySelectorAll('[data-split]').forEach(b => b.onclick = () => {
      if (confirm(this.t('splitConfirm'))) this.mutate('move_name', { name_id: b.dataset.split, product_id: null });
    });
    root.querySelectorAll('[data-move]').forEach(b => b.onclick = () => {
      const name = s.data.find(n => n.id === b.dataset.move);
      s.dialog = { kind: 'move', nameId: name.id, name: name.name, productId: name.product_id, target: '' }; this.render();
    });
    root.querySelectorAll('[data-history]').forEach(b => b.onclick = () => {
      s.nameId = b.dataset.history; s.offset = 0; s.view = 'history'; s.data = null; this.load();
    });
    on('all-names', 'click', () => { s.nameId = ''; s.offset = 0; this.load(); });
    on('previous', 'click', () => { s.offset = Math.max(0, s.offset - 100); this.load(); });
    on('next', 'click', () => { s.offset += 100; this.load(); });
    on('export', 'click', async () => {
      try {
        const data = await this.call('export_data');
        const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
        const a = document.createElement('a'); a.href = url; a.download = `pax0r-listkeeper-${s.entityId.replaceAll('.', '-')}.json`; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } catch (err) { s.error = err.message || this.t('error'); this.render(); }
    });
    on('delete', 'click', () => {
      const confirmation = prompt(`${this.t('currentList')}: ${s.entityId}\n\n${this.t('removeConfirm')}`);
      if (confirmation === 'DELETE SHOPPING HISTORY') this.mutate('delete_data', { confirmation });
    });
  }
}
customElements.define('pax0r-listkeeper-panel', Pax0rListkeeperPanel);
