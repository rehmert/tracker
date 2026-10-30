/* Local-only saved vial filter views; never stores quantities or edits inventory. */
(() => {
  const root = document.getElementById('vial-saved-views');
  const picker = document.getElementById('vial-view-picker');
  const save = document.getElementById('vial-view-save');
  const remove = document.getElementById('vial-view-delete');
  const message = document.getElementById('vial-view-message');
  const filter = document.getElementById('vial-filter-form');
  if (!root || !picker || !save || !remove || !filter) return;
  const KEY = 'tracker.vials.savedViews.v1';
  const allowed = new Set(['active', 'sealed', 'in_use', 'finished', 'discarded', 'all']);
  const status = new URLSearchParams(location.search).get('status') || 'active';
  const compound = filter.querySelector('[name="compound_id"]');
  const current = () => ({status: allowed.has(status) ? status : 'active', compound_id: compound?.value || ''});
  const read = () => {
    try {
      const value = JSON.parse(localStorage.getItem(KEY) || '{}');
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    } catch (_) { return {}; }
  };
  let views = read();
  const persist = () => { try { localStorage.setItem(KEY, JSON.stringify(views)); return true; } catch (_) { message.textContent = 'Browser storage is unavailable; views cannot be saved.'; return false; } };
  const refresh = (selected = '') => {
    picker.replaceChildren(new Option('Choose a saved view…', ''));
    Object.keys(views).sort((a,b) => a.localeCompare(b)).forEach(name => picker.add(new Option(name, name)));
    picker.value = selected;
    remove.disabled = !selected;
  };
  picker.addEventListener('change', () => {
    const name = picker.value;
    remove.disabled = !name;
    if (!name || !Object.prototype.hasOwnProperty.call(views, name)) return;
    const view = views[name];
    const params = new URLSearchParams();
    params.set('status', allowed.has(view.status) ? view.status : 'active');
    if (view.compound_id && /^\d+$/.test(String(view.compound_id))) params.set('compound_id', view.compound_id);
    location.assign('/vials?' + params.toString());
  });
  save.addEventListener('click', () => {
    const name = prompt('Name this vial view (up to 50 characters):');
    if (name === null) return;
    const clean = name.trim().slice(0, 50);
    if (!clean) { message.textContent = 'Enter a view name.'; return; }
    if (Object.prototype.hasOwnProperty.call(views, clean) && !confirm('Replace saved view "' + clean + '"?')) return;
    if (!Object.prototype.hasOwnProperty.call(views, clean) && Object.keys(views).length >= 30) { message.textContent = 'Maximum of 30 saved views reached.'; return; }
    views[clean] = current();
    if (persist()) { refresh(clean); message.textContent = 'Saved view "' + clean + '".'; }
  });
  remove.addEventListener('click', () => {
    const name = picker.value;
    if (!name || !Object.prototype.hasOwnProperty.call(views, name) || !confirm('Delete saved view "' + name + '"?')) return;
    delete views[name];
    if (persist()) { refresh(); message.textContent = 'Deleted saved view "' + name + '".'; }
  });
  refresh();
})();
