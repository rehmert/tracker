/* Browser-local, keyboard-accessible navigation preferences. */
(() => {
  const KEY = 'tracker-nav-order-v1', MODE = 'tracker-nav-mode-v1';
  const start = () => {
    const list = document.getElementById('nav-sortable');
    const select = document.getElementById('nav-sort-mode');
    const toggle = document.getElementById('nav-edit-toggle');
    const reset = document.getElementById('nav-reset');
    const help = document.getElementById('nav-sort-help');
    if (!list || !select || !toggle || !reset) return;
    const initial = [...list.children].map(el => el.dataset.navKey);
    const stored = () => { try { const a = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(a) ? a.filter(x => typeof x === 'string') : []; } catch { return []; } };
    let custom = stored(), editing = false;
    let mode = localStorage.getItem(MODE) || 'default';
    if (!['default','alpha','custom'].includes(mode)) mode = 'default';
    const apply = () => {
      select.value = mode;
      const items = [...list.children];
      const index = new Map(initial.map((key, i) => [key, i]));
      const ranks = new Map(custom.map((key, i) => [key, i]));
      items.sort((a,b) => mode === 'alpha'
        ? a.querySelector('a').textContent.trim().localeCompare(b.querySelector('a').textContent.trim())
        : mode === 'custom'
          ? (ranks.has(a.dataset.navKey) ? ranks.get(a.dataset.navKey) : custom.length + index.get(a.dataset.navKey)) - (ranks.has(b.dataset.navKey) ? ranks.get(b.dataset.navKey) : custom.length + index.get(b.dataset.navKey))
          : index.get(a.dataset.navKey) - index.get(b.dataset.navKey));
      items.forEach(el => list.appendChild(el));
      list.querySelectorAll('.nav-move').forEach(el => { el.hidden = !editing; });
      toggle.setAttribute('aria-pressed', String(editing));
      toggle.textContent = editing ? 'Done' : 'Reorder';
      help.hidden = !editing;
    };
    select.addEventListener('change', () => { mode = select.value; localStorage.setItem(MODE,mode); apply(); });
    toggle.addEventListener('click', () => { editing = !editing; if(editing && mode !== 'custom') { custom = [...list.children].map(x => x.dataset.navKey); mode = 'custom'; localStorage.setItem(MODE,mode); localStorage.setItem(KEY,JSON.stringify(custom)); } apply(); });
    reset.addEventListener('click', () => { mode='default'; custom=[]; editing=false; localStorage.removeItem(KEY); localStorage.removeItem(MODE); apply(); });
    list.addEventListener('click', event => {
      const button = event.target.closest('.nav-up, .nav-down');
      if(!button || !editing) return;
      const item = button.closest('li');
      const sibling = button.classList.contains('nav-up') ? item.previousElementSibling : item.nextElementSibling;
      if(!sibling) return;
      if(button.classList.contains('nav-up')) list.insertBefore(item,sibling); else list.insertBefore(sibling,item);
      custom = [...list.children].map(x => x.dataset.navKey);
      mode='custom'; localStorage.setItem(MODE,mode); localStorage.setItem(KEY,JSON.stringify(custom));
      apply(); button.focus();
    });
    apply();
  };
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded',start); else start();
})();
