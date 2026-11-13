/* Release 598: Dashboard In Stock pagination, composed with existing search. */
(() => {
  'use strict';
  function init() {
    const table = document.getElementById('inventory-rows');
    const control = document.querySelector('[data-inventory-pages598]');
    if (!table || !control || control.dataset.initialized) return;
    control.dataset.initialized = '1';
    const sizeInput = control.querySelector('[data-inventory-size598]');
    const previous = control.querySelector('[data-inventory-prev598]');
    const next = control.querySelector('[data-inventory-next598]');
    const status = control.querySelector('[data-inventory-status598]');
    const search = document.querySelector('input[data-filter-target="inventory-rows"]');
    const rows = Array.from(table.querySelectorAll(':scope > tr'));
    let page = 0;

    function filteredRows() {
      const term = (search?.value || '').trim().toLocaleLowerCase();
      return rows.filter(row =>
        (row.dataset.search || row.textContent || '').toLocaleLowerCase().includes(term));
    }

    function render() {
      const matches = filteredRows();
      const size = sizeInput.value === 'all' ? Infinity : Number(sizeInput.value);
      const totalPages = Number.isFinite(size)
        ? Math.max(1, Math.ceil(matches.length / size)) : 1;
      page = Math.max(0, Math.min(page, totalPages - 1));
      const visible = new Set(
        Number.isFinite(size) ? matches.slice(page * size, (page + 1) * size) : matches
      );
      rows.forEach(row => { row.hidden = !visible.has(row); });
      previous.disabled = page === 0;
      next.disabled = page >= totalPages - 1;
      const start = matches.length ? (Number.isFinite(size) ? page * size + 1 : 1) : 0;
      const end = matches.length ? (Number.isFinite(size) ? Math.min(matches.length, (page + 1) * size) : matches.length) : 0;
      status.textContent = 'Showing ' + start + '–' + end + ' of ' + matches.length +
        ' vials · Page ' + (page + 1) + ' of ' + totalPages;
    }

    sizeInput.addEventListener('change', () => { page = 0; render(); });
    previous.addEventListener('click', () => { if (page > 0) { page -= 1; render(); } });
    next.addEventListener('click', () => { page += 1; render(); });
    // Runs after layout.js's existing search filter and composes with its
    // session-restored input value without changing the saved search.
    search?.addEventListener('input', () => { page = 0; render(); });
    render();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once:true});
  } else {
    init();
  }
})();
