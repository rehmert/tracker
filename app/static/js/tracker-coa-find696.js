/* Release 696: read-only search of the COA rows already rendered to this user.
   No network, persistence, form submission or record mutation. */
(() => {
  'use strict';
  function init() {
    const root = document.querySelector('[data-flow696-coas]');
    if (!root || root.dataset.flow696Ready === 'yes') return;
    const input = root.querySelector('[data-flow696-search]');
    const reset = root.querySelector('[data-flow696-reset]');
    const count = root.querySelector('[data-flow696-count]');
    const empty = root.querySelector('[data-flow696-empty]');
    const rows = Array.from(root.querySelectorAll('[data-flow696-coa-row]'));
    if (!input || !reset || !count || !empty) return;
    root.dataset.flow696Ready = 'yes';
    const index = rows.map(row => ({
      row, text: row.textContent.normalize('NFKC').toLocaleLowerCase()
    }));
    function update() {
      const words = input.value.trim().normalize('NFKC').toLocaleLowerCase().split(/\s+/).filter(Boolean);
      let shown = 0;
      for (const item of index) {
        const show = words.every(word => item.text.includes(word));
        item.row.hidden = !show;
        if (show) shown++;
      }
      count.textContent = 'Showing ' + shown + ' of ' + index.length + ' certificates';
      empty.hidden = shown !== 0 || index.length === 0;
    }
    input.addEventListener('input', update);
    input.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        input.value = '';
        update();
      }
    });
    reset.addEventListener('click', () => {
      input.value = '';
      update();
      input.focus();
    });
    update();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
